"""Pull service: Orchestrate provider data ingestion.

This service handles authentication, client creation, and ingestion
of playlists and liked tracks from streaming providers. Uses the provider
abstraction layer so additional streaming services can be integrated with
minimal changes.
"""

from __future__ import annotations
import time
import logging
from typing import Dict, Any
from datetime import datetime
from pathlib import Path

from ..providers import get_provider_instance
from ..providers.spotify import ingest_playlists, ingest_liked
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
        self.changed_track_ids: set[str] = set()  # Track IDs that were added/updated


def pull_data(
    db: DatabaseInterface,
    provider: str,
    provider_config: Dict[str, Any],
    matching_config: Dict[str, Any],
    force_auth: bool = False,
    force_refresh: bool = False
) -> PullResult:
    """Ingest playlists and liked tracks for the selected provider.

    Uses provider abstraction to support multiple streaming services.
    Currently 'spotify' is the only implemented provider.
    
    Args:
        db: Database instance
        provider: Provider name (e.g., 'spotify')
        provider_config: Provider-specific configuration
        matching_config: Matching configuration (use_year, etc.)
        force_auth: Force full auth flow ignoring cached tokens
        force_refresh: Force refresh all tracks even if playlists unchanged
    """
    result = PullResult()
    start = time.time()
    
    # Get provider instance from registry
    try:
        provider_instance = get_provider_instance(provider)
    except KeyError:
        raise NotImplementedError(f"Provider '{provider}' not registered")
    
    # Validate configuration
    provider_instance.validate_config(provider_config)
    
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
    
    # Ensure cache_file is in the config for auth provider
    provider_config_with_cache = {**provider_config, 'cache_file': cache_file}
    
    auth = provider_instance.create_auth(provider_config_with_cache)
    
    tok_dict = auth.get_token(force=force_auth)
    if not isinstance(tok_dict, dict) or 'access_token' not in tok_dict:
        raise RuntimeError('Failed to obtain access token')
    
    result.token_expiry = tok_dict.get('expires_at')
    
    if result.token_expiry:
        remaining = int(result.token_expiry - time.time())
        logger.debug(f"Using access token (expires {datetime.fromtimestamp(result.token_expiry)}; +{remaining}s)")
    
    # Build client and ingest data
    client = provider_instance.create_client(tok_dict['access_token'])
    use_year = matching_config.get('use_year', False)
    
    playlist_track_ids = ingest_playlists(db, client, use_year=use_year, force_refresh=force_refresh)
    liked_track_ids = ingest_liked(db, client, use_year=use_year)
    
    # Combine changed track IDs from both sources
    result.changed_track_ids = playlist_track_ids | liked_track_ids
    
    # Gather statistics
    result.playlist_count = db.count_playlists()
    result.unique_playlist_tracks = db.count_unique_playlist_tracks()
    result.liked_tracks = db.count_liked_tracks()
    result.total_tracks = db.count_tracks()
    result.duration_seconds = time.time() - start
    
    return result


__all__ = ["pull_data", "PullResult"]
