"""Tests for GUI components (SortFilterTable, LogPanel, FilterBar, etc.)."""
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer
from psm.gui.components import SortFilterTable, LogPanel, FilterBar, UnifiedTracksProxyModel
from psm.gui.models import PlaylistsModel, UnifiedTracksModel


@pytest.fixture(scope='module')
def qapp():
    """Create QApplication instance for GUI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class TestSortFilterTable:
    """Tests for SortFilterTable component."""
    
    def test_creation(self, qapp):
        """Test component can be created."""
        model = PlaylistsModel()
        table = SortFilterTable(model)
        
        assert table is not None
        assert table.model() == model.proxy
    
    def test_set_default_sort(self, qapp):
        """Test setting default sort order."""
        model = PlaylistsModel()
        table = SortFilterTable(model)
        
        # Should not raise
        table.set_default_sort(0, Qt.AscendingOrder)
    
    def test_resize_columns(self, qapp):
        """Test resizing columns to contents."""
        model = PlaylistsModel()
        model.set_data([
            {
                'id': 'p1',
                'name': 'Test',
                'owner_name': 'user',
                'track_count': 10,
                'matched_count': 5,
                'unmatched_count': 5,
                'coverage': 50
            }
        ])
        
        table = SortFilterTable(model)
        table.resize_columns_to_contents()  # Should not raise
    
    def test_get_selected_row_data(self, qapp):
        """Test getting selected row data."""
        model = PlaylistsModel()
        model.set_data([
            {
                'id': 'p1',
                'name': 'Test',
                'owner_name': 'user',
                'track_count': 10,
                'matched_count': 5,
                'unmatched_count': 5,
                'coverage': 50
            }
        ])
        
        table = SortFilterTable(model)
        
        # No selection initially
        assert table.get_selected_row_data() is None
        
        # Select first row
        table.table_view.selectRow(0)
        row_data = table.get_selected_row_data()
        
        assert row_data is not None
        assert row_data['id'] == 'p1'
        assert row_data['name'] == 'Test'


class TestLogPanel:
    """Tests for LogPanel component."""
    
    def test_creation(self, qapp):
        """Test component can be created."""
        panel = LogPanel()
        assert panel is not None
    
    def test_append_log(self, qapp):
        """Test appending log messages."""
        panel = LogPanel()
        
        panel.append_log("INFO: Test message")
        panel.append_log("WARNING: Warning message")
        panel.append_log("ERROR: Error message")
        
        # Should not raise
        text = panel.log_text.toPlainText()
        assert "Test message" in text
        assert "Warning message" in text
        assert "Error message" in text
    
    def test_clear_logs(self, qapp):
        """Test clearing logs."""
        panel = LogPanel()
        
        panel.append_log("Test message")
        assert len(panel.log_text.toPlainText()) > 0
        
        panel.clear_logs()
        assert panel.log_text.toPlainText() == ""


class TestFilterBar:
    """Tests for FilterBar component."""
    
    def test_creation(self, qapp):
        """Test component can be created."""
        bar = FilterBar()
        assert bar is not None
    
    def test_get_track_filter(self, qapp):
        """Test getting track filter value."""
        bar = FilterBar()
        
        # Default should be "all"
        assert bar.get_track_filter() == "all"
        
        # Change to matched
        index = bar.status_combo.findText("Matched")
        bar.status_combo.setCurrentIndex(index)
        assert bar.get_track_filter() == "matched"
        
        # Change to unmatched
        index = bar.status_combo.findText("Unmatched")
        bar.status_combo.setCurrentIndex(index)
        assert bar.get_track_filter() == "unmatched"
    
    def test_get_search_text(self, qapp):
        """Test getting search text."""
        bar = FilterBar()
        
        assert bar.get_search_text() == ""
        
        bar.search_input.setText("test search")
        assert bar.get_search_text() == "test search"
    
    def test_clear_filters(self, qapp):
        """Test clearing all filters."""
        bar = FilterBar()
        
        # Set some filters
        bar.status_combo.setCurrentIndex(1)  # Matched
        bar.search_input.setText("test")
        
        # Clear
        bar.clear_filters()
        
        assert bar.get_track_filter() == "all"
        assert bar.get_search_text() == ""
    
    def test_filters_changed_signal(self, qapp):
        """Test that filters_changed signal is emitted."""
        bar = FilterBar()
        
        signal_received = []
        bar.filters_changed.connect(lambda: signal_received.append(True))
        
        # Change status filter
        bar.status_combo.setCurrentIndex(1)
        QApplication.processEvents()
        
        assert len(signal_received) > 0


class TestUnifiedTracksProxyModel:
    """Tests for UnifiedTracksProxyModel."""
    
    def test_creation(self, qapp):
        """Test proxy model can be created."""
        proxy = UnifiedTracksProxyModel()
        assert proxy is not None
    
    def test_playlist_filter(self, qapp):
        """Test filtering by playlist name."""
        model = UnifiedTracksModel()
        tracks = [
            {
                'id': 't1',
                'playlist_name': 'Workout',
                'owner_name': 'user',
                'track_name': 'Song 1',
                'artist_name': 'Artist 1',
                'album_name': 'Album 1',
                'matched': True,
                'local_path': '/music/s1.mp3',
                'match_score': 90
            },
            {
                'id': 't2',
                'playlist_name': 'Chill',
                'owner_name': 'user',
                'track_name': 'Song 2',
                'artist_name': 'Artist 2',
                'album_name': 'Album 2',
                'matched': False,
                'local_path': None,
                'match_score': None
            }
        ]
        model.set_data(tracks)
        
        proxy = UnifiedTracksProxyModel()
        proxy.setSourceModel(model)
        
        # No filter - should show all
        assert proxy.rowCount() == 2
        
        # Filter by "Workout"
        proxy.set_playlist_filter("Workout")
        assert proxy.rowCount() == 1
        
        # Filter by "Chill"
        proxy.set_playlist_filter("Chill")
        assert proxy.rowCount() == 1
        
        # Clear filter
        proxy.set_playlist_filter(None)
        assert proxy.rowCount() == 2
    
    def test_status_filter(self, qapp):
        """Test filtering by match status."""
        model = UnifiedTracksModel()
        tracks = [
            {
                'id': 't1',
                'playlist_name': 'Test',
                'owner_name': 'user',
                'track_name': 'Matched Song',
                'artist_name': 'Artist',
                'album_name': 'Album',
                'matched': True,
                'local_path': '/music/s1.mp3',
                'match_score': 90
            },
            {
                'id': 't2',
                'playlist_name': 'Test',
                'owner_name': 'user',
                'track_name': 'Unmatched Song',
                'artist_name': 'Artist',
                'album_name': 'Album',
                'matched': False,
                'local_path': None,
                'match_score': None
            }
        ]
        model.set_data(tracks)
        
        proxy = UnifiedTracksProxyModel()
        proxy.setSourceModel(model)
        
        # Show all
        proxy.set_status_filter("all")
        assert proxy.rowCount() == 2
        
        # Show only matched
        proxy.set_status_filter("matched")
        assert proxy.rowCount() == 1
        
        # Show only unmatched
        proxy.set_status_filter("unmatched")
        assert proxy.rowCount() == 1
    
    def test_search_filter(self, qapp):
        """Test search text filtering."""
        model = UnifiedTracksModel()
        tracks = [
            {
                'id': 't1',
                'playlist_name': 'Test',
                'owner_name': 'user',
                'track_name': 'Rock Song',
                'artist_name': 'Rock Artist',
                'album_name': 'Rock Album',
                'matched': True,
                'local_path': '/music/rock.mp3',
                'match_score': 90
            },
            {
                'id': 't2',
                'playlist_name': 'Test',
                'owner_name': 'user',
                'track_name': 'Jazz Song',
                'artist_name': 'Jazz Artist',
                'album_name': 'Jazz Album',
                'matched': False,
                'local_path': None,
                'match_score': None
            }
        ]
        model.set_data(tracks)
        
        proxy = UnifiedTracksProxyModel()
        proxy.setSourceModel(model)
        
        # No search - show all
        assert proxy.rowCount() == 2
        
        # Search for "rock"
        proxy.set_search_text_immediate("rock")
        assert proxy.rowCount() == 1
        
        # Search for "jazz"
        proxy.set_search_text_immediate("jazz")
        assert proxy.rowCount() == 1
        
        # Clear search
        proxy.set_search_text_immediate("")
        assert proxy.rowCount() == 2
    
    def test_debounced_search(self, qapp):
        """Test debounced search with timer."""
        model = UnifiedTracksModel()
        proxy = UnifiedTracksProxyModel()
        proxy.setSourceModel(model)
        
        # Should create a timer (won't actually filter until timer fires)
        proxy.set_search_text_debounced("test", delay_ms=300)
        
        # Timer should be pending
        # (We can't easily test the actual delay without blocking)
