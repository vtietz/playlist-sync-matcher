from pathlib import Path
from psm.db import Database
from psm.reporting.generator import compute_album_completeness


def _insert_track(db: Database, tid: str, artist: str, album: str, name: str):
    db.upsert_track({
        'id': tid,
        'name': name,
        'album': album,
        'artist': artist,
        'isrc': None,
        'duration_ms': 1000,
        'normalized': f'{name.lower()} {artist.lower()}'
    }, provider='spotify')


def test_album_completeness(tmp_path: Path):
    db = Database(tmp_path / 'test.db')
    # Album A (complete): 2 tracks, both matched
    _insert_track(db, 'a1', 'ArtistA', 'AlbumA', 'Song1')
    _insert_track(db, 'a2', 'ArtistA', 'AlbumA', 'Song2')
    # Album B (partial): 2 tracks, 1 matched
    _insert_track(db, 'b1', 'ArtistB', 'AlbumB', 'Song1')
    _insert_track(db, 'b2', 'ArtistB', 'AlbumB', 'Song2')
    # Album C (missing): 2 tracks, 0 matched
    _insert_track(db, 'c1', 'ArtistC', 'AlbumC', 'Song1')
    _insert_track(db, 'c2', 'ArtistC', 'AlbumC', 'Song2')
    # Insert library files & matches for A(2) and B(1)
    # library file helper
    def add_file(path_name, norm):
        db.add_library_file({
            'path': path_name,
            'size': 1000,
            'mtime': 0.0,
            'partial_hash': 'x',
            'title': 't',
            'album': 'alb',
            'artist': 'art',
            'duration': 1.0,
            'normalized': norm,
        })
    add_file('a1.mp3', 'song1 artista')
    add_file('a2.mp3', 'song2 artista')
    add_file('b1.mp3', 'song1 artistb')
    # Link matches manually
    # retrieve file ids
    file_rows = db.conn.execute('SELECT id, path FROM library_files').fetchall()
    file_map = {r['path']: r['id'] for r in file_rows}
    db.add_match('a1', file_map['a1.mp3'], 1.0, 'exact', provider='spotify')
    db.add_match('a2', file_map['a2.mp3'], 1.0, 'exact', provider='spotify')
    db.add_match('b1', file_map['b1.mp3'], 1.0, 'exact', provider='spotify')
    db.commit()
    rows = list(compute_album_completeness(db))
    status_map = {(r['artist'], r['album']): r for r in rows}
    assert status_map[('ArtistA', 'AlbumA')]['status'] == 'COMPLETE'
    assert status_map[('ArtistB', 'AlbumB')]['status'] == 'PARTIAL'
    assert status_map[('ArtistC', 'AlbumC')]['status'] == 'MISSING'