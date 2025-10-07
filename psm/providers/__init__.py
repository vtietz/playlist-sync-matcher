"""Provider abstraction public API.

Currently only Spotify is implemented. Additional providers can register
by importing this package and using the registry helpers.

This module provides two levels of abstraction:
1. Legacy: ProviderClient (protocol-based, for backward compatibility)
2. New: Provider (complete factory with auth + client + config validation)
"""
from .base import (
    Artist, Album, Track, Playlist, ProviderCapabilities, ProviderClient,
    AuthProvider, Provider, ProviderLinkGenerator,
    register, get, available_providers,
    register_provider, get_provider_instance, available_provider_instances,
)

# Import spotify provider so it registers itself on package import.
from . import spotify_provider  # noqa: F401


def create_provider(name: str, **kwargs):  # future kwargs for auth tokens
    """Factory returning a provider client class instance.

    For now this just returns an instance of the registered class for Spotify
    and passes through kwargs (none used yet). When other providers are added
    they can accept configuration/auth parameters here.
    
    Note: This is legacy. New code should use get_provider_instance() instead.
    """
    cls = get(name)
    # SpotifyProviderClient expects token string; defer token acquisition to services
    return cls(**kwargs)  # type: ignore[call-arg]

__all__ = [
    'Artist','Album','Track','Playlist','ProviderCapabilities','ProviderClient',
    'AuthProvider', 'Provider', 'ProviderLinkGenerator',
    'register','get','available_providers','create_provider',
    'register_provider', 'get_provider_instance', 'available_provider_instances',
]
