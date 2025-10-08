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
from ..config_types import MatchingConfig

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
        matching_cfg = MatchingConfig(duration_tolerance=3.0, max_candidates_per_track=300)
        engine = MatchingEngine(db, matching_cfg, provider='spotify')
        matches_count = engine.match_all()
    """
    
    def __init__(
        self,
        db: Database,
        matching_config: MatchingConfig,
        provider: str = 'spotify'
    ):
        """Initialize the matching engine.
        
        Args:
            db: Database instance
            matching_config: MatchingConfig instance with matching parameters
            provider: Provider name (default: 'spotify')
        """
        self.db = db
        self.selector = CandidateSelector()
        self.scoring_config = ScoringConfig()
        self.provider = provider
        
        # Extract config values
        self.dur_tolerance = matching_config.duration_tolerance
        self.max_candidates = matching_config.max_candidates_per_track
        
        self.progress_interval = 100  # Log progress every N tracks
    
    def match_all(self) -> int:
        """Match all tracks against all library files.
        
        This performs a full matching run, evaluating all tracks in the database
        against all library files. Progress is logged periodically and results
        are committed to the database.
        
        Returns:
            Number of matches created
        """
        start = time.time()
        
        # Fetch all tracks and files using repository methods
        track_rows = self.db.get_all_tracks(provider='spotify')
        tracks = [row.to_dict() for row in track_rows]
        
        file_rows = self.db.get_all_library_files()
        files = [self._normalize_file_dict(row.to_dict()) for row in file_rows]
        
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
        
        # Get match confidence counts using repository method
        method_counts = self.db.get_match_confidence_counts()
        
        # Count by confidence tier (methods are like "score:HIGH:...")
        certain = sum(count for method, count in method_counts.items() if 'CERTAIN' in method)
        high = sum(count for method, count in method_counts.items() if 'HIGH' in method)
        medium = sum(count for method, count in method_counts.items() if 'MEDIUM' in method)
        low = sum(count for method, count in method_counts.items() if 'LOW' in method)
        
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
    
    def match_tracks(
        self,
        track_ids: List[str] | None = None,
        all_files: List[Dict[str, Any]] | None = None
    ) -> int:
        """Incrementally match specific tracks against all library files.
        
        This is the inverse of match_files: instead of matching a few changed
        files against all tracks, we match all files against a few changed tracks.
        
        Use case: After 'pull' command adds/updates tracks in database.
        
        Args:
            track_ids: List of specific track IDs to match (if None, matches all unmatched tracks)
            all_files: Pre-loaded file list (optional, will query if None)
            
        Returns:
            Number of new matches created
        """
        # Get all library files if not provided
        if all_files is None:
            file_rows = self.db.get_all_library_files()
            all_files = [self._normalize_file_dict(row.to_dict()) for row in file_rows]
        
        if not all_files:
            logger.debug("No library files to match against")
            return 0
        
        # Get tracks to match
        if track_ids:
            # Match specific changed tracks
            if not track_ids:  # Empty list
                return 0
            
            track_rows = self.db.get_tracks_by_ids(track_ids, provider='spotify')
            tracks_to_match = [row.to_dict() for row in track_rows]
            
            # Delete existing matches for these tracks (they were updated)
            self.db.delete_matches_by_track_ids(track_ids)
        else:
            # Match all currently unmatched tracks (fallback)
            track_rows = self.db.get_unmatched_tracks(provider='spotify')
            tracks_to_match = [row.to_dict() for row in track_rows]
        
        if not tracks_to_match:
            logger.debug("No tracks need matching")
            return 0
        
        logger.info(f"Incrementally matching {len(all_files)} file(s) against {len(tracks_to_match)} changed track(s)...")
        
        new_matches = 0
        
        # For each changed track, find best file from library
        for track in tracks_to_match:
            # Build candidate subset using CandidateSelector
            candidates = self.selector.duration_prefilter(track, all_files, dur_tolerance=self.dur_tolerance)
            if not candidates:
                candidates = all_files  # Fallback if filter too strict
            
            # Pre-score and cap candidates using token similarity
            candidates = self.selector.token_prescore(track, candidates, max_candidates=self.max_candidates)
            
            # Find best match among candidates
            best_file_id = None
            best_breakdown = None
            best_score = -1.0
            
            for file_dict in candidates:
                breakdown = evaluate_pair(track, file_dict, self.scoring_config)
                if breakdown.confidence == MatchConfidence.REJECTED:
                    continue
                if breakdown.raw_score > best_score:
                    best_score = breakdown.raw_score
                    best_file_id = file_dict['id']
                    best_breakdown = breakdown
                if breakdown.confidence == MatchConfidence.CERTAIN:
                    break
            
            if best_breakdown and best_file_id is not None:
                self.db.add_match(
                    track['id'],
                    best_file_id,
                    best_breakdown.raw_score / 100.0,
                    f"score:{best_breakdown.confidence}",
                    provider=self.provider
                )
                new_matches += 1
        
        self.db.commit()
        logger.info(f"✓ Created {new_matches} new match(es) from {len(tracks_to_match)} changed track(s)")
        return new_matches
    
    def match_files(
        self,
        file_ids: List[int] | None = None,
        all_tracks: List[Dict[str, Any]] | None = None
    ) -> tuple[int, List[str]]:
        """Incrementally match specific files against all tracks.
        
        This is much more efficient than match_all() for watch mode scenarios
        where only a few files changed. Instead of re-matching all files against
        all tracks, we only match the changed files.
        
        Args:
            file_ids: List of specific file IDs to match (if None, matches all unmatched files)
            all_tracks: Pre-loaded track list (optional, will query if None)
            
        Returns:
            Tuple of (match_count, list of matched track IDs)
        """
        # Get all tracks if not provided
        if all_tracks is None:
            track_rows = self.db.get_all_tracks(provider='spotify')
            all_tracks = [row.to_dict() for row in track_rows]
        
        if not all_tracks:
            logger.debug("No tracks in database to match against")
            return (0, [])
        
        # Get files to match
        if file_ids:
            # Match specific changed files
            if not file_ids:  # Empty list
                return (0, [])
            
            file_rows = self.db.get_library_files_by_ids(file_ids)
            files_to_match = [self._normalize_file_dict(row.to_dict()) for row in file_rows]
            
            # Delete existing matches for these files (they were updated)
            self.db.delete_matches_by_file_ids(file_ids)
        else:
            # Match all currently unmatched files (fallback)
            file_rows = self.db.get_unmatched_library_files()
            files_to_match = [self._normalize_file_dict(row.to_dict()) for row in file_rows]
        
        if not files_to_match:
            logger.debug("No files need matching")
            return (0, [])
        
        logger.info(f"Incrementally matching {len(files_to_match)} file(s) against {len(all_tracks)} tracks...")
        
        new_matches = 0
        matched_track_ids = []  # Track which tracks got new matches
        
        # For each track, find best file from our changed file list
        for track in all_tracks:
            # Build candidate subset using CandidateSelector
            candidates = self.selector.duration_prefilter(track, files_to_match, dur_tolerance=self.dur_tolerance)
            if not candidates:
                candidates = files_to_match  # Fallback if filter too strict
            
            # Pre-score and cap candidates using token similarity
            candidates = self.selector.token_prescore(track, candidates, max_candidates=self.max_candidates)
            
            # Find best match among candidates
            best_file_id = None
            best_breakdown = None
            best_score = -1.0
            
            for file_dict in candidates:
                breakdown = evaluate_pair(track, file_dict, self.scoring_config)
                if breakdown.confidence == MatchConfidence.REJECTED:
                    continue
                if breakdown.raw_score > best_score:
                    best_score = breakdown.raw_score
                    best_file_id = file_dict['id']
                    best_breakdown = breakdown
                if breakdown.confidence == MatchConfidence.CERTAIN:
                    break
            
            if best_breakdown and best_file_id is not None:
                self.db.add_match(
                    track['id'],
                    best_file_id,
                    best_breakdown.raw_score / 100.0,
                    f"score:{best_breakdown.confidence}",
                    provider=self.provider
                )
                new_matches += 1
                matched_track_ids.append(track['id'])  # Track which tracks got matched
        
        self.db.commit()
        logger.info(f"✓ Created {new_matches} new match(es) from {len(files_to_match)} changed file(s)")
        return (new_matches, matched_track_ids)
    
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
