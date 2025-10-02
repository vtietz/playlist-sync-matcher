"""Match service: Orchestrate library-to-Spotify matching.

This service handles the matching engine, progress tracking,
and diagnostic reporting for unmatched tracks.
"""

from __future__ import annotations
import time
import logging
from typing import Dict, Any, List

from ..match.engine import match_and_store
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
    
    # Run matching engine (uses fuzzy_threshold and use_year from config)
    matched_count = match_and_store(db, config=config)
    
    # Gather statistics
    result.library_files = db.count_library_files()
    
    # Count unique albums in library
    cur = db.conn.execute('SELECT COUNT(DISTINCT album) FROM library_files')
    result.library_albums = cur.fetchone()[0]
    
    result.library_tracks = db.count_tracks()
    result.spotify_tracks = db.count_tracks()  # Same as library tracks after matching
    result.matched = matched_count
    result.unmatched = result.library_files - result.matched
    
    # Gather unmatched diagnostics
    if result.unmatched > 0:
        unmatched_cur = db.conn.execute('''
            SELECT artist, album, title
            FROM library_files
            WHERE file_id NOT IN (SELECT file_id FROM matches)
            ORDER BY artist, album, title
        ''')
        result.unmatched_list = [
            {'artist': row[0], 'album': row[1], 'title': row[2]}
            for row in unmatched_cur.fetchall()
        ]
    
    result.duration_seconds = time.time() - start
    return result
