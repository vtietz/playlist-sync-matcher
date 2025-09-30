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
    count = 0
    start = time.time()
    for p in iter_music_files(paths, extensions, ignore_patterns, follow_symlinks):
        try:
            st = p.stat()
            audio = mutagen.File(p)
            tags = extract_tags(audio)
            title = tags.get('title') or p.stem
            artist = tags.get('artist') or ''
            album = tags.get('album') or ''
            year_raw = tags.get('year') or ''
            # Normalize year to 4-digit if possible
            year = None
            if year_raw:
                # extract first 4 consecutive digits (common in date formats)
                import re as _re
                m = _re.search(r"(19|20)\d{2}", str(year_raw))
                if m:
                    year = int(m.group(0))
            duration = None
            if audio and getattr(audio, 'info', None) and getattr(audio.info, 'length', None):
                duration = float(audio.info.length)
            ph = partial_hash(p)
            nt, na, combo = normalize_title_artist(title, artist)
            if cfg.get('matching', {}).get('use_year') and year is not None:
                combo = f"{combo} {year}"
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
            count += 1
            if os.environ.get('SPX_DEBUG'):
                # Show concise tag summary for diagnostics
                print(f"[scan] {p} | title='{title}' artist='{artist}' album='{album}' year={year if year is not None else '-'} dur={duration if duration is not None else '-'} norm='{combo}'")
        except Exception as e:
            if os.environ.get('SPX_DEBUG'):
                print(f"[scan][error] Failed processing {p}: {e}")
            continue
    db.commit()
    if os.environ.get('SPX_DEBUG'):
        dur = time.time() - start
        print(f"[scan] Completed: files={count} in {dur:.2f}s")

__all__ = ["scan_library"]
