from __future__ import annotations
from pathlib import Path
from typing import Iterable, Dict, Any, Sequence
import os
import logging
from psm.utils.path_format import format_path_for_m3u

logger = logging.getLogger(__name__)

HEADER = "#EXTM3U"


def sanitize_filename(name: str) -> str:
    bad = '<>:"/\\|?*'
    for c in bad:
        name = name.replace(c, '_')
    return name.strip()


def export_strict(
    playlist: Dict[str, Any],
    tracks: Iterable[Dict[str, Any]],
    out_dir: Path,
    path_format: str = "absolute",
    library_roots: list[str] | None = None
):
    """Strict mode: only include resolved local file paths, omit missing tracks.
    
    Args:
        playlist: Playlist metadata dict
        tracks: Iterable of track dicts with 'local_path' field
        out_dir: Output directory for M3U file
        path_format: "absolute" or "relative" paths in M3U
        library_roots: Library root paths from config (for path reconstruction)
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    playlist_id = playlist.get('id', 'unknown')
    fname = f"{sanitize_filename(playlist.get('name', 'playlist'))}_{playlist_id[:8]}.m3u"
    path = out_dir / fname
    lines = [HEADER]
    
    # Add Spotify URL if playlist ID is available
    if playlist_id != 'unknown':
        lines.append(f"# Spotify: https://open.spotify.com/playlist/{playlist_id}")
    
    for t in tracks:
        local_path = t.get('local_path')
        if not local_path:
            continue
        formatted_path = format_path_for_m3u(local_path, path, path_format, library_roots)
        lines.append(formatted_path)
    path.write_text('\n'.join(lines), encoding='utf-8')
    
    kept = sum(1 for t in tracks if t.get('local_path'))
    logger.debug(f"[exported] strict playlist='{playlist.get('name')}' kept={kept} file={path}")
    return path


def _extinf_line(track: Dict[str, Any], mark_missing: bool = False) -> str:
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
    # Add visual indicator for missing tracks (shown in player UI)
    prefix = "❌ " if mark_missing else ""
    return f"#EXTINF:{dur_sec},{prefix}{artist} - {name}".strip()


def export_mirrored(
    playlist: Dict[str, Any],
    tracks: Sequence[Dict[str, Any]],
    out_dir: Path,
    path_format: str = "absolute",
    library_roots: list[str] | None = None
):
    """Mirrored mode: preserve full playlist order; include EXTINF lines for all tracks.
    Missing tracks use a placeholder path prefixed with '!' to indicate they're not available.
    This maintains M3U spec compliance (every #EXTINF has a path) while preserving track order.
    
    Args:
        playlist: Playlist metadata dict
        tracks: Sequence of track dicts with 'local_path' field
        out_dir: Output directory for M3U file
        path_format: "absolute" or "relative" paths in M3U
        library_roots: Library root paths from config (for path reconstruction)
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    playlist_id = playlist.get('id', 'unknown')
    fname = f"{sanitize_filename(playlist.get('name', 'playlist'))}_{playlist_id[:8]}.m3u"
    path = out_dir / fname
    lines = [HEADER]
    
    # Add Spotify URL if playlist ID is available
    if playlist_id != 'unknown':
        lines.append(f"# Spotify: https://open.spotify.com/playlist/{playlist_id}")
    
    # Collect missing tracks for summary
    missing_tracks = [t for t in tracks if not t.get('local_path')]
    if missing_tracks:
        lines.append(f"# NOTE: {len(missing_tracks)} tracks not found in library")
        lines.append(f"# Missing tracks are marked with ❌ emoji and won't play")
        lines.append("#")
    
    # Include ALL tracks to preserve order (mirrored mode)
    for t in tracks:
        is_missing = not t.get('local_path')
        lines.append(_extinf_line(t, mark_missing=is_missing))
        if t.get('local_path'):
            # Valid track - use actual path with formatting
            formatted_path = format_path_for_m3u(t['local_path'], path, path_format, library_roots)
            lines.append(formatted_path)
        else:
            # Missing track - use placeholder with '!' prefix
            artist = (t.get('artist') or 'Unknown Artist').strip()
            name = (t.get('name') or 'Unknown Track').strip()
            placeholder = f"!MISSING - {artist} - {name}"
            lines.append(placeholder)
    path.write_text('\n'.join(lines), encoding='utf-8')
    
    missing = sum(1 for t in tracks if not t.get('local_path'))
    logger.debug(f"[exported] mirrored playlist='{playlist.get('name')}' total={len(tracks)} missing={missing} file={path}")
    return path


def export_placeholders(
    playlist: Dict[str, Any],
    tracks: Sequence[Dict[str, Any]],
    out_dir: Path,
    placeholder_extension: str = '.missing',
    path_format: str = "absolute",
    library_roots: list[str] | None = None
):
    """Placeholders mode: like mirrored, but create placeholder files for missing tracks.

    Placeholder files allow media players to show positional gaps. Each placeholder
    is an empty (or tiny) file named using playlist position & track title.
    
    Args:
        playlist: Playlist metadata dict
        tracks: Sequence of track dicts with 'local_path' field
        out_dir: Output directory for M3U file
        placeholder_extension: Extension for placeholder files
        path_format: "absolute" or "relative" paths in M3U
        library_roots: Library root paths from config (for path reconstruction)
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    playlist_id = playlist.get('id', 'unknown')
    fname = f"{sanitize_filename(playlist.get('name', 'playlist'))}_{playlist_id[:8]}.m3u"
    path = out_dir / fname
    placeholders_dir = out_dir / (f"{sanitize_filename(playlist.get('name', 'playlist'))}_{playlist_id[:8]}_placeholders")
    placeholders_dir.mkdir(parents=True, exist_ok=True)
    lines = [HEADER]
    
    # Add Spotify URL if playlist ID is available
    if playlist_id != 'unknown':
        lines.append(f"# Spotify: https://open.spotify.com/playlist/{playlist_id}")
    
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
            # For placeholder files, use relative path
            rel_path = placeholder_path.relative_to(out_dir)
            lines.append(_extinf_line(t) + " (PLACEHOLDER)")
            lines.append(str(rel_path))
        else:
            lines.append(_extinf_line(t))
            formatted_path = format_path_for_m3u(t['local_path'], path, path_format, library_roots)
            lines.append(formatted_path)
    path.write_text('\n'.join(lines), encoding='utf-8')
    
    placeholders = sum(1 for t in tracks if not t.get('local_path'))
    logger.debug(f"[exported] placeholders playlist='{playlist.get('name')}' total={len(tracks)} placeholders={placeholders} file={path}")
    return path

__all__ = [
    "export_strict",
    "export_mirrored",
    "export_placeholders",
    "sanitize_filename",
]
