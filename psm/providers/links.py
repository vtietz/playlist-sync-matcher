"""Provider link generator utilities.

Provides easy access to provider-specific link generators for creating
web URLs to tracks, albums, artists, and playlists.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import ProviderLinkGenerator


def get_link_generator(provider: str = "spotify") -> "ProviderLinkGenerator":
    """Get the link generator for the specified provider.
    
    Args:
        provider: Provider name (default: "spotify")
    
    Returns:
        ProviderLinkGenerator instance for the provider
    
    Raises:
        ValueError: If provider is not supported
    
    Example:
        >>> links = get_link_generator("spotify")
        >>> track_url = links.track_url("3n3Ppam7vgaVa1iaRUc9Lp")
        >>> # Returns: "https://open.spotify.com/track/3n3Ppam7vgaVa1iaRUc9Lp"
    """
    if provider.lower() == "spotify":
        from .spotify.provider import SpotifyLinkGenerator
        return SpotifyLinkGenerator()
    
    # Future providers can be added here
    # elif provider.lower() == "deezer":
    #     from .deezer_provider import DeezerLinkGenerator
    #     return DeezerLinkGenerator()
    
    raise ValueError(f"Unsupported provider: {provider}. Available: spotify")


__all__ = ['get_link_generator']
