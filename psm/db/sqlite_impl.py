from __future__ import annotations
import sqlite3
import logging
from pathlib import Path
from typing import Iterable, Sequence, Any, Dict, Tuple, Optional
from .interface import DatabaseInterface

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
    "CREATE INDEX IF NOT EXISTS idx_tracks_isrc ON tracks(isrc);",
    "CREATE INDEX IF NOT EXISTS idx_tracks_normalized ON tracks(normalized);",
    "CREATE INDEX IF NOT EXISTS idx_library_files_normalized ON library_files(normalized);",
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

    def upsert_playlist(self, pid: str, name: str, snapshot_id: str | None, owner_id: str | None = None, owner_name: str | None = None, provider: str = 'spotify') -> None:
        self.conn.execute(
            "INSERT INTO playlists(id,provider,name,snapshot_id,owner_id,owner_name) VALUES(?,?,?,?,?,?) ON CONFLICT(id,provider) DO UPDATE SET name=excluded.name, snapshot_id=excluded.snapshot_id, owner_id=excluded.owner_id, owner_name=excluded.owner_name",
            (pid, provider, name, snapshot_id, owner_id, owner_name),
        )
        self.conn.commit()

    def playlist_snapshot_changed(self, pid: str, snapshot_id: str, provider: str = 'spotify') -> bool:
        cur = self.conn.execute("SELECT snapshot_id FROM playlists WHERE id=? AND provider=?", (pid, provider))
        row = cur.fetchone()
        if not row:
            return True
        return row[0] != snapshot_id

    def replace_playlist_tracks(self, pid: str, tracks: Sequence[Tuple[int, str, str | None]], provider: str = 'spotify'):
        self.conn.execute("DELETE FROM playlist_tracks WHERE playlist_id=? AND provider=?", (pid, provider))
        self.conn.executemany(
            "INSERT INTO playlist_tracks(playlist_id, provider, position, track_id, added_at) VALUES(?,?,?,?,?)",
            [(pid, provider, pos, tid, added) for (pos, tid, added) in tracks],
        )
        self.conn.commit()

    def upsert_track(self, track: Dict[str, Any], provider: str = 'spotify'):
        self.conn.execute(
            "INSERT INTO tracks(id,provider,name,album,artist,album_id,artist_id,isrc,duration_ms,normalized,year) VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id,provider) DO UPDATE SET name=excluded.name, album=excluded.album, artist=excluded.artist, album_id=excluded.album_id, artist_id=excluded.artist_id, isrc=excluded.isrc, duration_ms=excluded.duration_ms, normalized=excluded.normalized, year=excluded.year",
            (
                track.get("id"), provider, track.get("name"), track.get("album"), track.get("artist"),
                track.get("album_id"), track.get("artist_id"), track.get("isrc"), track.get("duration_ms"),
                track.get("normalized"), track.get("year"),
            ),
        )

    def upsert_liked(self, track_id: str, added_at: str, provider: str = 'spotify'):
        self.conn.execute(
            "INSERT INTO liked_tracks(track_id,provider,added_at) VALUES(?,?,?) ON CONFLICT(track_id,provider) DO UPDATE SET added_at=excluded.added_at",
            (track_id, provider, added_at),
        )

    def commit(self):
        self.conn.commit()

    def add_library_file(self, data: Dict[str, Any]):
        self.conn.execute(
            "INSERT INTO library_files(path,size,mtime,partial_hash,title,album,artist,duration,normalized,year,bitrate_kbps) VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET size=excluded.size, mtime=excluded.mtime, partial_hash=excluded.partial_hash, title=excluded.title, album=excluded.album, artist=excluded.artist, duration=excluded.duration, normalized=excluded.normalized, year=excluded.year, bitrate_kbps=excluded.bitrate_kbps",
            (
                data["path"], data.get("size"), data.get("mtime"), data.get("partial_hash"), data.get("title"),
                data.get("album"), data.get("artist"), data.get("duration"), data.get("normalized"),
                data.get("year"), data.get("bitrate_kbps"),
            ),
        )

    def add_match(self, track_id: str, file_id: int, score: float, method: str, provider: str = 'spotify'):
        self.conn.execute(
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

    def count_playlists(self, provider: str | None = 'spotify') -> int:
        if provider:
            cursor = self.conn.execute("SELECT COUNT(*) FROM playlists WHERE provider=?", (provider,))
        else:
            cursor = self.conn.execute("SELECT COUNT(*) FROM playlists")
        return cursor.fetchone()[0]

    def count_unique_playlist_tracks(self, provider: str | None = 'spotify') -> int:
        if provider:
            cursor = self.conn.execute("SELECT COUNT(DISTINCT track_id) FROM playlist_tracks WHERE provider=?", (provider,))
        else:
            cursor = self.conn.execute("SELECT COUNT(DISTINCT track_id) FROM playlist_tracks")
        return cursor.fetchone()[0]

    def count_liked_tracks(self, provider: str | None = 'spotify') -> int:
        if provider:
            cursor = self.conn.execute("SELECT COUNT(*) FROM liked_tracks WHERE provider=?", (provider,))
        else:
            cursor = self.conn.execute("SELECT COUNT(*) FROM liked_tracks")
        return cursor.fetchone()[0]

    def count_tracks(self, provider: str | None = 'spotify') -> int:
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

    def get_all_playlists(self, provider: str | None = 'spotify') -> list[sqlite3.Row]:
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
            return self.conn.execute(sql, (provider,)).fetchall()
        else:
            sql = """
            SELECT p.id, p.provider, p.name, p.owner_id, p.owner_name, p.snapshot_id,
                   COUNT(pt.track_id) as track_count
            FROM playlists p
            LEFT JOIN playlist_tracks pt ON pt.playlist_id = p.id AND pt.provider = p.provider
            GROUP BY p.id, p.provider, p.name, p.owner_id, p.owner_name, p.snapshot_id
            ORDER BY p.name
            """
            return self.conn.execute(sql).fetchall()

    def get_playlist_by_id(self, playlist_id: str, provider: str = 'spotify') -> Optional[sqlite3.Row]:
        sql = "SELECT id, provider, name, owner_id, owner_name, snapshot_id FROM playlists WHERE id=? AND provider=?"
        cur = self.conn.execute(sql, (playlist_id, provider))
        return cur.fetchone()

    def count_playlist_tracks(self, playlist_id: str, provider: str = 'spotify') -> int:
        cursor = self.conn.execute("SELECT COUNT(*) FROM playlist_tracks WHERE playlist_id=? AND provider=?", (playlist_id, provider))
        return cursor.fetchone()[0]

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
