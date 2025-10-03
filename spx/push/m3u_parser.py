from __future__ import annotations
"""Lightweight M3U parser for push feature.

We only need to recover the ordered list of local file paths from an exported
playlist file. We deliberately ignore extended metadata (#EXTINF etc.) and
comment lines. Lines beginning with '# Spotify:' are metadata and skipped.

Paths may be absolute (typical for strict/mirrored modes) or relative (the
placeholders mode may emit relative paths pointing into a *_placeholders dir).
We normalize by resolving relative paths against the playlist file's parent
directory. Resolution failures (e.g. path does not exist) are still returned as
the joined path string – existence is not required because we only map them to
tracks via the matches table using their stored absolute path when available.
"""
from pathlib import Path
from typing import List

def parse_m3u_paths(path: Path) -> List[str]:
    """Return ordered list of path-like lines from an M3U file.

    Args:
        path: Path to the .m3u / .m3u8 file.

    Returns:
        List of (string) paths in order they appeared (comments & metadata removed).
    """
    lines = []
    text = path.read_text(encoding='utf-8', errors='ignore')
    parent = path.parent
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith('#'):
            # Skip all comment / directive lines – we don't need metadata for reverse mapping
            continue
        p = Path(line)
        if not p.is_absolute():
            # Resolve relative paths against playlist directory
            p = (parent / p).resolve()
        else:
            # Normalize absolute path (remove .., symlinks if any)
            try:
                p = p.resolve()
            except Exception:
                # If resolution fails, fall back to original
                pass
        lines.append(str(p))
    return lines

__all__ = ["parse_m3u_paths"]
