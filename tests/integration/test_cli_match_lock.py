from pathlib import Path
from click.testing import CliRunner
from psm.cli import cli
from psm.db import Database


def test_cli_match_twice_no_lock(tmp_path: Path, test_config):
    db_path = tmp_path / "lock.db"
    test_config["database"]["path"] = str(db_path)
    db = Database(db_path)
    # Minimal data: one track + one file
    db.upsert_track(
        {
            "id": "t1",
            "name": "Song",
            "artist": "Artist",
            "album": "Album",
            "duration_ms": 100000,
            "normalized": "song artist",
            "isrc": None,
            "year": None,
        },
        provider="spotify",
    )
    db.add_library_file(
        {
            "path": "song.mp3",
            "size": 100,
            "mtime": 0.0,
            "partial_hash": "h",
            "title": "Song",
            "artist": "Artist",
            "album": "Album",
            "duration": 100.0,
            "normalized": "song artist",
            "year": None,
        }
    )
    db.commit()
    db.close()

    runner = CliRunner()
    r1 = runner.invoke(cli, ["match"], obj=test_config)
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(cli, ["match"], obj=test_config)
    assert r2.exit_code == 0, r2.output

    # Ensure only one match stored (idempotent behavior expected)
    db2 = Database(db_path)
    rows = db2.conn.execute("SELECT COUNT(*) c FROM matches").fetchone()
    assert rows["c"] == 1
    db2.close()

    print("✓ CLI match executed twice without database lock contention")
