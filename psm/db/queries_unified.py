"""Unified tracks queries for GUI table display.

Provides fast queries that return one row per track with minimal fields,
deferring expensive aggregations like playlist concatenation.
"""
from __future__ import annotations
import sqlite3
from typing import List, Dict, Any, Optional, Set

# Detect SQLite version for window function support
_SQLITE_VERSION = tuple(map(int, sqlite3.sqlite_version.split('.')))
_SUPPORTS_WINDOW_FUNCTIONS = _SQLITE_VERSION >= (3, 25, 0)


def list_unified_tracks_min(
    conn: sqlite3.Connection,
    provider: str,
    sort_column: Optional[str] = None,
    sort_order: str = 'ASC',
    limit: Optional[int] = None,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Get minimal unified tracks (one row per track, no playlists aggregation).

    Returns core track metadata with matched flag computed in SQL using EXISTS.
    Defers playlist name concatenation to lazy loading.

    Args:
        conn: SQLite connection
        provider: Provider filter
        sort_column: Column name to sort by (name, artist, album, year)
        sort_order: 'ASC' or 'DESC'
        limit: Maximum rows to return (for paging)
        offset: Row offset (for paging)

    Returns:
        List of dicts with: id, name, artist, album, year, matched (bool), local_path, playlist_count
    """
    # Build ORDER BY clause
    order_by = ""
    if sort_column:
        # Sanitize column name (whitelist approach)
        valid_columns = {'name', 'artist', 'album', 'year'}
        if sort_column.lower() in valid_columns:
            order_by = f"ORDER BY t.{sort_column.lower()} {sort_order}"
    else:
        # Default sort: artist ASC, album ASC, name ASC for consistent ordering
        order_by = "ORDER BY t.artist ASC, t.album ASC, t.name ASC"

    # Build LIMIT/OFFSET clause
    limit_clause = ""
    if limit is not None:
        limit_clause = f"LIMIT {int(limit)} OFFSET {int(offset)}"

    # Main query: one row per track with EXISTS check for matches and playlist count
    # Use window function or subquery to get best local_path per track
    # Prefer MANUAL confidence first, then highest score (M1 solution)

    if _SUPPORTS_WINDOW_FUNCTIONS:
        # Modern SQLite with window functions
        query = f"""
        SELECT
            t.id,
            t.name,
            t.artist,
            t.album,
            t.year,
            CASE WHEN m.track_id IS NOT NULL THEN 1 ELSE 0 END as matched,
            COALESCE(lf.path, '') as local_path,
            t.artist_id,
            t.album_id,
            m.score,
            m.method,
            lf.title,
            lf.artist as file_artist,
            lf.album as file_album,
            lf.year as file_year,
            lf.bitrate_kbps,
            COALESCE(pl_count.count, 0) as playlist_count,
            EXISTS(SELECT 1 FROM liked_tracks lt WHERE lt.track_id = t.id AND lt.provider = t.provider) as is_liked
        FROM tracks t
        LEFT JOIN (
            -- Get best match per track: prefer MANUAL confidence, then highest score
            SELECT
                track_id,
                provider,
                file_id,
                score,
                method
            FROM (
                SELECT
                    track_id,
                    provider,
                    file_id,
                    score,
                    method,
                    confidence,
                    ROW_NUMBER() OVER (
                        PARTITION BY track_id, provider
                        ORDER BY (CASE WHEN confidence = 'MANUAL' THEN 1 ELSE 0 END) DESC, score DESC
                    ) as rn
                FROM matches
            ) ranked
            WHERE rn = 1
        ) m ON t.id = m.track_id AND t.provider = m.provider
        LEFT JOIN library_files lf ON m.file_id = lf.id
        LEFT JOIN (
            -- Count playlists per track
            SELECT track_id, provider, COUNT(DISTINCT playlist_id) as count
            FROM playlist_tracks
            GROUP BY track_id, provider
        ) pl_count ON t.id = pl_count.track_id AND t.provider = pl_count.provider
        WHERE t.provider = ?
        {order_by}
        {limit_clause}
        """
    else:
        # Fallback for older SQLite without window functions
        query = f"""
        SELECT
            t.id,
            t.name,
            t.artist,
            t.album,
            t.year,
            CASE WHEN m.track_id IS NOT NULL THEN 1 ELSE 0 END as matched,
            COALESCE(lf.path, '') as local_path,
            t.artist_id,
            t.album_id,
            m.score,
            m.method,
            lf.title,
            lf.artist as file_artist,
            lf.album as file_album,
            lf.year as file_year,
            lf.bitrate_kbps,
            COALESCE(pl_count.count, 0) as playlist_count,
            EXISTS(SELECT 1 FROM liked_tracks lt WHERE lt.track_id = t.id AND lt.provider = t.provider) as is_liked
        FROM tracks t
        LEFT JOIN (
            -- Get best match per track: prefer MANUAL confidence, then highest score
            SELECT
                m1.track_id,
                m1.provider,
                m1.file_id,
                m1.score,
                m1.method
            FROM matches m1
            WHERE m1.confidence = 'MANUAL'
                OR NOT EXISTS (
                    SELECT 1 FROM matches m2
                    WHERE m2.track_id = m1.track_id
                        AND m2.provider = m1.provider
                        AND m2.confidence = 'MANUAL'
                )
            AND m1.score = (
                SELECT MAX(score)
                FROM matches m3
                WHERE m3.track_id = m1.track_id
                    AND m3.provider = m1.provider
                    AND (
                        m1.confidence = 'MANUAL'
                        OR NOT EXISTS (
                            SELECT 1 FROM matches m4
                            WHERE m4.track_id = m3.track_id
                                AND m4.provider = m3.provider
                                AND m4.confidence = 'MANUAL'
                        )
                    )
            )
        ) m ON t.id = m.track_id AND t.provider = m.provider
        LEFT JOIN library_files lf ON m.file_id = lf.id
        LEFT JOIN (
            -- Count playlists per track
            SELECT track_id, provider, COUNT(DISTINCT playlist_id) as count
            FROM playlist_tracks
            GROUP BY track_id, provider
        ) pl_count ON t.id = pl_count.track_id AND t.provider = pl_count.provider
        WHERE t.provider = ?
        {order_by}
        {limit_clause}
        """

    cursor = conn.execute(query, (provider,))

    results = []
    for row in cursor.fetchall():
        # Calculate missing metadata count for quality status
        missing_count = 0
        if not row[11]:  # title
            missing_count += 1
        if not row[12]:  # file_artist
            missing_count += 1
        if not row[13]:  # file_album
            missing_count += 1
        if not row[14]:  # file_year
            missing_count += 1

        results.append({
            'id': row[0],
            'name': row[1] or '',
            'artist': row[2] or '',
            'album': row[3] or '',
            'year': row[4],  # May be None
            'matched': bool(row[5]),  # 1/0 -> True/False
            'local_path': row[6],
            'artist_id': row[7],  # Artist Spotify ID
            'album_id': row[8],   # Album Spotify ID
            'score': row[9],  # Match score (0.0-1.0)
            'method': row[10],  # Match method string
            'missing_metadata_count': missing_count,  # For quality calculation
            'bitrate_kbps': row[15],  # For quality calculation
            'playlist_count': row[16],  # Number of playlists containing this track
            'is_liked': bool(row[17]),  # Liked status (1/0 -> True/False)
        })

    return results


def get_track_ids_for_playlist(
    conn: sqlite3.Connection,
    playlist_name: str,
    provider: str
) -> Set[str]:
    """Get set of track IDs that belong to a specific playlist.

    Used for efficient playlist filtering in GUI without loading playlists column.

    Args:
        conn: SQLite connection
        playlist_name: Name of playlist to filter by
        provider: Provider filter

    Returns:
        Set of track IDs in the playlist
    """
    cursor = conn.execute(
        """
        SELECT DISTINCT pt.track_id
        FROM playlist_tracks pt
        JOIN playlists p ON pt.playlist_id = p.id AND pt.provider = p.provider
        WHERE p.name = ? AND p.provider = ?
        """,
        (playlist_name, provider)
    )

    return {row[0] for row in cursor.fetchall()}
