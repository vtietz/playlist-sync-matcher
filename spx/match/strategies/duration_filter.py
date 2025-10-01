"""Duration-based candidate filtering strategy.

Filters out impossible matches based on track duration before expensive fuzzy matching.
This is a low-effort, high-impact optimization that can reduce fuzzy matching work by 5-20x.
"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Set
import time


class DurationFilterStrategy:
    """Filters candidates by duration tolerance before passing to next strategy.
    
    This is not a full matching strategy but a preprocessing step that narrows
    the candidate file set for expensive fuzzy matching.
    
    Typical duration tolerance: ±2 seconds (configurable via matching.duration_tolerance)
    """
    
    def __init__(self, tolerance_seconds: float = 2.0, debug: bool = False):
        self.tolerance = tolerance_seconds
        self.debug = debug
    
    def filter_candidates(self, tracks: List[Dict[str, Any]], files: List[Dict[str, Any]], 
                         already_matched: Set[str]) -> Dict[str, List[int]]:
        """Build a map of track_id -> list of candidate file_ids filtered by duration.
        
        Args:
            tracks: List of track dictionaries with duration_ms field
            files: List of file dictionaries with duration field (in seconds)
            already_matched: Set of track IDs to skip
        
        Returns:
            Dictionary mapping track_id to list of candidate file_ids
        """
        start = time.time()
        
        unmatched_tracks = [t for t in tracks if t['id'] not in already_matched]
        
        if self.debug:
            print(f"[duration_filter] Filtering {len(unmatched_tracks)} tracks against {len(files)} files (tolerance=±{self.tolerance}s)")
        
        # Build candidate map
        candidates: Dict[str, List[int]] = {}
        total_candidates = 0
        
        for track in unmatched_tracks:
            track_id = track['id']
            track_duration_ms = track.get('duration_ms')
            
            # If track has no duration, include all files as candidates (no filtering possible)
            if track_duration_ms is None:
                candidates[track_id] = [f['id'] for f in files]
                total_candidates += len(files)
                continue
            
            track_duration_sec = track_duration_ms / 1000.0
            track_candidates = []
            
            for file in files:
                file_duration = file.get('duration')
                
                # If file has no duration, include it as a candidate (no filtering possible)
                if file_duration is None:
                    track_candidates.append(file['id'])
                    continue
                
                # Check if durations are within tolerance
                duration_diff = abs(track_duration_sec - file_duration)
                if duration_diff <= self.tolerance:
                    track_candidates.append(file['id'])
            
            candidates[track_id] = track_candidates
            total_candidates += len(track_candidates)
        
        duration = time.time() - start
        avg_candidates = total_candidates / len(unmatched_tracks) if unmatched_tracks else 0
        reduction_pct = (1 - avg_candidates / len(files)) * 100 if files else 0
        
        if self.debug:
            print(f"[duration_filter] Filtered to {total_candidates} total candidates "
                  f"(avg {avg_candidates:.1f} per track, {reduction_pct:.1f}% reduction) in {duration:.2f}s")
        
        return candidates
