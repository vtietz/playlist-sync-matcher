"""Spotify provider wrapper.

Wraps the existing legacy `SpotifyClient` so higher layers can refer to a
provider-neutral interface. This is an internal adaptation layer; when other
providers (e.g. Deezer, Tidal) are added they should implement the same
Protocol defined in `spx.providers.base` and register themselves.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Dict, Any, Sequence
from .base import ProviderCapabilities, ProviderLinkGenerator, register, ProviderClient
from ..ingest.spotify import SpotifyClient


class SpotifyLinkGenerator:
    """Generates Spotify web URLs for tracks, albums, artists, and playlists."""
    
    def track_url(self, track_id: str) -> str:
        """Generate Spotify track URL."""
        return f"https://open.spotify.com/track/{track_id}"
    
    def album_url(self, album_id: str) -> str:
        """Generate Spotify album URL."""
        return f"https://open.spotify.com/album/{album_id}"
    
    def artist_url(self, artist_id: str) -> str:
        """Generate Spotify artist URL."""
        return f"https://open.spotify.com/artist/{artist_id}"
    
    def playlist_url(self, playlist_id: str) -> str:
        """Generate Spotify playlist URL."""
        return f"https://open.spotify.com/playlist/{playlist_id}"


@register
class SpotifyProviderClient(SpotifyClient):  # type: ignore[misc]
    name = 'spotify'
    capabilities = ProviderCapabilities(
        search=False,          # search not yet abstracted here
        create_playlist=False, # creation not implemented in legacy code
        batch_add=False,       # batch add not implemented
        supports_isrc=True,
        max_batch_size=100,
        replace_playlist=True, # write support (experimental push)
    )
    link_generator = SpotifyLinkGenerator()
    
    # The SpotifyClient already supplies the ingestion methods used by services.
    # We inherit directly and rely on its existing methods: current_user_profile,
    # current_user_playlists, playlist_items.

    # If future cross-provider features need additional normalized helpers,
    # they can be added here without touching the base SpotifyClient.


__all__ = ['SpotifyProviderClient', 'SpotifyLinkGenerator']
