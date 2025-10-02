"""Export service: Orchestrate playlist export to M3U files.

This service handles playlist enumeration, directory resolution,
and dispatching to the appropriate export mode.
"""

from __future__ import annotations
import logging
from typing import Dict, Any, List
from pathlib import Path

from ..export.playlists import export_strict, export_mirrored, export_placeholders, sanitize_filename
from ..db import Database

logger = logging.getLogger(__name__)


class ExportResult:
    """Results from an export operation."""
    
    def __init__(self):
        self.playlist_count = 0
        self.exported_files: List[str] = []


def _resolve_export_dir(
    base_dir: Path,
    organize_by_owner: bool,
    owner_id: str | None,
    owner_name: str | None,
    current_user_id: str | None
) -> Path:
    """Resolve export directory for a playlist.
    
    Args:
        base_dir: Base export directory
        organize_by_owner: Whether to organize by owner
        owner_id: Playlist owner ID
        owner_name: Playlist owner name
        current_user_id: Current user ID (for "my" vs owner name)
        
    Returns:
        Path to export directory for this playlist
    """
    if not organize_by_owner:
        return base_dir
    
    if owner_id and owner_id == current_user_id:
        return base_dir / 'my_playlists'
    elif owner_name:
        # Sanitize owner name to avoid invalid path characters
        folder_name = sanitize_filename(owner_name)
        return base_dir / folder_name
    else:
        return base_dir / 'other'


def export_playlists(
    db: Database,
    export_config: Dict[str, Any],
    organize_by_owner: bool = False,
    current_user_id: str | None = None
) -> ExportResult:
    """Export playlists to M3U files.
    
    Args:
        db: Database instance
        export_config: Export configuration (mode, directory, placeholder_extension)
        organize_by_owner: Organize playlists by owner
        current_user_id: Current user ID (for owner organization)
        
    Returns:
        ExportResult with count and file list
    """
    result = ExportResult()
    
    # Extract config
    export_dir = Path(export_config['directory'])
    mode = export_config.get('mode', 'strict')
    placeholder_ext = export_config.get('placeholder_extension', '.missing')
    
    # Get current user ID from metadata if not provided
    if organize_by_owner and current_user_id is None:
        current_user_id = db.get_meta('current_user_id')
    
    # Enumerate playlists
    cur = db.conn.execute("SELECT id, name, owner_id, owner_name FROM playlists")
    playlists = cur.fetchall()
    
    for pl in playlists:
        pl_id = pl['id']
        owner_id = pl['owner_id'] if 'owner_id' in pl.keys() else None
        owner_name = pl['owner_name'] if 'owner_name' in pl.keys() else None
        
        # Determine target directory
        target_dir = _resolve_export_dir(
            export_dir,
            organize_by_owner,
            owner_id,
            owner_name,
            current_user_id
        )
        
        # Fetch tracks with local paths
        track_rows = db.conn.execute(
            """
            SELECT pt.position, t.id as track_id, t.name, t.artist, t.album, t.duration_ms, lf.path AS local_path
            FROM playlist_tracks pt
            LEFT JOIN tracks t ON t.id = pt.track_id
            LEFT JOIN matches m ON m.track_id = pt.track_id
            LEFT JOIN library_files lf ON lf.id = m.file_id
            WHERE pt.playlist_id=?
            ORDER BY pt.position
            """,
            (pl_id,),
        ).fetchall()
        tracks = [dict(r) | {'position': r['position']} for r in track_rows]
        playlist_meta = {'name': pl['name'], 'id': pl_id}
        
        # Dispatch to export function based on mode
        if mode == 'strict':
            export_strict(playlist_meta, tracks, target_dir)
        elif mode == 'mirrored':
            export_mirrored(playlist_meta, tracks, target_dir)
        elif mode == 'placeholders':
            export_placeholders(playlist_meta, tracks, target_dir, placeholder_extension=placeholder_ext)
        else:
            logger.warning(f"Unknown export mode '{mode}', defaulting to strict")
            export_strict(playlist_meta, tracks, target_dir)
        
        result.exported_files.append(str(target_dir / f"{pl['name']}.m3u"))
    
    result.playlist_count = len(playlists)
    return result
