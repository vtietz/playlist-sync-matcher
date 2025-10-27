"""Unit tests for MatchingEngine class."""

import pytest
from psm.match.matching_engine import MatchingEngine
from psm.config_types import MatchingConfig
from psm.db import Database
from pathlib import Path
import tempfile


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    db = Database(db_path)
    yield db
    db.close()
    db_path.unlink()


@pytest.fixture
def sample_config():
    """Sample MatchingConfig for testing."""
    return MatchingConfig(duration_tolerance=2.0, max_candidates_per_track=500, fuzzy_threshold=0.85)


def test_matching_engine_initialization(temp_db, sample_config):
    """Test that MatchingEngine initializes correctly."""
    engine = MatchingEngine(temp_db, sample_config, provider="spotify")

    assert engine.db is temp_db
    assert engine.dur_tolerance == 2.0
    assert engine.max_candidates == 500
    assert engine.provider == "spotify"


def test_matching_engine_with_empty_database(temp_db, sample_config):
    """Test matching when database has no tracks or files."""
    engine = MatchingEngine(temp_db, sample_config)

    matched_count = engine.match_all()

    assert matched_count == 0


def test_matching_engine_with_no_files(temp_db, sample_config):
    """Test matching when database has tracks but no library files."""
    # Add a track
    temp_db.upsert_track(
        {
            "id": "track1",
            "name": "Test Track",
            "artist": "Test Artist",
            "album": "Test Album",
            "year": 2024,
            "isrc": "TEST123",
            "duration_ms": 180000,
            "normalized": "test track test artist",
        },
        provider="spotify",
    )
    temp_db.commit()

    engine = MatchingEngine(temp_db, sample_config)
    matched_count = engine.match_all()

    assert matched_count == 0


def test_matching_engine_basic_match(temp_db, sample_config):
    """Test basic matching with one track and one file."""
    # Add a track
    temp_db.upsert_track(
        {
            "id": "track1",
            "name": "Test Track",
            "artist": "Test Artist",
            "album": "Test Album",
            "year": 2024,
            "isrc": None,
            "duration_ms": 180000,
            "normalized": "test track test artist",
        },
        provider="spotify",
    )

    # Add a matching file
    temp_db.add_library_file(
        {
            "path": "/music/test_track.mp3",
            "title": "Test Track",
            "artist": "Test Artist",
            "album": "Test Album",
            "year": 2024,
            "duration": 180,  # 3 minutes
            "normalized": "test track test artist",
            "isrc": None,
        }
    )
    temp_db.commit()

    engine = MatchingEngine(temp_db, sample_config)
    matched_count = engine.match_all()

    assert matched_count == 1

    # Verify match was persisted
    matches = temp_db.conn.execute("SELECT * FROM matches").fetchall()
    assert len(matches) == 1
    assert matches[0]["track_id"] == "track1"


def test_matching_engine_with_multiple_candidates(temp_db, sample_config):
    """Test matching when there are multiple candidate files."""
    # Add a track
    temp_db.upsert_track(
        {
            "id": "track1",
            "name": "Hello",
            "artist": "Adele",
            "album": "25",
            "year": 2015,
            "isrc": None,
            "duration_ms": 295000,  # ~4:55
            "normalized": "hello adele",
        },
        provider="spotify",
    )

    # Add good match
    temp_db.add_library_file(
        {
            "path": "/music/adele_hello.mp3",
            "title": "Hello",
            "artist": "Adele",
            "album": "25",
            "year": 2015,
            "duration": 295,
            "normalized": "hello adele",
            "isrc": None,
        }
    )

    # Add poor match (different artist)
    temp_db.add_library_file(
        {
            "path": "/music/hello_beatles.mp3",
            "title": "Hello, Goodbye",
            "artist": "The Beatles",
            "album": "Magical Mystery Tour",
            "year": 1967,
            "duration": 207,
            "normalized": "hello goodbye beatles",
            "isrc": None,
        }
    )

    temp_db.commit()

    engine = MatchingEngine(temp_db, sample_config)
    matched_count = engine.match_all()

    assert matched_count == 1

    # Verify it matched the correct file
    matches = temp_db.conn.execute(
        "SELECT m.*, lf.path FROM matches m JOIN library_files lf ON m.file_id = lf.id"
    ).fetchall()
    assert len(matches) == 1
    assert "adele" in matches[0]["path"].lower()


@pytest.mark.parametrize(
    "config,provider,expected_tolerance,expected_max_candidates,expected_provider",
    [
        # Typed MatchingConfig with custom values
        (
            MatchingConfig(duration_tolerance=5.0, max_candidates_per_track=100, fuzzy_threshold=0.90),
            "custom_provider",
            5.0,
            100,
            "custom_provider",
        ),
        # Typed MatchingConfig with defaults
        (MatchingConfig(), "spotify", 5.0, 500, "spotify"),
        # Typed MatchingConfig with mixed values
        (
            MatchingConfig(duration_tolerance=3.0, max_candidates_per_track=200, fuzzy_threshold=0.80),
            "spotify",
            3.0,
            200,
            "spotify",
        ),
    ],
)
def test_matching_engine_config_variations(
    temp_db, config, provider, expected_tolerance, expected_max_candidates, expected_provider
):
    """Test MatchingEngine with various MatchingConfig instances."""
    engine = MatchingEngine(temp_db, config, provider=provider)

    assert engine.dur_tolerance == expected_tolerance
    assert engine.max_candidates == expected_max_candidates
    assert engine.provider == expected_provider


def test_match_tracks_with_specific_ids(temp_db, sample_config):
    """Test incremental matching of specific track IDs."""
    # Add tracks
    temp_db.upsert_track(
        {
            "id": "track1",
            "name": "Track 1",
            "artist": "Artist A",
            "album": "Album A",
            "year": 2024,
            "isrc": None,
            "duration_ms": 180000,
            "normalized": "track 1 artist a",
        },
        provider="spotify",
    )

    temp_db.upsert_track(
        {
            "id": "track2",
            "name": "Track 2",
            "artist": "Artist B",
            "album": "Album B",
            "year": 2024,
            "isrc": None,
            "duration_ms": 200000,
            "normalized": "track 2 artist b",
        },
        provider="spotify",
    )

    # Add matching files
    temp_db.add_library_file(
        {
            "path": "/music/track1.mp3",
            "title": "Track 1",
            "artist": "Artist A",
            "album": "Album A",
            "year": 2024,
            "duration": 180,
            "normalized": "track 1 artist a",
            "isrc": None,
        }
    )

    temp_db.add_library_file(
        {
            "path": "/music/track2.mp3",
            "title": "Track 2",
            "artist": "Artist B",
            "album": "Album B",
            "year": 2024,
            "duration": 200,
            "normalized": "track 2 artist b",
            "isrc": None,
        }
    )

    temp_db.commit()

    # Match only track1
    engine = MatchingEngine(temp_db, sample_config)
    matched = engine.match_tracks(track_ids=["track1"])

    assert matched == 1

    # Verify only track1 was matched
    matches = temp_db.conn.execute("SELECT track_id FROM matches").fetchall()
    assert len(matches) == 1
    assert matches[0]["track_id"] == "track1"


def test_match_tracks_with_no_ids_matches_unmatched(temp_db, sample_config):
    """Test that match_tracks with no IDs matches all unmatched tracks."""
    # Add tracks
    temp_db.upsert_track(
        {
            "id": "track1",
            "name": "Track 1",
            "artist": "Artist A",
            "album": "Album A",
            "year": 2024,
            "isrc": None,
            "duration_ms": 180000,
            "normalized": "track 1 artist a",
        },
        provider="spotify",
    )

    temp_db.upsert_track(
        {
            "id": "track2",
            "name": "Track 2",
            "artist": "Artist B",
            "album": "Album B",
            "year": 2024,
            "isrc": None,
            "duration_ms": 200000,
            "normalized": "track 2 artist b",
        },
        provider="spotify",
    )

    # Add matching files
    temp_db.add_library_file(
        {
            "path": "/music/track1.mp3",
            "title": "Track 1",
            "artist": "Artist A",
            "album": "Album A",
            "year": 2024,
            "duration": 180,
            "normalized": "track 1 artist a",
            "isrc": None,
        }
    )

    temp_db.add_library_file(
        {
            "path": "/music/track2.mp3",
            "title": "Track 2",
            "artist": "Artist B",
            "album": "Album B",
            "year": 2024,
            "duration": 200,
            "normalized": "track 2 artist b",
            "isrc": None,
        }
    )

    temp_db.commit()

    # Match without specifying IDs (should match all unmatched)
    engine = MatchingEngine(temp_db, sample_config)
    matched = engine.match_tracks(track_ids=None)

    assert matched == 2

    # Verify both were matched
    matches = temp_db.conn.execute("SELECT track_id FROM matches ORDER BY track_id").fetchall()
    assert len(matches) == 2
    assert matches[0]["track_id"] == "track1"
    assert matches[1]["track_id"] == "track2"


def test_match_files_with_specific_ids(temp_db, sample_config):
    """Test incremental matching of specific file IDs."""
    # Add tracks
    temp_db.upsert_track(
        {
            "id": "track1",
            "name": "Track 1",
            "artist": "Artist A",
            "album": "Album A",
            "year": 2024,
            "isrc": None,
            "duration_ms": 180000,
            "normalized": "track 1 artist a",
        },
        provider="spotify",
    )

    temp_db.upsert_track(
        {
            "id": "track2",
            "name": "Track 2",
            "artist": "Artist B",
            "album": "Album B",
            "year": 2024,
            "isrc": None,
            "duration_ms": 200000,
            "normalized": "track 2 artist b",
        },
        provider="spotify",
    )

    # Add matching files
    temp_db.add_library_file(
        {
            "path": "/music/track1.mp3",
            "title": "Track 1",
            "artist": "Artist A",
            "album": "Album A",
            "year": 2024,
            "duration": 180,
            "normalized": "track 1 artist a",
            "isrc": None,
        }
    )

    temp_db.add_library_file(
        {
            "path": "/music/track2.mp3",
            "title": "Track 2",
            "artist": "Artist B",
            "album": "Album B",
            "year": 2024,
            "duration": 200,
            "normalized": "track 2 artist b",
            "isrc": None,
        }
    )

    temp_db.commit()

    # Match only file ID 1
    engine = MatchingEngine(temp_db, sample_config)
    match_count, matched_track_ids = engine.match_files(file_ids=[1])

    assert match_count == 1
    assert "track1" in matched_track_ids

    # Verify only file 1 was matched
    matches = temp_db.conn.execute("SELECT file_id FROM matches").fetchall()
    assert len(matches) == 1
    assert matches[0]["file_id"] == 1


def test_match_files_with_no_ids_matches_unmatched(temp_db, sample_config):
    """Test that match_files with no IDs matches all unmatched files."""
    # Add tracks
    temp_db.upsert_track(
        {
            "id": "track1",
            "name": "Track 1",
            "artist": "Artist A",
            "album": "Album A",
            "year": 2024,
            "isrc": None,
            "duration_ms": 180000,
            "normalized": "track 1 artist a",
        },
        provider="spotify",
    )

    temp_db.upsert_track(
        {
            "id": "track2",
            "name": "Track 2",
            "artist": "Artist B",
            "album": "Album B",
            "year": 2024,
            "isrc": None,
            "duration_ms": 200000,
            "normalized": "track 2 artist b",
        },
        provider="spotify",
    )

    # Add matching files
    temp_db.add_library_file(
        {
            "path": "/music/track1.mp3",
            "title": "Track 1",
            "artist": "Artist A",
            "album": "Album A",
            "year": 2024,
            "duration": 180,
            "normalized": "track 1 artist a",
            "isrc": None,
        }
    )

    temp_db.add_library_file(
        {
            "path": "/music/track2.mp3",
            "title": "Track 2",
            "artist": "Artist B",
            "album": "Album B",
            "year": 2024,
            "duration": 200,
            "normalized": "track 2 artist b",
            "isrc": None,
        }
    )

    temp_db.commit()

    # Match without specifying IDs (should match all unmatched)
    engine = MatchingEngine(temp_db, sample_config)
    match_count, matched_track_ids = engine.match_files(file_ids=None)

    assert match_count == 2
    assert set(matched_track_ids) == {"track1", "track2"}

    # Verify both were matched
    matches = temp_db.conn.execute("SELECT file_id FROM matches ORDER BY file_id").fetchall()
    assert len(matches) == 2
    assert matches[0]["file_id"] == 1
    assert matches[1]["file_id"] == 2


def test_match_tracks_deletes_existing_matches(temp_db, sample_config):
    """Test that match_tracks deletes old matches for the specified tracks."""
    # Add track and file
    temp_db.upsert_track(
        {
            "id": "track1",
            "name": "Track 1",
            "artist": "Artist A",
            "album": "Album A",
            "year": 2024,
            "isrc": None,
            "duration_ms": 180000,
            "normalized": "track 1 artist a",
        },
        provider="spotify",
    )

    temp_db.add_library_file(
        {
            "path": "/music/track1.mp3",
            "title": "Track 1",
            "artist": "Artist A",
            "album": "Album A",
            "year": 2024,
            "duration": 180,
            "normalized": "track 1 artist a",
            "isrc": None,
        }
    )

    # Create an initial match manually
    temp_db.add_match("track1", 1, 0.90, "score:HIGH", provider="spotify")
    temp_db.commit()

    # Verify initial match exists
    matches = temp_db.conn.execute("SELECT * FROM matches WHERE track_id='track1'").fetchall()
    assert len(matches) == 1
    assert matches[0]["method"] == "score:HIGH"

    # Re-match the same track (should delete old match and create new)
    engine = MatchingEngine(temp_db, sample_config)
    matched = engine.match_tracks(track_ids=["track1"])

    assert matched == 1

    # Verify only one match exists (old one was deleted)
    matches = temp_db.conn.execute("SELECT * FROM matches WHERE track_id='track1'").fetchall()
    assert len(matches) == 1


def test_match_files_deletes_existing_matches(temp_db, sample_config):
    """Test that match_files deletes old matches for the specified files."""
    # Add track and file
    temp_db.upsert_track(
        {
            "id": "track1",
            "name": "Track 1",
            "artist": "Artist A",
            "album": "Album A",
            "year": 2024,
            "isrc": None,
            "duration_ms": 180000,
            "normalized": "track 1 artist a",
        },
        provider="spotify",
    )

    temp_db.add_library_file(
        {
            "path": "/music/track1.mp3",
            "title": "Track 1",
            "artist": "Artist A",
            "album": "Album A",
            "year": 2024,
            "duration": 180,
            "normalized": "track 1 artist a",
            "isrc": None,
        }
    )

    # Create an initial match manually
    temp_db.add_match("track1", 1, 0.90, "score:HIGH", provider="spotify")
    temp_db.commit()

    # Verify initial match exists
    matches = temp_db.conn.execute("SELECT * FROM matches WHERE file_id=1").fetchall()
    assert len(matches) == 1
    assert matches[0]["method"] == "score:HIGH"

    # Re-match the same file (should delete old match and create new)
    engine = MatchingEngine(temp_db, sample_config)
    match_count, matched_track_ids = engine.match_files(file_ids=[1])

    assert match_count == 1
    assert "track1" in matched_track_ids

    # Verify only one match exists (old one was deleted)
    matches = temp_db.conn.execute("SELECT * FROM matches WHERE file_id=1").fetchall()
    assert len(matches) == 1


def test_matching_engine_typed_config_with_matching(temp_db):
    """Test that typed config actually works for matching."""
    # Add track and file
    temp_db.upsert_track(
        {
            "id": "track1",
            "name": "Test Track",
            "artist": "Test Artist",
            "album": "Test Album",
            "year": 2024,
            "isrc": None,
            "duration_ms": 180000,
            "normalized": "test track test artist",
        },
        provider="spotify",
    )

    temp_db.add_library_file(
        {
            "path": "/music/test_track.mp3",
            "title": "Test Track",
            "artist": "Test Artist",
            "album": "Test Album",
            "year": 2024,
            "duration": 180,
            "normalized": "test track test artist",
            "isrc": None,
        }
    )
    temp_db.commit()

    # Create typed config
    typed_config = MatchingConfig(duration_tolerance=2.0, max_candidates_per_track=500)

    # Match using typed config
    engine = MatchingEngine(temp_db, typed_config, provider="spotify")
    matched_count = engine.match_all()

    assert matched_count == 1

    # Verify match was created
    matches = temp_db.conn.execute("SELECT * FROM matches").fetchall()
    assert len(matches) == 1
