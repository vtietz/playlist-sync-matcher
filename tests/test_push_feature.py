from __future__ import annotations
import pytest
from pathlib import Path
from psm.db import Database
from psm.push.m3u_parser import parse_m3u_paths
from psm.services.push_service import push_playlist


class StubCapabilities:
    def __init__(self, replace_playlist: bool):
        self.replace_playlist = replace_playlist


class StubClient:
    """Stub Spotify-like client for push tests (no network)."""
    def __init__(self, remote_ids, owner_id='me', replace_cap=True):
        self._remote_ids = list(remote_ids)
        self.replaced_with = None
        self.owner_id = owner_id
        self.capabilities = StubCapabilities(replace_cap)

    def playlist_items(self, playlist_id: str, verbose: bool = False):  # mimic real structure
        return [{'track': {'id': tid}} for tid in self._remote_ids]

    def get_playlist(self, playlist_id: str):
        return {'name': 'Test Playlist', 'owner': {'id': self.owner_id, 'display_name': 'Owner'}}

    def replace_playlist_tracks_remote(self, playlist_id: str, track_ids):
        self.replaced_with = list(track_ids)
        self._remote_ids = list(track_ids)


def _setup_db(tmp_path: Path) -> Database:
    db_path = tmp_path / 'test.db'
    db = Database(db_path)
    return db


def test_m3u_parser_basic(tmp_path: Path):
    p1 = tmp_path / 'a.mp3'
    p2 = tmp_path / 'b.mp3'
    p1.write_text('x')
    p2.write_text('y')
    playlist = tmp_path / 'list.m3u8'
    playlist.write_text('#EXTM3U\n# Comment\n#EXTINF:123,Meta\n' + str(p1) + '\n' + p2.name + '\n')
    paths = parse_m3u_paths(playlist)
    assert len(paths) == 2
    assert paths[0].endswith('a.mp3')
    assert paths[1].endswith('b.mp3')


def test_push_db_mode_no_change(tmp_path: Path):
    db = _setup_db(tmp_path)
    # current user
    db.set_meta('current_user_id', 'me')
    # playlist meta
    db.upsert_playlist('pl1', 'My', snapshot_id='s1', owner_id='me', owner_name='Me')
    # tracks & ordering desired
    for tid in ['t1', 't2']:
        db.upsert_track({'id': tid, 'name': tid, 'album': None, 'artist': 'A', 'isrc': None, 'duration_ms': 1000, 'normalized': tid, 'year': None})
    db.replace_playlist_tracks('pl1', [(0, 't1', None), (1, 't2', None)])
    db.commit()
    client = StubClient(['t1', 't2'])
    preview = push_playlist(db=db, playlist_id='pl1', client=client, m3u_path=None, apply=False)
    assert preview.changed is False
    assert preview.applied is False
    assert client.replaced_with is None


def test_push_db_mode_apply_change(tmp_path: Path):
    db = _setup_db(tmp_path)
    db.set_meta('current_user_id', 'me')
    db.upsert_playlist('pl1', 'My', snapshot_id='s1', owner_id='me', owner_name='Me')
    for tid in ['t1', 't2', 't3']:
        db.upsert_track({'id': tid, 'name': tid, 'album': None, 'artist': 'A', 'isrc': None, 'duration_ms': 1000, 'normalized': tid, 'year': None})
    db.replace_playlist_tracks('pl1', [(0, 't1', None), (1, 't2', None), (2, 't3', None)])
    db.commit()
    client = StubClient(['t3', 't2', 't1'])  # reversed remote ordering
    preview = push_playlist(db=db, playlist_id='pl1', client=client, m3u_path=None, apply=True)
    assert preview.changed is True
    assert preview.applied is True
    assert client.replaced_with == ['t1', 't2', 't3']


def test_push_capability_enforced(tmp_path: Path):
    db = _setup_db(tmp_path)
    db.set_meta('current_user_id', 'me')
    db.upsert_playlist('pl1', 'My', snapshot_id='s1', owner_id='me', owner_name='Me')
    db.upsert_track({'id': 't1', 'name': 't1', 'album': None, 'artist': 'A', 'isrc': None, 'duration_ms': 1000, 'normalized': 't1', 'year': None})
    db.replace_playlist_tracks('pl1', [(0, 't1', None)])
    db.commit()
    # Client that does NOT advertise replace capability
    client = StubClient(['t1', 'x2'], replace_cap=False)
    with pytest.raises(RuntimeError):
        push_playlist(db=db, playlist_id='pl1', client=client, m3u_path=None, apply=True)


def test_push_file_mode_with_unresolved(tmp_path: Path):
    db = _setup_db(tmp_path)
    db.set_meta('current_user_id', 'me')
    db.upsert_playlist('pl1', 'My', snapshot_id='s1', owner_id='me', owner_name='Me')
    # create local files and map one track
    file1 = tmp_path / 'song1.mp3'
    file1.write_text('data')
    unresolved_file = tmp_path / 'missing.mp3'
    # track mapping for file1 -> t1
    db.add_library_file({'path': str(file1), 'size': 1, 'mtime': 0.0, 'partial_hash': None, 'title': 's1', 'album': None, 'artist': 'A', 'duration': 1.0, 'normalized': 's1', 'year': None, 'bitrate_kbps': 320})
    fid = db.conn.execute('SELECT id FROM library_files WHERE path=?', (str(file1),)).fetchone()[0]
    db.upsert_track({'id': 't1', 'name': 's1', 'album': None, 'artist': 'A', 'isrc': None, 'duration_ms': 1000, 'normalized': 's1', 'year': None})
    db.add_match('t1', fid, 1.0, 'exact')
    # create m3u file referencing both existing and missing path
    m3u = tmp_path / 'pl1.m3u'
    m3u.write_text('#EXTM3U\n' + str(file1) + '\n' + str(unresolved_file) + '\n')
    client = StubClient([])
    preview = push_playlist(db=db, playlist_id='pl1', client=client, m3u_path=m3u, apply=False)
    assert preview.unmatched_file_paths == 1
    assert preview.new_count == 1  # only one track id resolved


def test_push_permission_denied(tmp_path: Path):
    db = _setup_db(tmp_path)
    db.set_meta('current_user_id', 'me')
    db.upsert_playlist('pl1', 'Foreign', snapshot_id='s1', owner_id='other', owner_name='Other')
    client = StubClient(['t1'], owner_id='other')
    with pytest.raises(PermissionError):
        push_playlist(db=db, playlist_id='pl1', client=client, m3u_path=None, apply=False)
