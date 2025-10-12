"""Tests for DataFacade."""
import pytest
from pathlib import Path
from psm.gui.data_facade import DataFacade
from psm.db.sqlite_impl import Database


@pytest.fixture
def db_with_data(tmp_path):
    """Create a database with test data."""
    db_path = tmp_path / "test.db"
    db = Database(Path(db_path))  # Database opens connection in __init__

    # Create test playlists
    db.upsert_playlist(
        pid='p1',
        name='Workout Mix',
        snapshot_id=None,
        owner_id='user1',
        owner_name='testuser',
        provider='spotify'
    )
    db.upsert_playlist(
        pid='p2',
        name='Chill Vibes',
        snapshot_id=None,
        owner_id='user1',
        owner_name='testuser',
        provider='spotify'
    )

    # Add tracks (upsert_track expects a dict with flat fields)
    db.upsert_track(
        track={
            'id': 't1',
            'name': 'Song 1',
            'artist': 'Artist 1',
            'album': 'Album 1',
            'duration_ms': 180000
        },
        provider='spotify'
    )
    db.upsert_track(
        track={
            'id': 't2',
            'name': 'Song 2',
            'artist': 'Artist 2',
            'album': 'Album 2',
            'duration_ms': 200000
        },
        provider='spotify'
    )

    # Link tracks to playlists using replace_playlist_tracks
    # Signature: replace_playlist_tracks(pid, tracks: Sequence[Tuple[int, str, str | None]], provider)
    # Tuple is (position, track_id, added_at)
    db.replace_playlist_tracks('p1', [(0, 't1', None), (1, 't2', None)], provider='spotify')
    db.replace_playlist_tracks('p2', [(0, 't2', None)], provider='spotify')

    # Add a local file (add_library_file expects a dict)
    file_data = {
        'path': '/music/song1.mp3',
        'title': 'Song 1',
        'artist': 'Artist 1',
        'album': 'Album 1',
        'duration_ms': 180000
    }
    db.add_library_file(file_data)

    # Get the file_id we just inserted
    # We need to query to get the auto-generated file_id
    conn = db.conn
    cursor = conn.execute("SELECT id FROM library_files WHERE path = ?", ('/music/song1.mp3',))
    row = cursor.fetchone()
    file_id = row[0] if row else 1

    # Add match (add_match expects: track_id, file_id, score, method, provider)
    db.add_match(
        track_id='t1',
        file_id=file_id,
        score=95.0,
        method='exact',
        provider='spotify'
    )

    yield db

    # Close connection (Database might not have close() method, use context manager protocol)
    if hasattr(db, 'close'):
        db.close()


class TestDataFacade:
    """Tests for DataFacade."""

    def test_list_playlists_includes_all_playlists_row(self, db_with_data):
        """Test that list_playlists returns playlists with coverage statistics."""
        facade = DataFacade(db_with_data, provider='spotify')
        playlists = facade.list_playlists()

        # Should have 2 playlists (no longer includes synthetic "All Playlists")
        assert len(playlists) == 2

        # Find "Workout Mix" playlist
        workout = next((p for p in playlists if p['name'] == 'Workout Mix'), None)
        assert workout is not None

        # Workout Mix should have coverage data
        assert 'coverage' in workout
        assert 'matched_count' in workout
        assert 'unmatched_count' in workout

    def test_list_playlists_calculates_match_statistics(self, db_with_data):
        """Test that playlists have correct match statistics."""
        facade = DataFacade(db_with_data, provider='spotify')
        playlists = facade.list_playlists()

        # Find "Workout Mix" playlist (should be index 1 or 2)
        workout = next(p for p in playlists if p['name'] == 'Workout Mix')

        # Workout Mix has 2 tracks: t1 (matched) and t2 (unmatched)
        assert workout['track_count'] == 2
        assert workout['matched_count'] == 1
        assert workout['unmatched_count'] == 1
        assert workout['coverage'] == 50  # 1/2 = 50%

    def test_list_all_tracks_unified(self, db_with_data):
        """Test listing all tracks with unified view data."""
        facade = DataFacade(db_with_data, provider='spotify')
        tracks = facade.list_all_tracks_unified()

        # Should have 2 unique tracks
        assert len(tracks) >= 2

        # Check that tracks have required fields (from list_all_tracks_unified implementation)
        for track in tracks:
            assert 'id' in track
            assert 'name' in track
            assert 'artist' in track
            assert 'album' in track
            assert 'matched' in track  # "Yes" or "No"
            assert 'local_path' in track
            assert 'playlists' in track  # Comma-separated playlist names

    def test_get_playlist_detail(self, db_with_data):
        """Test getting playlist detail with tracks."""
        facade = DataFacade(db_with_data, provider='spotify')

        tracks = facade.get_playlist_detail('p1')

        # Workout Mix has 2 tracks
        assert len(tracks) == 2

        # Check first track (matched)
        assert tracks[0]['track_id'] == 't1'
        assert tracks[0]['name'] == 'Song 1'
        assert tracks[0]['local_path'] == '/music/song1.mp3'

        # Check second track (unmatched)
        assert tracks[1]['track_id'] == 't2'
        assert tracks[1]['name'] == 'Song 2'
        assert tracks[1]['local_path'] is None

    def test_get_counts(self, db_with_data):
        """Test getting overall counts."""
        facade = DataFacade(db_with_data, provider='spotify')
        counts = facade.get_counts()

        assert counts['playlists'] == 2
        assert counts['tracks'] == 2  # Unique tracks
        assert counts['library_files'] == 1  # Changed from 'local_files' to 'library_files'
        assert counts['matches'] == 1
