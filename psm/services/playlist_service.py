"""Playlist service: Single-playlist operations.

Handles operations on individual playlists:
- Pull/ingest a single playlist
- Match tracks from a single playlist
- Export a single playlist
- Build (pull + match + export) a single playlist
"""

from __future__ import annotations
import time
import logging
from typing import Dict, Any
from pathlib import Path
from datetime import datetime

from ..auth.spotify_oauth import SpotifyAuth
from ..ingest.spotify import SpotifyClient
from ..db import Database, DatabaseInterface
from ..utils.normalization import normalize_title_artist
from ..match.engine import match_tracks
from ..export.playlists import export_strict, export_mirrored, export_placeholders, sanitize_filename

logger = logging.getLogger(__name__)


class SinglePlaylistResult:
    """Results from a single-playlist operation."""
    
    def __init__(self):
        self.playlist_id: str | None = None
        self.playlist_name: str | None = None
        self.tracks_processed = 0
        self.tracks_matched = 0
        self.exported_file: str | None = None
        self.duration_seconds = 0.0


def _extract_year(release_date: str | None):
    """Extract year from Spotify release date."""
    if not release_date:
        return None
    if len(release_date) >= 4 and release_date[:4].isdigit():
        return int(release_date[:4])
    return None


def pull_single_playlist(
    db: DatabaseInterface,
    playlist_id: str,
    spotify_config: Dict[str, Any],
    matching_config: Dict[str, Any],
    force_auth: bool = False
) -> SinglePlaylistResult:
    """Pull a single playlist from Spotify.
    
    Args:
        db: Database instance
        playlist_id: Spotify playlist ID to pull
        spotify_config: Spotify OAuth configuration
        matching_config: Matching configuration (for use_year)
        force_auth: Force full authentication flow
        verbose: Enable verbose logging
        
    Returns:
        SinglePlaylistResult with statistics
    """
    result = SinglePlaylistResult()
    result.playlist_id = playlist_id
    start = time.time()
    
    # Build auth and get token
    auth = SpotifyAuth(
        client_id=spotify_config['client_id'],
        redirect_scheme=spotify_config.get('redirect_scheme', 'http'),
        redirect_host=spotify_config.get('redirect_host', '127.0.0.1'),
        redirect_port=spotify_config.get('redirect_port', 9876),
        redirect_path=spotify_config.get('redirect_path', '/callback'),
        scope=spotify_config.get('scope', 'user-library-read playlist-read-private'),
        cache_file=spotify_config.get('cache_file', 'tokens.json'),
        cert_file=spotify_config.get('cert_file', 'cert.pem'),
        key_file=spotify_config.get('key_file', 'key.pem'),
    )
    
    tok_dict = auth.get_token(force=force_auth)
    if not isinstance(tok_dict, dict) or 'access_token' not in tok_dict:
        raise RuntimeError('Failed to obtain access token')
    
    # Build client
    client = SpotifyClient(tok_dict['access_token'])
    use_year = matching_config.get('use_year', False)
    
    # Fetch playlist metadata
    pl_data = client._get(f'/playlists/{playlist_id}')
    pl_name = pl_data.get('name', 'Unknown')
    snapshot_id = pl_data.get('snapshot_id')
    owner = pl_data.get('owner', {})
    owner_id = owner.get('id')
    owner_name = owner.get('display_name')
    
    result.playlist_name = pl_name
    
    logger.debug(f"[playlist] Pulling '{pl_name}' ({playlist_id})")
    
    # Fetch tracks
    tracks = client.playlist_items(playlist_id)
    simplified = []
    
    for idx, item in enumerate(tracks):
        track = item.get('track') or {}
        if not track:
            continue
        t_id = track.get('id')
        if not t_id:
            continue
        
        artist_names = ', '.join(a['name'] for a in track.get('artists', []) if a.get('name'))
        nt, na, combo = normalize_title_artist(track.get('name') or '', artist_names)
        year = _extract_year(((track.get('album') or {}).get('release_date')))
        
        if use_year and year:
            combo = f"{combo} {year}"
        
        simplified.append((idx, t_id, item.get('added_at')))
        db.upsert_track({
            'id': t_id,
            'name': track.get('name'),
            'album': (track.get('album') or {}).get('name'),
            'artist': artist_names,
            'isrc': ((track.get('external_ids') or {}).get('isrc')),
            'duration_ms': track.get('duration_ms'),
            'normalized': combo,
            'year': year,
        })
    
    # Update playlist and tracks
    db.upsert_playlist(playlist_id, pl_name, snapshot_id, owner_id, owner_name)
    db.replace_playlist_tracks(playlist_id, simplified)
    db.commit()
    
    result.tracks_processed = len(simplified)
    result.duration_seconds = time.time() - start
    
    logger.debug(f"[playlist] Pulled {result.tracks_processed} tracks in {result.duration_seconds:.2f}s")
    
    return result


def match_single_playlist(
    db: DatabaseInterface,
    playlist_id: str,
    config: Dict[str, Any]
) -> SinglePlaylistResult:
    """Match tracks from a single playlist against local library.
    
    Args:
        db: Database instance
        playlist_id: Spotify playlist ID to match
        config: Full configuration (for matching settings)
        verbose: Enable verbose logging
        
    Returns:
        SinglePlaylistResult with match statistics
    """
    result = SinglePlaylistResult()
    result.playlist_id = playlist_id
    start = time.time()
    
    # Get playlist metadata
    pl = db.get_playlist_by_id(playlist_id)
    if not pl:
        raise ValueError(f"Playlist {playlist_id} not found in database")
    
    result.playlist_name = pl['name']
    
    logger.debug(f"[playlist] Matching '{result.playlist_name}' ({playlist_id})")
    
    # Get matching config
    fuzzy_threshold = config.get('matching', {}).get('fuzzy_threshold', 0.78)
    
    # Get tracks for this playlist only
    cur = db.conn.execute(
        """
        SELECT t.id, t.name, t.artist, t.album, t.normalized, t.duration_ms, t.year
        FROM playlist_tracks pt
        JOIN tracks t ON t.id = pt.track_id
        WHERE pt.playlist_id = ?
        ORDER BY t.id
        """,
        (playlist_id,)
    )
    tracks_list = [dict(row) for row in cur.fetchall()]
    
    # Get all library files
    files_cur = db.conn.execute(
        "SELECT id as file_id, path, title, artist, album, normalized, duration, year FROM library_files"
    )
    files_list = [dict(row) for row in files_cur.fetchall()]
    
    # Run matching
    matches = match_tracks(tracks_list, files_list, fuzzy_threshold=fuzzy_threshold)
    
    # Store matches
    matched_count = 0
    for track_id, file_id, score, method in matches:
        db.add_match(track_id=track_id, file_id=file_id, score=score, method=method)
        matched_count += 1
    
    db.commit()
    
    result.tracks_processed = len(tracks_list)
    result.tracks_matched = matched_count
    result.duration_seconds = time.time() - start
    
    logger.debug(f"[playlist] Matched {matched_count}/{len(tracks_list)} tracks in {result.duration_seconds:.2f}s")
    
    return result


def export_single_playlist(
    db: DatabaseInterface,
    playlist_id: str,
    export_config: Dict[str, Any],
    organize_by_owner: bool = False,
    current_user_id: str | None = None
) -> SinglePlaylistResult:
    """Export a single playlist to M3U file.
    
    Args:
        db: Database instance
        playlist_id: Spotify playlist ID to export
        export_config: Export configuration (mode, directory, placeholder_extension)
        organize_by_owner: Organize playlists by owner
        current_user_id: Current user ID (for owner organization)
        verbose: Enable verbose logging
        
    Returns:
        SinglePlaylistResult with export path
    """
    result = SinglePlaylistResult()
    result.playlist_id = playlist_id
    start = time.time()
    
    # Get playlist metadata
    pl = db.get_playlist_by_id(playlist_id)
    if not pl:
        raise ValueError(f"Playlist {playlist_id} not found in database")
    
    result.playlist_name = pl['name']
    
    logger.debug(f"[playlist] Exporting '{result.playlist_name}' ({playlist_id})")
    
    # Extract config
    export_dir = Path(export_config['directory'])
    mode = export_config.get('mode', 'strict')
    placeholder_ext = export_config.get('placeholder_extension', '.missing')
    
    # Get current user ID from metadata if not provided
    if organize_by_owner and current_user_id is None:
        current_user_id = db.get_meta('current_user_id')
    
    # Determine target directory
    owner_id = pl['owner_id'] if 'owner_id' in pl.keys() else None
    owner_name = pl['owner_name'] if 'owner_name' in pl.keys() else None
    
    if organize_by_owner:
        if owner_id and owner_id == current_user_id:
            target_dir = export_dir / 'my_playlists'
        elif owner_name:
            folder_name = sanitize_filename(owner_name)
            target_dir = export_dir / folder_name
        else:
            target_dir = export_dir / 'other'
    else:
        target_dir = export_dir
    
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
        (playlist_id,),
    ).fetchall()
    
    tracks = [dict(r) | {'position': r['position']} for r in track_rows]
    playlist_meta = {'name': pl['name'], 'id': playlist_id}
    
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
    
    result.exported_file = str(target_dir / f"{pl['name']}.m3u")
    result.tracks_processed = len(tracks)
    result.duration_seconds = time.time() - start
    
    logger.debug(f"[playlist] Exported to {result.exported_file} in {result.duration_seconds:.2f}s")
    
    return result


def build_single_playlist(
    db: DatabaseInterface,
    playlist_id: str,
    spotify_config: Dict[str, Any],
    config: Dict[str, Any],
    force_auth: bool = False
) -> SinglePlaylistResult:
    """Build local artifacts for a single playlist (pull + match + export).
    
    Args:
        db: Database instance
    playlist_id: Spotify playlist ID to build
        spotify_config: Spotify OAuth configuration
        config: Full configuration
        force_auth: Force full authentication flow
        verbose: Enable verbose logging
        
    Returns:
        SinglePlaylistResult with combined statistics
    """
    result = SinglePlaylistResult()
    result.playlist_id = playlist_id
    start = time.time()
    
    # Pull
    pull_result = pull_single_playlist(db, playlist_id, spotify_config, config['matching'], force_auth)
    result.playlist_name = pull_result.playlist_name
    result.tracks_processed = pull_result.tracks_processed
    
    # Match
    match_result = match_single_playlist(db, playlist_id, config)
    result.tracks_matched = match_result.tracks_matched
    
    # Export
    organize_by_owner = config['export'].get('organize_by_owner', False)
    current_user_id = db.get_meta('current_user_id') if organize_by_owner else None
    export_result = export_single_playlist(db, playlist_id, config['export'], organize_by_owner, current_user_id)
    result.exported_file = export_result.exported_file
    
    result.duration_seconds = time.time() - start
    
    logger.debug(f"[playlist] Build complete for '{result.playlist_name}' in {result.duration_seconds:.2f}s")
    
    return result


__all__ = [
    "SinglePlaylistResult",
    "pull_single_playlist",
    "match_single_playlist",
    "export_single_playlist",
    "build_single_playlist",
]
