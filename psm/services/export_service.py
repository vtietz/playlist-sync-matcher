"""Export service: Orchestrate playlist export to M3U files.

This service handles playlist enumeration, directory resolution,
and dispatching to the appropriate export mode.
"""

from __future__ import annotations
import logging
from typing import Dict, Any, List
from pathlib import Path

from ..export.playlists import export_strict, export_mirrored, export_placeholders, sanitize_filename
from ..db import DatabaseInterface

logger = logging.getLogger(__name__)


class ExportResult:
    """Results from an export operation."""

    def __init__(self):
        self.playlist_count = 0
        self.exported_files: List[str] = []
        self.obsolete_files: List[str] = []  # Files that exist but aren't in current playlists
        self.cleaned_files: List[str] = []  # Files that were deleted during cleanup


def _find_existing_m3u_files(export_dir: Path) -> List[Path]:
    """Find all existing .m3u files in export directory (recursively).

    Args:
        export_dir: Export directory to scan

    Returns:
        List of .m3u file paths
    """
    if not export_dir.exists():
        return []
    return list(export_dir.rglob("*.m3u"))


def _detect_obsolete_files(
    existing_files: List[Path],
    exported_files: List[str]
) -> List[Path]:
    """Detect files that exist but weren't just exported.

    Args:
        existing_files: All existing .m3u files before export
        exported_files: Files that were just exported

    Returns:
        List of obsolete file paths
    """
    exported_set = {Path(f).resolve() for f in exported_files}
    obsolete = []
    for f in existing_files:
        if f.resolve() not in exported_set:
            obsolete.append(f)
    return obsolete


def _clean_export_directory(export_dir: Path) -> List[str]:
    """Delete all .m3u files in export directory.

    Args:
        export_dir: Export directory to clean

    Returns:
        List of deleted file paths
    """
    deleted = []
    if not export_dir.exists():
        return deleted

    for m3u_file in export_dir.rglob("*.m3u"):
        try:
            m3u_file.unlink()
            deleted.append(str(m3u_file))
            logger.debug(f"Deleted: {m3u_file}")
        except Exception as e:
            logger.warning(f"Failed to delete {m3u_file}: {e}")

    return deleted


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

    # Always use the actual owner name, even if it's the current user
    # This provides clearer organization and consistency
    if owner_name:
        # Sanitize owner name to avoid invalid path characters
        folder_name = sanitize_filename(owner_name)
        return base_dir / folder_name
    else:
        return base_dir / 'other'


def export_playlists(
    db: DatabaseInterface,
    export_config: Dict[str, Any],
    organize_by_owner: bool = False,
    current_user_id: str | None = None,
    library_paths: list[str] | None = None,
    playlist_ids: List[str] | None = None
) -> ExportResult:
    """Export playlists to M3U files.

    Automatically includes Liked Songs as a virtual playlist unless disabled in config.

    Args:
        db: Database instance
        export_config: Export configuration (mode, directory, placeholder_extension, include_liked_songs)
        organize_by_owner: Organize playlists by owner
        current_user_id: Current user ID (for owner organization)
        library_paths: Library root paths from config (for path reconstruction)
        playlist_ids: Optional list of specific playlist IDs to export (None = export all)

    Returns:
        ExportResult with count and file list
    """
    result = ExportResult()

    # Extract config
    export_dir = Path(export_config['directory'])
    mode = export_config.get('mode', 'strict')
    placeholder_ext = export_config.get('placeholder_extension', '.missing')
    include_liked_songs = export_config.get('include_liked_songs', True)  # Default: enabled
    path_format = export_config.get('path_format', 'absolute')
    use_library_roots = export_config.get('use_library_roots', True)
    clean_before_export = export_config.get('clean_before_export', False)
    detect_obsolete = export_config.get('detect_obsolete', True)

    # Prepare library roots for path reconstruction (if enabled)
    library_roots_param = library_paths if (use_library_roots and library_paths) else None

    # Clean export directory before export (if configured)
    if clean_before_export:
        logger.info("Cleaning export directory before export...")
        result.cleaned_files = _clean_export_directory(export_dir)
        if result.cleaned_files:
            logger.info(f"Deleted {len(result.cleaned_files)} existing .m3u files")

    # Capture existing files for obsolete detection (before export, after optional clean)
    existing_files_before = [] if clean_before_export else _find_existing_m3u_files(export_dir)

    # Get current user ID from metadata if not provided
    if organize_by_owner and current_user_id is None:
        current_user_id = db.get_meta('current_user_id')

    # Enumerate playlists using repository method (provider-aware, sorted)
    provider = 'spotify'  # TODO: Make configurable when adding multi-provider support
    playlists = db.list_playlists(playlist_ids, provider)

    total_playlists = len(playlists)

    # Group playlists by owner for logging
    from collections import defaultdict
    playlists_by_owner = defaultdict(list)
    for pl in playlists:
        owner = pl.get('owner_name') or pl.get('owner_id') or 'Unknown'
        playlists_by_owner[owner].append(pl)

    # Log export summary by owner (INFO mode)
    if not logger.isEnabledFor(logging.DEBUG):
        if playlist_ids:
            logger.info(f"Exporting {total_playlists} affected playlist(s) from {len(playlists_by_owner)} owner(s):")
        else:
            logger.info(f"Exporting {total_playlists} playlist(s) from {len(playlists_by_owner)} owner(s):")
        for owner in sorted(playlists_by_owner.keys()):
            count = len(playlists_by_owner[owner])
            logger.info(f"  • {owner}: {count} playlist(s)")

    for idx, pl in enumerate(playlists, 1):
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

        # Fetch tracks with local paths using repository method (provider-aware, best match only)
        track_rows = db.get_playlist_tracks_with_local_paths(pl_id, provider)
        tracks = [dict(r) | {'position': r['position']} for r in track_rows]
        playlist_meta = {'name': pl['name'], 'id': pl_id}

        # Log progress (only in DEBUG mode - INFO mode shows per-owner summary above)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"[{idx}/{total_playlists}] Exporting: {pl['name']}")

        # Dispatch to export function based on mode and capture actual path
        if mode == 'strict':
            actual_path = export_strict(playlist_meta, tracks, target_dir, path_format, library_roots_param)
        elif mode == 'mirrored':
            actual_path = export_mirrored(playlist_meta, tracks, target_dir, path_format, library_roots_param)
        elif mode == 'placeholders':
            actual_path = export_placeholders(playlist_meta, tracks, target_dir, placeholder_ext, path_format, library_roots_param)
        else:
            logger.warning(f"Unknown export mode '{mode}', defaulting to strict")
            actual_path = export_strict(playlist_meta, tracks, target_dir, path_format, library_roots_param)

        result.exported_files.append(str(actual_path))

    result.playlist_count = len(playlists)

    # Export Liked Songs as virtual playlist (unless disabled in config)
    # Skip Liked Songs during incremental/scoped exports (playlist_ids provided)
    # to avoid unnecessary full exports - caller should trigger full export if Liked Songs affected
    provider = 'spotify'  # TODO: Make configurable when adding multi-provider support
    if include_liked_songs and playlist_ids is None:
        liked_count = db.count_liked_tracks(provider=provider)
        if liked_count > 0:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Exporting Liked Songs as virtual playlist ({liked_count} tracks)")
            _export_liked_tracks(
                db,
                export_dir,
                mode,
                placeholder_ext,
                organize_by_owner,
                current_user_id,
                path_format,
                library_roots_param,
                result
            )

    # Detect obsolete files (if configured and not cleaned)
    if detect_obsolete and not clean_before_export and existing_files_before:
        result.obsolete_files = [
            str(f) for f in _detect_obsolete_files(existing_files_before, result.exported_files)
        ]
        if result.obsolete_files:
            logger.info(f"Found {len(result.obsolete_files)} obsolete playlist(s) in export directory")

    logger.info(
        f"✓ Exported "
        f"{result.playlist_count} playlists "
        f"to {export_dir}"
    )
    return result


def _export_liked_tracks(
    db: DatabaseInterface,
    export_dir: Path,
    mode: str,
    placeholder_ext: str,
    organize_by_owner: bool,
    current_user_id: str | None,
    path_format: str,
    library_roots: list[str] | None,
    result: ExportResult
) -> None:
    """Export liked tracks as a virtual 'Liked Songs' playlist.

    Args:
        db: Database instance
        export_dir: Base export directory
        mode: Export mode (strict/mirrored/placeholders)
        placeholder_ext: Extension for placeholder files
        organize_by_owner: Whether to organize by owner
        current_user_id: Current user ID (for owner organization)
        path_format: Path format for M3U files
        library_roots: Library root paths from config (for path reconstruction)
        result: Result object to update with export info
    """
    # Determine target directory
    if organize_by_owner:
        # Use current user's folder if available, otherwise root
        owner_name = db.get_meta('current_user_name')
        if owner_name:
            target_dir = _resolve_export_dir(
                export_dir,
                True,
                current_user_id,
                owner_name,
                current_user_id
            )
        else:
            target_dir = export_dir
    else:
        target_dir = export_dir

    # Fetch liked tracks with local paths using repository method (provider-aware, best match only)
    provider = 'spotify'  # TODO: Make configurable when adding multi-provider support
    track_rows = db.get_liked_tracks_with_local_paths(provider)

    tracks = [dict(r) for r in track_rows]

    # Add position attribute (0-indexed, preserving newest-first order)
    for i, track in enumerate(tracks):
        track['position'] = i

    playlist_meta = {
        'name': 'Liked Songs',
        'id': '_liked_songs_virtual'
    }

    # Dispatch to appropriate export mode and get the actual file path
    if mode == 'strict':
        actual_path = export_strict(playlist_meta, tracks, target_dir, path_format, library_roots)
    elif mode == 'mirrored':
        actual_path = export_mirrored(playlist_meta, tracks, target_dir, path_format, library_roots)
    elif mode == 'placeholders':
        actual_path = export_placeholders(playlist_meta, tracks, target_dir, placeholder_ext, path_format, library_roots)
    else:
        logger.warning(f"Unknown export mode '{mode}', defaulting to strict")
        actual_path = export_strict(playlist_meta, tracks, target_dir, path_format, library_roots)

    # Update result
    result.playlist_count += 1
    result.exported_files.append(str(actual_path))
