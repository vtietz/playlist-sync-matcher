from pathlib import Path
from psm.db import Database


def test_meta_set_get(tmp_path: Path):
    db = Database(tmp_path / 'm.db')
    assert db.get_meta('checkpoint') is None
    db.set_meta('checkpoint', '123')
    assert db.get_meta('checkpoint') == '123'
    db.set_meta('checkpoint', '456')
    assert db.get_meta('checkpoint') == '456'


def test_match_idempotent(tmp_path: Path):
    db = Database(tmp_path / 'm2.db')
    # Insert track + file
    db.upsert_track({'id': 't1', 'name': 'N', 'album': 'A', 'artist': 'R', 'isrc': None, 'duration_ms': 1000, 'normalized': 'n r'}, provider='spotify')
    db.add_library_file({'path': 'f1.mp3', 'size': 1, 'mtime': 0.0, 'partial_hash': 'h', 'title': 'N', 'album': 'A', 'artist': 'R', 'duration': 1.0, 'normalized': 'n r'})
    file_id = db.conn.execute('SELECT id FROM library_files').fetchone()['id']
    db.add_match('t1', file_id, 0.9, 'fuzzy', provider='spotify')
    db.add_match('t1', file_id, 1.0, 'exact', provider='spotify')  # update existing
    row = db.conn.execute('SELECT score, method FROM matches WHERE track_id=? AND file_id=?', ('t1', file_id)).fetchone()
    assert row['score'] == 1.0
    assert row['method'] == 'exact'