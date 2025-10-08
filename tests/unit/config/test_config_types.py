"""Unit tests for typed configuration dataclasses."""

import pytest
from psm.config_types import (
    MatchingConfig,
    LibraryConfig,
    SpotifyConfig,
    ExportConfig,
    ReportsConfig,
    DatabaseConfig,
    AppConfig,
    ProvidersConfig,
    TypedConfigDict
)


def test_matching_config_defaults():
    """Test MatchingConfig default values."""
    config = MatchingConfig()
    
    assert config.fuzzy_threshold == 0.78
    assert config.use_year is False
    assert config.duration_tolerance == 2.0
    assert config.show_unmatched_tracks == 20
    assert config.show_unmatched_albums == 20
    assert config.max_candidates_per_track == 500


def test_matching_config_custom_values():
    """Test MatchingConfig with custom values."""
    config = MatchingConfig(
        fuzzy_threshold=0.85,
        duration_tolerance=3.0,
        max_candidates_per_track=300
    )
    
    assert config.fuzzy_threshold == 0.85
    assert config.duration_tolerance == 3.0
    assert config.max_candidates_per_track == 300


def test_matching_config_to_dict():
    """Test MatchingConfig.to_dict() serialization."""
    config = MatchingConfig(fuzzy_threshold=0.90, duration_tolerance=1.5)
    
    data = config.to_dict()
    
    assert isinstance(data, dict)
    assert data['fuzzy_threshold'] == 0.90
    assert data['duration_tolerance'] == 1.5
    assert data['max_candidates_per_track'] == 500  # default


def test_library_config_defaults():
    """Test LibraryConfig default values."""
    config = LibraryConfig()
    
    assert config.paths == ["music"]
    assert config.extensions == [".mp3", ".flac", ".m4a", ".ogg"]
    assert config.follow_symlinks is False
    assert config.skip_unchanged is True
    assert config.min_bitrate_kbps == 320


def test_spotify_config_defaults():
    """Test SpotifyConfig default values."""
    config = SpotifyConfig()
    
    assert config.client_id is None
    assert config.redirect_scheme == "http"
    assert config.redirect_host == "127.0.0.1"
    assert config.redirect_port == 9876
    assert config.cache_file == "tokens.json"


def test_database_config_defaults():
    """Test DatabaseConfig default values."""
    config = DatabaseConfig()
    
    assert config.path == "data/spotify_sync.db"
    assert config.pragma_journal_mode == "WAL"


def test_export_config_defaults():
    """Test ExportConfig default values."""
    config = ExportConfig()
    
    assert config.directory == "export/playlists"
    assert config.mode == "mirrored"
    assert config.include_liked_songs is True


def test_app_config_defaults():
    """Test AppConfig default values."""
    config = AppConfig()
    
    assert config.log_level == "INFO"
    assert config.provider == "spotify"
    assert isinstance(config.matching, MatchingConfig)
    assert isinstance(config.library, LibraryConfig)
    assert isinstance(config.database, DatabaseConfig)


def test_app_config_to_dict():
    """Test AppConfig.to_dict() creates nested structure."""
    config = AppConfig()
    
    data = config.to_dict()
    
    assert isinstance(data, dict)
    assert 'matching' in data
    assert 'library' in data
    assert 'database' in data
    assert isinstance(data['matching'], dict)
    assert data['matching']['fuzzy_threshold'] == 0.78


def test_app_config_from_dict():
    """Test AppConfig.from_dict() creates typed config from dict."""
    raw_config = {
        'log_level': 'DEBUG',
        'provider': 'spotify',
        'providers': {
            'spotify': {
                'client_id': 'test123',
                'redirect_port': 8888
            }
        },
        'matching': {
            'fuzzy_threshold': 0.85,
            'duration_tolerance': 3.0
        },
        'library': {
            'paths': ['/music', '/media/music'],
            'min_bitrate_kbps': 256
        },
        'database': {
            'path': 'test.db'
        }
    }
    
    config = AppConfig.from_dict(raw_config)
    
    assert config.log_level == 'DEBUG'
    assert config.provider == 'spotify'
    assert config.matching.fuzzy_threshold == 0.85
    assert config.matching.duration_tolerance == 3.0
    assert config.library.paths == ['/music', '/media/music']
    assert config.library.min_bitrate_kbps == 256
    assert config.database.path == 'test.db'
    assert config.providers.spotify.client_id == 'test123'
    assert config.providers.spotify.redirect_port == 8888


def test_app_config_roundtrip():
    """Test that AppConfig can roundtrip to dict and back."""
    original = AppConfig(
        log_level='DEBUG',
        matching=MatchingConfig(fuzzy_threshold=0.90)
    )
    
    # Convert to dict
    data = original.to_dict()
    
    # Recreate from dict
    restored = AppConfig.from_dict(data)
    
    assert restored.log_level == 'DEBUG'
    assert restored.matching.fuzzy_threshold == 0.90


def test_typed_config_dict_wrapper():
    """Test TypedConfigDict provides typed access."""
    raw_dict = {
        'log_level': 'INFO',
        'provider': 'spotify',
        'providers': {'spotify': {'client_id': 'abc123'}},
        'matching': {'fuzzy_threshold': 0.80},
        'library': {'paths': ['/music']},
        'database': {'path': 'data/db.sqlite'},
        'export': {'directory': 'playlists'},
        'reports': {'directory': 'reports'}
    }
    
    config = TypedConfigDict(raw_dict)
    
    # Dict access still works
    assert config['log_level'] == 'INFO'
    assert config['matching']['fuzzy_threshold'] == 0.80
    
    # Typed access works
    assert config.typed.log_level == 'INFO'
    assert config.typed.matching.fuzzy_threshold == 0.80
    assert config.typed.provider == 'spotify'


def test_typed_config_dict_cache_invalidation():
    """Test that TypedConfigDict cache is invalidated on top-level modification."""
    config = TypedConfigDict({
        'log_level': 'INFO',
        'provider': 'spotify',
        'providers': {'spotify': {}},
        'matching': {'fuzzy_threshold': 0.78},
        'library': {},
        'database': {},
        'export': {},
        'reports': {}
    })
    
    # Access typed config
    typed1 = config.typed
    assert typed1.matching.fuzzy_threshold == 0.78
    
    # Modify top-level key (triggers __setitem__)
    config['matching'] = {'fuzzy_threshold': 0.90}
    
    # Typed config should reflect change
    typed2 = config.typed
    assert typed2.matching.fuzzy_threshold == 0.90


def test_matching_config_with_partial_dict():
    """Test that from_dict handles partial config (missing keys)."""
    partial = {
        'matching': {
            'fuzzy_threshold': 0.85
            # Other fields missing, should use defaults
        }
    }
    
    config = AppConfig.from_dict(partial)
    
    assert config.matching.fuzzy_threshold == 0.85
    assert config.matching.duration_tolerance == 2.0  # default
    assert config.matching.max_candidates_per_track == 500  # default


def test_providers_config_to_dict():
    """Test ProvidersConfig.to_dict()."""
    providers = ProvidersConfig(
        spotify=SpotifyConfig(client_id='test123', redirect_port=8080)
    )
    
    data = providers.to_dict()
    
    assert 'spotify' in data
    assert data['spotify']['client_id'] == 'test123'
    assert data['spotify']['redirect_port'] == 8080
