from pathlib import Path
from spx.db import Database
from spx.ingest.spotify import ingest_playlists


class MockClient:
    def __init__(self, playlists, items_map):
        self._playlists = playlists
        self._items_map = items_map
        self.calls = {'playlist_items': 0}

    def current_user_playlists(self):
        for pl in self._playlists:
            yield pl

    def playlist_items(self, pid: str):
        self.calls['playlist_items'] += 1
        return self._items_map.get(pid, [])


def _track_item(tid: str, name: str):
    return {
        'added_at': '2024-01-01T00:00:00Z',
        'track': {
            'id': tid,
            'name': name,
            'album': {'name': 'Album'},
            'artists': [{'name': 'Artist'}],
            'external_ids': {'isrc': None},
            'duration_ms': 1000,
        }
    }


def test_ingest_playlists_snapshot_gating(tmp_path: Path):
    db = Database(tmp_path / 'p.db')
    playlists = [{'id': 'pl1', 'name': 'List1', 'snapshot_id': 'snap1'}]
    items_map = {'pl1': [_track_item('t1', 'Song1'), _track_item('t2', 'Song2')]}
    client = MockClient(playlists, items_map)
    # First ingest -> should fetch items
    ingest_playlists(db, client)
    assert client.calls['playlist_items'] == 1
    row = db.conn.execute('SELECT COUNT(*) c FROM playlist_tracks WHERE playlist_id="pl1"').fetchone()
    assert row['c'] == 2
    # Second ingest with same snapshot -> should skip
    ingest_playlists(db, client)
    assert client.calls['playlist_items'] == 1  # unchanged
    # Change snapshot id -> should fetch again and replace
    client._playlists[0]['snapshot_id'] = 'snap2'
    ingest_playlists(db, client)
    assert client.calls['playlist_items'] == 2
    # Replace logic: still 2 tracks
    row2 = db.conn.execute('SELECT COUNT(*) c FROM playlist_tracks WHERE playlist_id="pl1"').fetchone()
    assert row2['c'] == 2