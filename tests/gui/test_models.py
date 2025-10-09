"""Tests for GUI models (PlaylistsModel, UnifiedTracksModel, etc.)."""
import pytest
from PySide6.QtCore import Qt
from psm.gui.models import PlaylistsModel, UnifiedTracksModel


class TestPlaylistsModel:
    """Tests for PlaylistsModel."""
    
    def test_initial_state(self):
        """Test model starts empty."""
        model = PlaylistsModel()
        assert model.rowCount() == 0
        assert model.columnCount() == 6  # Name, Owner, Tracks, Matched, Unmatched, Coverage
    
    def test_column_headers(self):
        """Test column headers are correct."""
        model = PlaylistsModel()
        expected_headers = ['Name', 'Owner', 'Tracks', 'Matched', 'Unmatched', 'Coverage %']
        
        for col, expected in enumerate(expected_headers):
            actual = model.headerData(col, Qt.Horizontal, Qt.DisplayRole)
            assert actual == expected
    
    def test_set_data_with_all_playlists(self):
        """Test setting data with 'All Playlists' row."""
        model = PlaylistsModel()
        
        playlists = [
            {
                'id': None,  # All Playlists marker
                'name': 'All Playlists',
                'owner_name': '',
                'track_count': 100,
                'matched_count': 75,
                'unmatched_count': 25,
                'coverage': 75
            },
            {
                'id': 'playlist1',
                'name': 'Workout Mix',
                'owner_name': 'testuser',
                'track_count': 50,
                'matched_count': 40,
                'unmatched_count': 10,
                'coverage': 80
            }
        ]
        
        model.set_data(playlists)
        
        assert model.rowCount() == 2
        
        # Check "All Playlists" row (models return strings for display)
        assert model.data(model.index(0, 0), Qt.DisplayRole) == 'All Playlists'
        assert model.data(model.index(0, 2), Qt.DisplayRole) == '100'
        assert model.data(model.index(0, 3), Qt.DisplayRole) == '75'
        assert model.data(model.index(0, 4), Qt.DisplayRole) == '25'
        assert model.data(model.index(0, 5), Qt.DisplayRole) == '75'  # Coverage is stored as int
        
        # Check regular playlist row
        assert model.data(model.index(1, 0), Qt.DisplayRole) == 'Workout Mix'
        assert model.data(model.index(1, 1), Qt.DisplayRole) == 'testuser'
        assert model.data(model.index(1, 2), Qt.DisplayRole) == '50'
        assert model.data(model.index(1, 5), Qt.DisplayRole) == '80'  # Coverage is stored as int
    
    def test_get_row_data(self):
        """Test retrieving row data by index."""
        model = PlaylistsModel()
        
        playlists = [
            {
                'id': None,
                'name': 'All Playlists',
                'owner_name': '',
                'track_count': 100,
                'matched_count': 75,
                'unmatched_count': 25,
                'coverage': 75
            }
        ]
        
        model.set_data(playlists)
        row_data = model.get_row_data(0)
        
        assert row_data is not None
        assert row_data['id'] is None
        assert row_data['name'] == 'All Playlists'
        assert row_data['track_count'] == 100
    
    def test_get_row_data_invalid_index(self):
        """Test get_row_data with invalid index."""
        model = PlaylistsModel()
        model.set_data([])
        
        assert model.get_row_data(-1) is None
        assert model.get_row_data(0) is None
        assert model.get_row_data(10) is None


class TestUnifiedTracksModel:
    """Tests for UnifiedTracksModel."""
    
    def test_initial_state(self):
        """Test model starts empty."""
        model = UnifiedTracksModel()
        assert model.rowCount() == 0
        assert model.columnCount() == 8  # Playlist, Owner, Track, Artist, Album, Matched, Local File, Match %
    
    def test_column_headers(self):
        """Test column headers are correct."""
        model = UnifiedTracksModel()
        expected_headers = [
            'Playlist', 'Owner', 'Track', 'Artist', 'Album',
            'Matched', 'Local File', 'Match %'
        ]
        
        for col, expected in enumerate(expected_headers):
            actual = model.headerData(col, Qt.Horizontal, Qt.DisplayRole)
            assert actual == expected
    
    def test_set_data(self):
        """Test setting track data."""
        model = UnifiedTracksModel()
        
        tracks = [
            {
                'playlist_name': 'Workout Mix',
                'owner': 'testuser',
                'name': 'Song 1',
                'artist': 'Artist 1',
                'album': 'Album 1',
                'matched': True,
                'local_path': '/music/song1.mp3',
                'completeness': 95
            },
            {
                'playlist_name': 'Chill Vibes',
                'owner': 'testuser',
                'name': 'Song 2',
                'artist': 'Artist 2',
                'album': 'Album 2',
                'matched': False,
                'local_path': None,
                'completeness': None
            }
        ]
        
        model.set_data(tracks)
        
        assert model.rowCount() == 2
        
        # Check matched track
        assert model.data(model.index(0, 0), Qt.DisplayRole) == 'Workout Mix'
        assert model.data(model.index(0, 1), Qt.DisplayRole) == 'testuser'
        assert model.data(model.index(0, 2), Qt.DisplayRole) == 'Song 1'
        assert model.data(model.index(0, 5), Qt.DisplayRole) == 'True'  # matched stored as bool
        assert model.data(model.index(0, 6), Qt.DisplayRole) == '/music/song1.mp3'
        assert model.data(model.index(0, 7), Qt.DisplayRole) == '95'  # completeness stored as int
        
        # Check unmatched track
        assert model.data(model.index(1, 5), Qt.DisplayRole) == 'False'
        assert model.data(model.index(1, 6), Qt.DisplayRole) == ''
        assert model.data(model.index(1, 7), Qt.DisplayRole) == ''
    
    def test_get_row_data(self):
        """Test retrieving row data by index."""
        model = UnifiedTracksModel()
        
        tracks = [
            {
                'id': 'track123',
                'playlist_name': 'Test',
                'owner': 'user',
                'name': 'Song',
                'artist': 'Artist',
                'album': 'Album',
                'matched': True,
                'local_path': '/music/song.mp3',
                'completeness': 90
            }
        ]
        
        model.set_data(tracks)
        row_data = model.get_row_data(0)
        
        assert row_data is not None
        assert row_data['id'] == 'track123'
        assert row_data['name'] == 'Song'
        assert row_data['matched'] is True
