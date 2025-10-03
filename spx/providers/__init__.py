"""Provider abstraction public API.

Currently only Spotify is implemented. Additional providers can register
by importing this package and using the registry helpers.
"""
from .base import (
    Artist, Album, Track, Playlist, ProviderCapabilities, ProviderClient,
    register, get, available_providers
)

# Import spotify provider so it registers itself on package import.
from . import spotify_provider  # noqa: F401


def create_provider(name: str, **kwargs):  # future kwargs for auth tokens
    """Factory returning a provider client class instance.

    For now this just returns an instance of the registered class for Spotify
    and passes through kwargs (none used yet). When other providers are added
    they can accept configuration/auth parameters here.
    """
    cls = get(name)
    # SpotifyProviderClient expects token string; defer token acquisition to services
    return cls(**kwargs)  # type: ignore[call-arg]

__all__ = [
    'Artist','Album','Track','Playlist','ProviderCapabilities','ProviderClient',
    'register','get','available_providers','create_provider'
]
