"""Matching engine for track-to-file matching.

This module provides the core matching engine that coordinates candidate
selection, fuzzy matching, and result persistence. It consolidates the
matching logic that was previously duplicated across multiple functions.
"""

from __future__ import annotations
import time
import logging
from typing import Dict, Any, List

from .scoring import ScoringConfig, evaluate_pair, MatchConfidence
from .candidate_selector import CandidateSelector
from ..db import Database

logger = logging.getLogger(__name__)


class MatchingEngine:
    """Core matching engine for track-to-file matching.
    
    This class orchestrates the matching process:
    1. Fetches tracks and files from database
    2. Selects candidates using CandidateSelector (duration + token filtering)
    3. Evaluates pairs using the scoring engine
    4. Persists matches to database
    5. Tracks progress and confidence distribution
    
    Example usage:
        engine = MatchingEngine(db, config)
        matches_count = engine.match_all()
    """
    
    def __init__(self, db: Database, config: Dict[str, Any]):
        """Initialize the matching engine.
        
        Args:
            db: Database instance
            config: Full configuration dict with 'matching' section
        """
        self.db = db
        self.config = config
        self.selector = CandidateSelector()
        self.scoring_config = ScoringConfig()
        
        # Extract matching configuration
        matching_cfg = config.get('matching', {})
        self.dur_tolerance = matching_cfg.get('duration_tolerance', 2.0)
        self.max_candidates = int(matching_cfg.get('max_candidates_per_track', 500))
        self.progress_interval = 100  # Log progress every N tracks
        self.provider = config.get('provider', 'spotify')
    
    def match_all(self) -> int:
        """Match all tracks against all library files.
        
        This performs a full matching run, evaluating all tracks in the database
        against all library files. Progress is logged periodically and results
        are committed to the database.
        
        Returns:
            Number of matches created
        """
        start = time.time()
        
        # Fetch all tracks and files
        cur_tracks = self.db.conn.execute(
            "SELECT id, name, artist, album, year, isrc, duration_ms, normalized FROM tracks"
        )
        tracks = [dict(row) for row in cur_tracks.fetchall()]
        
        cur_files = self.db.conn.execute(
            "SELECT id, path, title, artist, album, year, duration, normalized FROM library_files"
        )
        files = [self._normalize_file_dict(dict(row)) for row in cur_files.fetchall()]
        
        if not tracks or not files:
            logger.debug("No tracks or files to match")
            return 0
        
        matches = 0
        processed = 0
        last_progress_log = 0
        debug_logging = logger.isEnabledFor(logging.DEBUG)
        
        # Match each track to best file
        for track in tracks:
            processed += 1
            
            # Select candidates using two-stage filtering
            candidates = self.selector.duration_prefilter(
                track, files, dur_tolerance=self.dur_tolerance
            )
            if not candidates:  # Fallback if filter too strict
                candidates = files
            
            candidates = self.selector.token_prescore(
                track, candidates, max_candidates=self.max_candidates
            )
            
            # Find best match among candidates
            best_file_id = None
            best_breakdown = None
            best_score = -1.0
            
            for file_dict in candidates:
                breakdown = evaluate_pair(track, file_dict, self.scoring_config)
                
                if debug_logging:
                    logger.debug(
                        f"track={track['id']} vs file={file_dict['id']} "
                        f"raw={breakdown.raw_score:.1f} conf={breakdown.confidence} "
                        f"notes={breakdown.notes}"
                    )
                
                if breakdown.confidence == MatchConfidence.REJECTED:
                    continue
                
                if breakdown.raw_score > best_score:
                    best_score = breakdown.raw_score
                    best_file_id = file_dict['id']
                    best_breakdown = breakdown
                
                # Early exit on CERTAIN match
                if breakdown.confidence == MatchConfidence.CERTAIN:
                    break
            
            # Persist match if found
            if best_breakdown and best_file_id is not None:
                self.db.add_match(
                    track['id'],
                    best_file_id,
                    best_breakdown.raw_score / 100.0,
                    f"score:{best_breakdown.confidence}",
                    provider=self.provider
                )
                matches += 1
            
            # Log progress periodically
            if processed - last_progress_log >= self.progress_interval:
                self._log_progress(processed, len(tracks), matches, start)
                last_progress_log = processed
        
        # Commit all matches
        self.db.commit()
        
        # Log final summary
        duration = time.time() - start
        match_rate = (matches / len(tracks) * 100) if tracks else 0
        confidence_summary = self._get_confidence_summary(matches)
        
        logger.info(
            f"✓ Matched {matches}/{len(tracks)} tracks ({match_rate:.1f}%) in {duration:.2f}s"
        )
        if matches > 0:
            logger.info(f"  Confidence: {confidence_summary}")
        
        return matches
    
    def _log_progress(
        self, 
        processed: int, 
        total: int, 
        matches: int, 
        start_time: float
    ) -> None:
        """Log matching progress.
        
        Args:
            processed: Number of tracks processed so far
            total: Total number of tracks to process
            matches: Number of matches found so far
            start_time: Time matching started (from time.time())
        """
        elapsed = time.time() - start_time
        match_rate = (matches / processed * 100) if processed > 0 else 0
        unmatched = processed - matches
        
        logger.info(
            f"{processed}/{total} tracks "
            f"({processed/total*100:.0f}%) | "
            f"{matches} matched | "
            f"{unmatched} unmatched | "
            f"{processed/elapsed:.1f} tracks/s"
        )
        
        confidence_summary = self._get_confidence_summary(matches)
        logger.info(
            f"  Match rate: {match_rate:.1f}% | "
            f"Confidence breakdown: {confidence_summary}"
        )
    
    def _get_confidence_summary(self, total_matches: int) -> str:
        """Get a summary of match confidence distribution.
        
        Args:
            total_matches: Total number of matches created
        
        Returns:
            String showing counts for each confidence tier
        """
        if total_matches == 0:
            return "none"
        
        # Query match methods to extract confidence levels
        rows = self.db.conn.execute(
            "SELECT method FROM matches WHERE method LIKE 'score:%'"
        ).fetchall()
        
        # Count by confidence tier
        certain = sum(1 for r in rows if 'CERTAIN' in r[0])
        high = sum(1 for r in rows if 'HIGH' in r[0])
        medium = sum(1 for r in rows if 'MEDIUM' in r[0])
        low = sum(1 for r in rows if 'LOW' in r[0])
        
        parts = []
        if certain > 0:
            parts.append(f'{certain} certain')
        if high > 0:
            parts.append(f'{high} high')
        if medium > 0:
            parts.append(f'{medium} medium')
        if low > 0:
            parts.append(f'{low} low')
        
        return ", ".join(parts) if parts else "none"
    
    @staticmethod
    def _normalize_file_dict(raw_row: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize library file row to match scoring engine expectations.
        
        The scoring engine expects 'name' field while library stores 'title'.
        This adapter function harmonizes the field names and ensures all
        required keys exist with appropriate defaults.
        
        Args:
            raw_row: Raw file dict from database
        
        Returns:
            Normalized file dict with 'name' field
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


__all__ = ['MatchingEngine']
