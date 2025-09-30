from pathlib import Path
from types import SimpleNamespace
from spx.db import Database
from spx.ingest.library import scan_library


def test_library_scan_basic(tmp_path, monkeypatch):
    # Create a fake music file
    music_file = tmp_path / 'music' / 'test.mp3'
    music_file.parent.mkdir(parents=True)
    music_file.write_bytes(b'ID3' + b'\0'*1024)

    # Mock iter_music_files to return our single file
    from spx.ingest import library as libmod

    def fake_iter_music_files(paths, extensions, ignore_patterns, follow_symlinks):
        yield music_file

    monkeypatch.setattr(libmod, 'iter_music_files', fake_iter_music_files)

    # Mock mutagen.File to return object with tags and length
    class FakeAudio:
        def __init__(self):
            self.tags = {'title': 'Scan Song', 'artist': 'Scan Artist', 'album': 'Scan Album'}
            self.info = SimpleNamespace(length=123.45)

    import mutagen
    monkeypatch.setattr(mutagen, 'File', lambda p: FakeAudio())

    db = Database(tmp_path / 'db.sqlite')
    cfg = {
        'library': {
            'paths': [str(music_file.parent)],
            'extensions': ['.mp3'],
            'ignore_patterns': [],
            'follow_symlinks': False,
        }
    }
    scan_library(db, cfg)
    row = db.conn.execute('SELECT title, artist, album, normalized FROM library_files').fetchone()
    assert row is not None
    assert row['title'] == 'Scan Song'
    assert row['artist'] == 'Scan Artist'
    assert row['album'] == 'Scan Album'
    assert 'scan song' in row['normalized']