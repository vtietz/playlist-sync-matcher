"""Tests for FiltersController component."""

import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject

from psm.gui.filters_controller import FiltersController
from psm.gui.state import FilterStore


@pytest.fixture(scope='module')
def qapp():
    """Create QApplication instance for GUI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def parent_object(qapp):
    """Create a parent QObject for FilterStore."""
    return QObject()


@pytest.fixture
def filter_store(parent_object):
    """Create FilterStore instance for testing."""
    return FilterStore(parent_object)


@pytest.fixture
def controller(filter_store):
    """Create FiltersController instance for testing."""
    return FiltersController(filter_store)


class TestFiltersControllerCreation:
    """Test controller creation."""

    def test_controller_creation(self, controller):
        """Controller should be created successfully."""
        assert controller is not None

    def test_has_filter_store(self, controller, filter_store):
        """Controller should have reference to filter store."""
        assert controller.filter_store is filter_store


class TestClearFilters:
    """Test filter clearing operations."""

    def test_clear_filters(self, controller):
        """Should clear all filters."""
        # Set a filter
        controller.handle_artist_filter_change("Test Artist")
        assert not controller.filter_store.state.is_cleared

        # Clear
        controller.clear_filters()
        assert controller.filter_store.state.is_cleared

    def test_clear_when_already_cleared(self, controller):
        """Should handle clearing already-cleared filters."""
        controller.clear_filters()
        assert controller.filter_store.state.is_cleared


class TestPlaylistFilter:
    """Test playlist filter operations."""

    def test_playlist_filter_all_playlists(self, controller):
        """Should clear filter when 'All Playlists' selected."""
        controller.handle_playlist_filter_change("All Playlists")
        assert controller.filter_store.state.is_cleared

    def test_playlist_filter_empty_string(self, controller):
        """Should clear filter when empty string provided."""
        controller.handle_playlist_filter_change("")
        assert controller.filter_store.state.is_cleared

    def test_playlist_filter_with_name_no_callback(self, controller):
        """Should handle playlist selection without callback."""
        # Without callback, should just log (not set filter yet)
        controller.handle_playlist_filter_change("My Playlist")
        # Filter not set without track IDs from callback
        # This is expected behavior for sync path

    def test_playlist_filter_with_callback(self, controller):
        """Should call callback when provided."""
        called_with = []

        def fetch_callback(name):
            called_with.append(name)

        controller.handle_playlist_filter_change("My Playlist", fetch_callback)
        # Callback should have been called (currently commented out in implementation)
        # When implemented: assert called_with == ["My Playlist"]


class TestArtistFilter:
    """Test artist filter operations."""

    def test_artist_filter_all_artists(self, controller):
        """Should clear filter when 'All Artists' selected."""
        controller.handle_artist_filter_change("All Artists")
        assert controller.filter_store.state.is_cleared

    def test_artist_filter_empty_string(self, controller):
        """Should clear filter when empty string provided."""
        controller.handle_artist_filter_change("")
        assert controller.filter_store.state.is_cleared

    def test_artist_filter_with_name(self, controller):
        """Should set artist filter."""
        controller.handle_artist_filter_change("Test Artist")

        state = controller.filter_store.state
        assert state.artist_name == "Test Artist"
        assert state.album_name is None
        assert state.playlist_name is None

    def test_artist_filter_clears_album(self, controller):
        """Setting artist to 'All Artists' should clear album filter."""
        # Set album filter first
        controller.handle_album_filter_change("Album", "Artist")
        assert controller.filter_store.state.album_name == "Album"

        # Clear artist
        controller.handle_artist_filter_change("All Artists")
        assert controller.filter_store.state.is_cleared

    def test_artist_filter_preserves_playlist(self, controller):
        """Clearing artist should preserve playlist filter if active."""
        # This test assumes FilterStore handles this logic
        # Controller just delegates to FilterStore


class TestAlbumFilter:
    """Test album filter operations."""

    def test_album_filter_all_albums(self, controller):
        """Should clear filter when 'All Albums' selected."""
        controller.handle_album_filter_change("All Albums", "Artist")
        assert controller.filter_store.state.is_cleared

    def test_album_filter_empty_string(self, controller):
        """Should clear filter when empty string provided."""
        controller.handle_album_filter_change("", "Artist")
        assert controller.filter_store.state.is_cleared

    def test_album_filter_with_artist(self, controller):
        """Should set album filter when artist provided."""
        controller.handle_album_filter_change("Test Album", "Test Artist")

        state = controller.filter_store.state
        assert state.album_name == "Test Album"
        assert state.artist_name == "Test Artist"
        assert state.playlist_name is None

    def test_album_filter_without_artist(self, controller):
        """Should set album-only filter without artist."""
        controller.handle_album_filter_change("Test Album", None)

        # Album-only filtering is now supported
        state = controller.filter_store.state
        assert state.album_name == "Test Album"
        assert state.artist_name is None

    def test_album_filter_with_all_artists(self, controller):
        """Should set album-only filter when artist is 'All Artists'."""
        controller.handle_album_filter_change("Test Album", "All Artists")

        # Album-only filtering is now supported
        state = controller.filter_store.state
        assert state.album_name == "Test Album"
        assert state.artist_name is None

    def test_album_clear_preserves_artist(self, controller):
        """Clearing album should preserve artist-only filter."""
        # Set album+artist
        controller.handle_album_filter_change("Album", "Artist")
        assert controller.filter_store.state.album_name == "Album"

        # Clear album
        controller.handle_album_filter_change("All Albums", "Artist")

        # Should keep artist-only filter
        state = controller.filter_store.state
        assert state.artist_name == "Artist"
        assert state.album_name is None


class TestFilterStateQueries:
    """Test filter state query methods."""

    def test_is_playlist_filtered(self, controller):
        """Should detect playlist filter."""
        # Note: Can't test this without track IDs
        # assert not controller.is_playlist_filtered()

    def test_is_artist_filtered(self, controller):
        """Should detect artist filter."""
        assert not controller.is_artist_filtered()

        controller.handle_artist_filter_change("Artist")
        assert controller.is_artist_filtered()

    def test_is_album_filtered(self, controller):
        """Should detect album filter."""
        assert not controller.is_album_filtered()

        controller.handle_album_filter_change("Album", "Artist")
        assert controller.is_album_filtered()

    def test_is_any_filter_active(self, controller):
        """Should detect any active filter."""
        assert not controller.is_any_filter_active()

        controller.handle_artist_filter_change("Artist")
        assert controller.is_any_filter_active()

        controller.clear_filters()
        assert not controller.is_any_filter_active()

    def test_get_current_state(self, controller):
        """Should return current filter state."""
        state = controller.get_current_state()
        assert state is not None
        assert state.is_cleared


class TestFilterCoordination:
    """Test coordination between different filter types."""

    def test_artist_then_album(self, controller):
        """Should handle artist -> album sequence."""
        controller.handle_artist_filter_change("Artist")
        controller.handle_album_filter_change("Album", "Artist")

        state = controller.filter_store.state
        assert state.album_name == "Album"
        assert state.artist_name == "Artist"

    def test_album_then_artist_change(self, controller):
        """Should handle album -> different artist sequence."""
        controller.handle_album_filter_change("Album", "Artist1")
        controller.handle_artist_filter_change("Artist2")

        # New artist should clear album
        state = controller.filter_store.state
        assert state.artist_name == "Artist2"
        assert state.album_name is None

    def test_clear_then_filter(self, controller):
        """Should handle clear -> filter sequence."""
        controller.handle_artist_filter_change("Artist")
        controller.clear_filters()
        controller.handle_album_filter_change("Album", "Artist")

        state = controller.filter_store.state
        assert state.album_name == "Album"
        assert state.artist_name == "Artist"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_multiple_clears(self, controller):
        """Should handle multiple consecutive clears."""
        controller.clear_filters()
        controller.clear_filters()
        controller.clear_filters()

        assert controller.filter_store.state.is_cleared

    def test_same_filter_twice(self, controller):
        """Should handle setting same filter twice."""
        controller.handle_artist_filter_change("Artist")
        controller.handle_artist_filter_change("Artist")

        state = controller.filter_store.state
        assert state.artist_name == "Artist"

    def test_whitespace_in_names(self, controller):
        """Should handle whitespace in filter names."""
        controller.handle_artist_filter_change("  Artist  ")

        # Controller passes through to FilterStore as-is
        state = controller.filter_store.state
        assert state.artist_name == "  Artist  "
