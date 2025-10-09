"""Typed configuration dataclasses for spotify-m3u-sync.

Provides strongly-typed configuration objects that can be used throughout
the application for better type safety and IDE support.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any


@dataclass
class SpotifyConfig:
    """Spotify OAuth and API configuration."""
    client_id: str | None = None
    redirect_scheme: str = "http"
    redirect_host: str = "127.0.0.1"
    redirect_port: int = 9876
    redirect_path: str = "/callback"
    scope: str = "user-library-read playlist-read-private playlist-read-collaborative"
    cache_file: str = "tokens.json"
    cert_file: str = "cert.pem"
    key_file: str = "key.pem"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return asdict(self)


@dataclass
class LibraryConfig:
    """Local music library scanning configuration."""
    paths: List[str] = field(default_factory=lambda: ["music"])
    extensions: List[str] = field(default_factory=lambda: [".mp3", ".flac", ".m4a", ".ogg"])
    follow_symlinks: bool = False
    ignore_patterns: List[str] = field(default_factory=lambda: [".*"])
    skip_unchanged: bool = True
    fast_scan: bool = True
    commit_interval: int = 100
    min_bitrate_kbps: int = 320
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return asdict(self)


@dataclass
class MatchingConfig:
    """Track matching algorithm configuration (aligned with _DEFAULTS)."""
    fuzzy_threshold: float = 0.78  # 0.0-1.0 scale
    use_year: bool = False
    duration_tolerance: float = 5.0  # seconds (aligned with _DEFAULTS)
    show_unmatched_tracks: int = 20
    show_unmatched_albums: int = 20
    max_candidates_per_track: int = 500  # Performance safeguard: cap candidates per track
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return asdict(self)


@dataclass
class ProvidersConfig:
    """Configuration for all providers."""
    spotify: SpotifyConfig = field(default_factory=SpotifyConfig)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return {"spotify": self.spotify.to_dict()}


@dataclass
class ExportConfig:
    """Playlist export configuration."""
    directory: str = "export/playlists"
    mode: str = "mirrored"
    placeholder_extension: str = ".missing"
    organize_by_owner: bool = False
    include_liked_songs: bool = True  # Export Liked Songs as virtual playlist
    path_format: str = "absolute"  # "absolute" or "relative"
    use_library_roots: bool = True  # Reconstruct paths using config library roots
    clean_before_export: bool = False  # Delete all existing .m3u files before export
    auto_overwrite: bool = True  # Automatically overwrite existing files (false = prompt if newer)
    detect_obsolete: bool = True  # Detect and report/prompt about obsolete playlists
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return asdict(self)


@dataclass
class ReportsConfig:
    """Reporting configuration."""
    directory: str = "export/reports"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return asdict(self)


@dataclass
class DatabaseConfig:
    """Database configuration."""
    path: str = "data/spotify_sync.db"
    pragma_journal_mode: str = "WAL"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return asdict(self)


@dataclass
class AppConfig:
    """Root application configuration with all subsections."""
    log_level: str = "INFO"
    provider: str = "spotify"
    providers: ProvidersConfig = field(default_factory=ProvidersConfig)
    library: LibraryConfig = field(default_factory=LibraryConfig)
    matching: MatchingConfig = field(default_factory=MatchingConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    reports: ReportsConfig = field(default_factory=ReportsConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to nested dictionary for backward compatibility.
        
        Returns:
            Nested dict structure matching config format
        """
        return {
            "log_level": self.log_level,
            "provider": self.provider,
            "providers": self.providers.to_dict(),
            "library": self.library.to_dict(),
            "matching": self.matching.to_dict(),
            "export": self.export.to_dict(),
            "reports": self.reports.to_dict(),
            "database": self.database.to_dict(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AppConfig:
        """Create typed config from dictionary.
        
        Args:
            data: Dictionary config (from load_config)
            
        Returns:
            Typed AppConfig instance
        """
        # Get provider config from providers.{provider_name}
        provider_name = data.get("provider", "spotify")
        providers_data = data.get("providers", {})
        provider_config = providers_data.get(provider_name, {})
        
        return cls(
            log_level=data.get("log_level", "INFO"),
            provider=provider_name,
            providers=ProvidersConfig(spotify=SpotifyConfig(**provider_config)),
            library=LibraryConfig(**data.get("library", {})),
            matching=MatchingConfig(**data.get("matching", {})),
            export=ExportConfig(**data.get("export", {})),
            reports=ReportsConfig(**data.get("reports", {})),
            database=DatabaseConfig(**data.get("database", {})),
        )


# Type-aware config dict wrapper for gradual migration
class TypedConfigDict(dict):
    """Dictionary wrapper that provides typed access to config sections.
    
    This allows gradual migration from dict-based to typed config:
    - Existing code: cfg['spotify']['client_id']  (still works)
    - New code: cfg.typed.spotify.client_id  (typed access)
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._typed_cache: AppConfig | None = None
    
    @property
    def typed(self) -> AppConfig:
        """Get strongly-typed config object.
        
        Returns:
            AppConfig instance with typed access
        """
        if self._typed_cache is None:
            self._typed_cache = AppConfig.from_dict(self)
        return self._typed_cache
    
    def __setitem__(self, key, value):
        """Invalidate typed cache when dict is modified."""
        super().__setitem__(key, value)
        self._typed_cache = None
    
    def update(self, *args, **kwargs):
        """Invalidate typed cache when dict is updated."""
        super().update(*args, **kwargs)
        self._typed_cache = None


__all__ = [
    "AppConfig",
    "ProvidersConfig",
    "SpotifyConfig",
    "LibraryConfig",
    "MatchingConfig",
    "ExportConfig",
    "ReportsConfig",
    "DatabaseConfig",
    "TypedConfigDict",
]
