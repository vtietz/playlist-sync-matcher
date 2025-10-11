"""Controller for CLI command execution and action handlers."""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional
from PySide6.QtCore import QObject
import logging
import webbrowser
from pathlib import Path

from ..services import CommandService

if TYPE_CHECKING:
    from ..main_window import MainWindow
    from ..runner import CliExecutor
    from .db_auto_refresh_controller import DbAutoRefreshController
    from .data_refresh_controller import DataRefreshController

logger = logging.getLogger(__name__)


class CommandController(QObject):
    """Manages CLI command execution and UI action handlers.
    
    Responsibilities:
    - Execute CLI commands with standardized lifecycle
    - Coordinate with CommandService for process management
    - Update database monitor during command execution
    - Trigger appropriate refresh after commands
    - Handle all action button clicks (pull, scan, match, export, etc.)
    """
    
    def __init__(
        self,
        window: MainWindow,
        executor: CliExecutor,
        db_monitor: Optional[DbAutoRefreshController] = None,
        data_refresh: Optional[DataRefreshController] = None,
        parent: Optional[QObject] = None
    ):
        """Initialize controller.
        
        Args:
            window: Main window instance
            executor: CLI executor instance
            db_monitor: Database monitor controller
            data_refresh: Data refresh controller
            parent: Parent QObject
        """
        super().__init__(parent)
        self.window = window
        self.executor = executor
        self._db_monitor = db_monitor
        self._data_refresh = data_refresh
        
        # Initialize command service for standardized execution
        self.command_service = CommandService(
            executor=executor,
            enable_actions=window.enable_actions,
            watch_mode_controller=None  # Will be set later via set_watch_mode_controller()
        )
        
        # Connect action buttons
        self._connect_signals()
    
    def set_watch_mode_controller(self, watch_mode_controller):
        """Set watch mode controller for detecting watch state.
        
        Args:
            watch_mode_controller: WatchModeController instance
        """
        self.command_service.watch_mode_controller = watch_mode_controller
    
    def _connect_signals(self):
        """Connect action button signals."""
        # Action buttons
        self.window.on_pull_clicked.connect(self._on_pull)
        self.window.on_scan_clicked.connect(self._on_scan)
        self.window.on_match_clicked.connect(self._on_match)
        self.window.on_export_clicked.connect(self._on_export)
        self.window.on_report_clicked.connect(self._on_report)
        self.window.on_open_reports_clicked.connect(self._on_open_reports)
        self.window.on_refresh_clicked.connect(self._on_refresh)
        self.window.on_build_clicked.connect(self._on_build)
        self.window.on_analyze_clicked.connect(self._on_analyze)
        self.window.on_diagnose_clicked.connect(self._on_diagnose)
        
        # Per-playlist actions
        self.window.on_pull_one_clicked.connect(self._on_pull_one)
        self.window.on_match_one_clicked.connect(self._on_match_one)
        self.window.on_export_one_clicked.connect(self._on_export_one)
        
        # Per-track actions
        self.window.on_match_track_clicked.connect(self._on_match_track)
        
        # Cancel command
        self.window.on_cancel_clicked.connect(self._on_cancel)
    
    def _execute_command(self, args: list, success_message: str, refresh_after: bool = True, fast_refresh: bool = False):
        """Execute a CLI command using CommandService.
        
        Args:
            args: Command arguments
            success_message: Message to show on success
            refresh_after: Whether to refresh data after successful execution (default: True)
            fast_refresh: Use fast tracks-only refresh instead of full refresh (default: False)
        """
        # Clear log before execution
        self.window.clear_logs()
        
        # Set command running state in database monitor
        if self._db_monitor:
            self._db_monitor.set_command_running(True)
        
        # Choose refresh method
        if refresh_after and self._data_refresh:
            refresh_callback = self._data_refresh.refresh_tracks_only_async if fast_refresh else self._data_refresh.refresh_all_async
        else:
            refresh_callback = None
        
        # Wrap enable_actions to also clear command state
        original_enable_actions = self.command_service.enable_actions
        
        def wrapped_enable_actions(enabled: bool):
            # Call original callback
            original_enable_actions(enabled)
            
            # Clear command running state when re-enabling actions (command completed)
            if enabled and self._db_monitor:
                self._db_monitor.set_command_running(False)
        
        # Temporarily replace enable_actions callback
        self.command_service.enable_actions = wrapped_enable_actions
        
        # Wrap success callback to clear suppression flag after command completes
        def on_success():
            # Clear suppression flag (in case it was set for read-only ops)
            if self._db_monitor:
                self._db_monitor.set_suppression(False)
            
            # Call the actual refresh callback if needed
            if refresh_callback:
                refresh_callback()
        
        try:
            # Execute via command service with standardized lifecycle
            self.command_service.execute(
                args=args,
                on_log=self.window.append_log,
                on_execution_status=self.window.set_execution_status,
                on_success=on_success,  # Use wrapper that clears suppression flag
                success_message=success_message
            )
        finally:
            # Restore original callback
            self.command_service.enable_actions = original_enable_actions
    
    def _on_cancel(self):
        """Handle cancel button click."""
        logger.info("Cancel button clicked - stopping current command")
        self.command_service.stop_current()
        self.window.append_log("\n⚠ Command cancelled by user")
    
    def _on_pull(self):
        """Handle pull all playlists.
        
        Pull updates playlist structure (adds/removes playlists, changes track lists),
        so requires full refresh to reload playlists + tracks + counts.
        """
        self._execute_command(['pull'], "✓ Pull completed")  # Full refresh
    
    def _on_scan(self):
        """Handle library scan.
        
        Scan updates track metadata and may add new tracks. Uses fast refresh
        since playlists themselves don't change (tracks-only update is sufficient).
        """
        self._execute_command(['scan'], "✓ Scan completed", fast_refresh=True)
    
    def _on_match(self):
        """Handle match all tracks.
        
        Match only updates match scores/methods, so uses fast tracks-only refresh.
        """
        self._execute_command(['match'], "✓ Match completed", fast_refresh=True)
    
    def _on_export(self):
        """Handle export all playlists.
        
        Export writes M3U files but doesn't change the database,
        so no refresh is needed.
        """
        self._execute_command(['export'], "✓ Export completed", refresh_after=False)
    
    def _on_report(self):
        """Handle generate reports.
        
        Report generates HTML files but doesn't change the database,
        so no refresh is needed.
        """
        self._execute_command(['report'], "✓ Reports generated", refresh_after=False)
    
    def _on_analyze(self):
        """Handle analyze library quality (read-only - no refresh needed).
        
        Suppresses auto-refresh polling during execution since analyze
        only reads data and should not trigger UI updates. Uses both
        suppression flag and ignore window for defense-in-depth.
        """
        # Set ignore window to cover the operation plus brief aftermath
        if self._db_monitor:
            self._db_monitor.set_ignore_window(2.5)
            self._db_monitor.set_suppression(True)
        self._execute_command(['analyze'], "✓ Library quality analysis completed", refresh_after=False)
    
    def _on_diagnose(self, track_id: str):
        """Handle diagnose specific track (read-only - no refresh needed).
        
        Suppresses auto-refresh polling during execution since diagnose
        only reads data and should not trigger UI updates. Uses both
        suppression flag and ignore window for defense-in-depth.
        
        Args:
            track_id: ID of the track to diagnose
        """
        # Set ignore window to cover the operation plus brief aftermath
        if self._db_monitor:
            self._db_monitor.set_ignore_window(2.5)
            self._db_monitor.set_suppression(True)
        self._execute_command(['diagnose', track_id], f"✓ Diagnosis completed for track {track_id}", refresh_after=False)
    
    def _on_open_reports(self):
        """Handle opening reports index page in web browser."""
        try:
            from psm.config import load_config
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
    
    def _on_refresh(self):
        """Handle manual refresh button - reload all data from database.
        
        This is useful when the user has run CLI commands externally
        and wants to see the updated data in the GUI.
        """
        logger.info("Manual refresh requested")
        self.window.append_log("🔄 Refreshing data from database...")
        if self._data_refresh:
            self._data_refresh.refresh_all_async()
    
    def _on_build(self):
        """Handle build (scan + match + export)."""
        self._execute_command(['build'], "✓ Build completed")
    
    def _on_pull_one(self):
        """Handle pull single playlist."""
        playlist_id = self.window.get_selected_playlist_id()
        logger.debug(f"Pull one clicked - selected playlist ID: {playlist_id}")
        if playlist_id:
            logger.info(f"Executing: playlist pull {playlist_id}")
            # Use fast tracks-only refresh after single playlist operations
            self._execute_command(
                ['playlist', 'pull', playlist_id], 
                f"✓ Pulled playlist {playlist_id}",
                fast_refresh=True
            )
        else:
            logger.warning("Pull one clicked but no playlist selected")
            self.window.append_log("⚠ No playlist selected")
    
    def _on_match_one(self):
        """Handle match single playlist."""
        playlist_id = self.window.get_selected_playlist_id()
        logger.debug(f"Match one clicked - selected playlist ID: {playlist_id}")
        if playlist_id:
            logger.info(f"Executing: playlist match {playlist_id}")
            # Use fast tracks-only refresh after single playlist operations
            self._execute_command(
                ['playlist', 'match', playlist_id], 
                f"✓ Matched playlist {playlist_id}",
                fast_refresh=True
            )
        else:
            logger.warning("Match one clicked but no playlist selected")
            self.window.append_log("⚠ No playlist selected")
    
    def _on_export_one(self):
        """Handle export single playlist."""
        playlist_id = self.window.get_selected_playlist_id()
        logger.debug(f"Export one clicked - selected playlist ID: {playlist_id}")
        if playlist_id:
            logger.info(f"Executing: playlist export {playlist_id}")
            # Export doesn't change DB data, so no refresh needed
            self._execute_command(
                ['playlist', 'export', playlist_id], 
                f"✓ Exported playlist {playlist_id}",
                refresh_after=False  # Don't refresh for export
            )
        else:
            logger.warning("Export one clicked but no playlist selected")
            self.window.append_log("⚠ No playlist selected")
    
    def _on_match_track(self, track_id: str):
        """Handle match single track.
        
        Args:
            track_id: ID of track to match
        """
        logger.debug(f"Match track clicked - track ID: {track_id}")
        if track_id:
            logger.info(f"Matching single track: {track_id}")
            # Use async task to match this specific track
            self._match_specific_track_async(track_id)
        else:
            logger.warning("Match track clicked but no track ID provided")
            self.window.append_log("⚠ No track selected")
    
    def _match_specific_track_async(self, track_id: str):
        """Match a specific track asynchronously.
        
        Args:
            track_id: ID of track to match
        """
        from PySide6.QtCore import QTimer
        from ...services.match_service import match_changed_tracks
        from ...config import load_config
        from ...cli.helpers import get_db
        
        # Clear log and show progress
        self.window.append_log(f"Matching track {track_id}...")
        
        # Disable actions during matching
        self.command_service.enable_actions(False)
        
        def do_match():
            """Perform the matching operation in background."""
            try:
                # Load config and database
                cfg = load_config()
                
                with get_db(cfg) as db:
                    # Match just this one track
                    matched_count = match_changed_tracks(db, cfg, track_ids=[track_id])
                    
                    # Show result
                    if matched_count > 0:
                        self.window.append_log(f"✓ Matched track successfully")
                        logger.info(f"Matched 1 track")
                    else:
                        self.window.append_log(f"⚠ No match found for track")
                        logger.warning(f"No match found for track {track_id}")
                
            except Exception as e:
                logger.error(f"Error matching track: {e}", exc_info=True)
                self.window.append_log(f"✗ Error matching track: {e}")
            finally:
                # Re-enable actions
                self.command_service.enable_actions(True)
                
                # Fast refresh to update UI
                if self._data_refresh:
                    QTimer.singleShot(100, self._data_refresh.refresh_tracks_only_async)
        
        # Execute in thread pool
        self.command_service.executor.submit(do_match)
