"""Analytics and aggregation queries for GUI performance.

Contains SQL queries for DISTINCT values, coverage metrics, and batch operations
to avoid Python-side iteration and N+1 queries.
"""
from __future__ import annotations
import sqlite3
from typing import List, Dict, Any


def get_distinct_artists(conn: sqlite3.Connection, provider: str) -> List[str]:
    """Get unique artist names from tracks.
    
    Args:
        conn: SQLite connection
        provider: Provider filter
        
    Returns:
        Sorted list of unique artist names (excluding empty/None)
    """
    cursor = conn.execute(
        """
        SELECT DISTINCT artist 
        FROM tracks 
        WHERE provider = ? AND artist IS NOT NULL AND artist != ''
        ORDER BY artist
        """,
        (provider,)
    )
    return [row[0] for row in cursor.fetchall()]


def get_distinct_albums(conn: sqlite3.Connection, provider: str) -> List[str]:
    """Get unique album names from tracks.
    
    Args:
        conn: SQLite connection
        provider: Provider filter
        
    Returns:
        Sorted list of unique album names (excluding empty/None)
    """
    cursor = conn.execute(
        """
        SELECT DISTINCT album 
        FROM tracks 
        WHERE provider = ? AND album IS NOT NULL AND album != ''
        ORDER BY album
        """,
        (provider,)
    )
    return [row[0] for row in cursor.fetchall()]


def get_distinct_years(conn: sqlite3.Connection, provider: str) -> List[int]:
    """Get unique years from tracks.
    
    Args:
        conn: SQLite connection
        provider: Provider filter
        
    Returns:
        Sorted list of unique years (newest first, excluding None)
    """
    cursor = conn.execute(
        """
        SELECT DISTINCT year 
        FROM tracks 
        WHERE provider = ? AND year IS NOT NULL
        ORDER BY year DESC
        """,
        (provider,)
    )
    return [row[0] for row in cursor.fetchall()]


def get_playlist_coverage(conn: sqlite3.Connection, provider: str) -> List[Dict[str, Any]]:
    """Get playlist coverage statistics in a single query.
    
    Computes total tracks and matched tracks per playlist using SQL aggregation
    to avoid N+1 queries.
    
    Args:
        conn: SQLite connection
        provider: Provider filter
        
    Returns:
        List of dicts with id, name, owner_id, owner_name, track_count, 
        matched_count, unmatched_count, coverage
    """
    cursor = conn.execute(
        """
        SELECT 
            p.id,
            p.name,
            p.owner_id,
            p.owner_name,
            COUNT(DISTINCT pt.track_id) as total,
            COUNT(DISTINCT CASE WHEN m.track_id IS NOT NULL THEN pt.track_id END) as matched
        FROM playlists p
        LEFT JOIN playlist_tracks pt ON p.id = pt.playlist_id AND p.provider = pt.provider
        LEFT JOIN matches m ON pt.track_id = m.track_id AND pt.provider = m.provider
        WHERE p.provider = ?
        GROUP BY p.id, p.name, p.owner_id, p.owner_name
        ORDER BY p.owner_name, p.name
        """,
        (provider,)
    )
    
    results = []
    for row in cursor.fetchall():
        total = row[4]
        matched = row[5]
        coverage_pct = int((matched / total * 100) if total > 0 else 0)
        
        results.append({
            'id': row[0],
            'name': row[1],
            'owner_id': row[2],
            'owner_name': row[3],
            'track_count': total,  # Total number of tracks in playlist
            'matched_count': matched,
            'unmatched_count': total - matched,
            'coverage': coverage_pct,
        })
    
    return results


def get_playlists_for_track_ids(
    conn: sqlite3.Connection,
    track_ids: List[str],
    provider: str
) -> Dict[str, str]:
    """Get comma-separated playlist names for each track ID.
    
    Uses GROUP_CONCAT to aggregate playlist names in SQL instead of Python loops.
    
    Args:
        conn: SQLite connection
        track_ids: List of track IDs to look up
        provider: Provider filter
        
    Returns:
        Dict mapping track_id -> "Playlist A, Playlist B, ..." (sorted)
    """
    if not track_ids:
        return {}
    
    # SQLite has a limit on SQL parameters (999 typically), so batch if needed
    BATCH_SIZE = 500
    result = {}
    
    for i in range(0, len(track_ids), BATCH_SIZE):
        batch = track_ids[i:i + BATCH_SIZE]
        placeholders = ','.join('?' * len(batch))
        
        query = f"""
        SELECT 
            pt.track_id,
            GROUP_CONCAT(DISTINCT p.name) as playlists
        FROM playlist_tracks pt
        JOIN playlists p ON pt.playlist_id = p.id AND pt.provider = p.provider
        WHERE pt.track_id IN ({placeholders}) AND pt.provider = ?
        GROUP BY pt.track_id
        """
        
        cursor = conn.execute(query, batch + [provider])
        for row in cursor.fetchall():
            # Sort playlist names for consistency
            playlists = row[1]
            if playlists:
                playlist_list = [p.strip() for p in playlists.split(',')]
                result[row[0]] = ', '.join(sorted(playlist_list))
    
    return result
