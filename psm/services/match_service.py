"""Match service: Orchestrate library-to-Spotify matching.

This service handles the matching engine, progress tracking,
and diagnostic reporting for unmatched tracks.
"""

from __future__ import annotations
import time
import logging
from typing import Dict, Any, List

from ..match.scoring import ScoringConfig, evaluate_pair, MatchConfidence
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
    verbose: bool = False
) -> MatchResult:
    """Run matching engine and generate diagnostics.
    
    Args:
        db: Database instance
        config: Full configuration dict
        verbose: Enable verbose logging
        
    Returns:
        MatchResult with statistics and unmatched diagnostics
    """
    result = MatchResult()
    start = time.time()
    
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


def _run_scoring_engine(db: Database, config: Dict[str, Any]) -> int:
    """Run scoring-based engine and persist matches (authoritative engine)."""
    start = time.time()
    cur_tracks = db.conn.execute("SELECT id, name, artist, album, year, isrc, duration_ms, normalized FROM tracks")
    tracks = [dict(row) for row in cur_tracks.fetchall()]
    
    cur_files = db.conn.execute("SELECT id, path, title, artist, album, year, duration, normalized FROM library_files")
    files = [_normalize_file_dict(dict(row)) for row in cur_files.fetchall()]

    cfg = ScoringConfig()
    matches = 0

    # Optional simple duration prefilter to reduce candidate set size
    dur_tol = config.get('matching', {}).get('duration_tolerance', 2.0)
    use_duration_filter = dur_tol is not None

    max_candidates = int(config.get('matching', {}).get('max_candidates_per_track', 500))
    for t in tracks:
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
                logger.debug(f"[match][debug] track={t['id']} vs file={local['id']} raw={breakdown.raw_score:.1f} conf={breakdown.confidence} notes={breakdown.notes}")
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

    db.commit()
    dur = time.time() - start
    logger.info(f"[match] Matched {matches}/{len(tracks)} tracks using scoring engine in {dur:.2f}s")
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
