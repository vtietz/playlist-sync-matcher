from __future__ import annotations
import requests
from typing import Iterator, Dict, Any, List
from tenacity import retry, stop_after_attempt, wait_random_exponential
from datetime import datetime

API_BASE = "https://api.spotify.com/v1"

class SpotifyClient:
    def __init__(self, token: str):
        self.token = token

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    @retry(stop=stop_after_attempt(5), wait=wait_random_exponential(multiplier=1, max=30))
    def _get(self, path: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        r = requests.get(API_BASE + path, headers=self._headers(), params=params, timeout=30)
        if r.status_code == 429:
            # Spotify returns Retry-After header
            ra = int(r.headers.get("Retry-After", "1"))
            import time
            time.sleep(ra)
            raise Exception("rate limit retry")
        r.raise_for_status()
        return r.json()

    def current_user_playlists(self) -> Iterator[Dict[str, Any]]:
        limit = 50
        offset = 0
        while True:
            data = self._get('/me/playlists', params={'limit': limit, 'offset': offset})
            items = data.get('items', [])
            for pl in items:
                yield pl
            if len(items) < limit:
                break
            offset += limit

    def playlist_items(self, playlist_id: str) -> List[Dict[str, Any]]:
        tracks: List[Dict[str, Any]] = []
        limit = 100
        offset = 0
        while True:
            data = self._get(f'/playlists/{playlist_id}/tracks', params={'limit': limit, 'offset': offset})
            items = data.get('items', [])
            tracks.extend(items)
            if len(items) < limit:
                break
            offset += limit
        return tracks

    def liked_tracks(self) -> Iterator[Dict[str, Any]]:
        limit = 50
        offset = 0
        while True:
            data = self._get('/me/tracks', params={'limit': limit, 'offset': offset})
            items = data.get('items', [])
            for t in items:
                yield t
            if len(items) < limit:
                break
            offset += limit


def ingest_playlists(db, client: SpotifyClient):
    for pl in client.current_user_playlists():
        pid = pl['id']
        name = pl.get('name')
        snapshot_id = pl.get('snapshot_id')
        if not db.playlist_snapshot_changed(pid, snapshot_id):
            continue
        tracks = client.playlist_items(pid)
        simplified = []
        for idx, item in enumerate(tracks):
            track = item.get('track') or {}
            if not track:
                continue
            t_id = track.get('id')
            if not t_id:
                continue
            artist_names = ', '.join(a['name'] for a in track.get('artists', []) if a.get('name'))
            simplified.append((idx, t_id, item.get('added_at')))
            db.upsert_track({
                'id': t_id,
                'name': track.get('name'),
                'album': (track.get('album') or {}).get('name'),
                'artist': artist_names,
                'isrc': ((track.get('external_ids') or {}).get('isrc')),
                'duration_ms': track.get('duration_ms'),
                'normalized': None,
            })
        db.upsert_playlist(pid, name, snapshot_id)
        db.replace_playlist_tracks(pid, simplified)
        db.commit()


def ingest_liked(db, client: SpotifyClient):
    last_added_at = db.get_meta('liked_last_added_at')
    newest_seen = last_added_at
    for item in client.liked_tracks():
        added_at = item.get('added_at')
        track = item.get('track') or {}
        if not track:
            continue
        if last_added_at and added_at <= last_added_at:
            # already ingested due to sorting newest-first assumption
            break
        t_id = track.get('id')
        if not t_id:
            continue
        artist_names = ', '.join(a['name'] for a in track.get('artists', []) if a.get('name'))
        db.upsert_track({
            'id': t_id,
            'name': track.get('name'),
            'album': (track.get('album') or {}).get('name'),
            'artist': artist_names,
            'isrc': ((track.get('external_ids') or {}).get('isrc')),
            'duration_ms': track.get('duration_ms'),
            'normalized': None,
        })
        db.upsert_liked(t_id, added_at)
        if (not newest_seen) or added_at > newest_seen:
            newest_seen = added_at
    if newest_seen and newest_seen != last_added_at:
        db.set_meta('liked_last_added_at', newest_seen)
    db.commit()

__all__ = ["SpotifyClient", "ingest_playlists", "ingest_liked"]
