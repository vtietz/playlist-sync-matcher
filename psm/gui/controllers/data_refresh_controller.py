"""Controller for async data loading and refresh operations."""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional, List, Dict, Any, Callable
from PySide6.QtCore import QObject, QTimer
import logging

from ..services import TrackStreamingService
from ..utils.async_loader import MultiAsyncLoader

if TYPE_CHECKING:
    from ..main_window import MainWindow
    from ..data_facade import DataFacade
    from .db_auto_refresh_controller import DbAutoRefreshController

logger = logging.getLogger(__name__)


class DataRefreshController(QObject):
    """Manages async data loading and refresh operations.
    
    Responsibilities:
    - Async loading of playlists, tracks, albums, artists
    - Loader lifecycle management (cancellation, completion)
    - Streaming vs direct load decision
    - Filter state preservation across refreshes
    - Integration with DbAutoRefreshController for loader counting
    """
    
    def __init__(
        self,
        window: MainWindow,
        facade: DataFacade,
        facade_factory: Callable[[], DataFacade],
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
        
        # Track active loaders
        self._active_loaders: List[MultiAsyncLoader] = []
        self._filter_options_loaded = False
        
        # Track active streaming service (prevent garbage collection)
        self._active_streaming_service = None
        
        # Set up lazy playlist loading callback
        self.window.unified_tracks_view.set_playlist_fetch_callback(
            self._fetch_playlists_for_tracks
        )
    
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
            # Update database monitor with loader count
            if self._db_monitor:
                self._db_monitor.set_loader_count(0)
        
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
    
    def refresh_tracks_only_async(self):
        """Fast refresh path for track changes only (e.g., from external matching).
        
        This method only reloads tracks and counts, skipping playlists/albums/artists.
        Much faster than refresh_all_async() when metadata hasn't changed.
        """
        logger.info("Fast refresh: tracks only (async)...")
        
        # Cancel any running loaders first
        if self._active_loaders:
            logger.info("Cancelling previous loader...")
            for loader in self._active_loaders:
                loader.stop()
                loader.wait()
            self._active_loaders.clear()
            # Update database monitor with loader count
            if self._db_monitor:
                self._db_monitor.set_loader_count(0)
        
        # Define minimal loading functions
        load_funcs = {
            'tracks': lambda: self.facade_factory().list_all_tracks_unified_fast(),
            'counts': lambda: self.facade_factory().get_counts(),
        }
        
        # Create async loader
        loader = MultiAsyncLoader(load_funcs)
        loader.all_finished.connect(self._on_tracks_only_loaded)
        loader.error.connect(self._on_data_load_error)
        
        # Track loader to prevent garbage collection
        self._active_loaders.append(loader)
        
        # Update database monitor with loader count
        if self._db_monitor:
            self._db_monitor.set_loader_count(len(self._active_loaders))
        
        # Start loading
        loader.start()
    
    def _on_item_loaded(self, key: str, data):
        """Handle individual item loaded.
        
        Args:
            key: Data key (e.g., 'playlists', 'tracks')
            data: Loaded data
        """
        logger.debug(f"Loaded {key}: {len(data) if hasattr(data, '__len__') else 'N/A'} items")
    
    def _on_data_loaded(self, results: dict):
        """Handle all data loaded successfully.
        
        Args:
            results: Dict with all loaded data
        """
        logger.info("All data loaded successfully")
        
        # Save current filter state before updating data (will be restored after)
        saved_filter_state = self.window.filter_store.state
        saved_playlist_id = self.window.get_selected_playlist_id()
        logger.debug(f"Saved filter state before reload: {saved_filter_state.active_dimension}, playlist_id: {saved_playlist_id}")
        
        # Temporarily clear filter to prevent applying it to empty/partial data during reload
        self.window.filter_store.clear()
        
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
            is_streaming = False  # Track if we're using streaming mode
            if 'tracks' in results:
                # Use streaming for large datasets to avoid UI freeze
                track_count = len(results['tracks'])
                is_streaming = track_count > 5000
                
                if is_streaming:
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
            # NOTE: Don't clear if streaming - let streaming service handle it via on_complete callback
            if not is_streaming:
                self.window.set_execution_status(False)
                self.window.unified_tracks_view.hide_loading()
            self.window.append_log("Data loaded successfully")
            
            # Reapply active playlist filter if a playlist was selected before the reload
            # This ensures the filter uses fresh track_ids after DB changes (e.g., "Pull Selected", "Match Selected")
            logger.debug(f"After data load, saved_playlist_id: {saved_playlist_id}")
            if saved_playlist_id:
                # Fetch current playlist data to get name
                playlist = self.facade.get_playlist_by_id(saved_playlist_id)
                logger.debug(f"Fetched playlist data: {playlist.name if playlist else 'None'}")
                if playlist:
                    # Recompute filter with fresh track_ids from DB
                    logger.info(f"Reapplying playlist filter for '{playlist.name}' after data refresh")
                    # Import here to avoid circular dependency
                    from . import SelectionSyncController
                    # Access via parent controller if available
                    if hasattr(self, '_selection_sync'):
                        self._selection_sync.set_playlist_filter(playlist.name)
                else:
                    # Playlist was deleted - clear filter and selection
                    logger.warning(f"Playlist {saved_playlist_id} no longer exists - clearing selection")
                    self.window.unified_tracks_view.clear_filters()
                    self.window._selected_playlist_id = None
            elif saved_filter_state.active_dimension:
                # Restore non-playlist filter (artist/album) if it was active
                logger.info(f"Restoring {saved_filter_state.active_dimension} filter after data refresh")
                # Filter will be automatically restored by filter bar state
            else:
                logger.debug("No filter to reapply after data load")
            
            # Trigger lazy playlist loading for visible rows
            QTimer.singleShot(100, self.window.unified_tracks_view.trigger_lazy_playlist_load)
            
            # Update database change tracking after refresh
            if self._db_monitor:
                self._db_monitor.update_tracking()
            
        except Exception as e:
            logger.error(f"Error updating UI with loaded data: {e}", exc_info=True)
            self.window.append_log(f"Error updating UI: {e}")
            self.window.unified_tracks_view.hide_loading()
        
        finally:
            # Clean up loader reference
            if self._active_loaders:
                self._active_loaders.pop(0)
                # Update database monitor with new loader count
                if self._db_monitor:
                    self._db_monitor.set_loader_count(len(self._active_loaders))
    
    def _on_tracks_only_loaded(self, results: dict):
        """Handle tracks-only data loaded successfully (fast refresh).
        
        This is called after refresh_tracks_only_async() completes.
        Only updates tracks and counts without reloading playlists/albums/artists.
        
        Args:
            results: Dict with 'tracks' and 'counts' keys
        """
        logger.info("Tracks-only data loaded successfully")
        
        try:
            # Update tracks
            if 'tracks' in results:
                track_count = len(results['tracks'])
                logger.info(f"Updating {track_count} tracks")
                
                # Use streaming for very large datasets
                if track_count > 5000:
                    logger.info(f"Using streaming mode for {track_count} tracks")
                    # Get current playlists from window state (no need to reload)
                    playlists = self.window.playlists_model.data_rows
                    self._load_tracks_streaming(results['tracks'], playlists)
                else:
                    logger.info(f"Using direct load for {track_count} tracks")
                    # Get current playlists from window state
                    playlists = self.window.playlists_model.data_rows
                    self.window.update_unified_tracks(results['tracks'], playlists)
            
            # Update counts
            if 'counts' in results:
                self.window.update_status_counts(results['counts'])
            
            self.window.append_log("Tracks refreshed")
            
            # Update database change tracking after refresh
            if self._db_monitor:
                self._db_monitor.update_tracking()
            
        except Exception as e:
            logger.error(f"Error updating tracks: {e}", exc_info=True)
            self.window.append_log(f"Error updating tracks: {e}")
        
        finally:
            # Clean up loader reference
            if self._active_loaders:
                self._active_loaders.pop(0)
                # Update database monitor with new loader count
                if self._db_monitor:
                    self._db_monitor.set_loader_count(len(self._active_loaders))
    
    def _load_tracks_streaming(self, tracks: List[Dict[str, Any]], playlists: List[Dict[str, Any]]):
        """Load tracks using streaming API to avoid UI freeze on large datasets.
        
        Delegates to TrackStreamingService for chunk scheduling and progress updates.
        
        Args:
            tracks: List of all track dicts
            playlists: List of playlists (not used - kept for backward compatibility)
        """
        # Get pending sort if available (restored from window state)
        pending_sort = None
        if hasattr(self.window, '_pending_tracks_sort') and self.window._pending_tracks_sort is not None:
            pending_sort = self.window._pending_tracks_sort
            self.window._pending_tracks_sort = None  # Clear after capturing
        
        # Create streaming service instance and store reference to prevent garbage collection
        self._active_streaming_service = TrackStreamingService(
            view=self.window.unified_tracks_view,
            model=self.window.unified_tracks_model,
            on_progress=lambda current, total, msg: self.window.set_execution_status(True, msg),
            on_complete=self._on_streaming_complete
        )
        
        # Start streaming with current filter state
        self._active_streaming_service.start_streaming(
            tracks=tracks,
            filter_state=self.window.filter_store.state,
            pending_sort=pending_sort
        )
    
    def _on_streaming_complete(self):
        """Handle streaming completion - clear status and hide loading overlay."""
        self.window.set_execution_status(False)
        self.window.unified_tracks_view.hide_loading()
        # Clear reference to streaming service
        self._active_streaming_service = None
    
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
            # Update database monitor with new loader count
            if self._db_monitor:
                self._db_monitor.set_loader_count(len(self._active_loaders))
        
        # Update unified tracks view
        self._refresh_unified_tracks()
        
        # Update counts in status bar
        counts = self.facade.get_counts()
        self.window.update_status_counts(counts)
    
    def _refresh_unified_tracks(self):
        """Refresh unified tracks view (sync fallback)."""
        logger.info("Refreshing unified tracks...")
        tracks = self.facade.list_all_tracks_unified()
        playlists = self.facade.list_playlists()
        
        # Update view with data
        self.window.update_unified_tracks(tracks, playlists)
    
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
    
    def set_selection_sync_controller(self, selection_sync):
        """Set reference to SelectionSyncController for filter reapplication.
        
        Args:
            selection_sync: SelectionSyncController instance
        """
        self._selection_sync = selection_sync
