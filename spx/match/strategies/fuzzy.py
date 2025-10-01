"""Fuzzy matching strategy using RapidFuzz token_set_ratio.

This is the most expensive strategy but provides good quality matches for
tracks that don't have exact normalized matches.
"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Set, Optional
import time
import os
import click
from rapidfuzz import fuzz
from .base import MatchStrategy


class FuzzyMatchStrategy(MatchStrategy):
    """RapidFuzz-based fuzzy matching strategy.
    
    Uses token_set_ratio to find similar tracks. Can be expensive on large libraries,
    so best used with candidate filtering (e.g., duration-based).
    """
    
    def __init__(self, db, config: Dict[str, Any], debug: bool = False, 
                 candidate_file_ids: Optional[Dict[str, List[int]]] = None):
        super().__init__(db, config, debug)
        self.threshold = config.get('matching', {}).get('fuzzy_threshold', 0.78)
        # Map of track_id -> list of candidate file_ids (if prefiltered)
        self.candidate_file_ids = candidate_file_ids
    
    def get_name(self) -> str:
        return "fuzzy"
    
    def _score_fuzzy(self, t_norm: str, f_norm: str) -> float:
        """Calculate fuzzy similarity score (0.0 to 1.0)."""
        # token set ratio returns 0-100
        return fuzz.token_set_ratio(t_norm, f_norm) / 100.0
    
    def match(self, tracks: List[Dict[str, Any]], files: List[Dict[str, Any]], 
              already_matched: Set[str]) -> Tuple[List[Tuple[str, int, float, str]], Set[str]]:
        """Execute fuzzy matching on unmatched tracks."""
        start = time.time()
        
        # Filter to unmatched tracks
        unmatched_tracks = [t for t in tracks if t['id'] not in already_matched]
        
        if not unmatched_tracks:
            if self.debug:
                print(f"[{self.get_name()}] No unmatched tracks to process")
            return [], set()
        
        if self.debug:
            print(f"[{self.get_name()}] Fuzzy matching {len(unmatched_tracks)} unmatched tracks "
                  f"against {len(files)} files (threshold={self.threshold})")
        
        # Build file lookups
        file_by_id = {f['id']: f for f in files}
        track_by_id = {t['id']: t for t in tracks}
        
        matches: List[Tuple[str, int, float, str]] = []
        matched_track_ids: Set[str] = set()
        
        # Progress tracking - only show every 10% to reduce noise
        progress_interval = max(1, len(unmatched_tracks) // 10)  # Report every 10% instead of 1%
        last_progress_pct = 0
        
        for idx, track in enumerate(unmatched_tracks, 1):
            track_id = track['id']
            t_norm = track.get('normalized', '')
            
            if not t_norm:
                continue
            
            # Progress logging - only show if crossing a 10% boundary
            current_pct = int((idx / len(unmatched_tracks)) * 10) * 10  # Round to 10%
            if self.debug and current_pct > last_progress_pct and idx % progress_interval == 0:
                elapsed = time.time() - start
                tracks_per_sec = idx / elapsed if elapsed > 0 else 0
                eta = (len(unmatched_tracks) - idx) / tracks_per_sec if tracks_per_sec > 0 else 0
                print(f"[{self.get_name()}] Progress: {current_pct}% ({idx}/{len(unmatched_tracks)} tracks) - "
                      f"{len(matches)} matches - {tracks_per_sec:.1f} tracks/sec - ETA {eta:.0f}s")
                last_progress_pct = current_pct
            
            # Determine which files to check
            if self.candidate_file_ids and track_id in self.candidate_file_ids:
                # Use prefiltered candidates
                candidate_ids = self.candidate_file_ids[track_id]
                candidate_files = [file_by_id[fid] for fid in candidate_ids if fid in file_by_id]
            else:
                # Check all files (no prefiltering)
                candidate_files = files
            
            # Find best match among candidates
            best_file_id: Optional[int] = None
            best_score = 0.0
            
            for file in candidate_files:
                f_norm = file.get('normalized', '')
                if not f_norm:
                    continue
                
                score = self._score_fuzzy(t_norm, f_norm)
                if score >= self.threshold and score > best_score:
                    best_score = score
                    best_file_id = file['id']
            
            # Store match if found
            if best_file_id is not None:
                matches.append((track_id, best_file_id, best_score, self.get_name()))
                matched_track_ids.add(track_id)
                
                # Only log individual matches if we have very few (to avoid console spam)
                # For large match sets, rely on summary instead
        
        duration = time.time() - start
        
        if self.debug:
            print(f"[{self.get_name()}] Found {len(matches)} fuzzy matches in {duration:.2f}s")
            # Show quality distribution
            if matches:
                high_quality = sum(1 for _, _, score, _ in matches if score >= 0.9)
                medium_quality = sum(1 for _, _, score, _ in matches if 0.8 <= score < 0.9)
                low_quality = sum(1 for _, _, score, _ in matches if score < 0.8)
                print(f"[{self.get_name()}] Quality: {high_quality} high (≥0.9), {medium_quality} medium (0.8-0.9), {low_quality} low (<0.8)")
        
        return matches, matched_track_ids
