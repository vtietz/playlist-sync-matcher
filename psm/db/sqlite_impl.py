from __future__ import annotations
import sqlite3
import logging
import sys
from pathlib import Path
from typing import Iterable, Sequence, Any, Dict, Tuple, Optional, List
from .interface import DatabaseInterface
from .models import TrackRow, LibraryFileRow, MatchRow, PlaylistRow

logger = logging.getLogger(__name__)

SCHEMA = [
    "PRAGMA journal_mode=WAL;",
    # Clean provider‑namespaced schema (v1). Playlists & playlist_tracks include provider in PK for cross-provider coexistence.
    "CREATE TABLE IF NOT EXISTS playlists (id TEXT NOT NULL, provider TEXT NOT NULL DEFAULT 'spotify', name TEXT NOT NULL, snapshot_id TEXT, owner_id TEXT, owner_name TEXT, PRIMARY KEY(id, provider));",
    "CREATE TABLE IF NOT EXISTS playlist_tracks (playlist_id TEXT NOT NULL, provider TEXT NOT NULL DEFAULT 'spotify', position INTEGER NOT NULL, track_id TEXT NOT NULL, added_at TEXT, PRIMARY KEY(playlist_id, provider, position));",
    "CREATE TABLE IF NOT EXISTS tracks (id TEXT NOT NULL, provider TEXT NOT NULL DEFAULT 'spotify', name TEXT, album TEXT, artist TEXT, album_id TEXT, artist_id TEXT, isrc TEXT, duration_ms INTEGER, normalized TEXT, year INTEGER, PRIMARY KEY(id, provider));",
    "CREATE TABLE IF NOT EXISTS liked_tracks (track_id TEXT NOT NULL, provider TEXT NOT NULL DEFAULT 'spotify', added_at TEXT, PRIMARY KEY(track_id, provider));",
    "CREATE TABLE IF NOT EXISTS library_files (id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT UNIQUE, size INTEGER, mtime REAL, partial_hash TEXT, title TEXT, album TEXT, artist TEXT, duration REAL, normalized TEXT, year INTEGER, bitrate_kbps INTEGER);",
    "CREATE TABLE IF NOT EXISTS matches (track_id TEXT NOT NULL, provider TEXT NOT NULL DEFAULT 'spotify', file_id INTEGER NOT NULL, score REAL NOT NULL, method TEXT NOT NULL, PRIMARY KEY(track_id, provider, file_id));",
    # Existing indexes
    "CREATE INDEX IF NOT EXISTS idx_tracks_isrc ON tracks(isrc);",
    "CREATE INDEX IF NOT EXISTS idx_tracks_normalized ON tracks(normalized);",
    "CREATE INDEX IF NOT EXISTS idx_library_files_normalized ON library_files(normalized);",
    # Phase 7: Performance indexes for high-frequency joins
    "CREATE INDEX IF NOT EXISTS idx_playlist_tracks_playlist ON playlist_tracks(playlist_id, provider);",
    "CREATE INDEX IF NOT EXISTS idx_playlist_tracks_track ON playlist_tracks(track_id, provider);",
    "CREATE INDEX IF NOT EXISTS idx_matches_track ON matches(track_id, provider);",
    "CREATE INDEX IF NOT EXISTS idx_matches_file ON matches(file_id);",
    "CREATE INDEX IF NOT EXISTS idx_liked_tracks_track ON liked_tracks(track_id, provider);",
    # Metadata table
    "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);",
]

class Database(DatabaseInterface):
    def __init__(self, path: Path):
        self.path = path
        if not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self._closed = False
        self._init_schema()

    def __enter__(self) -> "Database":  # pragma: no cover
        return self

    def __exit__(self, exc_type, exc, tb):  # pragma: no cover
        self.close()

    def _init_schema(self) -> None:
        legacy = False
        try:
            cur = self.conn.execute("PRAGMA table_info(playlists)")
            cols = [r[1] for r in cur.fetchall()]
            if cols and 'provider' in cols:
                cur2 = self.conn.execute("PRAGMA table_info(playlists)")
                pk_cols = [r[1] for r in cur2.fetchall() if r[5] == 1 or r[5] == 2]
                if 'provider' not in pk_cols:
                    legacy = True
        except Exception:
            pass
        if legacy:
            for tbl in ["matches","playlist_tracks","playlists","tracks","liked_tracks","library_files"]:
                try:
                    self.conn.execute(f"DROP TABLE IF EXISTS {tbl}")
                except Exception:
                    pass
            self.conn.commit()
        cur = self.conn.cursor()
        for stmt in SCHEMA:
            cur.execute(stmt)
        self._ensure_column('tracks', 'artist_id', 'TEXT')
        self._ensure_column('tracks', 'album_id', 'TEXT')
        cur.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','1')")
        self.conn.commit()

    def _ensure_column(self, table: str, column: str, col_type: str):  # pragma: no cover
        cur = self.conn.execute(f"PRAGMA table_info({table})")
        cols = [r[1] for r in cur.fetchall()]
        if column not in cols:
            self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            self.conn.commit()

    def _execute_with_lock_handling(self, sql: str, params: Any = None):
        """Execute SQL with better diagnostics on database lock (but let SQLite retry)."""
        try:
            if params is not None:
                return self.conn.execute(sql, params)
            else:
                return self.conn.execute(sql)
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower():
                # Log diagnostic info but re-raise to let calling code handle it
                logger.warning("Database lock detected - SQLite will retry for up to 30 seconds")
                logger.warning("If this persists, check for:")
                logger.warning("  • DB Browser or other tools with database open")
                logger.warning("  • Long-running transactions in other processes")
            raise

    def upsert_playlist(self, pid: str, name: str, snapshot_id: str | None, owner_id: str | None = None, owner_name: str | None = None, provider: str | None = None) -> None:
        if provider is None:
            raise ValueError("provider parameter is required")
        self._execute_with_lock_handling(
            "INSERT INTO playlists(id,provider,name,snapshot_id,owner_id,owner_name) VALUES(?,?,?,?,?,?) ON CONFLICT(id,provider) DO UPDATE SET name=excluded.name, snapshot_id=excluded.snapshot_id, owner_id=excluded.owner_id, owner_name=excluded.owner_name",
            (pid, provider, name, snapshot_id, owner_id, owner_name),
        )

    def playlist_snapshot_changed(self, pid: str, snapshot_id: str, provider: str | None = None) -> bool:
        if provider is None:
            raise ValueError("provider parameter is required")
        cur = self.conn.execute("SELECT snapshot_id FROM playlists WHERE id=? AND provider=?", (pid, provider))
        row = cur.fetchone()
        if not row:
            return True
        return row[0] != snapshot_id

    def replace_playlist_tracks(self, pid: str, tracks: Sequence[Tuple[int, str, str | None]], provider: str | None = None):
        if provider is None:
            raise ValueError("provider parameter is required")
        self._execute_with_lock_handling("DELETE FROM playlist_tracks WHERE playlist_id=? AND provider=?", (pid, provider))
        # Use executemany for bulk inserts (with lock handling wrapper would be overkill here since we already hold transaction)
        self.conn.executemany(
            "INSERT INTO playlist_tracks(playlist_id, provider, position, track_id, added_at) VALUES(?,?,?,?,?)",
            [(pid, provider, pos, tid, added) for (pos, tid, added) in tracks],
        )

    def upsert_track(self, track: Dict[str, Any], provider: str | None = None):
        if provider is None:
            raise ValueError("provider parameter is required")
        self._execute_with_lock_handling(
            "INSERT INTO tracks(id,provider,name,album,artist,album_id,artist_id,isrc,duration_ms,normalized,year) VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id,provider) DO UPDATE SET name=excluded.name, album=excluded.album, artist=excluded.artist, album_id=excluded.album_id, artist_id=excluded.artist_id, isrc=excluded.isrc, duration_ms=excluded.duration_ms, normalized=excluded.normalized, year=excluded.year",
            (
                track.get("id"), provider, track.get("name"), track.get("album"), track.get("artist"),
                track.get("album_id"), track.get("artist_id"), track.get("isrc"), track.get("duration_ms"),
                track.get("normalized"), track.get("year"),
            ),
        )

    def upsert_liked(self, track_id: str, added_at: str, provider: str | None = None):
        if provider is None:
            raise ValueError("provider parameter is required")
        self._execute_with_lock_handling(
            "INSERT INTO liked_tracks(track_id,provider,added_at) VALUES(?,?,?) ON CONFLICT(track_id,provider) DO UPDATE SET added_at=excluded.added_at",
            (track_id, provider, added_at),
        )

    def commit(self):
        self.conn.commit()

    def add_library_file(self, data: Dict[str, Any]):
        self._execute_with_lock_handling(
            "INSERT INTO library_files(path,size,mtime,partial_hash,title,album,artist,duration,normalized,year,bitrate_kbps) VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET size=excluded.size, mtime=excluded.mtime, partial_hash=excluded.partial_hash, title=excluded.title, album=excluded.album, artist=excluded.artist, duration=excluded.duration, normalized=excluded.normalized, year=excluded.year, bitrate_kbps=excluded.bitrate_kbps",
            (
                data["path"], data.get("size"), data.get("mtime"), data.get("partial_hash"), data.get("title"),
                data.get("album"), data.get("artist"), data.get("duration"), data.get("normalized"),
                data.get("year"), data.get("bitrate_kbps"),
            ),
        )

    def add_match(self, track_id: str, file_id: int, score: float, method: str, provider: str | None = None):
        if provider is None:
            raise ValueError("provider parameter is required")
        self._execute_with_lock_handling(
            "INSERT INTO matches(track_id,provider,file_id,score,method) VALUES(?,?,?,?,?) ON CONFLICT(track_id,provider,file_id) DO UPDATE SET score=excluded.score, method=excluded.method",
            (track_id, provider, file_id, score, method),
        )

    def get_missing_tracks(self) -> Iterable[sqlite3.Row]:
        sql = """
    SELECT t.id, t.name, t.artist, t.album
    FROM tracks t
    LEFT JOIN matches m ON m.track_id = t.id AND m.provider = t.provider
    WHERE m.track_id IS NULL
        ORDER BY t.artist, t.album, t.name
        """
        return self.conn.execute(sql)

    def set_meta(self, key: str, value: str):
        self.conn.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

    def get_meta(self, key: str) -> Optional[str]:
        cur = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,))
        row = cur.fetchone()
        return row[0] if row else None

    def count_playlists(self, provider: str | None = None) -> int:
        # None means all providers, empty string not supported
        if provider:
            cursor = self.conn.execute("SELECT COUNT(*) FROM playlists WHERE provider=?", (provider,))
        else:
            cursor = self.conn.execute("SELECT COUNT(*) FROM playlists")
        return cursor.fetchone()[0]

    def count_unique_playlist_tracks(self, provider: str | None = None) -> int:
        # None means all providers
        if provider:
            cursor = self.conn.execute("SELECT COUNT(DISTINCT track_id) FROM playlist_tracks WHERE provider=?", (provider,))
        else:
            cursor = self.conn.execute("SELECT COUNT(DISTINCT track_id) FROM playlist_tracks")
        return cursor.fetchone()[0]

    def count_liked_tracks(self, provider: str | None = None) -> int:
        # None means all providers
        if provider:
            cursor = self.conn.execute("SELECT COUNT(*) FROM liked_tracks WHERE provider=?", (provider,))
        else:
            cursor = self.conn.execute("SELECT COUNT(*) FROM liked_tracks")
        return cursor.fetchone()[0]

    def count_tracks(self, provider: str | None = None) -> int:
        # None means all providers
        if provider:
            cursor = self.conn.execute("SELECT COUNT(*) FROM tracks WHERE provider=?", (provider,))
        else:
            cursor = self.conn.execute("SELECT COUNT(*) FROM tracks")
        return cursor.fetchone()[0]

    def count_library_files(self) -> int:
        cursor = self.conn.execute("SELECT COUNT(*) FROM library_files")
        return cursor.fetchone()[0]

    def count_matches(self) -> int:
        cursor = self.conn.execute("SELECT COUNT(*) FROM matches")
        return cursor.fetchone()[0]

    def get_all_playlists(self, provider: str | None = None) -> List[PlaylistRow]:
        # Default to 'spotify' when None for backward compat (common in tests)
        provider = provider if provider is not None else 'spotify'
        if provider:
            sql = """
            SELECT p.id, p.provider, p.name, p.owner_id, p.owner_name, p.snapshot_id,
                   COUNT(pt.track_id) as track_count
            FROM playlists p
            LEFT JOIN playlist_tracks pt ON pt.playlist_id = p.id AND pt.provider = p.provider
            WHERE p.provider=?
            GROUP BY p.id, p.provider, p.name, p.owner_id, p.owner_name, p.snapshot_id
            ORDER BY p.name
            """
            rows = self.conn.execute(sql, (provider,)).fetchall()
        else:
            sql = """
            SELECT p.id, p.provider, p.name, p.owner_id, p.owner_name, p.snapshot_id,
                   COUNT(pt.track_id) as track_count
            FROM playlists p
            LEFT JOIN playlist_tracks pt ON pt.playlist_id = p.id AND pt.provider = p.provider
            GROUP BY p.id, p.provider, p.name, p.owner_id, p.owner_name, p.snapshot_id
            ORDER BY p.name
            """
            rows = self.conn.execute(sql).fetchall()
        
        return [PlaylistRow.from_row(row) for row in rows]

    def get_playlist_by_id(self, playlist_id: str, provider: str | None = None) -> Optional[PlaylistRow]:
        if provider is None:
            raise ValueError("provider parameter is required")
        sql = "SELECT id, provider, name, owner_id, owner_name, snapshot_id, 0 as track_count FROM playlists WHERE id=? AND provider=?"
        cur = self.conn.execute(sql, (playlist_id, provider))
        row = cur.fetchone()
        return PlaylistRow.from_row(row) if row else None

    def count_playlist_tracks(self, playlist_id: str, provider: str | None = None) -> int:
        if provider is None:
            raise ValueError("provider parameter is required")
        cursor = self.conn.execute("SELECT COUNT(*) FROM playlist_tracks WHERE playlist_id=? AND provider=?", (playlist_id, provider))
        return cursor.fetchone()[0]
    
    def get_playlists_containing_tracks(self, track_ids: List[str], provider: str | None = None) -> List[str]:
        """Get list of playlist IDs that contain any of the specified tracks.
        
        Args:
            track_ids: List of track IDs to search for
            provider: Provider filter (default: 'spotify')
            
        Returns:
            List of distinct playlist IDs containing at least one of the tracks
        """
        if not track_ids:
            return []
        
        provider = provider if provider is not None else 'spotify'
        
        # Use parameterized query with IN clause
        placeholders = ','.join('?' * len(track_ids))
        sql = f"""
        SELECT DISTINCT playlist_id
        FROM playlist_tracks
        WHERE track_id IN ({placeholders})
          AND provider = ?
        ORDER BY playlist_id
        """
        
        params = list(track_ids) + [provider]
        rows = self.conn.execute(sql, params).fetchall()
        return [row[0] for row in rows]
    
    # --- Repository methods for matching engine ---
    
    def get_all_tracks(self, provider: str | None = None) -> List[TrackRow]:
        """Get all tracks with full metadata for matching."""
        if provider:
            sql = """
            SELECT id, provider, name, artist, album, year, isrc, duration_ms, normalized, album_id, artist_id
            FROM tracks
            WHERE provider=?
            ORDER BY artist, album, name
            """
            rows = self.conn.execute(sql, (provider,)).fetchall()
        else:
            sql = """
            SELECT id, provider, name, artist, album, year, isrc, duration_ms, normalized, album_id, artist_id
            FROM tracks
            ORDER BY artist, album, name
            """
            rows = self.conn.execute(sql).fetchall()
        
        return [TrackRow.from_row(row) for row in rows]
    
    def get_all_library_files(self) -> List[LibraryFileRow]:
        """Get all library files with full metadata for matching."""
        sql = """
        SELECT id, path, title, artist, album, year, duration, normalized, size, mtime, partial_hash, bitrate_kbps
        FROM library_files
        ORDER BY artist, album, title
        """
        rows = self.conn.execute(sql).fetchall()
        return [LibraryFileRow.from_row(row) for row in rows]
    
    def get_tracks_by_ids(self, track_ids: List[str], provider: str | None = None) -> List[TrackRow]:
        """Get specific tracks by their IDs."""
        if not track_ids:
            return []
        
        placeholders = ','.join('?' * len(track_ids))
        if provider:
            sql = f"""
            SELECT id, provider, name, artist, album, year, isrc, duration_ms, normalized, album_id, artist_id
            FROM tracks
            WHERE id IN ({placeholders}) AND provider=?
            """
            rows = self.conn.execute(sql, track_ids + [provider]).fetchall()
        else:
            sql = f"""
            SELECT id, provider, name, artist, album, year, isrc, duration_ms, normalized, album_id, artist_id
            FROM tracks
            WHERE id IN ({placeholders})
            """
            rows = self.conn.execute(sql, track_ids).fetchall()
        
        return [TrackRow.from_row(row) for row in rows]
    
    def get_library_files_by_ids(self, file_ids: List[int]) -> List[LibraryFileRow]:
        """Get specific library files by their IDs."""
        if not file_ids:
            return []
        
        placeholders = ','.join('?' * len(file_ids))
        sql = f"""
        SELECT id, path, title, artist, album, year, duration, normalized, size, mtime, partial_hash, bitrate_kbps
        FROM library_files
        WHERE id IN ({placeholders})
        """
        rows = self.conn.execute(sql, file_ids).fetchall()
        return [LibraryFileRow.from_row(row) for row in rows]
    
    def get_unmatched_tracks(self, provider: str | None = None) -> List[TrackRow]:
        """Get all tracks that don't have matches yet."""
        if provider:
            sql = """
            SELECT t.id, t.provider, t.name, t.artist, t.album, t.year, t.isrc, t.duration_ms, t.normalized, t.album_id, t.artist_id
            FROM tracks t
            LEFT JOIN matches m ON m.track_id = t.id AND m.provider = t.provider
            WHERE m.track_id IS NULL AND t.provider=?
            ORDER BY t.artist, t.album, t.name
            """
            rows = self.conn.execute(sql, (provider,)).fetchall()
        else:
            sql = """
            SELECT t.id, t.provider, t.name, t.artist, t.album, t.year, t.isrc, t.duration_ms, t.normalized, t.album_id, t.artist_id
            FROM tracks t
            LEFT JOIN matches m ON m.track_id = t.id AND m.provider = t.provider
            WHERE m.track_id IS NULL
            ORDER BY t.artist, t.album, t.name
            """
            rows = self.conn.execute(sql).fetchall()
        
        return [TrackRow.from_row(row) for row in rows]
    
    def get_unmatched_library_files(self) -> List[LibraryFileRow]:
        """Get all library files that don't have matches yet."""
        sql = """
        SELECT f.id, f.path, f.title, f.artist, f.album, f.year, f.duration, f.normalized, f.size, f.mtime, f.partial_hash, f.bitrate_kbps
        FROM library_files f
        LEFT JOIN matches m ON m.file_id = f.id
        WHERE m.file_id IS NULL
        ORDER BY f.artist, f.album, f.title
        """
        rows = self.conn.execute(sql).fetchall()
        return [LibraryFileRow.from_row(row) for row in rows]
    
    def delete_matches_by_track_ids(self, track_ids: List[str]):
        """Delete all matches for given track IDs."""
        if not track_ids:
            return
        
        placeholders = ','.join('?' * len(track_ids))
        sql = f"DELETE FROM matches WHERE track_id IN ({placeholders})"
        self._execute_with_lock_handling(sql, track_ids)
    
    def delete_matches_by_file_ids(self, file_ids: List[int]):
        """Delete all matches for given file IDs."""
        if not file_ids:
            return
        
        placeholders = ','.join('?' * len(file_ids))
        sql = f"DELETE FROM matches WHERE file_id IN ({placeholders})"
        self._execute_with_lock_handling(sql, file_ids)
    
    def count_distinct_library_albums(self) -> int:
        """Count unique albums in library files."""
        cursor = self.conn.execute("SELECT COUNT(DISTINCT album) FROM library_files WHERE album IS NOT NULL AND album != ''")
        return cursor.fetchone()[0]
    
    def get_match_confidence_counts(self) -> Dict[str, int]:
        """Get count of matches grouped by confidence level."""
        sql = "SELECT method, COUNT(*) FROM matches GROUP BY method"
        rows = self.conn.execute(sql).fetchall()
        return {row[0]: row[1] for row in rows}
    
    def get_playlist_occurrence_counts(self, track_ids: List[str]) -> Dict[str, int]:
        """Get count of playlists each track appears in."""
        if not track_ids:
            return {}
        
        placeholders = ','.join('?' * len(track_ids))
        sql = f"""
        SELECT track_id, COUNT(DISTINCT playlist_id) as count
        FROM playlist_tracks
        WHERE track_id IN ({placeholders})
        GROUP BY track_id
        """
        rows = self.conn.execute(sql, track_ids).fetchall()
        counts = {row[0]: row[1] for row in rows}
        
        # Fill in zero counts for tracks not in any playlist
        for track_id in track_ids:
            if track_id not in counts:
                counts[track_id] = 0
        
        return counts
    
    def get_liked_track_ids(self, track_ids: List[str], provider: str | None = None) -> List[str]:
        """Get which of the given track IDs are in liked_tracks."""
        if not track_ids:
            return []
        
        placeholders = ','.join('?' * len(track_ids))
        if provider:
            sql = f"SELECT track_id FROM liked_tracks WHERE track_id IN ({placeholders}) AND provider=?"
            rows = self.conn.execute(sql, track_ids + [provider]).fetchall()
        else:
            sql = f"SELECT track_id FROM liked_tracks WHERE track_id IN ({placeholders})"
            rows = self.conn.execute(sql, track_ids).fetchall()
        
        return [row[0] for row in rows]
    
    # --- Export service methods ---
    
    def list_playlists(self, playlist_ids: Optional[List[str]] = None, provider: str | None = None) -> List[Dict[str, Any]]:
        """List playlists with stable ordering.
        
        Returns playlists sorted by owner_name then name for consistent export order.
        Provider-aware to prevent cross-provider data leakage.
        """
        if provider is None:
            provider = 'spotify'  # Default for backward compat
        
        if playlist_ids:
            placeholders = ','.join('?' * len(playlist_ids))
            sql = f"""
            SELECT id, name, owner_id, owner_name
            FROM playlists
            WHERE id IN ({placeholders}) AND provider = ?
            ORDER BY owner_name, name
            """
            params = list(playlist_ids) + [provider]
            rows = self.conn.execute(sql, params).fetchall()
        else:
            sql = """
            SELECT id, name, owner_id, owner_name
            FROM playlists
            WHERE provider = ?
            ORDER BY owner_name, name
            """
            rows = self.conn.execute(sql, (provider,)).fetchall()
        
        return [dict(row) for row in rows]
    
    def get_playlist_tracks_with_local_paths(self, playlist_id: str, provider: str | None = None) -> List[Dict[str, Any]]:
        """Get playlist tracks with matched local file paths (best match only per track).
        
        Uses window function to select only the highest-scoring match per track.
        All joins are provider-aware to prevent cross-provider data leakage.
        """
        if provider is None:
            provider = 'spotify'  # Default for backward compat
        
        # Use window function to rank matches by score (highest first)
        # Then filter to only the best match (rn=1) in the outer query
        sql = """
        WITH ranked_matches AS (
            SELECT 
                m.track_id,
                m.file_id,
                m.score,
                ROW_NUMBER() OVER (PARTITION BY m.track_id ORDER BY m.score DESC) AS rn
            FROM matches m
            WHERE m.provider = ?
        )
        SELECT 
            pt.position,
            t.id as track_id,
            t.name,
            t.artist,
            t.album,
            t.duration_ms,
            lf.path AS local_path
        FROM playlist_tracks pt
        LEFT JOIN tracks t ON t.id = pt.track_id AND t.provider = pt.provider
        LEFT JOIN ranked_matches rm ON rm.track_id = pt.track_id AND rm.rn = 1
        LEFT JOIN library_files lf ON lf.id = rm.file_id
        WHERE pt.playlist_id = ? AND pt.provider = ?
        ORDER BY pt.position
        """
        
        rows = self.conn.execute(sql, (provider, playlist_id, provider)).fetchall()
        return [dict(row) | {'position': row['position']} for row in rows]
    
    def get_liked_tracks_with_local_paths(self, provider: str | None = None) -> List[Dict[str, Any]]:
        """Get liked tracks with matched local file paths (best match only per track), newest first.
        
        Uses window function to select only the highest-scoring match per track.
        All joins are provider-aware to prevent cross-provider data leakage.
        Ordered by added_at DESC (newest first) to match Spotify's behavior.
        """
        if provider is None:
            provider = 'spotify'  # Default for backward compat
        
        # Use window function to rank matches by score (highest first)
        # Then filter to only the best match (rn=1) in the outer query
        sql = """
        WITH ranked_matches AS (
            SELECT 
                m.track_id,
                m.file_id,
                m.score,
                ROW_NUMBER() OVER (PARTITION BY m.track_id ORDER BY m.score DESC) AS rn
            FROM matches m
            WHERE m.provider = ?
        )
        SELECT 
            lt.added_at,
            t.id as track_id,
            t.name,
            t.artist,
            t.album,
            t.duration_ms,
            lf.path AS local_path
        FROM liked_tracks lt
        LEFT JOIN tracks t ON t.id = lt.track_id AND t.provider = lt.provider
        LEFT JOIN ranked_matches rm ON rm.track_id = lt.track_id AND rm.rn = 1
        LEFT JOIN library_files lf ON lf.id = rm.file_id
        WHERE lt.provider = ?
        ORDER BY lt.added_at DESC
        """
        
        rows = self.conn.execute(sql, (provider, provider)).fetchall()
        return [dict(row) for row in rows]
    
    def get_track_by_id(self, track_id: str, provider: str | None = None) -> Optional[TrackRow]:
        """Get a single track by ID."""
        if provider is None:
            provider = 'spotify'  # Default for backward compat
        
        sql = """
        SELECT id, provider, name, artist, album, year, isrc, duration_ms, normalized, album_id, artist_id
        FROM tracks
        WHERE id = ? AND provider = ?
        """
        row = self.conn.execute(sql, (track_id, provider)).fetchone()
        return TrackRow.from_row(row) if row else None
    
    def get_match_for_track(self, track_id: str, provider: str | None = None) -> Optional[Dict[str, Any]]:
        """Get match details for a track if it exists."""
        if provider is None:
            provider = 'spotify'  # Default for backward compat
        
        sql = """
        SELECT 
            m.file_id, 
            m.score, 
            m.method,
            f.path, 
            f.title, 
            f.artist, 
            f.album, 
            f.duration, 
            f.normalized,
            f.year
        FROM matches m
        JOIN library_files f ON m.file_id = f.id
        WHERE m.track_id = ? AND m.provider = ?
        """
        row = self.conn.execute(sql, (track_id, provider)).fetchone()
        return dict(row) if row else None

    def close(self):
        if not self._closed:
            try:
                self.conn.commit()
                self.conn.close()
            except Exception:
                pass
            finally:
                self._closed = True

__all__ = ["Database"]
