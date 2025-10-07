"""Spotify provider package.

This package contains all Spotify-specific logic:
- auth.py: OAuth authentication
- client.py: API client for fetching/pushing data
- config.py: Configuration validation and defaults
- provider.py: Complete Spotify provider implementation

All Spotify logic should live here. Other parts of the codebase should use
the Provider interface from psm.providers.base instead of direct imports.
"""

from .auth import SpotifyAuthProvider
from .client import SpotifyAPIClient
from .ingestion import extract_year, ingest_playlists, ingest_liked

__all__ = [
    "SpotifyAuthProvider",
    "SpotifyAPIClient",
    "extract_year",
    "ingest_playlists",
    "ingest_liked",
]
