"""Tests for DataFacade."""
import pytest
from pathlib import Path
from psm.gui.data_facade import DataFacade
from psm.db.sqlite_impl import Database


@pytest.fixture
def db_with_data(tmp_path):
    """Create a database with test data."""
    db_path = tmp_path / "test.db"
    db = Database(Path(db_path))  # Use Path object, not string
    db.open()
    
    # Create test playlists
    db.upsert_playlist(
        playlist_id='p1',
        name='Workout Mix',
        owner_id='user1',
        owner_name='testuser',
        provider='spotify'
    )
    db.upsert_playlist(
        playlist_id='p2',
        name='Chill Vibes',
        owner_id='user1',
        owner_name='testuser',
        provider='spotify'
    )
    
    # Add tracks to playlists
    db.upsert_track(
        track_id='t1',
        name='Song 1',
        artist='Artist 1',
        album='Album 1',
        duration_ms=180000,
        provider='spotify'
    )
    db.upsert_track(
        track_id='t2',
        name='Song 2',
        artist='Artist 2',
        album='Album 2',
        duration_ms=200000,
        provider='spotify'
    )
    
    db.upsert_playlist_track('p1', 't1', position=0, provider='spotify')
    db.upsert_playlist_track('p1', 't2', position=1, provider='spotify')
    db.upsert_playlist_track('p2', 't2', position=0, provider='spotify')
    
    # Add a local file and match
    db.upsert_local_file(
        path='/music/song1.mp3',
        title='Song 1',
        artist='Artist 1',
        album='Album 1',
        duration_ms=180000
    )
    
    db.upsert_match(
        track_id='t1',
        local_path='/music/song1.mp3',
        match_score=95,
        provider='spotify'
    )
    
    yield db
    
    db.close()


class TestDataFacade:
    """Tests for DataFacade."""
    
    def test_list_playlists_includes_all_playlists_row(self, db_with_data):
        """Test that list_playlists includes 'All Playlists' as first row."""
        facade = DataFacade(db_with_data, provider='spotify')
        playlists = facade.list_playlists()
        
        # Should have 3 rows: All Playlists + 2 actual playlists
        assert len(playlists) == 3
        
        # First row should be "All Playlists"
        all_playlists = playlists[0]
        assert all_playlists['id'] is None
        assert all_playlists['name'] == 'All Playlists'
        assert all_playlists['owner_name'] == ''
        
        # Check aggregated statistics
        # t1 is in p1 (matched), t2 is in both p1 and p2 (unmatched)
        # Total: 3 track positions, 1 matched, 2 unmatched
        assert all_playlists['track_count'] == 3
        assert all_playlists['matched_count'] == 1
        assert all_playlists['unmatched_count'] == 2
        assert all_playlists['coverage'] == 33  # 1/3 = 33%
    
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
        
        # Should have 3 track positions total
        assert len(tracks) >= 2  # At least 2 unique tracks
        
        # Check that tracks have required fields
        for track in tracks:
            assert 'playlist_name' in track
            assert 'owner_name' in track
            assert 'track_name' in track
            assert 'artist_name' in track
            assert 'album_name' in track
            assert 'matched' in track
            assert 'local_path' in track
            assert 'match_score' in track
    
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
        assert counts['local_files'] == 1
        assert counts['matches'] == 1
