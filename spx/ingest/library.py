from __future__ import annotations
from pathlib import Path
from typing import Iterable, Dict, Any
import mutagen
from ..utils.fs import iter_music_files
from ..utils.hashing import partial_hash
from ..utils.normalization import normalize_title_artist
import time
import os

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
    
    # Batch load existing file metadata for skip-unchanged checks (avoids per-file queries)
    existing_files = {}
    if skip_unchanged:
        # Load all existing file metadata including tags for fast_scan mode
        if fast_scan:
            rows = db.conn.execute(
                "SELECT path, size, mtime, partial_hash, title, artist, album, year, duration, normalized FROM library_files"
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
                }
                for row in rows
            }
        else:
            rows = db.conn.execute("SELECT path, size, mtime, partial_hash FROM library_files").fetchall()
            existing_files = {row['path']: (row['size'], row['mtime'], row['partial_hash']) for row in rows}
        if os.environ.get('SPX_DEBUG'):
            print(f"[scan] Loaded {len(existing_files)} existing files for skip-unchanged checks")

    try:
        for p in iter_music_files(paths, extensions, ignore_patterns, follow_symlinks):
            files_seen += 1
            path_str = str(p)
            seen_paths.add(path_str)  # Track this path as seen
            try:
                st = p.stat()
            except OSError:
                io_errors += 1
                if os.environ.get('SPX_DEBUG'):
                    print(f"[scan][io-error] {p}")
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
                        if os.environ.get('SPX_DEBUG'):
                            print(f"[scan][skip] {p} unchanged (fast mode - no parsing)")
                        continue
                else:
                    # Normal mode: tuple format
                    size_db, mtime_db, hash_db = existing_data
                    if size_db == st.st_size and abs(mtime_db - st.st_mtime) < 1.0:
                        skipped_unchanged += 1
                        if os.environ.get('SPX_DEBUG'):
                            print(f"[scan][skip] {p} unchanged")
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
                    'path': str(p),
                    'size': st.st_size,
                    'mtime': st.st_mtime,
                    'partial_hash': ph,
                    'title': title,
                    'album': album,
                    'artist': artist,
                    'duration': duration,
                    'normalized': combo,
                    'year': year,
                })
                if existing:
                    updated += 1
                    action = "updated"
                else:
                    inserted += 1
                    action = "new"
                since_commit += 1
                if os.environ.get('SPX_DEBUG'):
                    print(f"[scan][{action}] {p} | title='{title}' artist='{artist}' album='{album}' year={year if year is not None else '-'} dur={duration if duration is not None else '-'} norm='{combo}'")
                if commit_interval and since_commit >= commit_interval:
                    db.commit()
                    if os.environ.get('SPX_DEBUG'):
                        print(f"[scan] interim commit after {since_commit} processed (inserted={inserted} updated={updated} skipped={skipped_unchanged})")
                    since_commit = 0
            except KeyboardInterrupt:
                print("[scan][interrupt] Caught keyboard interrupt; finalizing partial work...")
                break
            except Exception as e:
                other_errors += 1
                if os.environ.get('SPX_DEBUG'):
                    print(f"[scan][error] {p} {e}")
                continue
    finally:
        # Cleanup: remove files from DB that no longer exist on disk
        # Use set-based comparison instead of checking file.exists() for each DB row
        deleted = 0
        if os.environ.get('SPX_DEBUG'):
            print("[scan] Checking for deleted files...")
        
        # Get all paths from DB in one query
        rows = db.conn.execute("SELECT id, path FROM library_files").fetchall()
        db_paths = {row['path']: row['id'] for row in rows}
        
        # Find paths in DB but not seen during scan
        deleted_paths = set(db_paths.keys()) - seen_paths
        
        for path in deleted_paths:
            file_id = db_paths[path]
            db.conn.execute("DELETE FROM library_files WHERE id=?", (file_id,))
            # Also remove any matches for this file
            db.conn.execute("DELETE FROM matches WHERE file_id=?", (file_id,))
            deleted += 1
            if os.environ.get('SPX_DEBUG'):
                print(f"[scan][deleted] {path} (no longer exists)")
        
        db.commit()
        dur = time.time() - start
        if os.environ.get('SPX_DEBUG'):
            print(
                f"[scan] Summary: files_seen={files_seen} inserted={inserted} updated={updated} "
                f"skipped_unchanged={skipped_unchanged} deleted={deleted} tag_errors={tag_errors} io_errors={io_errors} other_errors={other_errors} in {dur:.2f}s"
            )

__all__ = ["scan_library"]
