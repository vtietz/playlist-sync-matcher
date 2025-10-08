"""Candidate selection utilities for matching engine.

This module provides helper functions to filter and pre-score candidate
files for matching against streaming tracks. These utilities reduce the
computational cost of matching by narrowing down the candidate pool before
expensive fuzzy matching is performed.
"""

from __future__ import annotations
from typing import List, Dict, Any, Tuple


class CandidateSelector:
    """Helper for selecting and pre-scoring candidate files for matching.
    
    This class consolidates the candidate selection logic that was previously
    duplicated across multiple matching functions. It provides:
    
    1. Duration-based prefiltering to exclude files with incompatible durations
    2. Token-based pre-scoring using Jaccard similarity to prioritize likely matches
    
    Example usage:
        selector = CandidateSelector()
        
        # Filter by duration
        candidates = selector.duration_prefilter(track, all_files, dur_tolerance=2.0)
        
        # Pre-score and cap candidates
        top_candidates = selector.token_prescore(
            track, 
            candidates, 
            max_candidates=500
        )
    """
    
    def duration_prefilter(
        self,
        track: Dict[str, Any],
        files: List[Dict[str, Any]],
        dur_tolerance: float | None = 2.0
    ) -> List[Dict[str, Any]]:
        """Filter files by duration compatibility with track.
        
        Uses a relaxed duration tolerance to avoid over-pruning when metadata
        rounding causes off-by-seconds inconsistencies. The minimum window is
        ±4 seconds or (dur_tolerance * 2), whichever is larger.
        
        Files without duration metadata are retained (can't exclude them).
        
        Args:
            track: Track dict with 'duration_ms' field (in milliseconds)
            files: List of file dicts with 'duration' field (in seconds)
            dur_tolerance: Base tolerance in seconds (default: 2.0)
                          Actual window = max(4, dur_tolerance * 2)
        
        Returns:
            List of files that pass the duration filter (or all files if track
            lacks duration metadata)
        """
        # If tolerance is None, skip filtering
        if dur_tolerance is None:
            return files
        
        # If track lacks duration, we can't filter
        if track.get('duration_ms') is None:
            return files
        
        target_sec = track['duration_ms'] / 1000.0
        
        # Use minimum ±4s window or (dur_tol * 2) to avoid over-pruning
        window = max(4, dur_tolerance * 2)
        
        # Keep files that:
        # 1. Have no duration metadata (can't exclude)
        # 2. Are within the duration window
        return [
            f for f in files
            if f.get('duration') is None 
            or abs(f.get('duration') - target_sec) <= window
        ]
    
    def token_prescore(
        self,
        track: Dict[str, Any],
        files: List[Dict[str, Any]],
        max_candidates: int = 500
    ) -> List[Dict[str, Any]]:
        """Pre-score files using Jaccard similarity and return top candidates.
        
        Uses token-based Jaccard similarity (intersection/union) on normalized
        strings to quickly estimate match quality. This is much faster than
        fuzzy matching and helps prioritize the most promising candidates.
        
        If the candidate pool is already smaller than max_candidates, returns
        all candidates without sorting (optimization).
        
        Args:
            track: Track dict with 'normalized' field (space-separated tokens)
            files: List of file dicts with 'normalized' field
            max_candidates: Maximum number of candidates to return
        
        Returns:
            List of top-scoring files (up to max_candidates), sorted by
            Jaccard similarity (highest first)
        """
        # If we're already under the cap, no need to pre-score
        if len(files) <= max_candidates:
            return files
        
        # Get normalized tokens for track
        track_tokens = set((track.get('normalized') or '').split())
        
        # Score each file using Jaccard similarity
        scored_files: List[Tuple[float, Dict[str, Any]]] = []
        for f in files:
            file_tokens = set((f.get('normalized') or '').split())
            similarity = self._jaccard_similarity(track_tokens, file_tokens)
            scored_files.append((similarity, f))
        
        # Sort by similarity (descending) and take top N
        scored_files.sort(key=lambda x: x[0], reverse=True)
        return [f for _, f in scored_files[:max_candidates]]
    
    @staticmethod
    def _jaccard_similarity(set1: set, set2: set) -> float:
        """Calculate Jaccard similarity between two sets.
        
        Returns intersection / union ratio (0.0 to 1.0).
        Used for fast candidate pre-scoring before full fuzzy matching.
        
        Args:
            set1: First set of tokens
            set2: Second set of tokens
        
        Returns:
            Jaccard similarity coefficient (0.0 to 1.0)
        """
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0


__all__ = ['CandidateSelector']
