"""Tests for GUI components (SortFilterTable, LogPanel, FilterBar, etc.)."""

import pytest
from PySide6.QtWidgets import QApplication, QHeaderView
from PySide6.QtCore import Qt
from psm.gui.components import SortFilterTable, LogPanel, FilterBar, UnifiedTracksProxyModel
from psm.gui.models import PlaylistsModel, UnifiedTracksModel


@pytest.fixture(scope="module")
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
        assert table.proxy_model.sourceModel() == model

    def test_set_default_sort(self, qapp):
        """Test setting default sort order."""
        model = PlaylistsModel()
        table = SortFilterTable(model)

        # Should not raise
        table.set_default_sort(0, Qt.AscendingOrder)

    def test_resize_columns(self, qapp):
        """Test resizing columns to contents."""
        model = PlaylistsModel()
        model.set_data(
            [
                {
                    "id": "p1",
                    "name": "Test",
                    "owner_name": "user",
                    "track_count": 10,
                    "matched_count": 5,
                    "unmatched_count": 5,
                    "coverage": 50,
                }
            ]
        )

        table = SortFilterTable(model)

        # Verify header is interactive and allows manual resizing
        header = table.table_view.horizontalHeader()
        assert header.sectionResizeMode(0) == QHeaderView.Interactive
        assert header.stretchLastSection() is True

    def test_get_selected_row_data(self, qapp):
        """Test getting selected row data."""
        model = PlaylistsModel()
        model.set_data(
            [
                {
                    "id": "p1",
                    "name": "Test",
                    "owner_name": "user",
                    "track_count": 10,
                    "matched_count": 5,
                    "unmatched_count": 5,
                    "coverage": 50,
                }
            ]
        )

        table = SortFilterTable(model)

        # No selection initially
        assert table.get_selected_row_data() is None

        # Select first row
        table.table_view.selectRow(0)
        row_data = table.get_selected_row_data()

        assert row_data is not None
        assert row_data["id"] == "p1"
        assert row_data["name"] == "Test"


class TestLogPanel:
    """Tests for LogPanel component."""

    def test_creation(self, qapp):
        """Test component can be created."""
        panel = LogPanel()
        assert panel is not None

    def test_append_log(self, qapp):
        """Test appending log messages."""
        panel = LogPanel()

        panel.append("INFO: Test message")
        panel.append("WARNING: Warning message")
        panel.append("ERROR: Error message")

        # Should not raise
        text = panel.log_text.toPlainText()
        assert "Test message" in text
        assert "Warning message" in text
        assert "Error message" in text

    def test_clear_logs(self, qapp):
        """Test clearing logs."""
        panel = LogPanel()

        panel.append("Test message")
        assert len(panel.log_text.toPlainText()) > 0

        panel.clear()
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
        index = bar.track_status_combo.findText("Matched")
        bar.track_status_combo.setCurrentIndex(index)
        assert bar.get_track_filter() == "matched"

        # Change to unmatched
        index = bar.track_status_combo.findText("Unmatched")
        bar.track_status_combo.setCurrentIndex(index)
        assert bar.get_track_filter() == "unmatched"

    def test_get_search_text(self, qapp):
        """Test getting search text."""
        bar = FilterBar()

        assert bar.get_search_text() == ""

        bar.search_field.setText("test search")
        assert bar.get_search_text() == "test search"

    def test_clear_filters(self, qapp):
        """Test clearing all filters."""
        bar = FilterBar()

        # Set some filters
        bar.track_status_combo.setCurrentIndex(1)  # Matched
        bar.search_field.setText("test")

        # Clear
        bar.clear_filters()

        assert bar.get_track_filter() == "all"
        assert bar.get_search_text() == ""

    def test_filters_changed_signal(self, qapp):
        """Test that filter_changed signal is emitted."""
        bar = FilterBar()

        signal_received = []
        bar.filter_changed.connect(lambda: signal_received.append(True))

        # Change status filter
        bar.track_status_combo.setCurrentIndex(1)
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
                "id": "t1",
                "name": "Song 1",
                "artist": "Artist 1",
                "album": "Album 1",
                "year": 2020,
                "matched": True,
                "confidence": "HIGH",
                "quality": "GOOD",
                "local_path": "/music/s1.mp3",
                "playlists": "Workout",  # Added playlists field
            },
            {
                "id": "t2",
                "name": "Song 2",
                "artist": "Artist 2",
                "album": "Album 2",
                "year": 2021,
                "matched": False,
                "confidence": None,
                "quality": None,
                "local_path": None,
                "playlists": "Chill",  # Added playlists field
            },
        ]
        model.set_data(tracks)

        proxy = UnifiedTracksProxyModel()
        proxy.setSourceModel(model)

        # No filter - should show all
        assert proxy.rowCount() == 2

        # Filter by "Workout" - need to pass track_ids set
        proxy.set_playlist_filter("Workout", track_ids={"t1"})
        assert proxy.rowCount() == 1

        # Filter by "Chill" - need to pass track_ids set
        proxy.set_playlist_filter("Chill", track_ids={"t2"})
        assert proxy.rowCount() == 1

        # Clear filter
        proxy.set_playlist_filter(None)
        assert proxy.rowCount() == 2

    def test_status_filter(self, qapp):
        """Test filtering by match status."""
        model = UnifiedTracksModel()
        tracks = [
            {
                "id": "t1",
                "name": "Matched Song",
                "artist": "Artist",
                "album": "Album",
                "year": 2020,
                "matched": True,
                "confidence": "HIGH",
                "quality": "GOOD",
                "local_path": "/music/s1.mp3",
                "playlists": "Test",
            },
            {
                "id": "t2",
                "name": "Unmatched Song",
                "artist": "Artist",
                "album": "Album",
                "year": 2021,
                "matched": False,
                "confidence": None,
                "quality": None,
                "local_path": None,
                "playlists": "Test",
            },
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
                "id": "t1",
                "name": "Rock Song",
                "artist": "Rock Artist",
                "album": "Rock Album",
                "year": 2020,
                "matched": True,
                "confidence": "HIGH",
                "quality": "GOOD",
                "local_path": "/music/rock.mp3",
                "playlists": "Test",
            },
            {
                "id": "t2",
                "name": "Jazz Song",
                "artist": "Jazz Artist",
                "album": "Jazz Album",
                "year": 2021,
                "matched": False,
                "confidence": None,
                "quality": None,
                "local_path": None,
                "playlists": "Test",
            },
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
