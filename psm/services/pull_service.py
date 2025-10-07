"""Pull service: Orchestrate provider data ingestion (currently Spotify).

This service presently handles authentication, client creation, and ingestion
of playlists and liked tracks from Spotify. A provider abstraction layer has
been introduced (see ``spx.providers``) so additional streaming services can
be integrated in the future with minimal changes here. For now we still
construct the concrete Spotify auth & client objects directly.
"""

from __future__ import annotations
import time
import logging
from typing import Dict, Any
from datetime import datetime
from pathlib import Path

from ..auth.spotify_oauth import SpotifyAuth
from ..ingest.spotify import SpotifyClient, ingest_playlists, ingest_liked
from ..db import Database, DatabaseInterface

logger = logging.getLogger(__name__)


class PullResult:
    """Results from a pull operation."""
    
    def __init__(self):
        self.token_reused = False
        self.token_expiry: float | None = None
        self.playlist_count = 0
        self.unique_playlist_tracks = 0
        self.liked_tracks = 0
        self.total_tracks = 0
        self.duration_seconds = 0.0


def pull_data(
    db: DatabaseInterface,
    provider: str,
    provider_config: Dict[str, Any],
    matching_config: Dict[str, Any],
    force_auth: bool = False,
    force_refresh: bool = False
) -> PullResult:
    """Ingest playlists and liked tracks for the selected provider.

    Currently only the 'spotify' provider is implemented. The interface is
    stable so additional providers can be added later without changing callers.
    
    Args:
        db: Database instance
        provider: Provider name (currently only 'spotify')
        provider_config: Provider-specific configuration
        matching_config: Matching configuration (use_year, etc.)
        force_auth: Force full auth flow ignoring cached tokens
        force_refresh: Force refresh all tracks even if playlists unchanged
    """
    if provider != 'spotify':
        raise NotImplementedError(f"Provider '{provider}' not implemented")

    result = PullResult()
    start = time.time()
    
    # Build auth and get token
    cache_file = provider_config.get('cache_file')
    if not cache_file:
        cache_file = f"{provider}_tokens.json"
    else:
        # For non-spotify providers (future), auto-prefix filename if it would collide.
        import os
        fname = os.path.basename(cache_file)
        if provider != 'spotify' and provider not in fname:
            cache_file = os.path.join(os.path.dirname(cache_file) or '.', f"{provider}_{fname}")

    auth = SpotifyAuth(
        client_id=provider_config['client_id'],
        redirect_scheme=provider_config.get('redirect_scheme', 'http'),
        redirect_host=provider_config.get('redirect_host', '127.0.0.1'),
        redirect_port=provider_config.get('redirect_port', 9876),
        redirect_path=provider_config.get('redirect_path', '/callback'),
        scope=provider_config.get('scope', 'user-library-read playlist-read-private'),
        cache_file=cache_file,
        cert_file=provider_config.get('cert_file', 'cert.pem'),
        key_file=provider_config.get('key_file', 'key.pem'),
    )
    
    tok_dict = auth.get_token(force=force_auth)
    if not isinstance(tok_dict, dict) or 'access_token' not in tok_dict:
        raise RuntimeError('Failed to obtain access token')
    
    result.token_expiry = tok_dict.get('expires_at')
    
    if result.token_expiry:
        remaining = int(result.token_expiry - time.time())
        logger.debug(f"Using access token (expires {datetime.fromtimestamp(result.token_expiry)}; +{remaining}s)")
    
    # Build client and ingest data
    client = SpotifyClient(tok_dict['access_token'])
    use_year = matching_config.get('use_year', False)
    
    ingest_playlists(db, client, use_year=use_year, force_refresh=force_refresh)
    ingest_liked(db, client, use_year=use_year)
    
    # Gather statistics
    result.playlist_count = db.count_playlists()
    result.unique_playlist_tracks = db.count_unique_playlist_tracks()
    result.liked_tracks = db.count_liked_tracks()
    result.total_tracks = db.count_tracks()
    result.duration_seconds = time.time() - start
    
    return result


__all__ = ["pull_data", "PullResult"]
