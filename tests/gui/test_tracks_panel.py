"""Tests for TracksPanel component."""

import pytest
from PySide6.QtWidgets import QApplication

from psm.gui.panels.tracks_panel import TracksPanel
from psm.gui.models import UnifiedTracksModel
from psm.gui.state import FilterStore


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for GUI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def tracks_panel(qapp):
    """Create TracksPanel instance with required models and components."""
    # Create model
    unified_tracks_model = UnifiedTracksModel()

    # Create filter store
    from PySide6.QtCore import QObject

    parent = QObject()
    filter_store = FilterStore(parent)

    # Create panel
    panel = TracksPanel(unified_tracks_model, filter_store)

    # Store references to prevent premature deletion
    panel._test_model = unified_tracks_model
    panel._test_filter_store = filter_store
    panel._test_parent = parent

    return panel


class TestTracksPanelCreation:
    """Test tracks panel creation and structure."""

    def test_panel_creation(self, tracks_panel):
        """Panel should be created successfully."""
        assert tracks_panel is not None

    def test_has_unified_tracks_view(self, tracks_panel):
        """Panel should have a unified tracks view."""
        assert hasattr(tracks_panel, "unified_tracks_view")
        assert tracks_panel.unified_tracks_view is not None

    def test_has_diagnose_button(self, tracks_panel):
        """Panel should have a diagnose button."""
        assert hasattr(tracks_panel, "btn_diagnose")
        assert tracks_panel.btn_diagnose is not None

    def test_diagnose_button_initially_disabled(self, tracks_panel):
        """Diagnose button should be disabled when no track is selected."""
        assert not tracks_panel.btn_diagnose.isEnabled()


class TestTracksPanelProperties:
    """Test tracks panel public properties."""

    def test_unified_tracks_view_property(self, tracks_panel):
        """Should provide access to unified tracks view."""
        view = tracks_panel.unified_tracks_view
        assert view is not None

    def test_tracks_table_property(self, tracks_panel):
        """Should provide access to tracks table."""
        table = tracks_panel.tracks_table
        assert table is not None
        assert table is tracks_panel.unified_tracks_view.tracks_table

    def test_filter_bar_property(self, tracks_panel):
        """Should provide access to filter bar."""
        filter_bar = tracks_panel.filter_bar
        assert filter_bar is not None
        assert filter_bar is tracks_panel.unified_tracks_view.filter_bar

    def test_proxy_model_property(self, tracks_panel):
        """Should provide access to proxy model."""
        proxy = tracks_panel.proxy_model
        assert proxy is not None
        assert proxy is tracks_panel.unified_tracks_view.proxy_model

    def test_btn_diagnose_property(self, tracks_panel):
        """Should provide access to diagnose button."""
        btn = tracks_panel.btn_diagnose
        assert btn is not None


class TestTracksPanelSignals:
    """Test signal emissions from panel."""

    def test_track_selected_signal_exists(self, tracks_panel):
        """Panel should have track_selected signal."""
        assert hasattr(tracks_panel, "track_selected")

    def test_diagnose_clicked_signal_exists(self, tracks_panel):
        """Panel should have diagnose_clicked signal."""
        assert hasattr(tracks_panel, "diagnose_clicked")

    def test_selection_changed_signal_exists(self, tracks_panel):
        """Panel should have selection_changed signal."""
        assert hasattr(tracks_panel, "selection_changed")

    def test_track_selected_signal_delegation(self, tracks_panel):
        """Should delegate track_selected signal from unified_tracks_view."""
        emitted = []
        tracks_panel.track_selected.connect(lambda track_id: emitted.append(track_id))

        # Trigger signal from unified_tracks_view
        tracks_panel.unified_tracks_view.track_selected.emit("test_track_123")

        assert len(emitted) == 1
        assert emitted[0] == "test_track_123"


class TestTracksPanelSelectionHandling:
    """Test track selection state management."""

    def test_has_selection_initially_false(self, tracks_panel):
        """Should have no selection initially."""
        assert not tracks_panel.has_selection()

    def test_diagnose_button_disabled_without_selection(self, tracks_panel):
        """Diagnose button should be disabled when no track is selected."""
        assert not tracks_panel.btn_diagnose.isEnabled()

    def test_get_selected_track_id_returns_none_when_no_selection(self, tracks_panel):
        """Should return None when no track is selected."""
        track_id = tracks_panel._get_selected_track_id()
        assert track_id is None


class TestTracksPanelDataUpdates:
    """Test data update methods."""

    def test_update_tracks(self, tracks_panel):
        """Should update tracks data in model."""
        tracks = [
            {
                "track_id": "track1",
                "name": "Test Track 1",
                "artist": "Artist 1",
                "album": "Album 1",
                "year": 2023,
                "matched": True,
                "confidence": 0.95,
                "quality": "High",
                "local_file": "/path/to/track1.mp3",
                "playlists": ["Playlist 1"],
            },
            {
                "track_id": "track2",
                "name": "Test Track 2",
                "artist": "Artist 2",
                "album": "Album 2",
                "year": 2024,
                "matched": False,
                "confidence": 0.0,
                "quality": "N/A",
                "local_file": "",
                "playlists": ["Playlist 2"],
            },
        ]
        playlists = [{"name": "Playlist 1"}, {"name": "Playlist 2"}]

        # Should not raise an exception
        tracks_panel.update_tracks(tracks, playlists)

    def test_populate_filter_options(self, tracks_panel):
        """Should populate filter dropdown options."""
        playlists = ["Playlist 1", "Playlist 2", "Playlist 3"]
        artists = ["Artist A", "Artist B", "Artist C"]
        albums = ["Album X", "Album Y", "Album Z"]
        years = ["2023", "2024", "2025"]

        # Should not raise an exception
        tracks_panel.populate_filter_options(playlists, artists, albums, years)


class TestTracksPanelIntegration:
    """Integration tests for realistic usage scenarios."""

    def test_typical_workflow(self, tracks_panel):
        """Simulate typical usage workflow."""
        # Initially no selection
        assert not tracks_panel.has_selection()
        assert not tracks_panel.btn_diagnose.isEnabled()

        # Update with tracks data
        tracks = [
            {
                "track_id": "track1",
                "name": "Song 1",
                "artist": "Artist 1",
                "album": "Album 1",
                "year": 2023,
                "matched": True,
                "confidence": 0.9,
                "quality": "High",
                "local_file": "/path/song1.mp3",
                "playlists": ["Favorites"],
            }
        ]
        playlists = [{"name": "Favorites"}]
        tracks_panel.update_tracks(tracks, playlists)

        # Populate filter options
        tracks_panel.populate_filter_options(["Favorites"], ["Artist 1"], ["Album 1"], ["2023"])

        # Verify still no selection
        assert not tracks_panel.has_selection()

    def test_component_access_chain(self, tracks_panel):
        """Should access nested components through property chain."""
        # Access through panel
        tracks_table = tracks_panel.tracks_table
        filter_bar = tracks_panel.filter_bar
        proxy_model = tracks_panel.proxy_model

        # Verify they're from the same unified_tracks_view
        assert tracks_table is tracks_panel.unified_tracks_view.tracks_table
        assert filter_bar is tracks_panel.unified_tracks_view.filter_bar
        assert proxy_model is tracks_panel.unified_tracks_view.proxy_model


class TestTracksPanelEdgeCases:
    """Test edge cases and error handling."""

    def test_update_with_empty_tracks(self, tracks_panel):
        """Should handle empty tracks list."""
        tracks_panel.update_tracks([], [])
        assert not tracks_panel.has_selection()

    def test_populate_with_empty_filters(self, tracks_panel):
        """Should handle empty filter options."""
        tracks_panel.populate_filter_options([], [], [], [])
        # Should not raise an exception

    def test_diagnose_without_selection_does_nothing(self, tracks_panel):
        """Clicking diagnose without selection should not crash."""
        emitted = []
        tracks_panel.diagnose_clicked.connect(lambda track_id: emitted.append(track_id))

        # Trigger diagnose button (should be disabled, but test the handler)
        tracks_panel._on_diagnose_clicked()

        # Should not emit signal
        assert len(emitted) == 0
