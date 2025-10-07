from __future__ import annotations
import pytest
from .mock_database import MockDatabase

@pytest.fixture
def mock_db():
    return MockDatabase()

@pytest.fixture
def sample_track():
    return {
        'id': 'track1',
        'name': 'Example Song',
        'album': 'Example Album',
        'artist': 'Example Artist',
        'album_id': 'alb1',
        'artist_id': 'art1',
        'isrc': 'ISRC123',
        'duration_ms': 180000,
        'normalized': 'example song example artist',
        'year': 2024,
    }

@pytest.fixture
def sample_library_file(tmp_path):
    return {
        'path': str(tmp_path / 'song.mp3'),
        'size': 1234,
        'mtime': 0.0,
        'partial_hash': 'abc',
        'title': 'Example Song',
        'album': 'Example Album',
        'artist': 'Example Artist',
        'duration': 180.0,
        'normalized': 'example song example artist',
        'year': 2024,
        'bitrate_kbps': 320,
    }
