from __future__ import annotations
import requests
from typing import Iterator, Dict, Any, List, Sequence
import time
import logging
import click
from tenacity import retry, stop_after_attempt, wait_random_exponential
from datetime import datetime
from ..utils.normalization import normalize_title_artist
from ..utils.logging_helpers import format_summary

logger = logging.getLogger(__name__)
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

    def _put(self, path: str, json: Dict[str, Any]) -> Dict[str, Any]:  # pragma: no cover (simple network wrapper)
        r = requests.put(API_BASE + path, headers=self._headers(), json=json, timeout=30)
        if r.status_code == 429:
            ra = int(r.headers.get("Retry-After", "1"))
            import time
            time.sleep(ra)
            raise Exception("rate limit retry")
        r.raise_for_status()
        if r.text:
            try:
                return r.json()
            except Exception:
                return {}
        return {}

    def _post(self, path: str, json: Dict[str, Any]) -> Dict[str, Any]:  # pragma: no cover
        r = requests.post(API_BASE + path, headers=self._headers(), json=json, timeout=30)
        if r.status_code == 429:
            ra = int(r.headers.get("Retry-After", "1"))
            import time
            time.sleep(ra)
            raise Exception("rate limit retry")
        r.raise_for_status()
        if r.text:
            try:
                return r.json()
            except Exception:
                return {}
        return {}

    def current_user_profile(self) -> Dict[str, Any]:
        """Get current user's profile information."""
        return self._get('/me')

    def current_user_playlists(self) -> Iterator[Dict[str, Any]]:
        limit = 50
        offset = 0
        while True:
            data = self._get('/me/playlists', params={'limit': limit, 'offset': offset})
            items = data.get('items', [])
            logger.debug(f"Fetched {len(items)} playlists (offset={offset})")
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
            logger.debug(f"Playlist {playlist_id} page fetched {len(items)} tracks (offset={offset})")
            if len(items) < limit:
                break
            offset += limit
        return tracks

    # ---------------- Write / detail helpers (used by push service) -----------------
    def get_playlist(self, playlist_id: str) -> Dict[str, Any]:  # pragma: no cover
        return self._get(f'/playlists/{playlist_id}')

    def replace_playlist_tracks_remote(self, playlist_id: str, track_ids: Sequence[str]):  # pragma: no cover
        """Full replace remote playlist tracks.

        Spotify's PUT replace endpoint accepts at most 100 URIs. For >100 we
        clear (empty replace) then batch POST add.
        """
        if not track_ids:
            # Clear playlist
            self._put(f'/playlists/{playlist_id}/tracks', json={'uris': []})
            return
        # Helper to chunk
        def chunks(seq, size):
            for i in range(0, len(seq), size):
                yield seq[i:i+size]
        if len(track_ids) <= 100:
            uris = [f'spotify:track:{tid}' for tid in track_ids]
            self._put(f'/playlists/{playlist_id}/tracks', json={'uris': uris})
            return
        # >100 – clear then add in batches
        self._put(f'/playlists/{playlist_id}/tracks', json={'uris': []})
        for batch in chunks(track_ids, 100):
            uris = [f'spotify:track:{tid}' for tid in batch]
            self._post(f'/playlists/{playlist_id}/tracks', json={'uris': uris})

    def liked_tracks(self) -> Iterator[Dict[str, Any]]:
        limit = 50
        offset = 0
        while True:
            data = self._get('/me/tracks', params={'limit': limit, 'offset': offset})
            items = data.get('items', [])
            logger.debug(f"Fetched {len(items)} liked tracks (offset={offset})")
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


def ingest_playlists(db, client: SpotifyClient, use_year: bool = False):
    """Ingest playlists from Spotify API into database.
    
    Args:
        db: Database instance
        client: SpotifyClient instance
        use_year: Include year in normalization (from config matching.use_year)
    """
    click.echo(click.style("=== Pulling playlists from Spotify ===", fg='cyan', bold=True))
    t0 = time.time()
    new_playlists = 0
    updated_playlists = 0
    unchanged_playlists = 0
    
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
        logger.error(f"Could not fetch current user profile: {e}")
    
    for pl in client.current_user_playlists():
        pid = pl['id']
        name = pl.get('name')
        snapshot_id = pl.get('snapshot_id')
        # Extract owner information
        owner = pl.get('owner', {})
        owner_id = owner.get('id') if owner else None
        owner_name = owner.get('display_name') if owner else None
        
        # Check if this is a new playlist or existing
        existing_playlist = db.conn.execute(
            "SELECT snapshot_id FROM playlists WHERE id = ?", (pid,)
        ).fetchone()
        
        if not db.playlist_snapshot_changed(pid, snapshot_id):
            unchanged_playlists += 1
            # Still upsert playlist metadata (including owner fields) even when skipped
            # This ensures new schema fields get populated without reprocessing tracks
            db.upsert_playlist(pid, name, snapshot_id, owner_id, owner_name)
            track_count = pl.get('tracks', {}).get('total', 0) if isinstance(pl.get('tracks'), dict) else 0
            logger.info(f"{click.style('[skip]', fg='yellow')} {name} ({track_count} tracks) - unchanged snapshot")
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
        
        # Determine if new or updated
        if existing_playlist:
            updated_playlists += 1
            action = "updated"
            color = "blue"
        else:
            new_playlists += 1
            action = "new"
            color = "green"
        
        logger.info(f"{click.style(f'[{action}]', fg=color)} {name} ({len(simplified)} tracks) | owner={owner_name or owner_id or 'unknown'}")
    
    total_processed = new_playlists + updated_playlists
    t1 = time.time()
    summary = format_summary(
        new=new_playlists,
        updated=updated_playlists,
        unchanged=unchanged_playlists,
        duration_seconds=t1 - t0,
        item_name="Playlists"
    )
    logger.info(summary)


def ingest_liked(db, client: SpotifyClient, use_year: bool = False):
    """Ingest liked tracks from Spotify API into database.
    
    Args:
        db: Database instance
        client: SpotifyClient instance
        use_year: Include year in normalization (from config matching.use_year)
    """
    click.echo(click.style("=== Pulling liked tracks ===", fg='cyan', bold=True))
    last_added_at = db.get_meta('liked_last_added_at')
    newest_seen = last_added_at
    t0 = time.time()
    new_tracks = 0
    updated_tracks = 0
    
    for item in client.liked_tracks():
        added_at = item.get('added_at')
        track = item.get('track') or {}
        if not track:
            continue
        if last_added_at and added_at <= last_added_at:
            # already ingested due to sorting newest-first assumption
            logger.info(f"Reached previously ingested liked track boundary at {added_at}; stopping.")
            break
        t_id = track.get('id')
        if not t_id:
            continue
        
        # Check if track already exists in database
        existing_track = db.conn.execute(
            "SELECT id FROM tracks WHERE id = ?", (t_id,)
        ).fetchone()
        
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
        
        # Determine if new or updated
        if existing_track:
            updated_tracks += 1
            action = "updated"
            color = "blue"
        else:
            new_tracks += 1
            action = "new"
            color = "green"
        
        track_name = track.get('name', 'Unknown')
        logger.debug(f"{click.style(f'[{action}]', fg=color)} ❤️  {track_name} | {artist_names}")
        
        if (not newest_seen) or added_at > newest_seen:
            newest_seen = added_at
    
    total_ingested = new_tracks + updated_tracks
    t1 = time.time()
    summary = format_summary(
        new=new_tracks,
        updated=updated_tracks,
        unchanged=0,  # Liked tracks don't track unchanged
        duration_seconds=t1 - t0,
        item_name="Liked tracks"
    )
    
    # Add newest timestamp info if available
    if newest_seen:
        summary += f" (newest={newest_seen})"
    
    logger.info(summary)
    if newest_seen and newest_seen != last_added_at:
        db.set_meta('liked_last_added_at', newest_seen)
    db.commit()

__all__ = ["SpotifyClient", "ingest_playlists", "ingest_liked"]
