"""Provider abstraction public API.

Currently only Spotify is implemented. Additional providers can register
by using register_provider() with a Provider instance.
"""

from .base import (
    Artist,
    Album,
    Track,
    Playlist,
    ProviderCapabilities,
    AuthProvider,
    Provider,
    ProviderLinkGenerator,
    register_provider,
    get_provider_instance,
    available_provider_instances,
)

# Register Spotify provider instance
from .spotify import SpotifyProvider

register_provider(SpotifyProvider())


__all__ = [
    "Artist",
    "Album",
    "Track",
    "Playlist",
    "ProviderCapabilities",
    "AuthProvider",
    "Provider",
    "ProviderLinkGenerator",
    "register_provider",
    "get_provider_instance",
    "available_provider_instances",
]
