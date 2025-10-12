"""Provider abstraction layer.

This module defines provider-neutral domain models and abstract interfaces
so additional music streaming providers (e.g. Deezer, Tidal, Apple Music) can
be integrated without changing higher-level services.

Current implementation wraps existing Spotify-specific logic; other providers
can implement the same interface and register themselves in the registry.

Key abstractions:
- Domain models: Artist, Album, Track, Playlist
- AuthProvider: OAuth/authentication interface
- ProviderClient: API client interface
- Provider: Complete provider factory
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence, Protocol, Dict, Any

# ---------------- Domain Models (minimal for current needs) -----------------

@dataclass(frozen=True)
class Artist:
    name: str
    external_id: str | None = None

@dataclass(frozen=True)
class Album:
    title: str
    external_id: str | None = None
    year: int | None = None

@dataclass(frozen=True)
class Track:
    title: str
    track_id: str  # provider-specific identifier
    artists: Sequence[Artist]
    album: Album | None
    duration_ms: int | None
    isrc: str | None = None
    normalized: str | None = None
    year: int | None = None
    provider: str = "spotify"

@dataclass(frozen=True)
class Playlist:
    playlist_id: str
    name: str
    owner_id: str | None
    owner_name: str | None
    snapshot_id: str | None
    provider: str = "spotify"

# ---------------- Capability descriptor -----------------

@dataclass(frozen=True)
class ProviderCapabilities:
    search: bool = True
    create_playlist: bool = False
    batch_add: bool = False
    supports_isrc: bool = True
    max_batch_size: int = 100
    # Indicates provider can fully replace (overwrite) playlist track ordering
    replace_playlist: bool = False

# ---------------- Link Generator (for web URLs) -----------------

class ProviderLinkGenerator(Protocol):
    """Protocol for generating web links to provider resources.

    Allows reports to link directly to tracks, albums, artists, and playlists
    on the streaming provider's website.
    """

    def track_url(self, track_id: str) -> str:
        """Generate URL for a track page."""
        ...  # pragma: no cover

    def album_url(self, album_id: str) -> str:
        """Generate URL for an album page."""
        ...  # pragma: no cover

    def artist_url(self, artist_id: str) -> str:
        """Generate URL for an artist page."""
        ...  # pragma: no cover

    def playlist_url(self, playlist_id: str) -> str:
        """Generate URL for a playlist page."""
        ...  # pragma: no cover

# ---------------- Authentication Provider -----------------

class AuthProvider(ABC):
    """Abstract authentication provider interface.

    Handles OAuth flows, token acquisition, refresh, and caching.
    Each provider (Spotify, Apple Music, etc.) implements this differently.
    """

    @abstractmethod
    def get_token(self, force: bool = False) -> Dict[str, Any]:
        """Get valid access token, potentially triggering OAuth flow.

        Args:
            force: Force full re-authentication even if cached token exists

        Returns:
            Token dict with at least 'access_token' and 'expires_at' keys

        Raises:
            RuntimeError: If authentication fails
        """

    @abstractmethod
    def clear_cache(self) -> None:
        """Clear cached credentials/tokens.

        Forces next get_token() to perform full authentication.
        """

    @abstractmethod
    def build_redirect_uri(self) -> str:
        """Build the OAuth redirect URI for this provider.

        Returns:
            Complete redirect URI (e.g., http://127.0.0.1:9876/callback)
        """

# ---------------- Provider Factory (Complete Provider) -----------------

class Provider(ABC):
    """Complete provider abstraction with auth + client factory.

    A Provider creates provider-specific auth and client instances and handles
    configuration validation.

    Example:
        provider = get_provider_instance('spotify')
        provider.validate_config(config['spotify'])
        auth = provider.create_auth(config['spotify'])
        token = auth.get_token()
        client = provider.create_client(token['access_token'])
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g., 'spotify', 'apple_music')."""

    @abstractmethod
    def create_auth(self, config: Dict[str, Any]) -> AuthProvider:
        """Create authentication provider from configuration.

        Args:
            config: Provider-specific configuration dict

        Returns:
            AuthProvider instance ready for token acquisition

        Raises:
            ValueError: If config is invalid
        """

    @abstractmethod
    def create_client(self, access_token: str) -> Any:
        """Create API client with access token.

        Args:
            access_token: Valid OAuth access token

        Returns:
            Provider-specific API client instance
        """

    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> None:
        """Validate provider-specific configuration.

        Args:
            config: Provider configuration dict

        Raises:
            ValueError: If required config keys missing or invalid
        """

    @abstractmethod
    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values for this provider.

        Returns:
            Dict with provider-specific default config
        """

    @abstractmethod
    def get_link_generator(self) -> ProviderLinkGenerator:
        """Get link generator for this provider.

        Returns:
            LinkGenerator instance for creating web URLs
        """


# ---------------- Provider instance registry -----------------

_provider_instances: dict[str, Provider] = {}


def register_provider(provider: Provider) -> None:
    """Register a provider instance.

    Args:
        provider: Provider instance to register
    """
    _provider_instances[provider.name] = provider


def get_provider_instance(name: str) -> Provider:
    """Get registered provider instance by name.

    Args:
        name: Provider name (e.g., 'spotify')

    Returns:
        Provider instance

    Raises:
        KeyError: If provider not registered
    """
    return _provider_instances[name]


def available_provider_instances() -> list[str]:
    """Get list of available provider instance names."""
    return sorted(_provider_instances.keys())


__all__ = [
    'Artist', 'Album', 'Track', 'Playlist', 'ProviderCapabilities',
    'ProviderLinkGenerator', 'AuthProvider', 'Provider',
    'register_provider', 'get_provider_instance', 'available_provider_instances',
]
