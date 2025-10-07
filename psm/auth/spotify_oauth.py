"""Spotify OAuth authentication - DEPRECATED.

This module is deprecated and maintained only for backward compatibility.
All Spotify logic has been moved to psm.providers.spotify.

Use psm.providers.spotify.SpotifyAuthProvider instead of SpotifyAuth.
This re-export will be removed in a future version.
"""
import warnings
from ..providers.spotify import SpotifyAuthProvider

# Backward compatibility alias
SpotifyAuth = SpotifyAuthProvider

# Emit deprecation warning when this module is imported
warnings.warn(
    "psm.auth.spotify_oauth is deprecated. "
    "Use psm.providers.spotify.SpotifyAuthProvider instead. "
    "This compatibility shim will be removed in a future version.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = ["SpotifyAuth"]
