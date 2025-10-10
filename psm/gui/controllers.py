"""Controllers wiring UI events to actions and data updates."""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional, List, Dict, Any
from PySide6.QtCore import QObject, QTimer, QSignalBlocker, Qt
import logging

from .services import CommandService
from .utils.async_loader import MultiAsyncLoader

if TYPE_CHECKING:
    from .main_window import MainWindow
    from .data_facade import DataFacade
    from .runner import CliExecutor

logger = logging.getLogger(__name__)


class MainController(QObject):
    """Main controller coordinating all GUI interactions."""
    
    def __init__(
        self, 
        window: MainWindow, 
        facade: DataFacade, 
        executor: CliExecutor,
        facade_factory=None,
        parent=None
    ):
        """Initialize controller.
        
        Args:
            window: Main window instance
            facade: Data facade instance (main thread)
            executor: CLI executor instance
            facade_factory: Callable that creates new facade instances for background threads
            parent: Parent QObject
        """
        super().__init__(parent)
        self.window = window
        self.facade = facade
        self.executor = executor
        self.facade_factory = facade_factory or (lambda: facade)  # Default to main facade if no factory
        
        # Initialize command service for standardized execution
        self.command_service = CommandService(
            executor=executor,
            enable_actions=window.enable_actions
        )
        
        # Track active async loaders
        self._active_loaders: list[MultiAsyncLoader] = []
        self._filter_options_loaded = False  # Track if filter options are loaded
        
        # Connect UI signals to handlers
        self._connect_signals()
        
        # Set up lazy playlist loading callback
        self.window.unified_tracks_view.set_playlist_fetch_callback(
            self._fetch_playlists_for_tracks
        )
        
        # FilterStore is already initialized in MainWindow.__init__
        # No coordinator initialization needed - simpler pattern!
        
        # Initial data load - use async to avoid blocking UI
        QTimer.singleShot(0, self.refresh_all_async)
    
    def _connect_signals(self):
        """Connect UI signals to controller methods."""
        # Playlist selection now handled via FilterStore (see MainWindow._on_playlist_selection_changed)
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
        
        # Action buttons
        self.window.on_pull_clicked.connect(self._on_pull)
        self.window.on_scan_clicked.connect(self._on_scan)
        self.window.on_match_clicked.connect(self._on_match)
        self.window.on_export_clicked.connect(self._on_export)
        self.window.on_report_clicked.connect(self._on_report)
        self.window.on_open_reports_clicked.connect(self._on_open_reports)
        self.window.on_build_clicked.connect(self._on_build)
        self.window.on_analyze_clicked.connect(self._on_analyze)
        self.window.on_diagnose_clicked.connect(self._on_diagnose)
        
        # Per-playlist actions
        self.window.on_pull_one_clicked.connect(self._on_pull_one)
        self.window.on_match_one_clicked.connect(self._on_match_one)
        self.window.on_export_one_clicked.connect(self._on_export_one)
        
        # Watch mode
        self.window.on_watch_toggled.connect(self._on_watch_toggled)
        
        # Cancel command
        self.window.on_cancel_clicked.connect(self._on_cancel)
        
        # Note: Filter options are now populated on-demand from visible data
        # in UnifiedTracksView.populate_filter_options_from_visible_data()
    
    def refresh_all(self):
        """Refresh all data in the UI (synchronous - blocks UI).
        
        NOTE: Use refresh_all_async() instead to prevent freezing.
        This method is kept for compatibility but should be avoided.
        """
        logger.info("Refreshing all data (sync)...")
        
        # Update playlists with counts
        playlists = self.facade.list_playlists()
        self.window.update_playlists(playlists)
        
        # Update unified tracks view
        self._refresh_unified_tracks()
        
        # Update counts in status bar
        counts = self.facade.get_counts()
        self.window.update_status_counts(counts)
    
    def refresh_all_async(self):
        """Refresh all data in the UI asynchronously (non-blocking).
        
        This method loads data in a background thread to prevent the UI
        from freezing, especially important for large libraries.
        Uses facade_factory to create thread-safe DB connections.
        """
        logger.info("Refreshing all data (async)...")
        
        # Cancel any running loaders first
        if self._active_loaders:
            logger.info("Cancelling previous loader...")
            for loader in self._active_loaders:
                loader.stop()
                loader.wait()
            self._active_loaders.clear()
        
        # Show loading state
        self.window.set_execution_status(True, "Loading data")
        self.window.unified_tracks_view.show_loading()
        
        # Define loading functions using facade_factory for thread safety
        # Each lambda creates a new facade with its own DB connection
        load_funcs = {
            'playlists': lambda: self.facade_factory().list_playlists(),
            'tracks': lambda: self.facade_factory().list_all_tracks_unified_fast(),  # Fast path!
            'albums_data': lambda: self.facade_factory().list_albums(),  # Aggregated albums
            'artists_data': lambda: self.facade_factory().list_artists(),  # Aggregated artists
            'artists': lambda: self.facade_factory().get_unique_artists(),
            'albums': lambda: self.facade_factory().get_unique_albums(),
            'years': lambda: self.facade_factory().get_unique_years(),
            'counts': lambda: self.facade_factory().get_counts(),
        }
        
        # Create async loader
        loader = MultiAsyncLoader(load_funcs)
        loader.all_finished.connect(self._on_data_loaded)
        loader.error.connect(self._on_data_load_error)
        loader.item_finished.connect(self._on_item_loaded)
        
        # Track loader to prevent garbage collection
        self._active_loaders.append(loader)
        
        # Start loading
        loader.start()
    
    def _on_item_loaded(self, key: str, data):
        """Handle individual item loaded.
        
        Args:
            key: Data key (e.g., 'playlists', 'tracks')
            data: Loaded data
        """
        logger.debug(f"Loaded {key}: {len(data) if hasattr(data, '__len__') else 'N/A'} items")
        # No progress updates needed - using simple execution status instead
    
    def _on_data_loaded(self, results: dict):
        """Handle all data loaded successfully.
        
        Args:
            results: Dict with all loaded data
        """
        logger.info("All data loaded successfully")
        
        try:
            # Update playlists
            if 'playlists' in results:
                self.window.update_playlists(results['playlists'])
            
            # Update albums
            if 'albums_data' in results:
                self.window.update_albums(results['albums_data'])
            
            # Update artists
            if 'artists_data' in results:
                self.window.update_artists(results['artists_data'])
            
            # Update tracks
            if 'tracks' in results:
                # Use streaming for large datasets to avoid UI freeze
                track_count = len(results['tracks'])
                if track_count > 5000:
                    logger.info(f"Using streaming mode for {track_count} tracks")
                    self._load_tracks_streaming(results['tracks'], results.get('playlists', []))
                else:
                    logger.info(f"Using direct load for {track_count} tracks")
                    self.window.update_unified_tracks(
                        results['tracks'],
                        results.get('playlists', [])
                    )
            
            # Update filter options (no owners needed)
            if all(k in results for k in ['artists', 'albums', 'years']):
                self.window.populate_track_filter_options(
                    results['artists'],
                    results['albums'],
                    results['years']
                )
                # Also populate albums view filter
                if hasattr(self.window, 'albums_view'):
                    self.window.albums_view.populate_filter_options()
            
            # Update counts
            if 'counts' in results:
                self.window.update_status_counts(results['counts'])
            
            # Clear execution status and hide loading overlay
            self.window.set_execution_status(False)
            self.window.unified_tracks_view.hide_loading()
            self.window.append_log("Data loaded successfully")
            
            # Reapply active playlist filter if a playlist is selected
            # This ensures the filter uses fresh track_ids after DB changes (e.g., "Pull Selected")
            selected_playlist_id = self.window.get_selected_playlist_id()
            if selected_playlist_id:
                # Fetch current playlist data to get name
                playlist = self.facade.get_playlist_by_id(selected_playlist_id)
                if playlist:
                    # Recompute filter with fresh track_ids from DB
                    logger.debug(f"Reapplying playlist filter for '{playlist.name}' after data refresh")
                    self.set_playlist_filter(playlist.name)
                else:
                    # Playlist was deleted - clear filter and selection
                    logger.info(f"Playlist {selected_playlist_id} no longer exists - clearing selection")
                    self.window.unified_tracks_view.clear_filters()
                    self.window._selected_playlist_id = None
            
            # Trigger lazy playlist loading for visible rows
            QTimer.singleShot(100, self.window.unified_tracks_view.trigger_lazy_playlist_load)
            
        except Exception as e:
            logger.error(f"Error updating UI with loaded data: {e}", exc_info=True)
            self.window.append_log(f"Error updating UI: {e}")
            self.window.unified_tracks_view.hide_loading()
        
        finally:
            # Clean up loader reference
            if self._active_loaders:
                self._active_loaders.pop(0)
    
    def _load_tracks_streaming(self, tracks: List[Dict[str, Any]], playlists: List[Dict[str, Any]]):
        """Load tracks using streaming API to avoid UI freeze on large datasets.
        
        Chunks data and appends incrementally with QTimer to keep UI responsive.
        
        Args:
            tracks: List of all track dicts
            playlists: List of playlists (for filter options, not used during streaming)
        """
        CHUNK_SIZE = 500  # Rows per chunk (reduced from 1000 for better responsiveness)
        CHUNK_DELAY_MS = 16  # ~60fps yield between chunks (was 0)
        
        view = self.window.unified_tracks_view
        model = self.window.unified_tracks_model
        
        # Pre-filter by playlist track_ids if active
        filter_state = self.window.filter_store.state
        if filter_state.active_dimension == 'playlist' and filter_state.track_ids:
            logger.debug(f"Pre-filtering {len(tracks)} tracks by playlist filter ({len(filter_state.track_ids)} IDs)")
            tracks = [row for row in tracks if row.get('id') in filter_state.track_ids]
            logger.debug(f"After pre-filtering: {len(tracks)} tracks")
        
        total_count = len(tracks)
        
        # Disable sorting and dynamic filtering during streaming
        view.tracks_table.setSortingEnabled(False)
        proxy = view.proxy_model
        proxy.setDynamicSortFilter(False)
        
        # Start streaming
        model.load_data_async_start(total_count)
        
        # Set streaming flag on view to gate lazy playlist loading
        view._is_streaming = True
        
        # Prepare chunked iterator
        chunk_iterator = [tracks[i:i + CHUNK_SIZE] for i in range(0, len(tracks), CHUNK_SIZE)]
        current_chunk_index = [0]  # Use list for closure mutation
        
        # Update status bar
        self.window.set_execution_status(True, f"Loading tracks (0/{total_count})...")
        
        def append_next_chunk():
            """Append next chunk via QTimer callback."""
            if current_chunk_index[0] >= len(chunk_iterator):
                # Streaming complete
                _finalize_streaming()
                return
            
            chunk = chunk_iterator[current_chunk_index[0]]
            model.load_data_async_append(chunk)
            
            current_chunk_index[0] += 1
            rows_loaded = min(current_chunk_index[0] * CHUNK_SIZE, total_count)
            
            # Update progress
            self.window.set_execution_status(True, f"Loading tracks ({rows_loaded}/{total_count})...")
            
            # Schedule next chunk (yield to event loop for ~60fps)
            QTimer.singleShot(CHUNK_DELAY_MS, append_next_chunk)
        
        def _finalize_streaming():
            """Finalize streaming: re-enable sorting, trigger lazy load, etc."""
            model.load_data_async_complete()
            view._is_streaming = False
            
            # Re-enable sorting and apply last sort column
            proxy.setDynamicSortFilter(True)
            view.tracks_table.setSortingEnabled(True)
            
            # Apply sort: use pending (restored) sort if available, otherwise default to Track name A-Z
            if hasattr(self.window, '_pending_tracks_sort') and self.window._pending_tracks_sort is not None:
                sort_col, sort_order = self.window._pending_tracks_sort
                view.tracks_table.sortByColumn(sort_col, sort_order)
                self.window._pending_tracks_sort = None  # Clear after applying
            elif view.tracks_table.horizontalHeader().sortIndicatorSection() == -1:
                # No sort indicator and no pending sort - apply default
                view.tracks_table.sortByColumn(0, Qt.AscendingOrder)  # Sort by Track name A-Z
            
            # Resize columns if dataset is small enough
            if total_count <= 1000:
                view.resize_columns_to_contents()
            
            # Clear execution status
            self.window.set_execution_status(False)
            
            # Trigger lazy playlist loading for visible rows
            QTimer.singleShot(100, view.trigger_lazy_playlist_load)
            
            logger.info(f"Streaming complete: {total_count} tracks loaded")
        
        # Start chunking
        QTimer.singleShot(0, append_next_chunk)
    
    def _fetch_playlists_for_tracks(self, track_ids: List[str]) -> Dict[str, str]:
        """Fetch playlist names for given track IDs (used by lazy loading).
        
        Args:
            track_ids: List of track IDs
            
        Returns:
            Dict mapping track_id -> comma-separated playlist names
        """
        return self.facade.get_playlists_for_tracks(track_ids)
    
    def _on_data_load_error(self, error_msg: str):
        """Handle data loading error.
        
        Args:
            error_msg: Error message
        """
        logger.error(f"Data loading error: {error_msg}")
        self.window.append_log(f"Error loading data: {error_msg}")
        self.window.set_execution_status(False)  # Set to Ready
        self.window.unified_tracks_view.hide_loading()
        
        # Clean up loader reference
        if self._active_loaders:
            self._active_loaders.pop(0)
        
        # Update unified tracks view
        self._refresh_unified_tracks()
        
        # Update counts in status bar
        counts = self.facade.get_counts()
        self.window.update_status_counts(counts)
    
    def _refresh_unified_tracks(self):
        """Refresh unified tracks view."""
        logger.info("Refreshing unified tracks...")
        tracks = self.facade.list_all_tracks_unified()
        playlists = self.facade.list_playlists()
        
        # Update view with data
        self.window.update_unified_tracks(tracks, playlists)
        
        # Filter options are loaded on-demand when user interacts with filters
    
    def _load_filter_options(self):
        """Load unique values for filter dropdowns (lazy loaded)."""
        if self._filter_options_loaded:
            return  # Already loaded, skip
        
        logger.info("Loading filter options...")
        
        # Get unique values for filter dropdowns (no owner filter needed)
        artists = self.facade.get_unique_artists()
        albums = self.facade.get_unique_albums()
        years = self.facade.get_unique_years()
        
        # Update filter options
        self.window.populate_track_filter_options(artists, albums, years)
        self._filter_options_loaded = True
        
        logger.info("Filter options loaded")
    
    def ensure_filter_options_loaded(self):
        """Public method to ensure filter options are loaded (called on-demand)."""
        self._load_filter_options()
    
    def _refresh_current_tab(self):
        """Refresh data for the currently visible tab.
        
        DEPRECATED: Now using unified view only, refresh all tracks instead.
        """
        self._refresh_unified_tracks()
    
    def _refresh_unmatched_tracks(self):
        """Refresh unmatched tracks tab."""
        logger.info("Refreshing unmatched tracks...")
        tracks = self.facade.list_unmatched_tracks()
        self.window.update_unmatched_tracks(tracks)
    
    def _refresh_matched_tracks(self):
        """Refresh matched tracks tab."""
        logger.info("Refreshing matched tracks...")
        tracks = self.facade.list_matched_tracks()
        self.window.update_matched_tracks(tracks)
    
    def _refresh_coverage(self):
        """Refresh coverage tab."""
        logger.info("Refreshing coverage...")
        coverage = self.facade.list_playlist_coverage()
        self.window.update_coverage(coverage)
    
    def _refresh_unmatched_albums(self):
        """Refresh unmatched albums tab."""
        logger.info("Refreshing unmatched albums...")
        albums = self.facade.list_unmatched_albums()
        self.window.update_unmatched_albums(albums)
    
    def _refresh_liked_tracks(self):
        """Refresh liked tracks tab."""
        logger.info("Refreshing liked tracks...")
        tracks = self.facade.list_liked_tracks()
        self.window.update_liked_tracks(tracks)
    
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
            
            # Clean up loader
            if loader in self._active_loaders:
                self._active_loaders.remove(loader)
        
        def on_error(error_msg):
            """Handle loading error."""
            logger.error(f"Failed to load playlist tracks: {error_msg}")
            # Clean up loader
            if loader in self._active_loaders:
                self._active_loaders.remove(loader)
        
        loader.all_finished.connect(on_loaded)
        loader.error.connect(on_error)
        
        # Track loader to prevent garbage collection
        self._active_loaders.append(loader)
        
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
    # Action handlers
    
    def _execute_command(self, args: list, success_message: str, refresh_after: bool = True):
        """Execute a CLI command using CommandService.
        
        Args:
            args: Command arguments
            success_message: Message to show on success
            refresh_after: Whether to refresh data after successful execution (default: True)
        """
        # Clear log before execution
        self.window.clear_logs()
        
        # Execute via command service with standardized lifecycle
        self.command_service.execute(
            args=args,
            on_log=self.window.append_log,
            on_execution_status=self.window.set_execution_status,
            on_success=self.refresh_all_async if refresh_after else None,  # Conditional refresh
            success_message=success_message
        )
    
    def _on_cancel(self):
        """Handle cancel button click."""
        logger.info("Cancel button clicked - stopping current command")
        self.command_service.stop_current()
        self.window.append_log("\n⚠ Command cancelled by user")
    
    def _on_pull(self):
        """Handle pull all playlists."""
        self._execute_command(['pull'], "✓ Pull completed")
    
    def _on_scan(self):
        """Handle library scan."""
        self._execute_command(['scan'], "✓ Scan completed")
    
    def _on_match(self):
        """Handle match all tracks."""
        self._execute_command(['match'], "✓ Match completed")
    
    def _on_export(self):
        """Handle export all playlists."""
        self._execute_command(['export'], "✓ Export completed")
    
    def _on_report(self):
        """Handle generate reports."""
        self._execute_command(['report'], "✓ Reports generated")
    
    def _on_analyze(self):
        """Handle analyze library quality (read-only - no refresh needed)."""
        self._execute_command(['analyze'], "✓ Library quality analysis completed", refresh_after=False)
    
    def _on_diagnose(self, track_id: str):
        """Handle diagnose specific track (read-only - no refresh needed).
        
        Args:
            track_id: ID of the track to diagnose
        """
        self._execute_command(['diagnose', track_id], f"✓ Diagnosis completed for track {track_id}", refresh_after=False)
    
    def _on_open_reports(self):
        """Handle opening reports index page in web browser."""
        import webbrowser
        from pathlib import Path
        from psm.config import load_config
        
        try:
            config = load_config()
            reports_dir = Path(config['reports']['directory']).resolve()  # Convert to absolute path
            index_file = reports_dir / 'index.html'
            
            if not reports_dir.exists():
                logger.warning(f"Reports directory does not exist: {reports_dir}")
                self.window.append_log(
                    f"⚠ Reports directory not found: {reports_dir}\n"
                    "Generate reports first."
                )
                return
            
            if not index_file.exists():
                logger.warning(f"Reports index not found: {index_file}")
                self.window.append_log(
                    f"⚠ Reports index.html not found\n"
                    "Generate reports first with: psm report"
                )
                return
            
            # Open index.html in default web browser
            webbrowser.open(index_file.as_uri())
            logger.info(f"Opened reports index in browser: {index_file}")
            self.window.append_log(f"✓ Opened reports in browser")
                
        except Exception as e:
            logger.exception("Failed to open reports")
            self.window.append_log(f"✗ Error opening reports: {e}")
    
    def _on_build(self):
        """Handle build (scan + match + export)."""
        self._execute_command(['build'], "✓ Build completed")
    
    def _on_pull_one(self):
        """Handle pull single playlist."""
        playlist_id = self.window.get_selected_playlist_id()
        if playlist_id:
            self._execute_command(
                ['playlist', 'pull', playlist_id], 
                f"✓ Pulled playlist {playlist_id}"
            )
    
    def _on_match_one(self):
        """Handle match single playlist."""
        playlist_id = self.window.get_selected_playlist_id()
        if playlist_id:
            self._execute_command(
                ['playlist', 'match', playlist_id], 
                f"✓ Matched playlist {playlist_id}"
            )
    
    def _on_export_one(self):
        """Handle export single playlist."""
        playlist_id = self.window.get_selected_playlist_id()
        if playlist_id:
            self._execute_command(
                ['playlist', 'export', playlist_id], 
                f"✓ Exported playlist {playlist_id}"
            )
    
    def _on_watch_toggled(self, enabled: bool):
        """Handle watch mode toggle.
        
        Args:
            enabled: True if watch mode enabled
        """
        if enabled:
            logger.info("Starting watch mode...")
            self.window.clear_logs()
            self.window.set_execution_status(True, "Watch mode")
            self.window.enable_actions(False)
            self.window.set_watch_mode(True)  # Update button label immediately
            
            def on_log(line: str):
                self.window.append_log(line)
            
            def on_progress(current: int, total: int, message: str):
                # Ignore progress updates in watch mode - just keep showing "Running: Watch mode"
                pass
            
            def on_finished(exit_code: int):
                self.window.set_watch_mode(False)
                self.window.enable_actions(True)
                self.window.set_execution_status(False)  # Set to Ready
                self.window.append_log("\nWatch mode stopped")
                self.refresh_all_async()  # Async refresh after watch mode stops
            
            def on_error(error: str):
                self.window.set_watch_mode(False)
                self.window.enable_actions(True)
                self.window.set_execution_status(False)  # Set to Ready
                self.window.append_log(f"\nError: {error}")
            
            self.executor.execute(
                ['build', '--watch'],
                on_log=on_log,
                on_progress=on_progress,
                on_finished=on_finished,
                on_error=on_error,
            )
        else:
            logger.info("Stopping watch mode...")
            self.executor.stop_current()
