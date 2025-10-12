"""Controller for selection synchronization between left panels and FilterStore."""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional
from PySide6.QtCore import QObject, QSignalBlocker
import logging

from ..utils.async_loader import MultiAsyncLoader

if TYPE_CHECKING:
    from ..main_window import MainWindow
    from ..data_facade import DataFacade
    from .db_auto_refresh_controller import DbAutoRefreshController

logger = logging.getLogger(__name__)


class SelectionSyncController(QObject):
    """Manages bidirectional sync between left panel selections and FilterStore.

    Responsibilities:
    - Handle playlist/album/artist selection from left panels
    - Async loading of playlist track IDs via PlaylistFilterLoader
    - Update FilterStore with filter state (single source of truth)
    - Sync FilterStore changes back to left panel selections
    - Prevent infinite selection loops via QSignalBlocker
    """

    def __init__(
        self,
        window: MainWindow,
        facade: DataFacade,
        facade_factory,
        db_monitor: Optional[DbAutoRefreshController] = None,
        parent: Optional[QObject] = None
    ):
        """Initialize controller.

        Args:
            window: Main window instance
            facade: Data facade for main thread
            facade_factory: Factory to create thread-safe facades
            db_monitor: Database monitor controller
            parent: Parent QObject
        """
        super().__init__(parent)
        self.window = window
        self.facade = facade
        self.facade_factory = facade_factory
        self._db_monitor = db_monitor

        # Track active loaders for playlist filtering
        self._active_loaders: list = []

        # Connect signals
        self._connect_signals()

    def _connect_signals(self):
        """Connect selection signals from left panels and FilterStore."""
        # Playlist selection now handled via FilterStore
        # Controller subscribes directly to PlaylistsTab.selection_changed for async loading
        self.window.playlists_tab.selection_changed.connect(self._on_playlist_selected)

        # Albums and Artists selection → FilterStore
        if hasattr(self.window, 'albums_view'):
            self.window.albums_view.album_selected.connect(self._on_album_selected)
        if hasattr(self.window, 'artists_view'):
            self.window.artists_view.artist_selected.connect(self._on_artist_selected)

        # FilterStore → Left panels (bidirectional sync)
        # When FilterStore state changes, update left panel selections
        self.window.filter_store.filterChanged.connect(self._on_filter_store_changed)

    def _on_playlist_selected(self, selected, deselected):
        """Handle playlist selection - async version to prevent UI freeze.

        Receives selection change from PlaylistsTab and triggers async filter update.

        Args:
            selected: QItemSelection of selected items
            deselected: QItemSelection of deselected items
        """
        # Check if selection is empty
        if selected.isEmpty():
            logger.info("Playlist selection cleared")
            self.window.enable_playlist_actions(False)
            self.window.filter_store.clear()
            return

        # Extract playlist name from selected indexes
        proxy_indexes = selected.indexes()
        if not proxy_indexes:
            logger.warning("No indexes in selection")
            return

        # Find index for column 0 (playlist name)
        proxy_index = None
        for idx in proxy_indexes:
            if idx.column() == 0:
                proxy_index = idx
                break

        if not proxy_index:
            logger.warning("No column 0 index found in selection")
            return

        # Map proxy index to source model
        source_index = self.window.playlist_proxy_model.mapToSource(proxy_index)
        source_row = source_index.row()

        # Get playlist name from source model
        # Try row_data first, fallback to display role
        row_data = self.window.playlists_model.get_row_data(source_row)
        if row_data:
            playlist_name = row_data.get('name') or row_data.get('id')
        else:
            # Fallback to display role
            playlist_name = self.window.playlists_model.index(source_row, 0).data()

        if not playlist_name:
            logger.warning(f"Could not extract playlist name from row {source_row}")
            return

        logger.info(f"Playlist selected: {playlist_name}")

        # Enable per-playlist actions
        self.window.enable_playlist_actions(True)

        # Update FilterStore with playlist filter (async to avoid freeze)
        self.set_playlist_filter_async(playlist_name)

    def _on_album_selected(self, album_name, artist_name):
        """Handle album selection from AlbumsView.

        Filters by album name only (not artist), even though the signal provides both.
        This allows seeing all tracks from an album across different artists/compilations.

        Args:
            album_name: Selected album name (or None to clear)
            artist_name: Selected artist name (provided but not used for filtering)
        """
        if album_name is None:
            logger.info("Album selection cleared")
            self.window.filter_store.clear()
        else:
            logger.info(f"Album selected: {album_name} (filtering by album only)")
            # Filter by album only - use artist_name for context but filter shows album only
            # Note: FilterState requires artist for albums, but we can use it without displaying
            self.window.filter_store.set_album(album_name, artist_name)

    def _on_artist_selected(self, artist_name):
        """Handle artist selection from ArtistsView.

        Args:
            artist_name: Selected artist name (or None to clear)
        """
        if artist_name is None:
            logger.info("Artist selection cleared")
            self.window.filter_store.clear()
        else:
            logger.info(f"Artist selected: {artist_name}")
            # Set artist filter in FilterStore (clears playlist filter per one-dimension rule)
            self.window.filter_store.set_artist(artist_name)

    def _on_filter_store_changed(self, filter_state):
        """Handle FilterStore state changes - update left panel selections (bidirectional sync).

        When FilterStore changes (e.g., via FilterBar dropdown), this updates the
        corresponding left panel selection to maintain UI consistency.

        Uses QSignalBlocker in select_* methods to prevent re-emission loops.

        Args:
            filter_state: Current FilterState from FilterStore
        """
        logger.debug(f"FilterStore changed: dimension={filter_state.active_dimension}")

        # Update left panel selection based on active dimension
        if filter_state.active_dimension == 'playlist' and filter_state.playlist_name:
            # Select playlist in left panel
            if hasattr(self.window, 'playlists_tab'):
                self.window.playlists_tab.select_playlist(filter_state.playlist_name)
                logger.debug(f"Updated playlist selection: {filter_state.playlist_name}")

        elif filter_state.active_dimension == 'album' and filter_state.album_name:
            # Select album in left panel
            if hasattr(self.window, 'albums_view'):
                self.window.albums_view.select_album(filter_state.album_name, filter_state.artist_name)
                logger.debug(f"Updated album selection: {filter_state.album_name} by {filter_state.artist_name}")

        elif filter_state.active_dimension == 'artist' and filter_state.artist_name:
            # Select artist in left panel
            if hasattr(self.window, 'artists_view'):
                self.window.artists_view.select_artist(filter_state.artist_name)
                logger.debug(f"Updated artist selection: {filter_state.artist_name}")

        elif filter_state.is_cleared:
            # Clear all left panel selections by clearing their selection models
            if hasattr(self.window, 'playlists_tab'):
                selection_model = self.window.playlists_tab.table_view.selectionModel()
                if selection_model:
                    with QSignalBlocker(selection_model):
                        selection_model.clearSelection()

            if hasattr(self.window, 'albums_view'):
                self.window.albums_view.table.clearSelection()

            if hasattr(self.window, 'artists_view'):
                self.window.artists_view.table.clearSelection()

            logger.debug("Cleared all left panel selections")

    def set_playlist_filter_async(self, playlist_name: Optional[str]):
        """Set playlist filter asynchronously to prevent UI freeze.

        Fetches track IDs for the playlist in a background thread,
        then publishes to FilterStore on completion.
        FilterStore emits filterChanged → UnifiedTracksView updates automatically.

        Args:
            playlist_name: Playlist name to filter by, or None to clear filter
        """
        if not playlist_name:
            # Clear filter immediately (no async needed)
            logger.info("Clearing playlist filter")
            self.window.filter_store.clear()
            return

        logger.info(f"set_playlist_filter_async called with: {playlist_name}")

        # Suppress auto-refresh during playlist loading (prevents false triggers)
        if self._db_monitor:
            self._db_monitor.set_suppression(True)

        # Cancel any previous playlist filter loaders
        # (Allow other loaders to continue - only cancel playlist filtering)
        for loader in self._active_loaders[:]:  # Copy list to avoid modification during iteration
            if hasattr(loader, '_is_playlist_filter') and loader._is_playlist_filter:
                logger.debug("Cancelling previous playlist filter loader")
                loader.stop()
                loader.wait()
                self._active_loaders.remove(loader)

        # Define async loading function using facade_factory for thread safety
        load_funcs = {
            'track_ids': lambda: self.facade_factory().get_track_ids_for_playlist(playlist_name)
        }

        # Create async loader
        loader = MultiAsyncLoader(load_funcs)
        loader._is_playlist_filter = True  # Mark as playlist filter loader
        loader._playlist_name = playlist_name  # Store playlist name for callback

        def on_loaded(results):
            """Handle track IDs loaded successfully."""
            track_ids = results.get('track_ids', [])
            logger.info(f"Loaded {len(track_ids)} tracks for playlist '{playlist_name}'")

            # Publish to FilterStore (single source of truth)
            # FilterStore will emit filterChanged → UnifiedTracksView.on_store_filter_changed()
            self.window.filter_store.set_playlist(playlist_name, set(track_ids))
            logger.debug(f"Published to FilterStore: {playlist_name}")

            # Set ignore window to prevent false refresh from WAL checkpoint
            # (Read operations can trigger WAL checkpoint, updating mtime without real writes)
            if self._db_monitor:
                self._db_monitor.set_ignore_window(2.5)
                self._db_monitor.set_suppression(False)

            # Clean up loader
            if loader in self._active_loaders:
                self._active_loaders.remove(loader)
                # Update database monitor with new loader count
                if self._db_monitor:
                    self._db_monitor.set_loader_count(len(self._active_loaders))

        def on_error(error_msg):
            """Handle loading error."""
            logger.error(f"Failed to load playlist tracks: {error_msg}")

            # Re-enable auto-refresh
            if self._db_monitor:
                self._db_monitor.set_suppression(False)

            # Clean up loader
            if loader in self._active_loaders:
                self._active_loaders.remove(loader)
                # Update database monitor with new loader count
                if self._db_monitor:
                    self._db_monitor.set_loader_count(len(self._active_loaders))

        loader.all_finished.connect(on_loaded)
        loader.error.connect(on_error)

        # Track loader to prevent garbage collection
        self._active_loaders.append(loader)

        # Update database monitor with loader count
        if self._db_monitor:
            self._db_monitor.set_loader_count(len(self._active_loaders))

        # Start loading in background
        loader.start()
        logger.debug(f"Started async loading of track IDs for playlist: {playlist_name}")

    def set_playlist_filter(self, playlist_name: Optional[str]):
        """Set playlist filter via FilterStore (single source of truth).

        DEPRECATED: Use set_playlist_filter_async() instead to prevent UI freeze.
        Kept for backward compatibility with FilterBar handlers.

        Args:
            playlist_name: Playlist name to filter by, or None to clear filter
        """
        # Delegate to async version
        self.set_playlist_filter_async(playlist_name)
