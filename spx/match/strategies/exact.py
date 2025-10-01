"""SQL-based exact matching strategy using indexed normalized fields."""
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Set
import time
import click
from .base import MatchStrategy


class ExactMatchStrategy(MatchStrategy):
    """SQL JOIN-based exact matching on normalized field.
    
    Uses indexed normalized columns for fast exact matches.
    This is typically the first and fastest strategy to run.
    """
    
    def get_name(self) -> str:
        return "sql_exact"
    
    def match(self, tracks: List[Dict[str, Any]], files: List[Dict[str, Any]], 
              already_matched: Set[str]) -> Tuple[List[Tuple[str, int, float, str]], Set[str]]:
        """Execute SQL-based exact matching."""
        start = time.time()
        
        if self.debug:
            print(f"[{self.get_name()}] Starting SQL exact matching on {len(tracks)} tracks...")
        
        # Use SQL JOIN to find exact matches - SQLite will use the normalized indices efficiently
        sql_exact = """
            SELECT t.id as track_id, lf.id as file_id
            FROM tracks t
            INNER JOIN library_files lf ON t.normalized = lf.normalized
            WHERE t.normalized IS NOT NULL AND t.normalized != ''
        """
        
        # If we have already matched tracks, exclude them
        if already_matched:
            placeholders = ','.join('?' * len(already_matched))
            sql_exact += f" AND t.id NOT IN ({placeholders})"
            exact_matches = self.db.conn.execute(sql_exact, tuple(already_matched)).fetchall()
        else:
            exact_matches = self.db.conn.execute(sql_exact).fetchall()
        
        # Build result list
        matches: List[Tuple[str, int, float, str]] = []
        matched_track_ids: Set[str] = set()
        
        # Build lookup maps for detailed logging
        file_by_id = {f['id']: f for f in files}
        track_by_id = {t['id']: t for t in tracks}
        
        for row in exact_matches:
            track_id = row['track_id']
            file_id = row['file_id']
            matches.append((track_id, file_id, 1.0, self.get_name()))
            matched_track_ids.add(track_id)
            
            # Only log matches, no per-match details unless explicitly verbose
            # (Per-match logging creates too much noise for large libraries)
        
        duration = time.time() - start
        
        if self.debug:
            print(f"[{self.get_name()}] Found {len(matches)} exact matches in {duration:.2f}s")
        
        return matches, matched_track_ids
