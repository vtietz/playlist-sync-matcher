"""Spotify provider wrapper.

Legacy wrapper that extends SpotifyAPIClient with ProviderClient protocol.
This is maintained for backward compatibility with existing code that uses
the old ProviderClient registry pattern.

New code should use psm.providers.spotify.SpotifyProvider instead.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Dict, Any, Sequence
from .base import ProviderCapabilities, ProviderLinkGenerator, register, ProviderClient
from .spotify import SpotifyAPIClient, SpotifyLinkGenerator


@register
class SpotifyProviderClient(SpotifyAPIClient):  # type: ignore[misc]
    """Legacy ProviderClient wrapper around SpotifyAPIClient.
    
    Registered in the old client registry for backward compatibility.
    New code should use SpotifyProvider from psm.providers.spotify instead.
    """
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
    
    # The SpotifyAPIClient already supplies the ingestion methods used by services.
    # We inherit directly and rely on its existing methods: current_user_profile,
    # current_user_playlists, playlist_items.

    # If future cross-provider features need additional normalized helpers,
    # they can be added here without touching the base SpotifyAPIClient.


__all__ = ['SpotifyProviderClient', 'SpotifyLinkGenerator']
