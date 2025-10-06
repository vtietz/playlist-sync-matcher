from __future__ import annotations
from pathlib import Path
from typing import Iterable, Dict, Any
import mutagen
from ..utils.fs import iter_music_files
from ..utils.hashing import partial_hash
from ..utils.normalization import normalize_title_artist
from ..utils.logging_helpers import log_progress, format_summary
import time
import logging
import click

logger = logging.getLogger(__name__)

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
    if getattr(audio, 'tags', None):
        for field, keys in TAG_CANDIDATES:
            for k in keys:
                if k in audio.tags:
                    val = audio.tags.get(k)
                    if isinstance(val, list):
                        val = val[0]
                    tags[field] = str(val)
                    break
    return tags


def scan_library(db, cfg):
    lib_cfg = cfg['library']
    paths = lib_cfg['paths']
    extensions = lib_cfg['extensions']
    ignore_patterns = lib_cfg.get('ignore_patterns', [])
    follow_symlinks = lib_cfg.get('follow_symlinks', False)
    skip_unchanged = lib_cfg.get('skip_unchanged', True)
    fast_scan = lib_cfg.get('fast_scan', True)  # Skip audio parsing for unchanged files
    commit_interval = int(lib_cfg.get('commit_interval', 100) or 0)
    use_year = cfg.get('matching', {}).get('use_year')

    click.echo(click.style("=== Scanning local library ===", fg='cyan', bold=True))
    
    # Log directories being scanned
    if isinstance(paths, list):
        logger.info(f"Scanning {len(paths)} director{'y' if len(paths) == 1 else 'ies'}:")
        for path in paths:
            logger.info(f"  • {path}")
    else:
        logger.info(f"Scanning: {paths}")
    logger.info("")
    
    start = time.time()
    files_seen = 0
    inserted = 0
    updated = 0
    skipped_unchanged = 0
    tag_errors = 0
    io_errors = 0
    other_errors = 0
    since_commit = 0
    seen_paths = set()  # Track files we've seen during scan for efficient deletion detection
    progress_interval = 100  # Log progress every N files
    last_progress_log = 0
    last_dir_logged = None  # Track current directory being scanned
    
    # Batch load existing file metadata for skip-unchanged checks (avoids per-file queries)
    existing_files = {}
    if skip_unchanged:
        # Load all existing file metadata including tags for fast_scan mode
        if fast_scan:
            rows = db.conn.execute(
                "SELECT path, size, mtime, partial_hash, title, artist, album, year, duration, normalized, bitrate_kbps FROM library_files"
            ).fetchall()
            existing_files = {
                row['path']: {
                    'size': row['size'],
                    'mtime': row['mtime'],
                    'hash': row['partial_hash'],
                    'title': row['title'],
                    'artist': row['artist'],
                    'album': row['album'],
                    'year': row['year'],
                    'duration': row['duration'],
                    'normalized': row['normalized'],
                    'bitrate_kbps': row['bitrate_kbps'],
                }
                for row in rows
            }
        else:
            rows = db.conn.execute("SELECT path, size, mtime, partial_hash FROM library_files").fetchall()
            existing_files = {row['path']: (row['size'], row['mtime'], row['partial_hash']) for row in rows}
        logger.debug(f"Loaded {len(existing_files)} existing files for skip-unchanged checks")

    try:
        for p in iter_music_files(paths, extensions, ignore_patterns, follow_symlinks):
            files_seen += 1
            
            # Log directory change (helps user see progress through large libraries)
            current_dir = str(p.parent)
            if current_dir != last_dir_logged:
                logger.debug(f"{click.style('[scanning]', fg='cyan')} {current_dir}")
                last_dir_logged = current_dir
            
            # Normalize path to use backslashes on Windows (consistent with DB storage)
            path_str = str(p.resolve())
            seen_paths.add(path_str)  # Track this path as seen
            try:
                st = p.stat()
            except OSError:
                io_errors += 1
                logger.debug(f"{click.style('[io-error]', fg='red')} {p}")
                continue

            # Skip unchanged fast path
            if skip_unchanged and path_str in existing_files:
                existing_data = existing_files[path_str]
                
                # Handle both fast_scan (dict) and normal (tuple) formats
                if isinstance(existing_data, dict):
                    # Fast scan mode: reuse existing tags without parsing
                    size_db, mtime_db = existing_data['size'], existing_data['mtime']
                    if size_db == st.st_size and abs(mtime_db - st.st_mtime) < 1.0:
                        skipped_unchanged += 1
                        logger.debug(f"{click.style('[skip]', fg='yellow')} {p} unchanged (fast mode - no parsing)")
                        
                        # Log progress even for skipped files so user knows scan is active
                        if files_seen - last_progress_log >= progress_interval:
                            elapsed = time.time() - start
                            log_progress(
                                processed=files_seen,
                                total=None,
                                new=inserted,
                                updated=updated,
                                skipped=skipped_unchanged,
                                elapsed_seconds=elapsed,
                                item_name="files"
                            )
                            last_progress_log = files_seen
                        continue
                else:
                    # Normal mode: tuple format
                    size_db, mtime_db, hash_db = existing_data
                    if size_db == st.st_size and abs(mtime_db - st.st_mtime) < 1.0:
                        skipped_unchanged += 1
                        logger.debug(f"{click.style('[skip]', fg='yellow')} {p} unchanged")
                        
                        # Log progress even for skipped files so user knows scan is active
                        if files_seen - last_progress_log >= progress_interval:
                            elapsed = time.time() - start
                            log_progress(
                                processed=files_seen,
                                total=None,
                                new=inserted,
                                updated=updated,
                                skipped=skipped_unchanged,
                                elapsed_seconds=elapsed,
                                item_name="files"
                            )
                            last_progress_log = files_seen
                        continue

            try:
                audio = mutagen.File(p)
            except Exception:
                # treat as tag error but still record minimal metadata (title from filename)
                audio = None
                tag_errors += 1

            try:
                tags = extract_tags(audio)
                title = tags.get('title') or p.stem
                artist = tags.get('artist') or ''
                album = tags.get('album') or ''
                year_raw = tags.get('year') or ''
                year = None
                if year_raw:
                    import re as _re
                    m = _re.search(r"(19|20)\d{2}", str(year_raw))
                    if m:
                        year = int(m.group(0))
                duration = None
                if audio and getattr(audio, 'info', None) and getattr(audio.info, 'length', None):
                    duration = float(audio.info.length)
                
                # Extract bitrate (convert to kbps)
                bitrate_kbps = None
                if audio and getattr(audio, 'info', None):
                    # Try to get bitrate from audio info
                    if hasattr(audio.info, 'bitrate') and audio.info.bitrate:
                        bitrate_kbps = int(audio.info.bitrate / 1000)  # Convert bits/sec to kbps
                    # Some formats use different attribute names
                    elif hasattr(audio.info, 'sample_rate') and hasattr(audio.info, 'bits_per_sample'):
                        # Calculate bitrate for lossless formats
                        sample_rate = audio.info.sample_rate
                        bits_per_sample = audio.info.bits_per_sample
                        channels = getattr(audio.info, 'channels', 2)
                        bitrate_kbps = int((sample_rate * bits_per_sample * channels) / 1000)
                
                ph = partial_hash(p)
                nt, na, combo = normalize_title_artist(title, artist)
                if use_year and year is not None:
                    combo = f"{combo} {year}"
                
                # Determine insert vs update (path_str already defined at top of loop)
                existing = None
                if path_str in existing_files:
                    # File was in DB, this is an update
                    existing = True
                else:
                    # Check if it exists but wasn't in our batch (edge case)
                    existing = db.conn.execute("SELECT id FROM library_files WHERE path=?", (path_str,)).fetchone()
                
                db.add_library_file({
                    'path': path_str,  # Use normalized path_str instead of str(p)
                    'size': st.st_size,
                    'mtime': st.st_mtime,
                    'partial_hash': ph,
                    'title': title,
                    'album': album,
                    'artist': artist,
                    'duration': duration,
                    'normalized': combo,
                    'year': year,
                    'bitrate_kbps': bitrate_kbps,
                })
                if existing:
                    updated += 1
                    action = "updated"
                    color = 'blue'
                else:
                    inserted += 1
                    action = "new"
                    color = 'green'
                since_commit += 1
                logger.debug(f"{click.style(f'[{action}]', fg=color)} {p} | title='{title}' artist='{artist}' album='{album}' year={year if year is not None else '-'} dur={duration if duration is not None else '-'} bitrate={bitrate_kbps if bitrate_kbps is not None else '-'} kbps norm='{combo}'")
                if commit_interval and since_commit >= commit_interval:
                    db.commit()
                    logger.debug(f"Interim commit after {since_commit} processed (inserted={inserted} updated={updated} skipped={skipped_unchanged})")
                    since_commit = 0
                
                # Log progress every N files
                if files_seen - last_progress_log >= progress_interval:
                    elapsed = time.time() - start
                    log_progress(
                        processed=files_seen,
                        total=None,  # Total unknown during iteration
                        new=inserted,
                        updated=updated,
                        skipped=skipped_unchanged,
                        elapsed_seconds=elapsed,
                        item_name="files"
                    )
                    last_progress_log = files_seen
                    
            except KeyboardInterrupt:
                print(f"{click.style('[interrupt]', fg='magenta')} Caught keyboard interrupt; finalizing partial work...")
                break
            except Exception as e:
                other_errors += 1
                logger.debug(f"{click.style('[error]', fg='red')} {p} {e}")
                continue
    finally:
        # Cleanup: remove files from DB that no longer exist on disk
        # Use set-based comparison instead of checking file.exists() for each DB row
        deleted = 0
        logger.debug("Checking for deleted files...")
        logger.debug(f"Seen {len(seen_paths)} files during this scan")
        
        # Get all paths from DB in one query
        rows = db.conn.execute("SELECT id, path FROM library_files").fetchall()
        db_paths = {row['path']: row['id'] for row in rows}
        
        logger.debug(f"Database contains {len(db_paths)} files")
        # Show sample of path formats for debugging
        if db_paths and seen_paths:
            db_sample = list(db_paths.keys())[0] if db_paths else None
            seen_sample = list(seen_paths)[0] if seen_paths else None
            if db_sample:
                logger.debug(f"Sample DB path: {db_sample}")
            if seen_sample:
                logger.debug(f"Sample seen path: {seen_sample}")
        
        # Find paths in DB but not seen during scan
        deleted_paths = set(db_paths.keys()) - seen_paths
        
        if deleted_paths:
            logger.debug(f"Found {len(deleted_paths)} files to delete")
            # Show first few for debugging
            for path in list(deleted_paths)[:3]:
                logger.debug(f"Will delete: {path}")
                # Check if a similar path exists in seen_paths (case/slash differences)
                similar = [sp for sp in seen_paths if sp.lower().replace('/', '\\') == path.lower().replace('/', '\\')]
                if similar:
                    logger.debug(f"WARNING: Similar path found in seen_paths: {similar[0]}")
                    logger.debug(f"This suggests a path normalization issue!")
        
        for path in deleted_paths:
            file_id = db_paths[path]
            db.conn.execute("DELETE FROM library_files WHERE id=?", (file_id,))
            # Also remove any matches for this file
            db.conn.execute("DELETE FROM matches WHERE file_id=?", (file_id,))
            deleted += 1
            logger.debug(f"{click.style('[deleted]', fg='red')} {path} (no longer exists)")
        
        db.commit()
        dur = time.time() - start
        summary = format_summary(
            new=inserted,
            updated=updated,
            unchanged=skipped_unchanged,
            deleted=deleted,
            duration_seconds=dur,
            item_name="Library"
        )
        logger.info(summary)
        if tag_errors or io_errors or other_errors:
            logger.debug(f"Errors: tag={tag_errors} io={io_errors} other={other_errors}")

__all__ = ["scan_library"]
