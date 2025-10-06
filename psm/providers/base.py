"""Provider abstraction layer.

This module defines provider-neutral domain models and an abstract client
interface so additional music streaming providers (e.g. Deezer, Tidal) can
be integrated without changing higher-level services.

Current implementation wraps existing Spotify-specific logic; other providers
can implement the same interface and register themselves in the registry.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Sequence, Optional, Protocol, runtime_checkable, Dict, Any

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

# ---------------- Provider client protocol -----------------

@runtime_checkable
class ProviderClient(Protocol):
    """Protocol for provider clients.

    Only methods actually needed by current services are specified. New
    functionality should be added incrementally once a second provider
    demonstrates the need, to avoid speculative over-abstraction.
    """

    name: str
    capabilities: ProviderCapabilities

    def current_user_profile(self) -> Dict[str, Any]: ...  # pragma: no cover
    def current_user_playlists(self, verbose: bool = False) -> Iterable[Dict[str, Any]]: ...  # pragma: no cover
    def playlist_items(self, playlist_id: str, verbose: bool = False) -> Sequence[Dict[str, Any]]: ...  # pragma: no cover

# ---------------- Registry -----------------

_registry: dict[str, type] = {}


def register(client_cls: type) -> type:
    _registry[getattr(client_cls, 'name', client_cls.__name__.lower())] = client_cls
    return client_cls


def get(provider_name: str) -> type:
    return _registry[provider_name]


def available_providers() -> list[str]:
    return sorted(_registry.keys())

__all__ = [
    'Artist', 'Album', 'Track', 'Playlist', 'ProviderCapabilities', 'ProviderClient',
    'ProviderLinkGenerator', 'register', 'get', 'available_providers'
]
