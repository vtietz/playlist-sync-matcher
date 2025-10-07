from pathlib import Path
from psm.db import Database
from psm.services.match_service import run_matching


def test_scoring_integration_basic(tmp_path: Path):
    db_path = tmp_path / 'test.db'
    db = Database(db_path)
    track = {
        'id': 'track1',
        'name': 'Exact Song',
        'album': 'Some Album',
        'artist': 'Great Artist',
        'isrc': 'ISRC1',
        'duration_ms': 200000,
        'normalized': 'exact song great artist'
    }
    db.upsert_track(track, provider='spotify')
    db.add_library_file({
        'path': 'great.mp3',
        'size': 1111,
        'mtime': 0.0,
        'partial_hash': 'abc',
        'title': 'Exact Song',
        'album': 'Some Album',
        'artist': 'Great Artist',
        'duration': 200.0,
        'normalized': 'exact song great artist'
    })
    db.commit()

    cfg = {
        'matching': {
            'duration_tolerance': 2.0,
        },
        'spotify': {'client_id': None},
        'export': {},
        'reports': {},
        'library': {},
        'database': {'path': str(db_path)},
        'log_level': 'ERROR'
    }

    result = run_matching(db, cfg)
    assert result.matched == 1
    row = db.conn.execute('SELECT method, score FROM matches WHERE track_id=?', ('track1',)).fetchone()
    assert row is not None
    assert row['method'].startswith('score:')
