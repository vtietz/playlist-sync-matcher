"""Spotify provider wrapper.

Wraps the existing legacy `SpotifyClient` so higher layers can refer to a
provider-neutral interface. This is an internal adaptation layer; when other
providers (e.g. Deezer, Tidal) are added they should implement the same
Protocol defined in `spx.providers.base` and register themselves.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Dict, Any, Sequence
from .base import ProviderCapabilities, register, ProviderClient
from ..ingest.spotify import SpotifyClient


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
    # The SpotifyClient already supplies the ingestion methods used by services.
    # We inherit directly and rely on its existing methods: current_user_profile,
    # current_user_playlists, playlist_items.

    # If future cross-provider features need additional normalized helpers,
    # they can be added here without touching the base SpotifyClient.

__all__ = ['SpotifyProviderClient']
