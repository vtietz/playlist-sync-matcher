"""Match service: Orchestrate library-to-Spotify matching.

This service handles the matching engine, progress tracking,
and diagnostic reporting for unmatched tracks.
"""

from __future__ import annotations
import time
import logging
from typing import Dict, Any, List

import click

from ..match.scoring import ScoringConfig, evaluate_pair, MatchConfidence
from ..db import Database
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
    
    # Print operation header
    print(click.style("=== Matching tracks to library files ===", fg='cyan', bold=True))
    
    # Always use scoring engine (legacy strategy pipeline removed)
    matched_count = _run_scoring_engine(db, config)
    
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


def _jaccard_similarity(set1: set, set2: set) -> float:
    """Calculate Jaccard similarity between two sets.
    
    Returns intersection / union ratio (0.0 to 1.0).
    Used for fast candidate pre-scoring before full fuzzy matching.
    """
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0


def _get_confidence_summary(db: Database, total_matches: int) -> str:
    """Get a summary of match confidence distribution.
    
    Returns a colored string showing counts for each confidence tier.
    """
    if total_matches == 0:
        return "none"
    
    # Query match methods to extract confidence levels
    rows = db.conn.execute(
        "SELECT method FROM matches WHERE method LIKE 'score:%'"
    ).fetchall()
    
    # Count by confidence tier
    certain = sum(1 for r in rows if 'CERTAIN' in r[0])
    high = sum(1 for r in rows if 'HIGH' in r[0])
    medium = sum(1 for r in rows if 'MEDIUM' in r[0])
    low = sum(1 for r in rows if 'LOW' in r[0])
    
    parts = []
    if certain > 0:
        parts.append(click.style(f'{certain} certain', fg='green'))
    if high > 0:
        parts.append(click.style(f'{high} high', fg='blue'))
    if medium > 0:
        parts.append(click.style(f'{medium} medium', fg='yellow'))
    if low > 0:
        parts.append(click.style(f'{low} low', fg='red'))
    
    return ", ".join(parts) if parts else "none"


def _run_scoring_engine(db: Database, config: Dict[str, Any]) -> int:
    """Run scoring-based engine and persist matches (authoritative engine)."""
    start = time.time()
    cur_tracks = db.conn.execute("SELECT id, name, artist, album, year, isrc, duration_ms, normalized FROM tracks")
    tracks = [dict(row) for row in cur_tracks.fetchall()]
    
    cur_files = db.conn.execute("SELECT id, path, title, artist, album, year, duration, normalized FROM library_files")
    files = [_normalize_file_dict(dict(row)) for row in cur_files.fetchall()]

    cfg = ScoringConfig()
    matches = 0
    processed = 0
    progress_interval = 100  # Log progress every N tracks
    last_progress_log = 0

    # Optional simple duration prefilter to reduce candidate set size
    dur_tol = config.get('matching', {}).get('duration_tolerance', 2.0)
    use_duration_filter = dur_tol is not None

    max_candidates = int(config.get('matching', {}).get('max_candidates_per_track', 500))
    for t in tracks:
        processed += 1
        # Enable detailed logging if DEBUG level is active
        debug_logging = logger.isEnabledFor(logging.DEBUG)
        
        # Build candidate subset (duration prefilter) then cap list length
        if use_duration_filter and t.get('duration_ms') is not None:
            pre = _duration_prefilter_single(t, files, dur_tol)
            if not pre:  # fallback in edge case of overly strict filter
                pre = files
        else:
            pre = files

        if len(pre) > max_candidates:
            # Use Jaccard similarity for fast pre-scoring to prioritize likely matches
            norm_tokens = set((t.get('normalized') or '').split())
            scored_subset = []
            for f in pre:
                fn_tokens = set((f.get('normalized') or '').split())
                similarity = _jaccard_similarity(norm_tokens, fn_tokens)
                scored_subset.append((similarity, f))
            scored_subset.sort(key=lambda x: x[0], reverse=True)
            candidate_list = [f for _, f in scored_subset[:max_candidates]]
        else:
            candidate_list = pre

        # Evaluate candidates directly; early exit on CERTAIN
        best_local_id = None
        best_breakdown = None
        best_score = -1.0
        for local in candidate_list:
            breakdown = evaluate_pair(t, local, cfg)
            if debug_logging:
                logger.debug(f"track={t['id']} vs file={local['id']} raw={breakdown.raw_score:.1f} conf={breakdown.confidence} notes={breakdown.notes}")
            if breakdown.confidence == MatchConfidence.REJECTED:
                continue
            if breakdown.raw_score > best_score:
                best_score = breakdown.raw_score
                best_local_id = local['id']
                best_breakdown = breakdown
            if breakdown.confidence == MatchConfidence.CERTAIN:
                break

        if not best_breakdown or best_local_id is None:
            continue
        db.add_match(t['id'], best_local_id, best_breakdown.raw_score / 100.0, f"score:{best_breakdown.confidence}")
        matches += 1
        
        # Log progress every N tracks
        if processed - last_progress_log >= progress_interval:
            elapsed = time.time() - start
            match_rate = (matches / processed * 100) if processed > 0 else 0
            log_progress(
                processed=processed,
                total=len(tracks),
                new=matches,
                updated=0,
                skipped=processed - matches,
                elapsed_seconds=elapsed,
                item_name="tracks"
            )
            logger.info(f"  Match rate: {click.style(f'{match_rate:.1f}%', fg='cyan')} | Confidence breakdown: {_get_confidence_summary(db, matches)}")
            last_progress_log = processed

    db.commit()
    dur = time.time() - start
    match_rate = (matches / len(tracks) * 100) if tracks else 0
    
    # Get confidence breakdown for final summary
    confidence_summary = _get_confidence_summary(db, matches)
    
    logger.info(
        f"{click.style('✓', fg='green')} Matched "
        f"{click.style(f'{matches}/{len(tracks)}', fg='green')} tracks "
        f"({match_rate:.1f}%) in {dur:.2f}s"
    )
    if matches > 0:
        logger.info(f"  Confidence: {confidence_summary}")
    return matches


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
        logger.info(click.style("✓ All tracks matched!", fg='green', bold=True))
        return
    
    unmatched_ids = [row['id'] for row in unmatched_rows]
    track_by_id = {row['id']: dict(row) for row in unmatched_rows}
    
    logger.info("")
    logger.info(click.style("=== Unmatched Diagnostics ===", fg='yellow', bold=True))
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
        logger.info(f"{click.style('[Top Unmatched Tracks]', fg='red')} (by playlist popularity):")
        
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
            logger.info(f"{click.style('[Top Missing Albums]', fg='red')} (by playlist popularity):")
            
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
