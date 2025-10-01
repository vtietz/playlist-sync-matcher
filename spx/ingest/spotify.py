from __future__ import annotations
import requests
from typing import Iterator, Dict, Any, List
import os
import time
from tenacity import retry, stop_after_attempt, wait_random_exponential
from datetime import datetime
from ..utils.normalization import normalize_title_artist

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

    def current_user_profile(self) -> Dict[str, Any]:
        """Get current user's profile information."""
        return self._get('/me')

    def current_user_playlists(self, verbose: bool = False) -> Iterator[Dict[str, Any]]:
        limit = 50
        offset = 0
        while True:
            data = self._get('/me/playlists', params={'limit': limit, 'offset': offset})
            items = data.get('items', [])
            if verbose or os.environ.get('SPX_DEBUG'):
                print(f"[ingest] Fetched {len(items)} playlists (offset={offset})")
            for pl in items:
                yield pl
            if len(items) < limit:
                break
            offset += limit

    def playlist_items(self, playlist_id: str, verbose: bool = False) -> List[Dict[str, Any]]:
        tracks: List[Dict[str, Any]] = []
        limit = 100
        offset = 0
        while True:
            data = self._get(f'/playlists/{playlist_id}/tracks', params={'limit': limit, 'offset': offset})
            items = data.get('items', [])
            tracks.extend(items)
            if verbose or os.environ.get('SPX_DEBUG'):
                print(f"[ingest] Playlist {playlist_id} page fetched {len(items)} tracks (offset={offset})")
            if len(items) < limit:
                break
            offset += limit
        return tracks

    def liked_tracks(self, verbose: bool = False) -> Iterator[Dict[str, Any]]:
        limit = 50
        offset = 0
        while True:
            data = self._get('/me/tracks', params={'limit': limit, 'offset': offset})
            items = data.get('items', [])
            if verbose or os.environ.get('SPX_DEBUG'):
                print(f"[ingest] Fetched {len(items)} liked tracks (offset={offset})")
            for t in items:
                yield t
            if len(items) < limit:
                break
            offset += limit


def _extract_year(release_date: str | None):
    if not release_date:
        return None
    # Spotify can return YYYY-MM-DD, YYYY-MM, or YYYY
    if len(release_date) >= 4 and release_date[:4].isdigit():
        return int(release_date[:4])
    return None


def ingest_playlists(db, client: SpotifyClient, verbose: bool = False, debug: bool = False, use_year: bool = False):
    """Ingest playlists from Spotify API into database.
    
    Args:
        db: Database instance
        client: SpotifyClient instance
        verbose: Print progress messages
        debug: Print debug messages
        use_year: Include year in normalization (from config matching.use_year)
    """
    t0 = time.time()
    processed = 0
    skipped = 0
    
    # Get and store current user ID for owner comparison
    try:
        user_profile = client.current_user_profile()
        user_id = user_profile.get('id')
        if user_id:
            current_stored_id = db.get_meta('current_user_id')
            if current_stored_id != user_id:
                db.set_meta('current_user_id', user_id)
                db.commit()
    except Exception as e:
        if verbose or debug:
            print(f"[ingest] Could not fetch current user profile: {e}")
    
    for pl in client.current_user_playlists(verbose=verbose, debug=debug):
        pid = pl['id']
        name = pl.get('name')
        snapshot_id = pl.get('snapshot_id')
        # Extract owner information
        owner = pl.get('owner', {})
        owner_id = owner.get('id') if owner else None
        owner_name = owner.get('display_name') if owner else None
        
        if not db.playlist_snapshot_changed(pid, snapshot_id):
            skipped += 1
            # Still upsert playlist metadata (including owner fields) even when skipped
            # This ensures new schema fields get populated without reprocessing tracks
            db.upsert_playlist(pid, name, snapshot_id, owner_id, owner_name)
            if verbose or debug:
                print(f"[ingest] Skipping unchanged playlist '{name}' ({pid}) snapshot={snapshot_id}")
            continue
        tracks = client.playlist_items(pid, verbose=verbose, debug=debug)
        simplified = []
        for idx, item in enumerate(tracks):
            track = item.get('track') or {}
            if not track:
                continue
            t_id = track.get('id')
            if not t_id:
                continue
            artist_names = ', '.join(a['name'] for a in track.get('artists', []) if a.get('name'))
            # normalization
            nt, na, combo = normalize_title_artist(track.get('name') or '', artist_names)
            year = _extract_year(((track.get('album') or {}).get('release_date')))
            if use_year and year:
                combo = f"{combo} {year}"
            simplified.append((idx, t_id, item.get('added_at')))
            db.upsert_track({
                'id': t_id,
                'name': track.get('name'),
                'album': (track.get('album') or {}).get('name'),
                'artist': artist_names,
                'isrc': ((track.get('external_ids') or {}).get('isrc')),
                'duration_ms': track.get('duration_ms'),
                'normalized': combo,
                'year': year,
            })
        db.upsert_playlist(pid, name, snapshot_id, owner_id, owner_name)
        db.replace_playlist_tracks(pid, simplified)
        db.commit()
        processed += 1
        if verbose or debug:
            print(f"[ingest] Updated playlist '{name}' ({pid}) tracks={len(simplified)} snapshot={snapshot_id}")
    if verbose or debug:
        print(f"[ingest] Playlists ingestion complete: updated={processed} (skipped={skipped}) in {time.time()-t0:.2f}s")


def ingest_liked(db, client: SpotifyClient, verbose: bool = False, debug: bool = False, use_year: bool = False):
    """Ingest liked tracks from Spotify API into database.
    
    Args:
        db: Database instance
        client: SpotifyClient instance
        verbose: Print progress messages
        debug: Print debug messages
        use_year: Include year in normalization (from config matching.use_year)
    """
    last_added_at = db.get_meta('liked_last_added_at')
    newest_seen = last_added_at
    t0 = time.time()
    ingested = 0
    for item in client.liked_tracks(verbose=verbose, debug=debug):
        added_at = item.get('added_at')
        track = item.get('track') or {}
        if not track:
            continue
        if last_added_at and added_at <= last_added_at:
            # already ingested due to sorting newest-first assumption
            if verbose or debug:
                print(f"[ingest] Reached previously ingested liked track boundary at {added_at}; stopping.")
            break
        t_id = track.get('id')
        if not t_id:
            continue
        artist_names = ', '.join(a['name'] for a in track.get('artists', []) if a.get('name'))
        nt, na, combo = normalize_title_artist(track.get('name') or '', artist_names)
        year = _extract_year(((track.get('album') or {}).get('release_date')))
        if use_year and year:
            combo = f"{combo} {year}"
        db.upsert_track({
            'id': t_id,
            'name': track.get('name'),
            'album': (track.get('album') or {}).get('name'),
            'artist': artist_names,
            'isrc': ((track.get('external_ids') or {}).get('isrc')),
            'duration_ms': track.get('duration_ms'),
            'normalized': combo,
            'year': year,
        })
        db.upsert_liked(t_id, added_at)
        if (not newest_seen) or added_at > newest_seen:
            newest_seen = added_at
        ingested += 1
    if verbose or debug:
        print(f"[ingest] Liked tracks ingested={ingested} (newest_seen={newest_seen}) in {time.time()-t0:.2f}s")
    if newest_seen and newest_seen != last_added_at:
        db.set_meta('liked_last_added_at', newest_seen)
    db.commit()

__all__ = ["SpotifyClient", "ingest_playlists", "ingest_liked"]
