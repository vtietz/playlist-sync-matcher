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
    top_unmatched_albums: int = 10
) -> MatchResult:
    """Run matching engine and generate diagnostics.
    
    Args:
        db: Database instance
        config: Full configuration dict
        verbose: Enable verbose logging
        top_unmatched_tracks: Number of top unmatched tracks to show (INFO mode)
        top_unmatched_albums: Number of top unmatched albums to show (INFO mode)
        
    Returns:
        MatchResult with statistics and unmatched diagnostics
    """
    result = MatchResult()
    start = time.time()
    
    # Log operation header
    logger.info("=== Matching tracks to library files ===")
    
    # Use matching engine
    engine = MatchingEngine(db, config)
    matched_count = engine.match_all()
    
    # Gather statistics
    result.library_files = db.count_library_files()
    
    # Count unique albums in library using repository method
    result.library_albums = db.count_distinct_library_albums()
    
    result.spotify_tracks = db.count_tracks()
    result.matched = matched_count
    result.unmatched = result.library_files - result.matched
    
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
    
    return result


def _normalize_file_dict(raw_row: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize library file row to match scoring engine expectations.
    
    The scoring engine expects 'name' field while library stores 'title'.
    This adapter function harmonizes the field names and ensures all
    required keys exist with appropriate defaults.
    """
    return {
        'id': raw_row['id'],
        'path': raw_row.get('path', ''),
        'title': raw_row.get('title') or raw_row.get('name') or '',
        'name': raw_row.get('title') or raw_row.get('name') or '',  # Scoring expects 'name'
        'artist': raw_row.get('artist') or '',
        'album': raw_row.get('album'),
        'year': raw_row.get('year'),
        'duration': raw_row.get('duration'),
        'normalized': raw_row.get('normalized') or '',
        'isrc': raw_row.get('isrc'),
    }


def _duration_prefilter_single(track: Dict[str, Any], files: List[Dict[str, Any]], dur_tol: float) -> List[Dict[str, Any]]:
    """Return candidate files passing relaxed duration tolerance for a single track.

    We intentionally allow a minimum ±4s window or (dur_tol * 2) to avoid
    over-pruning when metadata rounding causes off-by-seconds inconsistencies.
    If a library file lacks duration metadata it is retained (can't exclude).
    """
    if track.get('duration_ms') is None:
        return files
    target_sec = track['duration_ms'] / 1000.0
    window = max(4, dur_tol * 2)
    return [f for f in files if f.get('duration') is None or abs(f.get('duration') - target_sec) <= window]


def build_duration_candidate_map(tracks: List[Dict[str, Any]], files: List[Dict[str, Any]], dur_tol: float) -> Dict[str, List[int]]:
    """Utility exposed for tests replacing legacy DurationFilterStrategy.

    Returns mapping track_id -> list of file ids passing duration filter.
    """
    result: Dict[str, List[int]] = {}
    for t in tracks:
        candidates = _duration_prefilter_single(t, files, dur_tol)
        result[t['id']] = [c['id'] for c in candidates]
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
    # Delegate to matching engine
    engine = MatchingEngine(db, config)
    return engine.match_tracks(track_ids=track_ids)


def match_changed_files(
    db: Database,
    config: Dict[str, Any],
    file_ids: List[int] | None = None
) -> int:
    """Incrementally match only changed/new files against all tracks.
    
    This is much more efficient than run_matching() for watch mode scenarios
    where only a few files changed. Instead of re-matching all files against
    all tracks, we only match the changed files.
    
    Args:
        db: Database instance
        config: Full configuration dict
        file_ids: List of specific file IDs to match (if None, matches all unmatched files)
        
    Returns:
        Number of new matches created
    """
    # Delegate to matching engine
    engine = MatchingEngine(db, config)
    return engine.match_files(file_ids=file_ids)
