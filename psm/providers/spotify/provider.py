"""Spotify provider implementation.

Complete Spotify provider that implements the Provider interface.
Handles authentication, client creation, configuration validation, and link generation.
"""

from __future__ import annotations
from typing import Dict, Any
from ..base import Provider, AuthProvider, ProviderClient, ProviderLinkGenerator
from .auth import SpotifyAuthProvider
from .client import SpotifyAPIClient


class SpotifyLinkGenerator:
    """Generates Spotify web URLs for tracks, albums, artists, and playlists."""
    
    def track_url(self, track_id: str) -> str:
        """Generate Spotify track URL."""
        return f"https://open.spotify.com/track/{track_id}"
    
    def album_url(self, album_id: str) -> str:
        """Generate Spotify album URL."""
        return f"https://open.spotify.com/album/{album_id}"
    
    def artist_url(self, artist_id: str) -> str:
        """Generate Spotify artist URL."""
        return f"https://open.spotify.com/artist/{artist_id}"
    
    def playlist_url(self, playlist_id: str) -> str:
        """Generate Spotify playlist URL."""
        return f"https://open.spotify.com/playlist/{playlist_id}"


class SpotifyProvider(Provider):
    """Spotify streaming provider implementation.
    
    Provides factory methods for creating Spotify auth and client instances,
    validates configuration, and provides default config values.
    """
    
    @property
    def name(self) -> str:
        """Provider identifier."""
        return "spotify"
    
    def create_auth(self, config: Dict[str, Any]) -> AuthProvider:
        """Create Spotify authentication provider.
        
        Args:
            config: Spotify configuration dict with keys:
                - client_id: Spotify application client ID
                - redirect_port: OAuth callback port (default: 9876)
                - redirect_scheme: http or https (default: http)
                - redirect_host: Callback host (default: 127.0.0.1)
                - redirect_path: Callback path (default: /callback)
                - cache_file: Token cache file path (default: tokens.json)
                - scope: OAuth scope (default: user-library-read ...)
                - cert_file: SSL cert for HTTPS (optional)
                - key_file: SSL key for HTTPS (optional)
                - timeout_seconds: OAuth timeout (default: 300)
        
        Returns:
            SpotifyAuthProvider instance
            
        Raises:
            ValueError: If required config missing
        """
        # Validate required fields
        if 'client_id' not in config:
            raise ValueError("Spotify config missing required field: client_id")
        
        # Get config values with defaults
        return SpotifyAuthProvider(
            client_id=config['client_id'],
            redirect_port=config.get('redirect_port', 9876),
            scope=config.get('scope', 'user-library-read playlist-read-private playlist-modify-public playlist-modify-private'),
            cache_file=config.get('cache_file', 'tokens.json'),
            redirect_path=config.get('redirect_path', '/callback'),
            redirect_scheme=config.get('redirect_scheme', 'http'),
            redirect_host=config.get('redirect_host', '127.0.0.1'),
            cert_file=config.get('cert_file'),
            key_file=config.get('key_file'),
            timeout_seconds=config.get('timeout_seconds', 300),
        )
    
    def create_client(self, access_token: str) -> ProviderClient:
        """Create Spotify API client.
        
        Args:
            access_token: Valid Spotify OAuth access token
            
        Returns:
            SpotifyAPIClient instance
        """
        return SpotifyAPIClient(access_token)  # type: ignore[return-value]
    
    def validate_config(self, config: Dict[str, Any]) -> None:
        """Validate Spotify configuration.
        
        Args:
            config: Spotify configuration dict
            
        Raises:
            ValueError: If required fields missing or invalid
        """
        # Check required fields
        if 'client_id' not in config:
            raise ValueError("Spotify config missing required field: client_id")
        
        # Validate types if present
        if 'redirect_port' in config:
            port = config['redirect_port']
            if not isinstance(port, int) or port < 1 or port > 65535:
                raise ValueError(f"Invalid redirect_port: {port}. Must be integer 1-65535")
        
        if 'redirect_scheme' in config:
            scheme = config['redirect_scheme']
            if scheme not in ('http', 'https'):
                raise ValueError(f"Invalid redirect_scheme: {scheme}. Must be 'http' or 'https'")
        
        if 'timeout_seconds' in config:
            timeout = config['timeout_seconds']
            if not isinstance(timeout, int) or timeout < 1:
                raise ValueError(f"Invalid timeout_seconds: {timeout}. Must be positive integer")
    
    def get_default_config(self) -> Dict[str, Any]:
        """Get default Spotify configuration.
        
        Returns:
            Dict with default config values (client_id must be provided by user)
        """
        return {
            'redirect_port': 9876,
            'redirect_scheme': 'http',
            'redirect_host': '127.0.0.1',
            'redirect_path': '/callback',
            'cache_file': 'tokens.json',
            'scope': 'user-library-read playlist-read-private playlist-modify-public playlist-modify-private',
            'timeout_seconds': 300,
        }
    
    def get_link_generator(self) -> ProviderLinkGenerator:
        """Get Spotify link generator.
        
        Returns:
            SpotifyLinkGenerator instance
        """
        return SpotifyLinkGenerator()  # type: ignore[return-value]


__all__ = ["SpotifyProvider", "SpotifyLinkGenerator"]
