"""Year-based matching strategy.

This strategy matches tracks using normalized artist + title + year.
It helps distinguish between:
- Original recordings vs. remasters
- Different live versions from specific years
- Re-recordings of the same song
"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Set
import logging
from .base import MatchStrategy

logger = logging.getLogger(__name__)


class YearMatchStrategy(MatchStrategy):
    """Match using normalized artist + title + year."""
    
    def get_name(self) -> str:
        return "year_match"
    
    def match(self, tracks: List[Dict[str, Any]], files: List[Dict[str, Any]], 
              already_matched: Set[str]) -> Tuple[List[Tuple[str, int, float, str]], Set[str]]:
        """Execute year-based matching on unmatched tracks."""
        
        # Filter to unmatched tracks that have year info
        unmatched_tracks = [t for t in tracks 
                           if t['id'] not in already_matched 
                           and t.get('year') and t.get('normalized')]
        
        if not unmatched_tracks:
            if self.debug:
                print(f"[{self.get_name()}] No unmatched tracks with year info to process")
            return [], set()
        
        # Build file index: (normalized, year) -> file_id
        file_index: Dict[Tuple[str, int], int] = {}
        file_by_id = {f['id']: f for f in files}
        
        for f in files:
            if f.get('normalized') and f.get('year'):
                key = (f['normalized'], f['year'])
                # First match wins (don't overwrite)
                if key not in file_index:
                    file_index[key] = f['id']
        
        if self.debug:
            print(f"[{self.get_name()}] Built index with {len(file_index)} (track+year) combinations")
            print(f"[{self.get_name()}] Matching {len(unmatched_tracks)} tracks with year info")
        
        matches: List[Tuple[str, int, float, str]] = []
        matched_track_ids: Set[str] = set()
        
        for track in unmatched_tracks:
            track_id = track['id']
            track_norm = track.get('normalized', '')
            track_year = track.get('year')
            
            if not track_norm or not track_year:
                continue
            
            key = (track_norm, track_year)
            
            if key in file_index:
                file_id = file_index[key]
                matches.append((track_id, file_id, 1.0, self.get_name()))
                matched_track_ids.add(track_id)
                
                if self.debug:
                    file_path = file_by_id[file_id].get('path', 'unknown')
                    print(f"[{self.get_name()}] [MATCH] Year: "
                          f"{track.get('artist', '')} - {track.get('name', '')} "
                          f"({track_year}) -> {file_path}")
        
        if self.debug:
            print(f"[{self.get_name()}] Found {len(matches)} year-based matches")
        
        return matches, matched_track_ids
