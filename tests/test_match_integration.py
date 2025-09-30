from pathlib import Path
from spx.db import Database
from spx.match.engine import match_and_store


def test_match_and_store_basic(tmp_path: Path):
    db_path = tmp_path / 'test.db'
    db = Database(db_path)
    # Insert a track and a library file with identical normalized value
    track = {
        'id': 'track1',
        'name': 'Song Title',
        'album': 'Album',
        'artist': 'Artist',
        'isrc': None,
        'duration_ms': 123000,
        'normalized': 'song title artist'
    }
    db.upsert_track(track)
    db.add_library_file({
        'path': 'dummy.mp3',
        'size': 1000,
        'mtime': 0.0,
        'partial_hash': 'abc',
        'title': 'Song Title',
        'album': 'Album',
        'artist': 'Artist',
        'duration': 123.0,
        'normalized': 'song title artist'
    })
    db.commit()
    count = match_and_store(db, fuzzy_threshold=0.5)
    assert count == 1
    row = db.conn.execute("SELECT track_id, file_id, method FROM matches").fetchone()
    assert row is not None
    assert row['track_id'] == 'track1'
    assert row['method'] in ('exact', 'fuzzy')
