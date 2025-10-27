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

from ..providers import get_provider_instance
from ..providers.spotify import extract_year
from ..db import DatabaseInterface
from ..utils.normalization import normalize_title_artist
from ..match.matching_engine import MatchingEngine
from ..export.playlists import export_strict, export_mirrored, export_placeholders
from .export_service import _resolve_export_dir

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


def pull_single_playlist(
    db: DatabaseInterface,
    playlist_id: str,
    spotify_config: Dict[str, Any],
    matching_config: Dict[str, Any],
    force_auth: bool = False,
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

    # Get provider instance (currently hard-coded to Spotify)
    provider = get_provider_instance("spotify")

    # Validate configuration
    provider.validate_config(spotify_config)

    # Build auth and get token
    auth = provider.create_auth(spotify_config)

    # In test mode we avoid invoking the real auth flow entirely (no browser / network)
    # Tests should use MockDatabase and mock the service layer, not call real Spotify services
    tok_dict = auth.get_token(force=force_auth)
    if not isinstance(tok_dict, dict) or "access_token" not in tok_dict:
        raise RuntimeError("Failed to obtain access token")

    client = provider.create_client(tok_dict["access_token"])
    use_year = matching_config.get("use_year", False)

    # Fetch playlist metadata
    pl_data = client._get(f"/playlists/{playlist_id}")
    pl_name = pl_data.get("name", "Unknown")
    snapshot_id = pl_data.get("snapshot_id")
    owner = pl_data.get("owner", {})
    owner_id = owner.get("id")
    owner_name = owner.get("display_name")

    result.playlist_name = pl_name

    logger.debug(f"[playlist] Pulling '{pl_name}' ({playlist_id})")

    # Fetch tracks
    tracks = client.playlist_items(playlist_id)
    simplified = []

    for idx, item in enumerate(tracks):
        track = item.get("track") or {}
        if not track:
            continue
        t_id = track.get("id")
        if not t_id:
            continue

        artist_names = ", ".join(a["name"] for a in track.get("artists", []) if a.get("name"))
        nt, na, combo = normalize_title_artist(track.get("name") or "", artist_names)
        year = extract_year(((track.get("album") or {}).get("release_date")))

        if use_year and year:
            combo = f"{combo} {year}"

        simplified.append((idx, t_id, item.get("added_at")))
        db.upsert_track(
            {
                "id": t_id,
                "name": track.get("name"),
                "album": (track.get("album") or {}).get("name"),
                "artist": artist_names,
                "isrc": ((track.get("external_ids") or {}).get("isrc")),
                "duration_ms": track.get("duration_ms"),
                "normalized": combo,
                "year": year,
            },
            provider="spotify",
        )

    # Update playlist and tracks
    db.upsert_playlist(playlist_id, pl_name, snapshot_id, owner_id, owner_name, provider="spotify")
    db.replace_playlist_tracks(playlist_id, simplified, provider="spotify")
    db.commit()

    result.tracks_processed = len(simplified)
    result.duration_seconds = time.time() - start

    logger.debug(f"[playlist] Pulled {result.tracks_processed} tracks in {result.duration_seconds:.2f}s")

    return result


def match_single_playlist(db: DatabaseInterface, playlist_id: str, config: Dict[str, Any]) -> SinglePlaylistResult:
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
    pl = db.get_playlist_by_id(playlist_id, provider="spotify")
    if not pl:
        raise ValueError(f"Playlist {playlist_id} not found in database")

    result.playlist_name = pl.name

    logger.debug(f"[playlist] Matching '{result.playlist_name}' ({playlist_id})")

    # Get track IDs for this specific playlist only
    provider = config.get("provider", "spotify")
    playlist_track_rows = db.get_playlist_tracks_with_local_paths(playlist_id, provider)
    playlist_track_ids = [row["track_id"] for row in playlist_track_rows if row.get("track_id")]

    logger.info(f"Matching {len(playlist_track_ids)} tracks from playlist '{result.playlist_name}'")

    # Get matching config
    fuzzy_threshold = config.get("matching", {}).get("fuzzy_threshold", 0.78)
    duration_tolerance = config.get("matching", {}).get("duration_tolerance", 5.0)

    # Run matching using MatchingEngine for only this playlist's tracks
    from ..config_types import MatchingConfig
    from psm.config import _DEFAULTS

    matching_config_dict = {
        "fuzzy_threshold": fuzzy_threshold,
        "duration_tolerance": duration_tolerance,
    }
    matching_cfg = MatchingConfig(**{**_DEFAULTS.get("matching", {}), **matching_config_dict})

    engine = MatchingEngine(db, matching_cfg, provider=provider)  # type: ignore
    new_matches = engine.match_tracks(track_ids=playlist_track_ids)  # Match only this playlist's tracks

    db.commit()

    # Count how many tracks from this playlist are now matched
    matched_count = 0
    for track_id in playlist_track_ids:
        if db.get_match_for_track(track_id, provider=provider):
            matched_count += 1

    result.tracks_processed = len(playlist_track_ids)
    result.tracks_matched = matched_count
    result.duration_seconds = time.time() - start

    logger.debug(
        f"[playlist] Found {new_matches} match(es) ({matched_count}/{len(playlist_track_ids)} total) in {result.duration_seconds:.2f}s"
    )

    return result


def export_single_playlist(
    db: DatabaseInterface,
    playlist_id: str,
    export_config: Dict[str, Any],
    organize_by_owner: bool = False,
    current_user_id: str | None = None,
    library_paths: list[str] | None = None,
    provider: str = "spotify",
) -> SinglePlaylistResult:
    """Export a single playlist to M3U file.

    Args:
        db: Database instance
        playlist_id: Spotify playlist ID to export
        export_config: Export configuration (mode, directory, placeholder_extension, path_format, use_library_roots)
        organize_by_owner: Organize playlists by owner
        current_user_id: Current user ID (for owner organization)
        library_paths: Library root paths from config (for path reconstruction)
        provider: Provider name (default: 'spotify')

    Returns:
        SinglePlaylistResult with export path
    """
    result = SinglePlaylistResult()
    result.playlist_id = playlist_id
    start = time.time()

    # Get playlist metadata
    pl = db.get_playlist_by_id(playlist_id, provider=provider)
    if not pl:
        raise ValueError(f"Playlist {playlist_id} not found in database")

    result.playlist_name = pl.name

    logger.debug(f"[playlist] Exporting '{result.playlist_name}' ({playlist_id})")

    # Extract config
    export_dir = Path(export_config["directory"])
    mode = export_config.get("mode", "strict")
    placeholder_ext = export_config.get("placeholder_extension", ".missing")
    path_format = export_config.get("path_format", "absolute")
    use_library_roots = export_config.get("use_library_roots", True)

    # Prepare library roots for path reconstruction (if enabled)
    library_roots_param = library_paths if (use_library_roots and library_paths) else None

    # Get current user ID from metadata if not provided
    if organize_by_owner and current_user_id is None:
        current_user_id = db.get_meta("current_user_id")

    # Determine target directory using consistent resolution logic
    target_dir = _resolve_export_dir(export_dir, organize_by_owner, pl.owner_id, pl.owner_name, current_user_id)

    # Fetch tracks with local paths using repository method (provider-aware, best match only)
    track_rows = db.get_playlist_tracks_with_local_paths(playlist_id, provider)
    tracks = [dict(r) | {"position": r["position"]} for r in track_rows]
    playlist_meta = {"name": pl.name, "id": playlist_id}

    # Dispatch to export function based on mode (with path format and library roots)
    if mode == "strict":
        actual_path = export_strict(playlist_meta, tracks, target_dir, path_format, library_roots_param)
    elif mode == "mirrored":
        actual_path = export_mirrored(playlist_meta, tracks, target_dir, path_format, library_roots_param)
    elif mode == "placeholders":
        actual_path = export_placeholders(
            playlist_meta, tracks, target_dir, placeholder_ext, path_format, library_roots_param
        )
    else:
        logger.warning(f"Unknown export mode '{mode}', defaulting to strict")
        actual_path = export_strict(playlist_meta, tracks, target_dir, path_format, library_roots_param)

    result.exported_file = str(actual_path)
    result.tracks_processed = len(tracks)
    result.duration_seconds = time.time() - start

    logger.debug(f"[playlist] Exported to {result.exported_file} in {result.duration_seconds:.2f}s")

    return result


def build_single_playlist(
    db: DatabaseInterface,
    playlist_id: str,
    spotify_config: Dict[str, Any],
    config: Dict[str, Any],
    force_auth: bool = False,
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
    pull_result = pull_single_playlist(db, playlist_id, spotify_config, config["matching"], force_auth)
    result.playlist_name = pull_result.playlist_name
    result.tracks_processed = pull_result.tracks_processed

    # Match
    match_result = match_single_playlist(db, playlist_id, config)
    result.tracks_matched = match_result.tracks_matched

    # Export
    provider = config.get("provider", "spotify")
    organize_by_owner = config["export"].get("organize_by_owner", False)
    current_user_id = db.get_meta("current_user_id") if organize_by_owner else None
    library_paths = config.get("library", {}).get("paths", [])
    export_result = export_single_playlist(
        db, playlist_id, config["export"], organize_by_owner, current_user_id, library_paths, provider
    )
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
