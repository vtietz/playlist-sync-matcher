from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass
import mutagen
from ..utils.fs import iter_music_files, normalize_library_path
from ..utils.hashing import partial_hash
from ..utils.normalization import normalize_title_artist
from ..utils.logging_helpers import log_progress, format_summary
import time
import logging
import click
from datetime import datetime, timedelta
import re

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    """Results from a library scan operation."""

    files_seen: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    deleted: int = 0
    errors: int = 0
    duration_seconds: float = 0.0


TAG_CANDIDATES = [
    ("title", ["title", "TIT2"]),
    ("artist", ["artist", "TPE1"]),
    ("album", ["album", "TALB"]),
    # Year / date tags (ID3 TDRC, TYER, DATE etc.)
    ("year", ["date", "year", "TDRC", "TDOR", "TYER"]),
]


def extract_tags(audio) -> Dict[str, Any]:
    tags = {}
    if not audio:
        return tags
    if getattr(audio, "tags", None):
        for field, keys in TAG_CANDIDATES:
            for k in keys:
                if k in audio.tags:
                    val = audio.tags.get(k)
                    if isinstance(val, list):
                        val = val[0]
                    tags[field] = str(val)
                    break
    return tags


def parse_time_string(time_str: str) -> float:
    """Parse human-readable time strings into Unix timestamp.

    Supports:
    - Relative: "2 hours ago", "30 minutes ago", "1 day ago"
    - ISO format: "2025-10-08 10:30:00"
    - Unix timestamp: "1728123456.789"

    Returns:
        Unix timestamp (seconds since epoch)
    """
    if not time_str:
        raise ValueError("time_str cannot be empty or None")

    time_str = time_str.strip().lower()

    # Try Unix timestamp
    try:
        return float(time_str)
    except ValueError:
        pass

    # Try ISO format
    try:
        dt = datetime.fromisoformat(time_str)
        return dt.timestamp()
    except ValueError:
        pass

    # Try relative time (e.g., "2 hours ago")
    match = re.match(r"(\d+)\s*(second|minute|hour|day|week)s?\s+ago", time_str)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)

        unit_map = {
            "second": timedelta(seconds=1),
            "minute": timedelta(minutes=1),
            "hour": timedelta(hours=1),
            "day": timedelta(days=1),
            "week": timedelta(weeks=1),
        }

        delta = unit_map[unit] * amount
        return (datetime.now() - delta).timestamp()

    raise ValueError(f"Unable to parse time string: {time_str}")


def scan_specific_files(db, cfg: Dict[str, Any], file_paths: List[Path]) -> ScanResult:
    """Scan only specific files (used by watch mode).

    Args:
        db: Database instance
        cfg: Configuration dict
        file_paths: List of specific file paths to scan

    Returns:
        ScanResult with scan statistics
    """
    lib_cfg = cfg["library"]
    use_year = cfg.get("matching", {}).get("use_year")
    commit_interval = int(lib_cfg.get("commit_interval", 100) or 0)

    result = ScanResult()
    start = time.time()
    since_commit = 0

    logger.info(f"Scanning {len(file_paths)} specific files...")

    for p in file_paths:
        if not isinstance(p, Path):
            p = Path(p)

        if not p.exists():
            # File was deleted, handle removal
            path_str = str(p.resolve())
            row = db.conn.execute("SELECT id FROM library_files WHERE path=?", (path_str,)).fetchone()
            if row:
                file_id = row["id"]
                db.conn.execute("DELETE FROM library_files WHERE id=?", (file_id,))
                db.conn.execute("DELETE FROM matches WHERE file_id=?", (file_id,))
                result.deleted += 1
                logger.debug(f"{click.style('[deleted]', fg='red')} {p}")
            continue

        result.files_seen += 1

        try:
            _process_single_file(db, cfg, p, result, use_year)
            since_commit += 1

            if commit_interval and since_commit >= commit_interval:
                db.commit()
                since_commit = 0

        except Exception as e:
            result.errors += 1
            logger.debug(f"{click.style('[error]', fg='red')} {p}: {e}")

    db.commit()
    result.duration_seconds = time.time() - start
    return result


def scan_library_incremental(
    db, cfg: Dict[str, Any], changed_since: float | None = None, specific_paths: List[Path] | None = None
) -> ScanResult:
    """Scan library with incremental mode support.

    Args:
        db: Database instance
        cfg: Configuration dict
        changed_since: Unix timestamp - only scan files modified after this time
        specific_paths: List of specific paths to scan (directories or files)

    Returns:
        ScanResult with scan statistics
    """
    # If specific files provided, use targeted scan
    if specific_paths and all(p.is_file() if isinstance(p, Path) else Path(p).is_file() for p in specific_paths):
        return scan_specific_files(db, cfg, specific_paths)

    lib_cfg = cfg["library"]

    # Override paths if specific paths provided
    if specific_paths:
        lib_cfg = {**lib_cfg, "paths": [str(p) for p in specific_paths]}

    # Perform full scan with filtering
    return _scan_library_internal(db, cfg, lib_cfg, changed_since=changed_since)


def _process_single_file(db, cfg: Dict[str, Any], p: Path, result: ScanResult, use_year: bool) -> None:
    """Process a single file and update the database.

    Helper function used by both full and incremental scans.
    Updates result object in-place.
    """
    # Use normalized path for consistent database storage
    path_str = normalize_library_path(p)

    try:
        st = p.stat()
    except OSError:
        result.errors += 1
        logger.debug(f"{click.style('[io-error]', fg='red')} {p}")
        return

    try:
        audio = mutagen.File(p)
    except Exception:
        audio = None
        result.errors += 1

    tags = extract_tags(audio)
    title = tags.get("title") or p.stem
    artist = tags.get("artist") or ""
    album = tags.get("album") or ""
    year_raw = tags.get("year") or ""
    year = None
    if year_raw:
        m = re.search(r"(19|20)\d{2}", str(year_raw))
        if m:
            year = int(m.group(0))

    duration = None
    if audio and getattr(audio, "info", None) and getattr(audio.info, "length", None):
        duration = float(audio.info.length)

    # Extract bitrate
    bitrate_kbps = None
    if audio and getattr(audio, "info", None):
        if hasattr(audio.info, "bitrate") and audio.info.bitrate:
            bitrate_kbps = int(audio.info.bitrate / 1000)
        elif hasattr(audio.info, "sample_rate") and hasattr(audio.info, "bits_per_sample"):
            sample_rate = audio.info.sample_rate
            bits_per_sample = audio.info.bits_per_sample
            channels = getattr(audio.info, "channels", 2)
            bitrate_kbps = int((sample_rate * bits_per_sample * channels) / 1000)

    ph = partial_hash(p)
    nt, na, combo = normalize_title_artist(title, artist)
    if use_year and year is not None:
        combo = f"{combo} {year}"

    # Check if exists
    existing = db.conn.execute("SELECT id FROM library_files WHERE path=?", (path_str,)).fetchone()

    db.add_library_file(
        {
            "path": path_str,
            "size": st.st_size,
            "mtime": st.st_mtime,
            "partial_hash": ph,
            "title": title,
            "album": album,
            "artist": artist,
            "duration": duration,
            "normalized": combo,
            "year": year,
            "bitrate_kbps": bitrate_kbps,
        }
    )

    if existing:
        result.updated += 1
        action = "updated"
        color = "blue"
    else:
        result.inserted += 1
        action = "new"
        color = "green"

    logger.debug(
        f"{click.style(f'[{action}]', fg=color)} {p} | title='{title}' artist='{artist}' album='{album}' year={year if year is not None else '-'}"
    )


def _scan_library_internal(
    db, cfg: Dict[str, Any], lib_cfg: Dict[str, Any], changed_since: float | None = None
) -> ScanResult:
    """Internal scan implementation with optional time-based filtering.

    This is refactored from the original scan_library to support incremental mode.
    """
    paths = lib_cfg["paths"]
    extensions = lib_cfg["extensions"]
    ignore_patterns = lib_cfg.get("ignore_patterns", [])
    follow_symlinks = lib_cfg.get("follow_symlinks", False)
    skip_unchanged = lib_cfg.get("skip_unchanged", True)
    fast_scan = lib_cfg.get("fast_scan", True)
    commit_interval = int(lib_cfg.get("commit_interval", 100) or 0)
    use_year = cfg.get("matching", {}).get("use_year")

    result = ScanResult()
    start = time.time()
    since_commit = 0
    seen_paths = set()
    progress_interval = 100
    last_progress_log = 0
    last_dir_logged = None

    # Batch load existing file metadata
    existing_files = {}
    if skip_unchanged:
        if fast_scan:
            rows = db.conn.execute(
                "SELECT path, size, mtime, partial_hash, title, artist, album, year, duration, normalized, bitrate_kbps FROM library_files"
            ).fetchall()
            existing_files = {
                row["path"]: {
                    "size": row["size"],
                    "mtime": row["mtime"],
                    "hash": row["partial_hash"],
                    "title": row["title"],
                    "artist": row["artist"],
                    "album": row["album"],
                    "year": row["year"],
                    "duration": row["duration"],
                    "normalized": row["normalized"],
                    "bitrate_kbps": row["bitrate_kbps"],
                }
                for row in rows
            }
        else:
            rows = db.conn.execute("SELECT path, size, mtime, partial_hash FROM library_files").fetchall()
            existing_files = {row["path"]: (row["size"], row["mtime"], row["partial_hash"]) for row in rows}
        logger.debug(f"Loaded {len(existing_files)} existing files for skip-unchanged checks")

    try:
        for p in iter_music_files(paths, extensions, ignore_patterns, follow_symlinks):
            result.files_seen += 1

            # Log directory change
            current_dir = str(p.parent)
            if current_dir != last_dir_logged:
                logger.debug(f"{click.style('[scanning]', fg='cyan')} {current_dir}")
                last_dir_logged = current_dir

            path_str = str(p.resolve())
            seen_paths.add(path_str)

            try:
                st = p.stat()
            except OSError:
                result.errors += 1
                logger.debug(f"{click.style('[io-error]', fg='red')} {p}")
                continue

            # Check if file exists in DB
            file_in_db = path_str in existing_files

            # Time-based filtering: ONLY skip files that are ALREADY in DB and not modified
            if changed_since is not None and file_in_db:
                # File exists in DB, check if it was modified since cutoff
                if st.st_mtime < changed_since:
                    # Not modified since cutoff - skip it
                    result.skipped += 1
                    logger.debug(f"{click.style('[skip-old]', fg='yellow')} {p} (not modified since cutoff)")

                    if result.files_seen - last_progress_log >= progress_interval:
                        elapsed = time.time() - start
                        log_progress(
                            processed=result.files_seen,
                            total=None,
                            new=result.inserted,
                            updated=result.updated,
                            skipped=result.skipped,
                            elapsed_seconds=elapsed,
                            item_name="files",
                        )
                        last_progress_log = result.files_seen
                    continue

            # Skip unchanged fast path (only for files already in DB)
            if skip_unchanged and file_in_db:
                existing_data = existing_files[path_str]

                if isinstance(existing_data, dict):
                    size_db, mtime_db = existing_data["size"], existing_data["mtime"]
                    if size_db == st.st_size and abs(mtime_db - st.st_mtime) < 1.0:
                        result.skipped += 1
                        logger.debug(f"{click.style('[skip]', fg='yellow')} {p} unchanged (fast mode - no parsing)")

                        if result.files_seen - last_progress_log >= progress_interval:
                            elapsed = time.time() - start
                            log_progress(
                                processed=result.files_seen,
                                total=None,
                                new=result.inserted,
                                updated=result.updated,
                                skipped=result.skipped,
                                elapsed_seconds=elapsed,
                                item_name="files",
                            )
                            last_progress_log = result.files_seen
                        continue
                else:
                    size_db, mtime_db, hash_db = existing_data
                    if size_db == st.st_size and abs(mtime_db - st.st_mtime) < 1.0:
                        result.skipped += 1
                        logger.debug(f"{click.style('[skip]', fg='yellow')} {p} unchanged")

                        if result.files_seen - last_progress_log >= progress_interval:
                            elapsed = time.time() - start
                            log_progress(
                                processed=result.files_seen,
                                total=None,
                                new=result.inserted,
                                updated=result.updated,
                                skipped=result.skipped,
                                elapsed_seconds=elapsed,
                                item_name="files",
                            )
                            last_progress_log = result.files_seen
                        continue

            _process_single_file(db, cfg, p, result, use_year)
            since_commit += 1

            if commit_interval and since_commit >= commit_interval:
                db.commit()
                logger.debug(f"Interim commit after {since_commit} processed")
                since_commit = 0

            if result.files_seen - last_progress_log >= progress_interval:
                elapsed = time.time() - start
                log_progress(
                    processed=result.files_seen,
                    total=None,
                    new=result.inserted,
                    updated=result.updated,
                    skipped=result.skipped,
                    elapsed_seconds=elapsed,
                    item_name="files",
                )
                last_progress_log = result.files_seen

    except KeyboardInterrupt:
        print(f"{click.style('[interrupt]', fg='magenta')} Caught keyboard interrupt; finalizing partial work...")
    finally:
        # Cleanup: remove deleted files
        rows = db.conn.execute("SELECT id, path FROM library_files").fetchall()
        db_paths = {row["path"]: row["id"] for row in rows}

        deleted_paths = set(db_paths.keys()) - seen_paths

        for path in deleted_paths:
            file_id = db_paths[path]
            db.conn.execute("DELETE FROM library_files WHERE id=?", (file_id,))
            db.conn.execute("DELETE FROM matches WHERE file_id=?", (file_id,))
            result.deleted += 1
            logger.debug(f"{click.style('[deleted]', fg='red')} {path} (no longer exists)")

        db.commit()
        result.duration_seconds = time.time() - start

    return result


def scan_library(db, cfg):
    """Scan local music library and index track metadata.

    This is the main entry point for library scanning.
    For incremental scans, use scan_library_incremental() instead.
    """
    lib_cfg = cfg["library"]

    click.echo(click.style("=== Scanning local library ===", fg="cyan", bold=True))

    # Log directories being scanned
    paths = lib_cfg["paths"]
    if isinstance(paths, list):
        logger.info(f"Scanning {len(paths)} director{'y' if len(paths) == 1 else 'ies'}:")
        for path in paths:
            logger.info(f"  • {path}")
    else:
        logger.info(f"Scanning: {paths}")
    logger.info("")

    # Use internal implementation
    result = _scan_library_internal(db, cfg, lib_cfg, changed_since=None)

    # Print summary
    summary = format_summary(
        new=result.inserted,
        updated=result.updated,
        unchanged=result.skipped,
        deleted=result.deleted,
        duration_seconds=result.duration_seconds,
        item_name="Library",
    )
    logger.info(summary)
    if result.errors:
        logger.debug(f"Errors: {result.errors}")


__all__ = ["scan_library", "scan_library_incremental", "scan_specific_files", "parse_time_string", "ScanResult"]
