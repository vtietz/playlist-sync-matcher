"""Spotify API client.

Handles all HTTP requests to Spotify Web API endpoints.
Implements provider-specific API interaction patterns.

Moved from psm.ingest.spotify to encapsulate all Spotify logic in the provider package.
"""

from __future__ import annotations
import requests
from typing import Iterator, Dict, Any, List, Sequence
import os
import time
import logging
from tenacity import retry, stop_after_attempt, wait_random_exponential

logger = logging.getLogger(__name__)
API_BASE = "https://api.spotify.com/v1"


class SpotifyAPIClient:
    """Spotify Web API client.

    Provides methods for fetching user data, playlists, tracks, and liked songs.
    Also supports write operations (playlist updates) for push functionality.
    """

    def __init__(self, token: str):
        """Initialize client with access token.

        Args:
            token: Valid Spotify OAuth access token
        """
        self.token = token

    def _headers(self) -> Dict[str, str]:
        """Build authorization headers for API requests."""
        return {"Authorization": f"Bearer {self.token}"}

    @retry(stop=stop_after_attempt(5), wait=wait_random_exponential(multiplier=1, max=30))
    def _get(self, path: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Execute GET request with retry logic and rate limit handling.

        Args:
            path: API endpoint path (e.g., '/me/playlists')
            params: Optional query parameters

        Returns:
            JSON response as dict

        Raises:
            requests.HTTPError: On non-retryable errors
        """
        if os.environ.get("PSM__TEST__MODE") == "1":  # pragma: no cover - test shortcut
            if path.startswith("/playlists/"):
                pid = path.split("/")[-1]
                return {
                    "id": pid,
                    "name": "Stub Playlist",
                    "snapshot_id": "snap-stub",
                    "owner": {"id": "owner", "display_name": "Owner"},
                }
            if path.endswith("/tracks"):
                return {"items": []}
            if path == "/me":
                return {"id": "user-stub"}
            return {}
        r = requests.get(API_BASE + path, headers=self._headers(), params=params, timeout=30)
        if r.status_code == 429:
            # Spotify returns Retry-After header
            ra = int(r.headers.get("Retry-After", "1"))
            time.sleep(ra)
            raise Exception("rate limit retry")
        r.raise_for_status()
        return r.json()

    def _put(self, path: str, json: Dict[str, Any]) -> Dict[str, Any]:  # pragma: no cover (simple network wrapper)
        """Execute PUT request with rate limit handling.

        Args:
            path: API endpoint path
            json: Request body as dict

        Returns:
            JSON response as dict (may be empty)
        """
        r = requests.put(API_BASE + path, headers=self._headers(), json=json, timeout=30)
        if r.status_code == 429:
            ra = int(r.headers.get("Retry-After", "1"))
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
        """Execute POST request with rate limit handling.

        Args:
            path: API endpoint path
            json: Request body as dict

        Returns:
            JSON response as dict (may be empty)
        """
        r = requests.post(API_BASE + path, headers=self._headers(), json=json, timeout=30)
        if r.status_code == 429:
            ra = int(r.headers.get("Retry-After", "1"))
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
        """Get current user's profile information.

        Returns:
            User profile dict with 'id', 'display_name', etc.
        """
        return self._get("/me")

    def current_user_playlists(self) -> Iterator[Dict[str, Any]]:
        """Fetch all playlists for the current user.

        Yields:
            Playlist dicts with 'id', 'name', 'snapshot_id', 'owner', etc.
        """
        limit = 50
        offset = 0
        while True:
            data = self._get("/me/playlists", params={"limit": limit, "offset": offset})
            items = data.get("items", [])
            logger.debug(f"Fetched {len(items)} playlists (offset={offset})")
            for pl in items:
                yield pl
            if len(items) < limit:
                break
            offset += limit

    def playlist_items(self, playlist_id: str) -> List[Dict[str, Any]]:
        """Fetch all tracks in a playlist.

        Args:
            playlist_id: Spotify playlist ID

        Returns:
            List of playlist item dicts with 'track' and 'added_at'
        """
        if os.environ.get("PSM__TEST__MODE") == "1":  # pragma: no cover - test shortcut
            return [
                {
                    "added_at": "2025-01-01T00:00:00Z",
                    "track": {
                        "id": "track_stub_1",
                        "name": "Stub Track",
                        "artists": [{"name": "Stub Artist"}],
                        "album": {"name": "Stub Album", "release_date": "2024-01-01"},
                        "external_ids": {"isrc": "ISRCSTUB1"},
                        "duration_ms": 180000,
                    },
                }
            ]
        tracks: List[Dict[str, Any]] = []
        limit = 100
        offset = 0
        while True:
            data = self._get(f"/playlists/{playlist_id}/tracks", params={"limit": limit, "offset": offset})
            items = data.get("items", [])
            tracks.extend(items)
            logger.debug(f"Playlist {playlist_id} page fetched {len(items)} tracks (offset={offset})")
            if len(items) < limit:
                break
            offset += limit
        return tracks

    # ---------------- Write / detail helpers (used by push service) -----------------

    def get_playlist(self, playlist_id: str) -> Dict[str, Any]:  # pragma: no cover
        """Fetch detailed playlist information.

        Args:
            playlist_id: Spotify playlist ID

        Returns:
            Playlist dict with full metadata
        """
        return self._get(f"/playlists/{playlist_id}")

    def replace_playlist_tracks_remote(self, playlist_id: str, track_ids: Sequence[str]):  # pragma: no cover
        """Replace all tracks in a playlist with a new set.

        Spotify's PUT replace endpoint accepts at most 100 URIs. For >100 we
        clear (empty replace) then batch POST add.

        Args:
            playlist_id: Spotify playlist ID
            track_ids: List of Spotify track IDs (without 'spotify:track:' prefix)
        """
        if not track_ids:
            # Clear playlist
            self._put(f"/playlists/{playlist_id}/tracks", json={"uris": []})
            return

        # Helper to chunk
        def chunks(seq, size):
            for i in range(0, len(seq), size):
                yield seq[i : i + size]

        if len(track_ids) <= 100:
            uris = [f"spotify:track:{tid}" for tid in track_ids]
            self._put(f"/playlists/{playlist_id}/tracks", json={"uris": uris})
            return
        # >100 – clear then add in batches
        self._put(f"/playlists/{playlist_id}/tracks", json={"uris": []})
        for batch in chunks(track_ids, 100):
            uris = [f"spotify:track:{tid}" for tid in batch]
            self._post(f"/playlists/{playlist_id}/tracks", json={"uris": uris})

    def liked_tracks(self) -> Iterator[Dict[str, Any]]:
        """Fetch all liked (saved) tracks for the current user.

        Yields:
            Track item dicts with 'track' and 'added_at'
        """
        limit = 50
        offset = 0
        while True:
            data = self._get("/me/tracks", params={"limit": limit, "offset": offset})
            items = data.get("items", [])
            logger.debug(f"Fetched {len(items)} liked tracks (offset={offset})")
            for t in items:
                yield t
            if len(items) < limit:
                break
            offset += limit


__all__ = ["SpotifyAPIClient"]
