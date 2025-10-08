"""Unit tests for MatchingEngine class."""

import pytest
from psm.match.matching_engine import MatchingEngine
from psm.db import Database
from pathlib import Path
import tempfile


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)
    
    db = Database(db_path)
    yield db
    db.close()
    db_path.unlink()


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        'provider': 'spotify',
        'matching': {
            'duration_tolerance': 2.0,
            'max_candidates_per_track': 500
        }
    }


def test_matching_engine_initialization(temp_db, sample_config):
    """Test that MatchingEngine initializes correctly."""
    engine = MatchingEngine(temp_db, sample_config)
    
    assert engine.db is temp_db
    assert engine.config == sample_config
    assert engine.dur_tolerance == 2.0
    assert engine.max_candidates == 500
    assert engine.provider == 'spotify'


def test_matching_engine_with_empty_database(temp_db, sample_config):
    """Test matching when database has no tracks or files."""
    engine = MatchingEngine(temp_db, sample_config)
    
    matched_count = engine.match_all()
    
    assert matched_count == 0


def test_matching_engine_with_no_files(temp_db, sample_config):
    """Test matching when database has tracks but no library files."""
    # Add a track
    temp_db.upsert_track({
        'id': 'track1',
        'name': 'Test Track',
        'artist': 'Test Artist',
        'album': 'Test Album',
        'year': 2024,
        'isrc': 'TEST123',
        'duration_ms': 180000,
        'normalized': 'test track test artist'
    }, provider='spotify')
    temp_db.commit()
    
    engine = MatchingEngine(temp_db, sample_config)
    matched_count = engine.match_all()
    
    assert matched_count == 0


def test_matching_engine_basic_match(temp_db, sample_config):
    """Test basic matching with one track and one file."""
    # Add a track
    temp_db.upsert_track({
        'id': 'track1',
        'name': 'Test Track',
        'artist': 'Test Artist',
        'album': 'Test Album',
        'year': 2024,
        'isrc': None,
        'duration_ms': 180000,
        'normalized': 'test track test artist'
    }, provider='spotify')
    
    # Add a matching file
    temp_db.add_library_file({
        'path': '/music/test_track.mp3',
        'title': 'Test Track',
        'artist': 'Test Artist',
        'album': 'Test Album',
        'year': 2024,
        'duration': 180,  # 3 minutes
        'normalized': 'test track test artist',
        'isrc': None
    })
    temp_db.commit()
    
    engine = MatchingEngine(temp_db, sample_config)
    matched_count = engine.match_all()
    
    assert matched_count == 1
    
    # Verify match was persisted
    matches = temp_db.conn.execute("SELECT * FROM matches").fetchall()
    assert len(matches) == 1
    assert matches[0]['track_id'] == 'track1'


def test_matching_engine_with_multiple_candidates(temp_db, sample_config):
    """Test matching when there are multiple candidate files."""
    # Add a track
    temp_db.upsert_track({
        'id': 'track1',
        'name': 'Hello',
        'artist': 'Adele',
        'album': '25',
        'year': 2015,
        'isrc': None,
        'duration_ms': 295000,  # ~4:55
        'normalized': 'hello adele'
    }, provider='spotify')
    
    # Add good match
    temp_db.add_library_file({
        'path': '/music/adele_hello.mp3',
        'title': 'Hello',
        'artist': 'Adele',
        'album': '25',
        'year': 2015,
        'duration': 295,
        'normalized': 'hello adele',
        'isrc': None
    })
    
    # Add poor match (different artist)
    temp_db.add_library_file({
        'path': '/music/hello_beatles.mp3',
        'title': 'Hello, Goodbye',
        'artist': 'The Beatles',
        'album': 'Magical Mystery Tour',
        'year': 1967,
        'duration': 207,
        'normalized': 'hello goodbye beatles',
        'isrc': None
    })
    
    temp_db.commit()
    
    engine = MatchingEngine(temp_db, sample_config)
    matched_count = engine.match_all()
    
    assert matched_count == 1
    
    # Verify it matched the correct file
    matches = temp_db.conn.execute(
        "SELECT m.*, lf.path FROM matches m JOIN library_files lf ON m.file_id = lf.id"
    ).fetchall()
    assert len(matches) == 1
    assert 'adele' in matches[0]['path'].lower()


def test_get_confidence_summary_with_no_matches(temp_db, sample_config):
    """Test confidence summary when there are no matches."""
    engine = MatchingEngine(temp_db, sample_config)
    
    summary = engine._get_confidence_summary(0)
    
    assert summary == "none"


def test_get_confidence_summary_with_matches(temp_db, sample_config):
    """Test confidence summary with various confidence levels."""
    # Add some test matches with different confidence levels
    temp_db.upsert_track({'id': 't1', 'name': 'T1', 'artist': 'A1', 'album': 'AL1', 
                          'year': 2024, 'isrc': None, 'duration_ms': 180000, 'normalized': 't1 a1'}, provider='spotify')
    temp_db.upsert_track({'id': 't2', 'name': 'T2', 'artist': 'A2', 'album': 'AL2',
                          'year': 2024, 'isrc': None, 'duration_ms': 180000, 'normalized': 't2 a2'}, provider='spotify')
    temp_db.upsert_track({'id': 't3', 'name': 'T3', 'artist': 'A3', 'album': 'AL3',
                          'year': 2024, 'isrc': None, 'duration_ms': 180000, 'normalized': 't3 a3'}, provider='spotify')
    
    temp_db.add_library_file({'path': '/f1.mp3', 'title': 'T1', 'artist': 'A1', 'album': 'AL1',
                              'year': 2024, 'duration': 180, 'normalized': 't1 a1', 'isrc': None})
    temp_db.add_library_file({'path': '/f2.mp3', 'title': 'T2', 'artist': 'A2', 'album': 'AL2',
                              'year': 2024, 'duration': 180, 'normalized': 't2 a2', 'isrc': None})
    temp_db.add_library_file({'path': '/f3.mp3', 'title': 'T3', 'artist': 'A3', 'album': 'AL3',
                              'year': 2024, 'duration': 180, 'normalized': 't3 a3', 'isrc': None})
    
    # Add matches with different confidence levels
    temp_db.add_match('t1', 1, 0.95, 'score:CERTAIN', provider='spotify')
    temp_db.add_match('t2', 2, 0.85, 'score:HIGH', provider='spotify')
    temp_db.add_match('t3', 3, 0.75, 'score:MEDIUM', provider='spotify')
    temp_db.commit()
    
    engine = MatchingEngine(temp_db, sample_config)
    summary = engine._get_confidence_summary(3)
    
    assert 'certain' in summary
    assert 'high' in summary
    assert 'medium' in summary


def test_normalize_file_dict():
    """Test file dict normalization helper."""
    raw = {
        'id': 1,
        'path': '/music/test.mp3',
        'title': 'Test Song',
        'artist': 'Test Artist',
        'album': 'Test Album',
        'year': 2024,
        'duration': 180,
        'normalized': 'test song test artist',
        'isrc': 'TEST123'
    }
    
    normalized = MatchingEngine._normalize_file_dict(raw)
    
    # Should have 'name' field matching 'title'
    assert normalized['name'] == 'Test Song'
    assert normalized['title'] == 'Test Song'
    assert normalized['artist'] == 'Test Artist'
    assert normalized['id'] == 1


def test_normalize_file_dict_missing_title():
    """Test normalization when title is missing."""
    raw = {
        'id': 1,
        'path': '/music/test.mp3',
        'artist': 'Test Artist',
        'album': None,
        'year': None,
        'duration': None,
        'normalized': '',
        'isrc': None
    }
    
    normalized = MatchingEngine._normalize_file_dict(raw)
    
    # Should handle missing fields gracefully
    assert normalized['name'] == ''
    assert normalized['title'] == ''
    assert normalized['artist'] == 'Test Artist'
    assert normalized['album'] is None


def test_matching_engine_progress_logging(temp_db, sample_config, caplog):
    """Test that progress logging happens at intervals."""
    import logging
    caplog.set_level(logging.INFO)
    
    # Add 150 tracks to trigger progress logging (progress_interval=100)
    for i in range(150):
        temp_db.upsert_track({
            'id': f'track{i}',
            'name': f'Track {i}',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'year': 2024,
            'isrc': None,
            'duration_ms': 180000,
            'normalized': f'track {i} test artist'
        }, provider='spotify')
    
    # Add some library files so there's something to match against
    for i in range(10):
        temp_db.add_library_file({
            'path': f'/music/track{i}.mp3',
            'title': f'Track {i}',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'year': 2024,
            'duration': 180,
            'normalized': f'track {i} test artist',
            'isrc': None
        })
    
    temp_db.commit()
    
    engine = MatchingEngine(temp_db, sample_config)
    engine.match_all()
    
    # Check that progress was logged
    log_messages = [record.message for record in caplog.records]
    progress_logs = [msg for msg in log_messages if 'tracks/s' in msg]
    
    # Should have at least one progress log (at 100 tracks)
    assert len(progress_logs) >= 1


def test_matching_engine_custom_config(temp_db):
    """Test engine with custom configuration values."""
    custom_config = {
        'provider': 'custom_provider',
        'matching': {
            'duration_tolerance': 5.0,
            'max_candidates_per_track': 100
        }
    }
    
    engine = MatchingEngine(temp_db, custom_config)
    
    assert engine.dur_tolerance == 5.0
    assert engine.max_candidates == 100
    assert engine.provider == 'custom_provider'


def test_matching_engine_default_config(temp_db):
    """Test engine with missing config sections uses defaults."""
    minimal_config = {}
    
    engine = MatchingEngine(temp_db, minimal_config)
    
    # Should use defaults
    assert engine.dur_tolerance == 2.0
    assert engine.max_candidates == 500
    assert engine.provider == 'spotify'


def test_match_tracks_with_specific_ids(temp_db, sample_config):
    """Test incremental matching of specific track IDs."""
    # Add tracks
    temp_db.upsert_track({
        'id': 'track1',
        'name': 'Track 1',
        'artist': 'Artist A',
        'album': 'Album A',
        'year': 2024,
        'isrc': None,
        'duration_ms': 180000,
        'normalized': 'track 1 artist a'
    }, provider='spotify')
    
    temp_db.upsert_track({
        'id': 'track2',
        'name': 'Track 2',
        'artist': 'Artist B',
        'album': 'Album B',
        'year': 2024,
        'isrc': None,
        'duration_ms': 200000,
        'normalized': 'track 2 artist b'
    }, provider='spotify')
    
    # Add matching files
    temp_db.add_library_file({
        'path': '/music/track1.mp3',
        'title': 'Track 1',
        'artist': 'Artist A',
        'album': 'Album A',
        'year': 2024,
        'duration': 180,
        'normalized': 'track 1 artist a',
        'isrc': None
    })
    
    temp_db.add_library_file({
        'path': '/music/track2.mp3',
        'title': 'Track 2',
        'artist': 'Artist B',
        'album': 'Album B',
        'year': 2024,
        'duration': 200,
        'normalized': 'track 2 artist b',
        'isrc': None
    })
    
    temp_db.commit()
    
    # Match only track1
    engine = MatchingEngine(temp_db, sample_config)
    matched = engine.match_tracks(track_ids=['track1'])
    
    assert matched == 1
    
    # Verify only track1 was matched
    matches = temp_db.conn.execute("SELECT track_id FROM matches").fetchall()
    assert len(matches) == 1
    assert matches[0]['track_id'] == 'track1'


def test_match_tracks_with_no_ids_matches_unmatched(temp_db, sample_config):
    """Test that match_tracks with no IDs matches all unmatched tracks."""
    # Add tracks
    temp_db.upsert_track({
        'id': 'track1',
        'name': 'Track 1',
        'artist': 'Artist A',
        'album': 'Album A',
        'year': 2024,
        'isrc': None,
        'duration_ms': 180000,
        'normalized': 'track 1 artist a'
    }, provider='spotify')
    
    temp_db.upsert_track({
        'id': 'track2',
        'name': 'Track 2',
        'artist': 'Artist B',
        'album': 'Album B',
        'year': 2024,
        'isrc': None,
        'duration_ms': 200000,
        'normalized': 'track 2 artist b'
    }, provider='spotify')
    
    # Add matching files
    temp_db.add_library_file({
        'path': '/music/track1.mp3',
        'title': 'Track 1',
        'artist': 'Artist A',
        'album': 'Album A',
        'year': 2024,
        'duration': 180,
        'normalized': 'track 1 artist a',
        'isrc': None
    })
    
    temp_db.add_library_file({
        'path': '/music/track2.mp3',
        'title': 'Track 2',
        'artist': 'Artist B',
        'album': 'Album B',
        'year': 2024,
        'duration': 200,
        'normalized': 'track 2 artist b',
        'isrc': None
    })
    
    temp_db.commit()
    
    # Match without specifying IDs (should match all unmatched)
    engine = MatchingEngine(temp_db, sample_config)
    matched = engine.match_tracks(track_ids=None)
    
    assert matched == 2
    
    # Verify both were matched
    matches = temp_db.conn.execute("SELECT track_id FROM matches ORDER BY track_id").fetchall()
    assert len(matches) == 2
    assert matches[0]['track_id'] == 'track1'
    assert matches[1]['track_id'] == 'track2'


def test_match_files_with_specific_ids(temp_db, sample_config):
    """Test incremental matching of specific file IDs."""
    # Add tracks
    temp_db.upsert_track({
        'id': 'track1',
        'name': 'Track 1',
        'artist': 'Artist A',
        'album': 'Album A',
        'year': 2024,
        'isrc': None,
        'duration_ms': 180000,
        'normalized': 'track 1 artist a'
    }, provider='spotify')
    
    temp_db.upsert_track({
        'id': 'track2',
        'name': 'Track 2',
        'artist': 'Artist B',
        'album': 'Album B',
        'year': 2024,
        'isrc': None,
        'duration_ms': 200000,
        'normalized': 'track 2 artist b'
    }, provider='spotify')
    
    # Add matching files
    temp_db.add_library_file({
        'path': '/music/track1.mp3',
        'title': 'Track 1',
        'artist': 'Artist A',
        'album': 'Album A',
        'year': 2024,
        'duration': 180,
        'normalized': 'track 1 artist a',
        'isrc': None
    })
    
    temp_db.add_library_file({
        'path': '/music/track2.mp3',
        'title': 'Track 2',
        'artist': 'Artist B',
        'album': 'Album B',
        'year': 2024,
        'duration': 200,
        'normalized': 'track 2 artist b',
        'isrc': None
    })
    
    temp_db.commit()
    
    # Match only file ID 1
    engine = MatchingEngine(temp_db, sample_config)
    matched = engine.match_files(file_ids=[1])
    
    assert matched == 1
    
    # Verify only file 1 was matched
    matches = temp_db.conn.execute("SELECT file_id FROM matches").fetchall()
    assert len(matches) == 1
    assert matches[0]['file_id'] == 1


def test_match_files_with_no_ids_matches_unmatched(temp_db, sample_config):
    """Test that match_files with no IDs matches all unmatched files."""
    # Add tracks
    temp_db.upsert_track({
        'id': 'track1',
        'name': 'Track 1',
        'artist': 'Artist A',
        'album': 'Album A',
        'year': 2024,
        'isrc': None,
        'duration_ms': 180000,
        'normalized': 'track 1 artist a'
    }, provider='spotify')
    
    temp_db.upsert_track({
        'id': 'track2',
        'name': 'Track 2',
        'artist': 'Artist B',
        'album': 'Album B',
        'year': 2024,
        'isrc': None,
        'duration_ms': 200000,
        'normalized': 'track 2 artist b'
    }, provider='spotify')
    
    # Add matching files
    temp_db.add_library_file({
        'path': '/music/track1.mp3',
        'title': 'Track 1',
        'artist': 'Artist A',
        'album': 'Album A',
        'year': 2024,
        'duration': 180,
        'normalized': 'track 1 artist a',
        'isrc': None
    })
    
    temp_db.add_library_file({
        'path': '/music/track2.mp3',
        'title': 'Track 2',
        'artist': 'Artist B',
        'album': 'Album B',
        'year': 2024,
        'duration': 200,
        'normalized': 'track 2 artist b',
        'isrc': None
    })
    
    temp_db.commit()
    
    # Match without specifying IDs (should match all unmatched)
    engine = MatchingEngine(temp_db, sample_config)
    matched = engine.match_files(file_ids=None)
    
    assert matched == 2
    
    # Verify both were matched
    matches = temp_db.conn.execute("SELECT file_id FROM matches ORDER BY file_id").fetchall()
    assert len(matches) == 2
    assert matches[0]['file_id'] == 1
    assert matches[1]['file_id'] == 2


def test_match_tracks_deletes_existing_matches(temp_db, sample_config):
    """Test that match_tracks deletes old matches for the specified tracks."""
    # Add track and file
    temp_db.upsert_track({
        'id': 'track1',
        'name': 'Track 1',
        'artist': 'Artist A',
        'album': 'Album A',
        'year': 2024,
        'isrc': None,
        'duration_ms': 180000,
        'normalized': 'track 1 artist a'
    }, provider='spotify')
    
    temp_db.add_library_file({
        'path': '/music/track1.mp3',
        'title': 'Track 1',
        'artist': 'Artist A',
        'album': 'Album A',
        'year': 2024,
        'duration': 180,
        'normalized': 'track 1 artist a',
        'isrc': None
    })
    
    # Create an initial match manually
    temp_db.add_match('track1', 1, 0.90, 'score:HIGH', provider='spotify')
    temp_db.commit()
    
    # Verify initial match exists
    matches = temp_db.conn.execute("SELECT * FROM matches WHERE track_id='track1'").fetchall()
    assert len(matches) == 1
    assert matches[0]['method'] == 'score:HIGH'
    
    # Re-match the same track (should delete old match and create new)
    engine = MatchingEngine(temp_db, sample_config)
    matched = engine.match_tracks(track_ids=['track1'])
    
    assert matched == 1
    
    # Verify only one match exists (old one was deleted)
    matches = temp_db.conn.execute("SELECT * FROM matches WHERE track_id='track1'").fetchall()
    assert len(matches) == 1


def test_match_files_deletes_existing_matches(temp_db, sample_config):
    """Test that match_files deletes old matches for the specified files."""
    # Add track and file
    temp_db.upsert_track({
        'id': 'track1',
        'name': 'Track 1',
        'artist': 'Artist A',
        'album': 'Album A',
        'year': 2024,
        'isrc': None,
        'duration_ms': 180000,
        'normalized': 'track 1 artist a'
    }, provider='spotify')
    
    temp_db.add_library_file({
        'path': '/music/track1.mp3',
        'title': 'Track 1',
        'artist': 'Artist A',
        'album': 'Album A',
        'year': 2024,
        'duration': 180,
        'normalized': 'track 1 artist a',
        'isrc': None
    })
    
    # Create an initial match manually
    temp_db.add_match('track1', 1, 0.90, 'score:HIGH', provider='spotify')
    temp_db.commit()
    
    # Verify initial match exists
    matches = temp_db.conn.execute("SELECT * FROM matches WHERE file_id=1").fetchall()
    assert len(matches) == 1
    assert matches[0]['method'] == 'score:HIGH'
    
    # Re-match the same file (should delete old match and create new)
    engine = MatchingEngine(temp_db, sample_config)
    matched = engine.match_files(file_ids=[1])
    
    assert matched == 1
    
    # Verify only one match exists (old one was deleted)
    matches = temp_db.conn.execute("SELECT * FROM matches WHERE file_id=1").fetchall()
    assert len(matches) == 1

