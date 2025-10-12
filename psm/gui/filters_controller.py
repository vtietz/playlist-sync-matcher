"""Filters controller for managing all filter operations.

This controller encapsulates all filter-related logic:
- Playlist filtering
- Artist/album filtering
- Filter coordination
- FilterStore integration
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Callable
import logging

if TYPE_CHECKING:
    from psm.gui.state import FilterStore

logger = logging.getLogger(__name__)


class FiltersController:
    """Manages all filter operations and FilterStore interactions.

    This controller centralizes filter management logic, reducing
    MainWindow's responsibility and improving testability.

    Example:
        controller = FiltersController(filter_store)
        controller.handle_playlist_filter_change("My Playlist", fetch_tracks_callback)
        controller.handle_artist_filter_change("Artist Name")
        controller.clear_filters()
    """

    def __init__(self, filter_store: FilterStore):
        """Initialize filters controller.

        Args:
            filter_store: FilterStore instance to manage
        """
        self.filter_store = filter_store

    def clear_filters(self):
        """Clear all active filters."""
        self.filter_store.clear()
        logger.debug("All filters cleared")

    def handle_playlist_filter_change(
        self,
        playlist_name: Optional[str],
        fetch_tracks_callback: Optional[Callable[[str], None]] = None
    ):
        """Handle playlist filter change from FilterBar.

        Args:
            playlist_name: Selected playlist name, or None for "All Playlists"
            fetch_tracks_callback: Optional callback to fetch playlist tracks
                                  Should accept playlist_name and return track IDs
        """
        if not playlist_name or playlist_name == "All Playlists":
            self.clear_filters()
            return

        logger.debug(f"Playlist filter changed to: {playlist_name}")

        # If callback provided, use it to fetch tracks asynchronously
        # This routes to MainOrchestrator → SelectionSyncController → FilterStore
        if fetch_tracks_callback:
            logger.debug(f"Invoking async callback for playlist: {playlist_name}")
            fetch_tracks_callback(playlist_name)
        else:
            # Synchronous path (will freeze UI for large playlists)
            logger.debug(f"No async callback provided for playlist: {playlist_name}")

    def handle_artist_filter_change(self, artist_name: Optional[str]):
        """Handle artist filter change from FilterBar.

        Args:
            artist_name: Selected artist name, or None for "All Artists"
        """
        if not artist_name or artist_name == "All Artists":
            # Clear artist filter (but keep playlist if set)
            current_state = self.filter_store.state
            if current_state.active_dimension in ("artist", "album"):
                self.clear_filters()
            return

        logger.debug(f"Artist filter changed to: {artist_name}")
        self.filter_store.set_artist(artist_name)

    def handle_album_filter_change(self, album_name: Optional[str], artist_name: Optional[str] = None):
        """Handle album filter change from FilterBar.

        Args:
            album_name: Selected album name, or None for "All Albums"
            artist_name: Optional artist name (provides context when both selected)
        """
        if not album_name or album_name == "All Albums":
            # Clear album filter (but keep artist if set in current state)
            current_state = self.filter_store.state
            if current_state.active_dimension in ("artist", "album") and current_state.artist_name:
                # Keep artist-only filter using artist from current state
                self.filter_store.set_artist(current_state.artist_name)
            else:
                self.clear_filters()
            return

        # Album filter now works with or without artist context
        if artist_name and artist_name != "All Artists":
            logger.debug(f"Album filter changed to: {album_name} (artist: {artist_name})")
            self.filter_store.set_album(album_name, artist_name)
        else:
            # Album-only filtering (no artist constraint)
            logger.debug(f"Album filter changed to: {album_name} (album-only)")
            self.filter_store.set_album(album_name, None)

    def get_current_state(self):
        """Get current filter state.

        Returns:
            Current FilterState
        """
        return self.filter_store.state

    def is_playlist_filtered(self) -> bool:
        """Check if playlist filter is active.

        Returns:
            True if playlist filter is active
        """
        return self.filter_store.state.active_dimension == "playlist"

    def is_artist_filtered(self) -> bool:
        """Check if artist filter is active.

        Returns:
            True if artist filter is active
        """
        return self.filter_store.state.active_dimension == "artist"

    def is_album_filtered(self) -> bool:
        """Check if album filter is active.

        Returns:
            True if album filter is active
        """
        return self.filter_store.state.active_dimension == "album"

    def is_any_filter_active(self) -> bool:
        """Check if any filter is active.

        Returns:
            True if any filter dimension is active
        """
        return not self.filter_store.state.is_cleared
