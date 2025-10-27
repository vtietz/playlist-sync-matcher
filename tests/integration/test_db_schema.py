from pathlib import Path
from psm.db import Database


def test_schema_tables(tmp_path: Path):
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    cur = db.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    names = {r[0] for r in cur.fetchall()}
    for needed in {"playlists", "playlist_tracks", "tracks", "liked_tracks", "library_files", "matches", "meta"}:
        assert needed in names
    db.close()
