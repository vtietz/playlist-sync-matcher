from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Iterable, Sequence, Any, Dict, Tuple, Optional

SCHEMA = [
    "PRAGMA journal_mode=WAL;",
    "CREATE TABLE IF NOT EXISTS playlists (id TEXT PRIMARY KEY, name TEXT NOT NULL, snapshot_id TEXT, last_full_ingest TIMESTAMP, owner_id TEXT, owner_name TEXT);",
    "CREATE TABLE IF NOT EXISTS playlist_tracks (playlist_id TEXT NOT NULL, position INTEGER NOT NULL, track_id TEXT NOT NULL, added_at TEXT, PRIMARY KEY(playlist_id, position));",
    # year column will be added via migration if missing
    "CREATE TABLE IF NOT EXISTS tracks (id TEXT PRIMARY KEY, name TEXT, album TEXT, artist TEXT, isrc TEXT, duration_ms INTEGER, normalized TEXT);",
    "CREATE TABLE IF NOT EXISTS liked_tracks (track_id TEXT PRIMARY KEY, added_at TEXT);",
    # year column will be added via migration if missing
    "CREATE TABLE IF NOT EXISTS library_files (id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT UNIQUE, size INTEGER, mtime REAL, partial_hash TEXT, title TEXT, album TEXT, artist TEXT, duration REAL, normalized TEXT);",
    "CREATE TABLE IF NOT EXISTS matches (track_id TEXT NOT NULL, file_id INTEGER NOT NULL, score REAL NOT NULL, method TEXT NOT NULL, PRIMARY KEY(track_id, file_id));",
    "CREATE INDEX IF NOT EXISTS idx_tracks_isrc ON tracks(isrc);",
    "CREATE INDEX IF NOT EXISTS idx_tracks_normalized ON tracks(normalized);",
    "CREATE INDEX IF NOT EXISTS idx_library_files_normalized ON library_files(normalized);",
    "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);",
]


class Database:
    def __init__(self, path: Path):
        self.path = path
        if not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        # Increase timeout to better tolerate brief writer contention, especially on Windows.
        self.conn = sqlite3.connect(path, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self._closed = False
        self._init_schema()

    # Context manager support ensures connections are always closed even if an exception bubbles up.
    def __enter__(self) -> "Database":  # pragma: no cover - trivial
        return self

    def __exit__(self, exc_type, exc, tb):  # pragma: no cover - trivial
        self.close()

    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        for stmt in SCHEMA:
            cur.execute(stmt)
        self.conn.commit()
        # Migrations: add 'year' columns if not exist
        self._ensure_column('tracks', 'year', 'INTEGER')
        self._ensure_column('library_files', 'year', 'INTEGER')
        # Migrations: add owner info to playlists
        self._ensure_column('playlists', 'owner_id', 'TEXT')
        self._ensure_column('playlists', 'owner_name', 'TEXT')

    def _ensure_column(self, table: str, column: str, col_type: str):
        cur = self.conn.execute(f"PRAGMA table_info({table})")
        cols = [r[1] for r in cur.fetchall()]
        if column not in cols:
            self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            self.conn.commit()

    def upsert_playlist(self, pid: str, name: str, snapshot_id: str | None, owner_id: str | None = None, owner_name: str | None = None) -> None:
        self.conn.execute(
            "INSERT INTO playlists(id,name,snapshot_id,owner_id,owner_name) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name, snapshot_id=excluded.snapshot_id, owner_id=excluded.owner_id, owner_name=excluded.owner_name",
            (pid, name, snapshot_id, owner_id, owner_name),
        )
        self.conn.commit()

    def playlist_snapshot_changed(self, pid: str, snapshot_id: str) -> bool:
        cur = self.conn.execute("SELECT snapshot_id FROM playlists WHERE id=?", (pid,))
        row = cur.fetchone()
        if not row:
            return True
        return row[0] != snapshot_id

    def replace_playlist_tracks(self, pid: str, tracks: Sequence[Tuple[int, str, str | None]]):
        # tracks: (position, track_id, added_at)
        self.conn.execute("DELETE FROM playlist_tracks WHERE playlist_id=?", (pid,))
        self.conn.executemany(
            "INSERT INTO playlist_tracks(playlist_id, position, track_id, added_at) VALUES(?,?,?,?)",
            [(pid, pos, tid, added) for (pos, tid, added) in tracks],
        )
        self.conn.commit()

    def upsert_track(self, track: Dict[str, Any]):
        self.conn.execute(
            "INSERT INTO tracks(id,name,album,artist,isrc,duration_ms,normalized,year) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name, album=excluded.album, artist=excluded.artist, isrc=excluded.isrc, duration_ms=excluded.duration_ms, normalized=excluded.normalized, year=excluded.year",
            (
                track.get("id"),
                track.get("name"),
                track.get("album"),
                track.get("artist"),
                track.get("isrc"),
                track.get("duration_ms"),
                track.get("normalized"),
                track.get("year"),
            ),
        )

    def upsert_liked(self, track_id: str, added_at: str):
        self.conn.execute(
            "INSERT INTO liked_tracks(track_id,added_at) VALUES(?,?) ON CONFLICT(track_id) DO UPDATE SET added_at=excluded.added_at",
            (track_id, added_at),
        )

    def commit(self):
        self.conn.commit()

    def add_library_file(self, data: Dict[str, Any]):
        self.conn.execute(
            "INSERT INTO library_files(path,size,mtime,partial_hash,title,album,artist,duration,normalized,year) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET size=excluded.size, mtime=excluded.mtime, partial_hash=excluded.partial_hash, title=excluded.title, album=excluded.album, artist=excluded.artist, duration=excluded.duration, normalized=excluded.normalized, year=excluded.year",
            (
                data["path"],
                data.get("size"),
                data.get("mtime"),
                data.get("partial_hash"),
                data.get("title"),
                data.get("album"),
                data.get("artist"),
                data.get("duration"),
                data.get("normalized"),
                data.get("year"),
            ),
        )

    def add_match(self, track_id: str, file_id: int, score: float, method: str):
        self.conn.execute(
            "INSERT INTO matches(track_id,file_id,score,method) VALUES(?,?,?,?) ON CONFLICT(track_id,file_id) DO UPDATE SET score=excluded.score, method=excluded.method",
            (track_id, file_id, score, method),
        )

    def get_missing_tracks(self) -> Iterable[sqlite3.Row]:
        sql = """
        SELECT t.id, t.name, t.artist, t.album
        FROM tracks t
        LEFT JOIN matches m ON m.track_id = t.id
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

    # Summary count methods for reporting
    def count_playlists(self) -> int:
        """Return the total number of playlists."""
        cursor = self.conn.execute("SELECT COUNT(*) FROM playlists")
        return cursor.fetchone()[0]
    
    def count_unique_playlist_tracks(self) -> int:
        """Return the count of distinct track_ids in playlist_tracks."""
        cursor = self.conn.execute("SELECT COUNT(DISTINCT track_id) FROM playlist_tracks")
        return cursor.fetchone()[0]
    
    def count_liked_tracks(self) -> int:
        """Return the total number of liked tracks."""
        cursor = self.conn.execute("SELECT COUNT(*) FROM liked_tracks")
        return cursor.fetchone()[0]
    
    def count_tracks(self) -> int:
        """Return the total number of tracks."""
        cursor = self.conn.execute("SELECT COUNT(*) FROM tracks")
        return cursor.fetchone()[0]
    
    def count_library_files(self) -> int:
        """Return the total number of library files."""
        cursor = self.conn.execute("SELECT COUNT(*) FROM library_files")
        return cursor.fetchone()[0]
    
    def count_matches(self) -> int:
        """Return the total number of matches."""
        cursor = self.conn.execute("SELECT COUNT(*) FROM matches")
        return cursor.fetchone()[0]
    
    def get_all_playlists(self) -> list[sqlite3.Row]:
        """Return all playlists with their metadata and track counts.
        
        Returns:
            List of Row objects with columns: id, name, owner_id, owner_name, snapshot_id, track_count
        """
        sql = """
        SELECT 
            p.id, 
            p.name, 
            p.owner_id, 
            p.owner_name, 
            p.snapshot_id,
            COUNT(pt.track_id) as track_count
        FROM playlists p
        LEFT JOIN playlist_tracks pt ON pt.playlist_id = p.id
        GROUP BY p.id, p.name, p.owner_id, p.owner_name, p.snapshot_id
        ORDER BY p.name
        """
        return self.conn.execute(sql).fetchall()
    
    def get_playlist_by_id(self, playlist_id: str) -> Optional[sqlite3.Row]:
        """Get a single playlist by ID.
        
        Args:
            playlist_id: Spotify playlist ID
            
        Returns:
            Row with columns: id, name, owner_id, owner_name, snapshot_id, or None if not found
        """
        sql = "SELECT id, name, owner_id, owner_name, snapshot_id FROM playlists WHERE id=?"
        cur = self.conn.execute(sql, (playlist_id,))
        return cur.fetchone()
    
    def count_playlist_tracks(self, playlist_id: str) -> int:
        """Return the number of tracks in a specific playlist.
        
        Args:
            playlist_id: Spotify playlist ID
            
        Returns:
            Number of tracks in the playlist
        """
        cursor = self.conn.execute("SELECT COUNT(*) FROM playlist_tracks WHERE playlist_id=?", (playlist_id,))
        return cursor.fetchone()[0]

    def close(self):
        # Make close idempotent to avoid hangs when called multiple times
        if not self._closed:
            try:
                self.conn.commit()
                self.conn.close()
            except Exception:
                pass  # Already closed or in invalid state
            finally:
                self._closed = True

__all__ = ["Database"]
