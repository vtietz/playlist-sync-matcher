"""Match service: Orchestrate library-to-Spotify matching.

This service handles the matching engine, progress tracking,
and diagnostic reporting for unmatched tracks.
"""

from __future__ import annotations
import time
import logging
from typing import Dict, Any, List

from ..match.matching_engine import MatchingEngine
from ..db import Database
from ..config_types import MatchingConfig

logger = logging.getLogger(__name__)


class MatchResult:
    """Results from a match operation."""

    def __init__(self):
        self.library_files = 0
        self.library_albums = 0
        self.library_tracks = 0
        self.spotify_tracks = 0
        self.matched = 0
        self.unmatched = 0
        self.unmatched_list: List[Dict[str, Any]] = []
        self.duration_seconds = 0.0


def run_matching(
    db: Database,
    config: Dict[str, Any],
    verbose: bool = False,
    top_unmatched_tracks: int = 20,
    top_unmatched_albums: int = 10,
    force_full: bool = False
) -> MatchResult:
    """Run matching engine and generate diagnostics.

    Args:
        db: Database instance
        config: Full configuration dict
        verbose: Enable verbose logging
        top_unmatched_tracks: Number of top unmatched tracks to show (INFO mode)
        top_unmatched_albums: Number of top unmatched albums to show (INFO mode)
        force_full: If True, re-match all tracks; if False (default), skip already-matched tracks

    Returns:
        MatchResult with statistics and unmatched diagnostics
    """
    result = MatchResult()
    start = time.time()

    # Convert dict config to typed MatchingConfig
    matching_dict = config.get('matching', {})
    matching_config = MatchingConfig(
        duration_tolerance=matching_dict.get('duration_tolerance', 2.0),
        max_candidates_per_track=int(matching_dict.get('max_candidates_per_track', 500)),
        fuzzy_threshold=matching_dict.get('fuzzy_threshold', 0.85)
    )
    provider = config.get('provider', 'spotify')

    # Get logging configuration
    logging_dict = config.get('logging', {})
    progress_enabled = logging_dict.get('progress_enabled', True)
    progress_interval = logging_dict.get('progress_interval', 100)

    # Use matching engine with logging config
    engine = MatchingEngine(
        db,
        matching_config,
        provider=provider,
        progress_enabled=progress_enabled,
        progress_interval=progress_interval
    )

    if force_full:
        # Full re-match: delete all existing matches and re-run from scratch
        logger.info("Forcing full re-match (deleting existing matches)...")
        db.delete_all_matches()
        db.commit()
        matched_count = engine.match_all()
    else:
        # Smart incremental: only match tracks that don't have matches yet
        logger.info("Smart matching (skipping already-matched tracks)...")
        matched_count = engine.match_tracks(track_ids=None)  # None = match all unmatched

    # Gather statistics
    result.library_files = db.count_library_files()

    # Count unique albums in library using repository method
    result.library_albums = db.count_distinct_library_albums()

    result.spotify_tracks = db.count_tracks()
    result.matched = matched_count
    result.unmatched = result.spotify_tracks - result.matched

    # Gather unmatched diagnostics using repository method
    if result.unmatched > 0:
        unmatched_files = db.get_unmatched_library_files()
        result.unmatched_list = [
            {'artist': f.artist, 'album': f.album, 'title': f.title}
            for f in unmatched_files
        ]

    result.duration_seconds = time.time() - start

    # Show unmatched diagnostics (INFO mode) - moved from DEBUG
    _show_unmatched_diagnostics(db, top_unmatched_tracks, top_unmatched_albums)

    # Set write signal for GUI auto-refresh
    db.set_meta('last_write_epoch', str(time.time()))
    db.set_meta('last_write_source', 'match')
    logger.debug("Write signal updated: match operation completed")

    return result


def _show_unmatched_diagnostics(db: Database, top_tracks: int = 20, top_albums: int = 10):
    """Show unmatched track and album diagnostics in INFO mode.

    This was previously only available in DEBUG mode. Now shown automatically
    after matching to help users identify what's missing in their library.

    Args:
        db: Database instance
        top_tracks: Number of top unmatched tracks to show
        top_albums: Number of top unmatched albums to show
    """
    # Get all unmatched tracks using repository method
    unmatched_tracks = db.get_unmatched_tracks(provider='spotify')

    if not unmatched_tracks:
        logger.info("")
        logger.info("✓ All tracks matched!")
        return

    unmatched_ids = [t.id for t in unmatched_tracks]
    track_by_id = {t.id: t for t in unmatched_tracks}

    logger.info("")
    logger.info("=== Unmatched Diagnostics ===")
    logger.info(f"Total unmatched: {len(unmatched_ids)} tracks")

    # ---------------------------------------------------------------
    # 1. Top Unmatched Tracks (by playlist popularity)
    # ---------------------------------------------------------------
    occurrence_counts = {}  # Initialize here so it's available for albums section

    if top_tracks > 0:
        # Get playlist occurrence counts using repository method
        if unmatched_ids:
            occurrence_counts = db.get_playlist_occurrence_counts(unmatched_ids)

        # Check liked tracks using repository method
        liked_ids = set()
        if unmatched_ids:
            liked_ids = set(db.get_liked_track_ids(unmatched_ids, provider='spotify'))

        # Sort by popularity
        sorted_unmatched = sorted(
            unmatched_ids,
            key=lambda tid: (
                -occurrence_counts.get(tid, 0),
                (track_by_id[tid].artist or '').lower() if tid in track_by_id else '',
                (track_by_id[tid].name or '').lower() if tid in track_by_id else ''
            )
        )

        display_count = min(top_tracks, len(sorted_unmatched))

        logger.info("")
        logger.info("[Top Unmatched Tracks] (by playlist popularity):")

        for track_id in sorted_unmatched[:display_count]:
            track = track_by_id.get(track_id)
            if not track:
                continue
            count = occurrence_counts.get(track_id, 0)
            is_liked = track_id in liked_ids
            liked_marker = " ❤️" if is_liked else ""

            logger.info(
                f"  [{count:2d} playlist{'s' if count != 1 else ' '}] "
                f"{track.artist or ''} - {track.name or ''}{liked_marker}"
            )

        if len(sorted_unmatched) > display_count:
            logger.info(f"  ... and {len(sorted_unmatched) - display_count} more")

    # ---------------------------------------------------------------
    # 2. Top Unmatched Albums (grouped by album)
    # ---------------------------------------------------------------
    if top_albums > 0:
        album_stats = {}  # album_key -> {'artist': ..., 'album': ..., 'track_count': ..., 'total_occurrences': ...}

        for track_id in unmatched_ids:
            track = track_by_id.get(track_id)
            if not track:
                continue
            artist = track.artist or ''
            album = track.album or ''

            if not album or album == '':
                continue  # Skip tracks without album info

            # Use artist + album as key (case-insensitive)
            album_key = f"{artist.lower()}|{album.lower()}"

            if album_key not in album_stats:
                album_stats[album_key] = {
                    'artist': artist,
                    'album': album,
                    'track_count': 0,
                    'total_occurrences': 0,
                }

            album_stats[album_key]['track_count'] += 1
            album_stats[album_key]['total_occurrences'] += occurrence_counts.get(track_id, 0)

        # Sort albums by total occurrences (descending), then by track count
        sorted_albums = sorted(
            album_stats.items(),
            key=lambda item: (-item[1]['total_occurrences'], -item[1]['track_count'], item[1]['artist'].lower())
        )

        if sorted_albums:
            display_album_count = min(top_albums, len(sorted_albums))

            logger.info("")
            logger.info("[Top Missing Albums] (by playlist popularity):")

            for _, album_info in sorted_albums[:display_album_count]:
                artist = album_info['artist']
                album = album_info['album']
                track_count = album_info['track_count']
                total_occ = album_info['total_occurrences']

                logger.info(
                    f"  [{total_occ:2d} occurrences] {artist} - {album} "
                    f"({track_count} track{'s' if track_count != 1 else ''})"
                )

            if len(sorted_albums) > display_album_count:
                logger.info(f"  ... and {len(sorted_albums) - display_album_count} more albums")


def match_changed_tracks(
    db: Database,
    config: Dict[str, Any],
    track_ids: List[str] | None = None
) -> int:
    """Incrementally match all files against only changed/new tracks.

    This is the inverse of match_changed_files: instead of matching a few changed
    files against all tracks, we match all files against a few changed tracks.

    Use case: After 'pull' command adds/updates tracks in database.

    Args:
        db: Database instance
        config: Full configuration dict
        track_ids: List of specific track IDs to match (if None, matches all unmatched tracks)

    Returns:
        Number of new matches created
    """
    # Convert dict config to typed MatchingConfig
    matching_dict = config.get('matching', {})
    matching_config = MatchingConfig(
        duration_tolerance=matching_dict.get('duration_tolerance', 2.0),
        max_candidates_per_track=int(matching_dict.get('max_candidates_per_track', 500)),
        fuzzy_threshold=matching_dict.get('fuzzy_threshold', 0.85)
    )
    provider = config.get('provider', 'spotify')

    # Delegate to matching engine
    engine = MatchingEngine(db, matching_config, provider=provider)
    return engine.match_tracks(track_ids=track_ids)


def match_changed_files(
    db: Database,
    config: Dict[str, Any],
    file_ids: List[int] | None = None
) -> tuple[int, List[str]]:
    """Incrementally match only changed/new files against all tracks.

    This is much more efficient than run_matching() for watch mode scenarios
    where only a few files changed. Instead of re-matching all files against
    all tracks, we only match the changed files.

    Args:
        db: Database instance
        config: Full configuration dict
        file_ids: List of specific file IDs to match (if None, matches all unmatched files)

    Returns:
        Tuple of (match_count, list of matched track IDs)
    """
    # Convert dict config to typed MatchingConfig
    matching_dict = config.get('matching', {})
    matching_config = MatchingConfig(
        duration_tolerance=matching_dict.get('duration_tolerance', 2.0),
        max_candidates_per_track=int(matching_dict.get('max_candidates_per_track', 500)),
        fuzzy_threshold=matching_dict.get('fuzzy_threshold', 0.85)
    )
    provider = config.get('provider', 'spotify')

    # Delegate to matching engine
    engine = MatchingEngine(db, matching_config, provider=provider)
    return engine.match_files(file_ids=file_ids)
