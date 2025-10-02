"""Pull service: Orchestrate Spotify data ingestion.

This service handles authentication, client creation, and ingestion
of playlists and liked tracks from Spotify.
"""

from __future__ import annotations
import time
import logging
from typing import Dict, Any
from datetime import datetime
from pathlib import Path

from ..auth.spotify_oauth import SpotifyAuth
from ..ingest.spotify import SpotifyClient, ingest_playlists, ingest_liked
from ..db import Database

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


def pull_spotify_data(
    db: Database,
    spotify_config: Dict[str, Any],
    matching_config: Dict[str, Any],
    force_auth: bool = False,
    verbose: bool = False
) -> PullResult:
    """Pull playlists and liked tracks from Spotify.
    
    Args:
        db: Database instance
        spotify_config: Spotify OAuth configuration
        matching_config: Matching configuration (for use_year)
        force_auth: Force full authentication flow
        verbose: Enable verbose logging
        
    Returns:
        PullResult with statistics and timing
    """
    result = PullResult()
    start = time.time()
    
    # Build auth and get token
    auth = SpotifyAuth(
        client_id=spotify_config['client_id'],
        redirect_scheme=spotify_config.get('redirect_scheme', 'http'),
        redirect_host=spotify_config.get('redirect_host', '127.0.0.1'),
        redirect_port=spotify_config.get('redirect_port', 9876),
        redirect_path=spotify_config.get('redirect_path', '/callback'),
        scope=spotify_config.get('scope', 'user-library-read playlist-read-private'),
        cache_file=spotify_config.get('cache_file', 'tokens.json'),
        cert_file=spotify_config.get('cert_file', 'cert.pem'),
        key_file=spotify_config.get('key_file', 'key.pem'),
    )
    
    tok_dict = auth.get_token(force=force_auth)
    if not isinstance(tok_dict, dict) or 'access_token' not in tok_dict:
        raise RuntimeError('Failed to obtain access token')
    
    result.token_expiry = tok_dict.get('expires_at')
    
    if verbose and result.token_expiry:
        remaining = int(result.token_expiry - time.time())
        logger.info(f"[pull] Using access token (expires {datetime.fromtimestamp(result.token_expiry)}; +{remaining}s)")
    
    # Build client and ingest data
    client = SpotifyClient(tok_dict['access_token'])
    use_year = matching_config.get('use_year', False)
    
    ingest_playlists(db, client, verbose=verbose, use_year=use_year)
    ingest_liked(db, client, verbose=verbose, use_year=use_year)
    
    # Gather statistics
    result.playlist_count = db.count_playlists()
    result.unique_playlist_tracks = db.count_unique_playlist_tracks()
    result.liked_tracks = db.count_liked_tracks()
    result.total_tracks = db.count_tracks()
    result.duration_seconds = time.time() - start
    
    return result
