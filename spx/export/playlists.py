from __future__ import annotations
from pathlib import Path
from typing import Iterable, Dict, Any, Sequence
import os

HEADER = "#EXTM3U"


def sanitize_filename(name: str) -> str:
    bad = '<>:"/\\|?*'
    for c in bad:
        name = name.replace(c, '_')
    return name.strip()


def export_strict(playlist: Dict[str, Any], tracks: Iterable[Dict[str, Any]], out_dir: Path):
    """Strict mode: only include resolved local file paths, omit missing tracks."""
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = sanitize_filename(playlist.get('name', 'playlist')) + '.m3u8'
    path = out_dir / fname
    lines = [HEADER]
    for t in tracks:
        local_path = t.get('local_path')
        if not local_path:
            continue
        lines.append(str(local_path))
    path.write_text('\n'.join(lines), encoding='utf-8')
    if os.environ.get('SPX_DEBUG'):
        kept = sum(1 for t in tracks if t.get('local_path'))
        print(f"[export] strict playlist='{playlist.get('name')}' kept={kept} file={path}")
    return path


def _extinf_line(track: Dict[str, Any]) -> str:
    # Duration in seconds (rounded) or -1 if unknown
    dur_ms = track.get('duration_ms')
    if dur_ms is None:
        dur_sec = -1
    else:
        try:
            dur_sec = int(round(float(dur_ms) / 1000.0))
        except Exception:
            dur_sec = -1
    artist = track.get('artist') or ''
    name = track.get('name') or ''
    return f"#EXTINF:{dur_sec},{artist} - {name}".strip()


def export_mirrored(playlist: Dict[str, Any], tracks: Sequence[Dict[str, Any]], out_dir: Path):
    """Mirrored mode: preserve full playlist order; include EXTINF lines for all tracks.
    Missing tracks are annotated but do not create placeholder files.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = sanitize_filename(playlist.get('name', 'playlist')) + '.m3u8'
    path = out_dir / fname
    lines = [HEADER]
    for t in tracks:
        lines.append(_extinf_line(t) + (" (MISSING)" if not t.get('local_path') else ""))
        if t.get('local_path'):
            lines.append(str(t['local_path']))
        else:
            # Leave a commented marker to keep position
            artist = t.get('artist') or ''
            name = t.get('name') or ''
            lines.append(f"# MISSING: {artist} - {name}")
    path.write_text('\n'.join(lines), encoding='utf-8')
    if os.environ.get('SPX_DEBUG'):
        missing = sum(1 for t in tracks if not t.get('local_path'))
        print(f"[export] mirrored playlist='{playlist.get('name')}' total={len(tracks)} missing={missing} file={path}")
    return path


def export_placeholders(playlist: Dict[str, Any], tracks: Sequence[Dict[str, Any]], out_dir: Path, placeholder_extension: str = '.missing'):
    """Placeholders mode: like mirrored, but create placeholder files for missing tracks.

    Placeholder files allow media players to show positional gaps. Each placeholder
    is an empty (or tiny) file named using playlist position & track title.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = sanitize_filename(playlist.get('name', 'playlist')) + '.m3u8'
    path = out_dir / fname
    placeholders_dir = out_dir / (sanitize_filename(playlist.get('name', 'playlist')) + '_placeholders')
    placeholders_dir.mkdir(parents=True, exist_ok=True)
    lines = [HEADER]
    used_names = set()
    for t in tracks:
        pos = t.get('position')
        base_name = f"{pos:04d}_" if isinstance(pos, int) else ''
        title_part = sanitize_filename((t.get('name') or 'missing').strip()) or 'missing'
        candidate_name = base_name + title_part + placeholder_extension
        # ensure uniqueness
        counter = 1
        unique_name = candidate_name
        while unique_name in used_names:
            unique_name = base_name + title_part + f"_{counter}" + placeholder_extension
            counter += 1
        used_names.add(unique_name)
        if not t.get('local_path'):
            placeholder_path = placeholders_dir / unique_name
            if not placeholder_path.exists():
                placeholder_path.write_text("Missing track placeholder", encoding='utf-8')
            # For playlist line use relative path
            rel_path = placeholder_path.relative_to(out_dir)
            lines.append(_extinf_line(t) + " (PLACEHOLDER)")
            lines.append(str(rel_path))
        else:
            lines.append(_extinf_line(t))
            lines.append(str(t['local_path']))
    path.write_text('\n'.join(lines), encoding='utf-8')
    if os.environ.get('SPX_DEBUG'):
        placeholders = sum(1 for t in tracks if not t.get('local_path'))
        print(f"[export] placeholders playlist='{playlist.get('name')}' total={len(tracks)} placeholders={placeholders} file={path}")
    return path

__all__ = [
    "export_strict",
    "export_mirrored",
    "export_placeholders",
    "sanitize_filename",
]
