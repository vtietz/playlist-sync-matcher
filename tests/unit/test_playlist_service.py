"""Unit tests for playlist service (single-playlist operations)."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from psm.services.playlist_service import (
    match_single_playlist,
    SinglePlaylistResult,
)


@pytest.fixture
def mock_db():
    """Create a mock database."""
    db = Mock()
    
    # Mock playlist data
    mock_playlist = Mock()
    mock_playlist.id = 'test_playlist_123'
    mock_playlist.name = 'Test Playlist'
    db.get_playlist_by_id.return_value = mock_playlist
    
    # Mock playlist tracks - simulate 5 tracks in the playlist
    mock_playlist_tracks = [
        {
            'position': 0,
            'track_id': 'track_1',
            'name': 'Song 1',
            'artist': 'Artist 1',
            'album': 'Album 1',
            'year': 2020,
            'duration_ms': 180000,
            'local_path': None
        },
        {
            'position': 1,
            'track_id': 'track_2',
            'name': 'Song 2',
            'artist': 'Artist 2',
            'album': 'Album 2',
            'year': 2021,
            'duration_ms': 200000,
            'local_path': '/music/song2.mp3'
        },
        {
            'position': 2,
            'track_id': 'track_3',
            'name': 'Song 3',
            'artist': 'Artist 3',
            'album': 'Album 3',
            'year': 2022,
            'duration_ms': 190000,
            'local_path': None
        },
        {
            'position': 3,
            'track_id': 'track_4',
            'name': 'Song 4',
            'artist': 'Artist 4',
            'album': 'Album 4',
            'year': 2023,
            'duration_ms': 210000,
            'local_path': None
        },
        {
            'position': 4,
            'track_id': 'track_5',
            'name': 'Song 5',
            'artist': 'Artist 5',
            'album': 'Album 5',
            'year': 2024,
            'duration_ms': 195000,
            'local_path': '/music/song5.mp3'
        },
    ]
    db.get_playlist_tracks_with_local_paths.return_value = mock_playlist_tracks
    
    # Mock get_match_for_track - tracks 2 and 5 are already matched
    def mock_get_match(track_id, provider=None):
        if track_id in ['track_2', 'track_5']:
            return Mock(score=0.95, file_id='file_123')
        return None
    
    db.get_match_for_track.side_effect = mock_get_match
    
    return db


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    return {
        'matching': {
            'fuzzy_threshold': 0.78,
            'duration_tolerance': 5.0,
        }
    }


def test_match_single_playlist_only_matches_playlist_tracks(mock_db, mock_config):
    """Test that match_single_playlist only matches tracks from the specified playlist."""
    
    with patch('psm.services.playlist_service.MatchingEngine') as MockEngine:
        # Create a mock engine instance
        mock_engine_instance = Mock()
        mock_engine_instance.match_tracks.return_value = 2  # 2 new matches found
        MockEngine.return_value = mock_engine_instance
        
        # Call the function
        result = match_single_playlist(
            db=mock_db,
            playlist_id='test_playlist_123',
            config=mock_config
        )
        
        # Verify MatchingEngine.match_tracks was called with ONLY the playlist's track IDs
        mock_engine_instance.match_tracks.assert_called_once()
        call_args = mock_engine_instance.match_tracks.call_args
        track_ids_arg = call_args.kwargs['track_ids']
        
        # Should have exactly 5 track IDs (the tracks in the playlist)
        assert track_ids_arg is not None, "track_ids should not be None"
        assert len(track_ids_arg) == 5, f"Expected 5 track IDs, got {len(track_ids_arg)}"
        assert set(track_ids_arg) == {'track_1', 'track_2', 'track_3', 'track_4', 'track_5'}
        
        # Verify result
        assert isinstance(result, SinglePlaylistResult)
        assert result.playlist_id == 'test_playlist_123'
        assert result.playlist_name == 'Test Playlist'
        assert result.tracks_processed == 5
        assert result.tracks_matched == 2  # tracks 2 and 5 are matched


def test_match_single_playlist_does_not_match_all_tracks(mock_db, mock_config):
    """Test that match_single_playlist does NOT pass track_ids=None (which would match all tracks)."""
    
    with patch('psm.services.playlist_service.MatchingEngine') as MockEngine:
        mock_engine_instance = Mock()
        mock_engine_instance.match_tracks.return_value = 2
        MockEngine.return_value = mock_engine_instance
        
        # Call the function
        match_single_playlist(
            db=mock_db,
            playlist_id='test_playlist_123',
            config=mock_config
        )
        
        # Verify that track_ids was NOT None (would match all tracks)
        call_args = mock_engine_instance.match_tracks.call_args
        track_ids_arg = call_args.kwargs.get('track_ids')
        
        assert track_ids_arg is not None, \
            "CRITICAL BUG: track_ids=None would match ALL tracks in database instead of just the playlist!"


def test_match_single_playlist_nonexistent_playlist(mock_db, mock_config):
    """Test that match_single_playlist raises error for nonexistent playlist."""
    
    # Mock playlist not found
    mock_db.get_playlist_by_id.return_value = None
    
    with pytest.raises(ValueError, match="Playlist .* not found"):
        match_single_playlist(
            db=mock_db,
            playlist_id='nonexistent_playlist',
            config=mock_config
        )


def test_match_single_playlist_empty_playlist(mock_db, mock_config):
    """Test matching an empty playlist."""
    
    # Mock empty playlist
    mock_db.get_playlist_tracks_with_local_paths.return_value = []
    
    with patch('psm.services.playlist_service.MatchingEngine') as MockEngine:
        mock_engine_instance = Mock()
        mock_engine_instance.match_tracks.return_value = 0
        MockEngine.return_value = mock_engine_instance
        
        result = match_single_playlist(
            db=mock_db,
            playlist_id='test_playlist_123',
            config=mock_config
        )
        
        # Should process 0 tracks
        assert result.tracks_processed == 0
        assert result.tracks_matched == 0
        
        # Should still call match_tracks with empty list
        mock_engine_instance.match_tracks.assert_called_once()
        call_args = mock_engine_instance.match_tracks.call_args
        track_ids_arg = call_args.kwargs['track_ids']
        assert track_ids_arg == []


def test_match_single_playlist_commits_database(mock_db, mock_config):
    """Test that match_single_playlist commits the database after matching."""
    
    with patch('psm.services.playlist_service.MatchingEngine') as MockEngine:
        mock_engine_instance = Mock()
        mock_engine_instance.match_tracks.return_value = 2
        MockEngine.return_value = mock_engine_instance
        
        match_single_playlist(
            db=mock_db,
            playlist_id='test_playlist_123',
            config=mock_config
        )
        
        # Verify commit was called
        mock_db.commit.assert_called_once()


def test_match_single_playlist_respects_config(mock_db, mock_config):
    """Test that match_single_playlist uses matching configuration correctly."""
    
    custom_config = {
        'matching': {
            'fuzzy_threshold': 0.85,
            'duration_tolerance': 3.0,
        }
    }
    
    with patch('psm.services.playlist_service.MatchingEngine') as MockEngine:
        mock_engine_instance = Mock()
        mock_engine_instance.match_tracks.return_value = 1
        MockEngine.return_value = mock_engine_instance
        
        match_single_playlist(
            db=mock_db,
            playlist_id='test_playlist_123',
            config=custom_config
        )
        
        # Verify MatchingEngine was instantiated with correct config
        MockEngine.assert_called_once()
        call_args = MockEngine.call_args
        matching_cfg = call_args.args[1]
        
        # Check that the config values were used
        assert matching_cfg.fuzzy_threshold == 0.85
        assert matching_cfg.duration_tolerance == 3.0
