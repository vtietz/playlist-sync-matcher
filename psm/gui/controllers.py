"""Controllers wiring UI events to actions and data updates."""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional, List, Dict
from PySide6.QtCore import QObject, QTimer
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
        
        # Initial data load - use async to avoid blocking UI
        QTimer.singleShot(0, self.refresh_all_async)
    
    def _connect_signals(self):
        """Connect UI signals to controller methods."""
        # Playlist selection
        self.window.on_playlist_selected.connect(self._on_playlist_selected)
        self.window.on_playlist_filter_requested.connect(self.set_playlist_filter)
        
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
        
        # Show loading state - indeterminate progress
        self.window.set_progress(0, 0, "Loading data...")
        self.window.unified_tracks_view.show_loading()
        
        # Define loading functions using facade_factory for thread safety
        # Each lambda creates a new facade with its own DB connection
        load_funcs = {
            'playlists': lambda: self.facade_factory().list_playlists(),
            'tracks': lambda: self.facade_factory().list_all_tracks_unified_fast(),  # Fast path!
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
        
        # Update progress based on key
        progress_map = {
            'playlists': 15,
            'tracks': 45,
            'artists': 65,
            'albums': 80,
            'years': 90,
            'counts': 100,
        }
        if key in progress_map:
            self.window.set_progress(progress_map[key], 100, f"Loading {key}...")
    
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
            
            # Update tracks
            if 'tracks' in results:
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
            
            # Update counts
            if 'counts' in results:
                self.window.update_status_counts(results['counts'])
            
            # Clear progress and hide loading overlay
            self.window.set_progress(0, 100, "Ready")
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
        self.window.set_progress(0, 100, "Error loading data")
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
    
    def _on_playlist_selected(self, playlist_id: str):
        """Handle playlist selection.
        
        Args:
            playlist_id: Selected playlist ID
        """
        logger.info(f"Playlist selected: {playlist_id}")
        
        # Enable per-playlist actions
        self.window.enable_playlist_actions(True)
    
    def set_playlist_filter(self, playlist_name: Optional[str]):
        """Set playlist filter on unified tracks view.
        
        Fetches track IDs for the playlist and passes them to the view for efficient filtering.
        
        Args:
            playlist_name: Playlist name to filter by, or None to clear filter
        """
        if playlist_name:
            # Fetch track IDs for this playlist
            track_ids = self.facade.get_track_ids_for_playlist(playlist_name)
            self.window.unified_tracks_view.set_playlist_filter(playlist_name, track_ids)
        else:
            self.window.unified_tracks_view.set_playlist_filter(None, None)
    
    # Action handlers
    
    def _execute_command(self, args: list, success_message: str, refresh_after: bool = True):
        """Execute a CLI command using CommandService.
        
        Args:
            args: Command arguments
            success_message: Message to show on success
            refresh_after: Whether to refresh data after successful execution (default: True)
        """
        # Clear log and reset progress before execution
        self.window.clear_logs()
        self.window.set_progress(0, 100, "Starting...")
        
        # Execute via command service with standardized lifecycle
        self.command_service.execute(
            args=args,
            on_log=self.window.append_log,
            on_progress=self.window.set_progress,
            on_success=self.refresh_all_async if refresh_after else None,  # Conditional refresh
            success_message=success_message
        )
    
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
        """Handle open reports directory in OS file browser."""
        import subprocess
        from pathlib import Path
        from psm.config import load_config
        
        try:
            config = load_config()
            reports_dir = Path(config['reports']['directory'])
            
            if not reports_dir.exists():
                logger.warning(f"Reports directory does not exist: {reports_dir}")
                self.window.append_log(
                    f"⚠ Reports directory not found: {reports_dir}\n"
                    "Generate reports first."
                )
                return
            
            # Open in OS file browser
            if reports_dir.is_dir():
                # Windows
                subprocess.run(['explorer', str(reports_dir)])
                logger.info(f"Opened reports directory: {reports_dir}")
                self.window.append_log(f"✓ Opened {reports_dir}")
            else:
                logger.error(f"Reports path is not a directory: {reports_dir}")
                self.window.append_log(f"✗ Not a directory: {reports_dir}")
                
        except Exception as e:
            logger.exception("Failed to open reports directory")
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
            self.window.set_progress(0, 0, "Watching...")
            self.window.enable_actions(False)
            self.window.set_watch_mode(True)  # Update button label immediately
            
            def on_log(line: str):
                self.window.append_log(line)
            
            def on_progress(current: int, total: int, message: str):
                self.window.set_progress(current, total, message)
            
            def on_finished(exit_code: int):
                self.window.set_watch_mode(False)
                self.window.enable_actions(True)
                self.window.append_log("\nWatch mode stopped")
                self.refresh_all_async()  # Async refresh after watch mode stops
            
            def on_error(error: str):
                self.window.set_watch_mode(False)
                self.window.enable_actions(True)
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
