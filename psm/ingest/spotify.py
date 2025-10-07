"""Spotify ingestion - DEPRECATED.

This module is deprecated and maintained only for backward compatibility.
All Spotify logic has been moved to psm.providers.spotify.

Use the following imports instead:
- psm.providers.spotify.SpotifyAPIClient instead of SpotifyClient
- psm.providers.spotify.ingest_playlists
- psm.providers.spotify.ingest_liked

This re-export will be removed in a future version.
"""
import warnings
from ..providers.spotify import SpotifyAPIClient, ingest_playlists, ingest_liked

# Backward compatibility alias
SpotifyClient = SpotifyAPIClient

# Emit deprecation warning when this module is imported
warnings.warn(
    "psm.ingest.spotify is deprecated. "
    "Use psm.providers.spotify.SpotifyAPIClient, ingest_playlists, and ingest_liked instead. "
    "This compatibility shim will be removed in a future version.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = ["SpotifyClient", "ingest_playlists", "ingest_liked"]
