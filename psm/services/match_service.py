"""Match service: Orchestrate library-to-Spotify matching.

This service handles the matching engine, progress tracking,
and diagnostic reporting for unmatched tracks.
"""

from __future__ import annotations
import time
import logging
from typing import Dict, Any, List

from ..match.scoring import ScoringConfig, evaluate_pair, MatchConfidence
from ..match.candidate_selector import CandidateSelector
from ..match.matching_engine import MatchingEngine
from ..db import Database, DatabaseInterface
from ..utils.logging_helpers import log_progress

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
    
    # Count unique albums in library
    cur = db.conn.execute('SELECT COUNT(DISTINCT album) FROM library_files')
    result.library_albums = cur.fetchone()[0]
    
    result.spotify_tracks = db.count_tracks()
    result.matched = matched_count
    result.unmatched = result.library_files - result.matched
    
    # Gather unmatched diagnostics
    if result.unmatched > 0:
        unmatched_cur = db.conn.execute('''
            SELECT artist, album, title
            FROM library_files
            WHERE id NOT IN (SELECT file_id FROM matches)
            ORDER BY artist, album, title
        ''')
        result.unmatched_list = [
            {'artist': row[0], 'album': row[1], 'title': row[2]}
            for row in unmatched_cur.fetchall()
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
    # Get all unmatched track IDs
    unmatched_rows = db.conn.execute("""
        SELECT id, name, artist, album
        FROM tracks
        WHERE id NOT IN (SELECT track_id FROM matches)
    """).fetchall()
    
    if not unmatched_rows:
        logger.info("")
        logger.info("✓ All tracks matched!")
        return
    
    unmatched_ids = [row['id'] for row in unmatched_rows]
    track_by_id = {row['id']: dict(row) for row in unmatched_rows}
    
    logger.info("")
    logger.info("=== Unmatched Diagnostics ===")
    logger.info(f"Total unmatched: {len(unmatched_ids)} tracks")
    
    # ---------------------------------------------------------------
    # 1. Top Unmatched Tracks (by playlist popularity)
    # ---------------------------------------------------------------
    occurrence_counts = {}  # Initialize here so it's available for albums section
    
    if top_tracks > 0:
        # Get playlist occurrence counts
        if unmatched_ids:
            placeholders = ','.join('?' * len(unmatched_ids))
            count_rows = db.conn.execute(
                f"SELECT track_id, COUNT(DISTINCT playlist_id) as count FROM playlist_tracks "
                f"WHERE track_id IN ({placeholders}) GROUP BY track_id",
                unmatched_ids
            ).fetchall()
            occurrence_counts = {row['track_id']: row['count'] for row in count_rows}
            # Fill in zero counts for tracks not in any playlist
            for track_id in unmatched_ids:
                if track_id not in occurrence_counts:
                    occurrence_counts[track_id] = 0
        
        # Check liked tracks
        liked_ids = set()
        if unmatched_ids:
            placeholders = ','.join('?' * len(unmatched_ids))
            liked_rows = db.conn.execute(
                f"SELECT track_id FROM liked_tracks WHERE track_id IN ({placeholders})",
                unmatched_ids
            ).fetchall()
            liked_ids = {row['track_id'] for row in liked_rows}
        
        # Sort by popularity
        sorted_unmatched = sorted(
            unmatched_ids,
            key=lambda tid: (
                -occurrence_counts.get(tid, 0),
                track_by_id.get(tid, {}).get('artist', '').lower(),
                track_by_id.get(tid, {}).get('name', '').lower()
            )
        )
        
        display_count = min(top_tracks, len(sorted_unmatched))
        
        logger.info("")
        logger.info("[Top Unmatched Tracks] (by playlist popularity):")
        
        for track_id in sorted_unmatched[:display_count]:
            track = track_by_id.get(track_id, {})
            count = occurrence_counts.get(track_id, 0)
            is_liked = track_id in liked_ids
            liked_marker = " ❤️" if is_liked else ""
            
            logger.info(
                f"  [{count:2d} playlist{'s' if count != 1 else ' '}] "
                f"{track.get('artist', '')} - {track.get('name', '')}{liked_marker}"
            )
        
        if len(sorted_unmatched) > display_count:
            logger.info(f"  ... and {len(sorted_unmatched) - display_count} more")
    
    # ---------------------------------------------------------------
    # 2. Top Unmatched Albums (grouped by album)
    # ---------------------------------------------------------------
    if top_albums > 0:
        album_stats = {}  # album_key -> {'artist': ..., 'album': ..., 'track_count': ..., 'total_occurrences': ...}
        
        for track_id in unmatched_ids:
            track = track_by_id.get(track_id, {})
            artist = track.get('artist', '')
            album = track.get('album', '')
            
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
    # Get all library files
    cur_files = db.conn.execute("SELECT id, path, title, artist, album, year, duration, normalized FROM library_files")
    all_files = [_normalize_file_dict(dict(row)) for row in cur_files.fetchall()]
    
    if not all_files:
        logger.debug("No library files to match against")
        return 0
    
    # Get tracks to match
    if track_ids:
        # Match specific changed tracks
        if not track_ids:  # Empty list
            return 0
        
        placeholders = ','.join('?' * len(track_ids))
        cur_tracks = db.conn.execute(
            f"SELECT id, name, artist, album, year, isrc, duration_ms, normalized FROM tracks WHERE id IN ({placeholders})",
            track_ids
        )
        tracks_to_match = [dict(row) for row in cur_tracks.fetchall()]
        
        # Delete existing matches for these tracks (they were updated)
        db.conn.execute(f"DELETE FROM matches WHERE track_id IN ({placeholders})", track_ids)
        db.commit()
    else:
        # Match all currently unmatched tracks (fallback)
        cur_tracks = db.conn.execute('''
            SELECT id, name, artist, album, year, isrc, duration_ms, normalized
            FROM tracks
            WHERE id NOT IN (SELECT track_id FROM matches)
        ''')
        tracks_to_match = [dict(row) for row in cur_tracks.fetchall()]
    
    if not tracks_to_match:
        logger.debug("No tracks need matching")
        return 0
    
    logger.info(f"Incrementally matching {len(all_files)} file(s) against {len(tracks_to_match)} changed track(s)...")
    
    # Use the same scoring engine logic as full matching
    cfg = ScoringConfig()
    selector = CandidateSelector()
    dur_tol = config.get('matching', {}).get('duration_tolerance', 2.0)
    max_candidates = int(config.get('matching', {}).get('max_candidates_per_track', 500))
    provider = config.get('provider', 'spotify')
    
    new_matches = 0
    
    # For each changed track, find best file from library
    for track in tracks_to_match:
        # Build candidate subset using CandidateSelector
        candidates = selector.duration_prefilter(track, all_files, dur_tolerance=dur_tol)
        if not candidates:
            candidates = all_files  # Fallback if filter too strict
        
        # Pre-score and cap candidates using token similarity
        candidates = selector.token_prescore(track, candidates, max_candidates=max_candidates)
        
        # Find best match among candidates
        best_file_id = None
        best_breakdown = None
        best_score = -1.0
        
        for file_dict in candidates:
            breakdown = evaluate_pair(track, file_dict, cfg)
            if breakdown.confidence == MatchConfidence.REJECTED:
                continue
            if breakdown.raw_score > best_score:
                best_score = breakdown.raw_score
                best_file_id = file_dict['id']
                best_breakdown = breakdown
            if breakdown.confidence == MatchConfidence.CERTAIN:
                break
        
        if best_breakdown and best_file_id is not None:
            db.add_match(
                track['id'],
                best_file_id,
                best_breakdown.raw_score / 100.0,
                f"score:{best_breakdown.confidence}",
                provider=provider
            )
            new_matches += 1
    
    db.commit()
    logger.info(f"✓ Created {new_matches} new match(es) from {len(tracks_to_match)} changed track(s)")
    return new_matches


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
    # Get all tracks to match against
    cur_tracks = db.conn.execute("SELECT id, name, artist, album, year, isrc, duration_ms, normalized FROM tracks")
    all_tracks = [dict(row) for row in cur_tracks.fetchall()]
    
    if not all_tracks:
        logger.debug("No tracks in database to match against")
        return 0
    
    # Get files to match
    if file_ids:
        # Match specific changed files
        if not file_ids:  # Empty list
            return 0
        
        placeholders = ','.join('?' * len(file_ids))
        cur_files = db.conn.execute(
            f"SELECT id, path, title, artist, album, year, duration, normalized FROM library_files WHERE id IN ({placeholders})",
            file_ids
        )
        files_to_match = [_normalize_file_dict(dict(row)) for row in cur_files.fetchall()]
        
        # Delete existing matches for these files (they were updated)
        db.conn.execute(f"DELETE FROM matches WHERE file_id IN ({placeholders})", file_ids)
        db.commit()
    else:
        # Match all currently unmatched files (fallback)
        cur_files = db.conn.execute('''
            SELECT id, path, title, artist, album, year, duration, normalized
            FROM library_files
            WHERE id NOT IN (SELECT file_id FROM matches)
        ''')
        files_to_match = [_normalize_file_dict(dict(row)) for row in cur_files.fetchall()]
    
    if not files_to_match:
        logger.debug("No files need matching")
        return 0
    
    logger.info(f"Incrementally matching {len(files_to_match)} file(s) against {len(all_tracks)} tracks...")
    
    # Use the same scoring engine logic as full matching
    cfg = ScoringConfig()
    selector = CandidateSelector()
    dur_tol = config.get('matching', {}).get('duration_tolerance', 2.0)
    max_candidates = int(config.get('matching', {}).get('max_candidates_per_track', 500))
    provider = config.get('provider', 'spotify')
    
    new_matches = 0
    
    # For each track, find best file from our changed file list
    for track in all_tracks:
        # Build candidate subset using CandidateSelector
        candidates = selector.duration_prefilter(track, files_to_match, dur_tolerance=dur_tol)
        if not candidates:
            candidates = files_to_match  # Fallback if filter too strict
        
        # Pre-score and cap candidates using token similarity
        candidates = selector.token_prescore(track, candidates, max_candidates=max_candidates)
        
        # Find best match among candidates
        best_file_id = None
        best_breakdown = None
        best_score = -1.0
        
        for file_dict in candidates:
            breakdown = evaluate_pair(track, file_dict, cfg)
            if breakdown.confidence == MatchConfidence.REJECTED:
                continue
            if breakdown.raw_score > best_score:
                best_score = breakdown.raw_score
                best_file_id = file_dict['id']
                best_breakdown = breakdown
            if breakdown.confidence == MatchConfidence.CERTAIN:
                break
        
        if best_breakdown and best_file_id is not None:
            db.add_match(
                track['id'],
                best_file_id,
                best_breakdown.raw_score / 100.0,
                f"score:{best_breakdown.confidence}",
                provider=provider
            )
            new_matches += 1
    
    db.commit()
    logger.info(f"✓ Created {new_matches} new match(es) from {len(files_to_match)} changed file(s)")
    return new_matches
