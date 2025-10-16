"""Tests for ModelCoordinator class."""

import pytest
from unittest.mock import Mock
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from psm.gui.model_coordinator import ModelCoordinator


@pytest.fixture(scope='session')
def qapp():
    """Create QApplication instance for all GUI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class TestModelCoordinatorCreation:
    """Test ModelCoordinator initialization."""

    def test_creates_all_models(self, qapp):
        """ModelCoordinator should create all 10 table models."""
        coordinator = ModelCoordinator()

        assert coordinator.playlists_model is not None
        assert coordinator.playlist_detail_model is not None
        assert coordinator.unmatched_tracks_model is not None
        assert coordinator.matched_tracks_model is not None
        assert coordinator.coverage_model is not None
        assert coordinator.unmatched_albums_model is not None
        assert coordinator.liked_tracks_model is not None
        assert coordinator.unified_tracks_model is not None
        assert coordinator.albums_model is not None
        assert coordinator.artists_model is not None

    def test_pending_sorts_initialized_to_none(self, qapp):
        """Pending sort states should be None initially."""
        coordinator = ModelCoordinator()

        assert coordinator._pending_playlists_sort is None
        assert coordinator._pending_tracks_sort is None
        assert coordinator._pending_albums_sort is None
        assert coordinator._pending_artists_sort is None

    def test_view_references_initialized_to_none(self, qapp):
        """View references should be None until set_views() is called."""
        coordinator = ModelCoordinator()

        assert coordinator._playlists_table_view is None
        assert coordinator._albums_view is None
        assert coordinator._artists_view is None
        assert coordinator._unified_tracks_view is None


class TestSetViews:
    """Test view reference management."""

    def test_set_views_stores_references(self, qapp):
        """set_views() should store all view references."""
        coordinator = ModelCoordinator()

        # Mock views
        playlists_table = Mock()
        albums_view = Mock()
        artists_view = Mock()
        unified_tracks_view = Mock()

        coordinator.set_views(playlists_table, albums_view, artists_view, unified_tracks_view)

        assert coordinator._playlists_table_view is playlists_table
        assert coordinator._albums_view is albums_view
        assert coordinator._artists_view is artists_view
        assert coordinator._unified_tracks_view is unified_tracks_view


class TestPendingSortMethods:
    """Test pending sort state management."""

    def test_set_pending_playlists_sort(self, qapp):
        """Should store pending playlists sort state."""
        coordinator = ModelCoordinator()

        coordinator.set_pending_playlists_sort(0, Qt.AscendingOrder)

        assert coordinator._pending_playlists_sort == (0, Qt.AscendingOrder)

    def test_set_pending_tracks_sort(self, qapp):
        """Should store pending tracks sort state."""
        coordinator = ModelCoordinator()

        coordinator.set_pending_tracks_sort(2, Qt.DescendingOrder)

        assert coordinator._pending_tracks_sort == (2, Qt.DescendingOrder)

    def test_set_pending_albums_sort(self, qapp):
        """Should store pending albums sort state."""
        coordinator = ModelCoordinator()

        coordinator.set_pending_albums_sort(3, Qt.DescendingOrder)

        assert coordinator._pending_albums_sort == (3, Qt.DescendingOrder)

    def test_set_pending_artists_sort(self, qapp):
        """Should store pending artists sort state."""
        coordinator = ModelCoordinator()

        coordinator.set_pending_artists_sort(1, Qt.AscendingOrder)

        assert coordinator._pending_artists_sort == (1, Qt.AscendingOrder)


class TestUpdatePlaylists:
    """Test update_playlists() method."""

    def test_updates_model_data(self, qapp):
        """Should call set_data on playlists model."""
        coordinator = ModelCoordinator()

        coordinator.playlists_model.set_data = Mock()
        playlists = [{"id": "1", "name": "Test Playlist"}]

        coordinator.update_playlists(playlists)

        coordinator.playlists_model.set_data.assert_called_once_with(playlists)

    def test_resizes_columns_when_view_set(self, qapp):
        """Should set minimum column widths and apply sort when view is available."""
        coordinator = ModelCoordinator()

        # Mock view
        mock_view = Mock()
        mock_view.columnWidth = Mock(return_value=100)
        mock_view.setColumnWidth = Mock()
        mock_view.sortByColumn = Mock()

        coordinator.set_views(mock_view, None, None, None)
        coordinator.playlists_model.set_data = Mock()

        coordinator.update_playlists([{"id": "1"}])

        # Should set minimum column widths (not call resizeColumnsToContents)
        assert mock_view.setColumnWidth.call_count == 2  # Two columns
        mock_view.setColumnWidth.assert_any_call(0, max(250, 100))
        mock_view.setColumnWidth.assert_any_call(1, max(120, 100))

    def test_applies_pending_sort(self, qapp):
        """Should apply pending sort and clear it."""
        coordinator = ModelCoordinator()

        mock_view = Mock()
        mock_view.resizeColumnsToContents = Mock()
        mock_view.columnWidth = Mock(return_value=100)
        mock_view.setColumnWidth = Mock()
        mock_view.sortByColumn = Mock()

        coordinator.set_views(mock_view, None, None, None)
        coordinator.set_pending_playlists_sort(1, Qt.DescendingOrder)
        coordinator.playlists_model.set_data = Mock()

        coordinator.update_playlists([{"id": "1"}])

        mock_view.sortByColumn.assert_called_once_with(1, Qt.DescendingOrder)
        assert coordinator._pending_playlists_sort is None  # Cleared

    def test_applies_default_sort_when_no_pending(self, qapp):
        """Should apply default sort when no pending sort."""
        coordinator = ModelCoordinator()

        mock_view = Mock()
        mock_view.resizeColumnsToContents = Mock()
        mock_view.columnWidth = Mock(return_value=100)
        mock_view.setColumnWidth = Mock()
        mock_view.sortByColumn = Mock()

        coordinator.set_views(mock_view, None, None, None)
        coordinator.playlists_model.set_data = Mock()

        coordinator.update_playlists([{"id": "1"}])

        # Default: column 0, ascending
        mock_view.sortByColumn.assert_called_once_with(0, Qt.AscendingOrder)

    def test_handles_no_view_gracefully(self, qapp):
        """Should not crash when no view is set."""
        coordinator = ModelCoordinator()

        coordinator.playlists_model.set_data = Mock()

        # Should not raise
        coordinator.update_playlists([{"id": "1"}])

        coordinator.playlists_model.set_data.assert_called_once()


class TestUpdateAlbums:
    """Test update_albums() method."""

    def test_updates_model_data(self, qapp):
        """Should call set_data on albums model."""
        coordinator = ModelCoordinator()

        coordinator.albums_model.set_data = Mock()
        albums = [{"name": "Test Album"}]

        coordinator.update_albums(albums)

        coordinator.albums_model.set_data.assert_called_once_with(albums)

    def test_applies_pending_sort(self, qapp):
        """Should apply pending sort and clear it."""
        coordinator = ModelCoordinator()

        mock_view = Mock()
        mock_view.table = Mock()
        mock_view.table.sortByColumn = Mock()

        coordinator.set_views(None, mock_view, None, None)
        coordinator.set_pending_albums_sort(1, Qt.AscendingOrder)
        coordinator.albums_model.set_data = Mock()

        coordinator.update_albums([{"name": "Album"}])

        mock_view.table.sortByColumn.assert_called_once_with(1, Qt.AscendingOrder)
        assert coordinator._pending_albums_sort is None

    def test_applies_default_sort(self, qapp):
        """Should apply default sort (column 3 descending)."""
        coordinator = ModelCoordinator()

        mock_view = Mock()
        mock_view.table = Mock()
        mock_view.table.sortByColumn = Mock()

        coordinator.set_views(None, mock_view, None, None)
        coordinator.albums_model.set_data = Mock()

        coordinator.update_albums([{"name": "Album"}])

        mock_view.table.sortByColumn.assert_called_once_with(3, Qt.DescendingOrder)


class TestUpdateArtists:
    """Test update_artists() method."""

    def test_updates_model_data(self, qapp):
        """Should call set_data on artists model."""
        coordinator = ModelCoordinator()

        coordinator.artists_model.set_data = Mock()
        artists = [{"name": "Test Artist"}]

        coordinator.update_artists(artists)

        coordinator.artists_model.set_data.assert_called_once_with(artists)

    def test_applies_pending_sort(self, qapp):
        """Should apply pending sort and clear it."""
        coordinator = ModelCoordinator()

        mock_view = Mock()
        mock_view.table = Mock()
        mock_view.table.sortByColumn = Mock()

        coordinator.set_views(None, None, mock_view, None)
        coordinator.set_pending_artists_sort(2, Qt.AscendingOrder)
        coordinator.artists_model.set_data = Mock()

        coordinator.update_artists([{"name": "Artist"}])

        mock_view.table.sortByColumn.assert_called_once_with(2, Qt.AscendingOrder)
        assert coordinator._pending_artists_sort is None

    def test_applies_default_sort(self, qapp):
        """Should apply default sort (column 3 descending)."""
        coordinator = ModelCoordinator()

        mock_view = Mock()
        mock_view.table = Mock()
        mock_view.table.sortByColumn = Mock()

        coordinator.set_views(None, None, mock_view, None)
        coordinator.artists_model.set_data = Mock()

        coordinator.update_artists([{"name": "Artist"}])

        mock_view.table.sortByColumn.assert_called_once_with(3, Qt.DescendingOrder)


class TestSimpleUpdateMethods:
    """Test simple update methods that just set model data."""

    def test_update_unmatched_tracks(self, qapp):
        """Should update unmatched tracks model."""
        coordinator = ModelCoordinator()

        coordinator.unmatched_tracks_model.set_data = Mock()
        tracks = [{"title": "Track 1"}]

        coordinator.update_unmatched_tracks(tracks)

        coordinator.unmatched_tracks_model.set_data.assert_called_once_with(tracks)

    def test_update_matched_tracks(self, qapp):
        """Should update matched tracks model."""
        coordinator = ModelCoordinator()

        coordinator.matched_tracks_model.set_data = Mock()
        tracks = [{"title": "Track 2"}]

        coordinator.update_matched_tracks(tracks)

        coordinator.matched_tracks_model.set_data.assert_called_once_with(tracks)

    def test_update_coverage(self, qapp):
        """Should update coverage model."""
        coordinator = ModelCoordinator()

        coordinator.coverage_model.set_data = Mock()
        coverage = [{"playlist": "PL1", "coverage": 0.95}]

        coordinator.update_coverage(coverage)

        coordinator.coverage_model.set_data.assert_called_once_with(coverage)

    def test_update_unmatched_albums(self, qapp):
        """Should update unmatched albums model."""
        coordinator = ModelCoordinator()

        coordinator.unmatched_albums_model.set_data = Mock()
        albums = [{"name": "Album 1"}]

        coordinator.update_unmatched_albums(albums)

        coordinator.unmatched_albums_model.set_data.assert_called_once_with(albums)

    def test_update_liked_tracks(self, qapp):
        """Should update liked tracks model."""
        coordinator = ModelCoordinator()

        coordinator.liked_tracks_model.set_data = Mock()
        tracks = [{"title": "Liked Track"}]

        coordinator.update_liked_tracks(tracks)

        coordinator.liked_tracks_model.set_data.assert_called_once_with(tracks)


class TestUpdateUnifiedTracks:
    """Test update_unified_tracks() method."""

    def test_updates_model_data(self, qapp):
        """Should update unified tracks model."""
        coordinator = ModelCoordinator()

        coordinator.unified_tracks_model.set_data = Mock()
        tracks = [{"title": "Track"}]
        playlists = [{"name": "PL1"}]

        coordinator.update_unified_tracks(tracks, playlists)

        coordinator.unified_tracks_model.set_data.assert_called_once_with(tracks)

    def test_preserves_column_widths_when_view_set(self, qapp):
        """Should NOT auto-resize columns to preserve user-set widths."""
        coordinator = ModelCoordinator()

        mock_view = Mock()

        coordinator.set_views(None, None, None, mock_view)
        coordinator.unified_tracks_model.set_data = Mock()

        coordinator.update_unified_tracks([{"title": "Track"}], [])

        # Verify no auto-resize methods are called
        assert not hasattr(mock_view, 'resize_columns_to_contents') or \
               not mock_view.resize_columns_to_contents.called

    def test_handles_no_view_gracefully(self, qapp):
        """Should not crash when no view is set."""
        coordinator = ModelCoordinator()

        coordinator.unified_tracks_model.set_data = Mock()

        # Should not raise
        coordinator.update_unified_tracks([{"title": "Track"}], [])

        coordinator.unified_tracks_model.set_data.assert_called_once()


class TestIntegration:
    """Integration tests for ModelCoordinator."""

    def test_multiple_updates_preserve_state(self, qapp):
        """Multiple updates should work correctly."""
        coordinator = ModelCoordinator()

        coordinator.playlists_model.set_data = Mock()
        coordinator.albums_model.set_data = Mock()
        coordinator.artists_model.set_data = Mock()

        # Update multiple models
        coordinator.update_playlists([{"id": "1"}])
        coordinator.update_albums([{"name": "Album"}])
        coordinator.update_artists([{"name": "Artist"}])

        # All should be called
        coordinator.playlists_model.set_data.assert_called_once()
        coordinator.albums_model.set_data.assert_called_once()
        coordinator.artists_model.set_data.assert_called_once()

    def test_pending_sorts_independent(self, qapp):
        """Pending sorts for different tables should be independent."""
        coordinator = ModelCoordinator()

        # Set different pending sorts
        coordinator.set_pending_playlists_sort(0, Qt.AscendingOrder)
        coordinator.set_pending_albums_sort(1, Qt.DescendingOrder)
        coordinator.set_pending_artists_sort(2, Qt.AscendingOrder)

        # All should be stored independently
        assert coordinator._pending_playlists_sort == (0, Qt.AscendingOrder)
        assert coordinator._pending_albums_sort == (1, Qt.DescendingOrder)
        assert coordinator._pending_artists_sort == (2, Qt.AscendingOrder)

    def test_view_updates_without_crashing(self, qapp):
        """Should handle view operations without crashing."""
        coordinator = ModelCoordinator()

        # Create mock views
        playlists_view = Mock()
        playlists_view.resizeColumnsToContents = Mock()
        playlists_view.columnWidth = Mock(return_value=150)
        playlists_view.setColumnWidth = Mock()
        playlists_view.sortByColumn = Mock()

        albums_view = Mock()
        albums_view.table = Mock()
        albums_view.table.sortByColumn = Mock()

        coordinator.set_views(playlists_view, albums_view, None, None)
        coordinator.playlists_model.set_data = Mock()
        coordinator.albums_model.set_data = Mock()

        # Should not crash
        coordinator.update_playlists([{"id": "1"}])
        coordinator.update_albums([{"name": "Album"}])

        # Verify operations were called
        assert playlists_view.sortByColumn.called
        assert albums_view.table.sortByColumn.called
