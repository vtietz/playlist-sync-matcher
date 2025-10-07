from pathlib import Path
from psm.db import Database
from psm.services.match_service import run_matching


def test_match_and_store_basic(tmp_path: Path):
    db_path = tmp_path / 'test.db'
    db = Database(db_path)
    # Insert a track and a library file with identical semantic metadata
    track = {
        'id': 'track1',
        'name': 'Song Title',
        'album': 'Album',
        'artist': 'Artist',
        'isrc': None,
        'duration_ms': 123000,
        'normalized': 'song title artist'
    }
    db.upsert_track(track, provider='spotify')
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

    result = run_matching(db, config={})
    assert result.matched == 1
    row = db.conn.execute("SELECT track_id, file_id, method, score FROM matches").fetchone()
    assert row is not None
    assert row['track_id'] == 'track1'
    # Scoring engine stores method as score:<confidence>
    assert row['method'].startswith('score:')
    # Score should be reasonably high (>=0.75 scaled)
    assert row['score'] >= 0.75
