from __future__ import annotations
import time

class StubSpotifyClient:
    """Minimal stub of SpotifyClient used for E2E tests (no network)."""
    def __init__(self, token: str):  # signature compatibility
        self.token = token

    def playlist_items(self, playlist_id: str, verbose: bool = True):  # returns iterable of track item dicts
        return [
            {
                'added_at': '2025-01-01T00:00:00Z',
                'track': {
                    'id': 'track_stub_1',
                    'name': 'Stub Track',
                    'artists': [{'name': 'Stub Artist'}],
                    'album': {'name': 'Stub Album', 'release_date': '2024-01-01'},
                    'external_ids': {'isrc': 'ISRCSTUB1'},
                    'duration_ms': 180000,
                }
            }
        ]

    def _get(self, path: str):  # playlist metadata fetch
        if path.startswith('/playlists/'):
            pid = path.split('/')[-1]
            return {
                'id': pid,
                'name': 'Stub Playlist',
                'snapshot_id': 'snap123',
                'owner': {'id': 'owner123', 'display_name': 'Owner Name'},
            }
        return {}

# Stub SpotifyAuth.get_token override helper
class StubAuth:
    def __init__(self, *a, **k):
        pass
    def get_token(self, force: bool = False):
        return {'access_token': 'stub-token', 'expires_at': time.time() + 3600}
