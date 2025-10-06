"""Pytest fixtures for test configuration."""
import pytest

# Temporarily disable all signal handling to isolate KeyboardInterrupt issue

def pytest_sessionstart(session):  # type: ignore[no-untyped-def]
    pass

def pytest_sessionfinish(session, exitstatus):  # type: ignore[no-untyped-def]
    pass

from pathlib import Path
from typing import Dict, Any


@pytest.fixture
def test_config(tmp_path: Path) -> Dict[str, Any]:
    """Provide a minimal test configuration as a dict.
    
    Tests should use this fixture and pass cfg to CLI/modules directly,
    rather than creating config files or setting environment variables.
    
    Default paths are isolated to tmp_path for test isolation.
    Tests can override individual values using dict update or deep_merge.
    """
    return {
        'log_level': 'DEBUG',
        'spotify': {
            'client_id': '',
            'redirect_scheme': 'http',
            'redirect_host': '127.0.0.1',
            'redirect_port': 9876,
            'redirect_path': '/callback',
            'scope': 'user-library-read playlist-read-private playlist-read-collaborative',
            'cache_file': str(tmp_path / 'tokens.json'),
            'cert_file': str(tmp_path / 'cert.pem'),
            'key_file': str(tmp_path / 'key.pem'),
        },
        'library': {
            'paths': [str(tmp_path / 'music')],
            'extensions': ['.mp3', '.flac', '.m4a', '.ogg'],
            'follow_symlinks': False,
            'ignore_patterns': ['.*'],
            'skip_unchanged': True,
            'fast_scan': True,
            'commit_interval': 10,
        },
        'matching': {
            'fuzzy_threshold': 0.78,
            'exact_bonus': 0.05,
            'album_match_bonus': 0.04,
            'use_year': False,
            'duration_tolerance': 2.0,
            'strategies': ['sql_exact', 'duration_filter', 'fuzzy'],
            'show_unmatched_tracks': 20,
            'show_unmatched_albums': 20,
        },
        'export': {
            'directory': str(tmp_path / 'export'),
            'mode': 'strict',
            'placeholder_extension': '.missing',
            'organize_by_owner': False,
        },
        'reports': {
            'directory': str(tmp_path / 'reports'),
        },
        'database': {
            'path': str(tmp_path / 'db.sqlite'),
            'pragma_journal_mode': 'WAL',
        },
    }
