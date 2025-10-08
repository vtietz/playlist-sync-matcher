"""Controllers wiring UI events to actions and data updates."""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional
from PySide6.QtCore import QObject
import logging

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
        parent=None
    ):
        """Initialize controller.
        
        Args:
            window: Main window instance
            facade: Data facade instance
            executor: CLI executor instance
            parent: Parent QObject
        """
        super().__init__(parent)
        self.window = window
        self.facade = facade
        self.executor = executor
        
        # Connect UI signals to handlers
        self._connect_signals()
        
        # Initial data load
        self.refresh_all()
    
    def _connect_signals(self):
        """Connect UI signals to controller methods."""
        # Playlist selection
        self.window.on_playlist_selected.connect(self._on_playlist_selected)
        
        # Action buttons
        self.window.on_pull_clicked.connect(self._on_pull)
        self.window.on_scan_clicked.connect(self._on_scan)
        self.window.on_match_clicked.connect(self._on_match)
        self.window.on_export_clicked.connect(self._on_export)
        self.window.on_report_clicked.connect(self._on_report)
        self.window.on_build_clicked.connect(self._on_build)
        
        # Per-playlist actions
        self.window.on_pull_one_clicked.connect(self._on_pull_one)
        self.window.on_match_one_clicked.connect(self._on_match_one)
        self.window.on_export_one_clicked.connect(self._on_export_one)
        
        # Watch mode
        self.window.on_watch_toggled.connect(self._on_watch_toggled)
        
        # Tab changes
        self.window.on_tab_changed.connect(self._on_tab_changed)
    
    def refresh_all(self):
        """Refresh all data in the UI."""
        logger.info("Refreshing all data...")
        
        # Update playlists
        playlists = self.facade.list_playlists()
        self.window.update_playlists(playlists)
        
        # Update counts in status bar
        counts = self.facade.get_counts()
        self.window.update_status_counts(counts)
        
        # Refresh currently visible tab
        self._refresh_current_tab()
    
    def _refresh_current_tab(self):
        """Refresh data for the currently visible tab."""
        current_tab = self.window.get_current_tab()
        
        if current_tab == 'unmatched_tracks':
            self._refresh_unmatched_tracks()
        elif current_tab == 'matched_tracks':
            self._refresh_matched_tracks()
        elif current_tab == 'coverage':
            self._refresh_coverage()
        elif current_tab == 'unmatched_albums':
            self._refresh_unmatched_albums()
        elif current_tab == 'liked':
            self._refresh_liked_tracks()
    
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
        
        # Load playlist detail
        detail = self.facade.get_playlist_detail(playlist_id)
        self.window.update_playlist_detail(detail)
        
        # Enable per-playlist actions
        self.window.enable_playlist_actions(True)
    
    def _on_tab_changed(self, tab_name: str):
        """Handle tab change.
        
        Args:
            tab_name: New tab name
        """
        logger.info(f"Tab changed to: {tab_name}")
        self._refresh_current_tab()
    
    # Action handlers
    
    def _execute_command(self, args: list, success_message: str):
        """Execute a CLI command with standard callbacks.
        
        Args:
            args: Command arguments
            success_message: Message to show on success
        """
        self.window.clear_logs()
        self.window.set_progress(0, 100, "Starting...")
        self.window.enable_actions(False)
        
        def on_log(line: str):
            self.window.append_log(line)
        
        def on_progress(current: int, total: int, message: str):
            self.window.set_progress(current, total, message)
        
        def on_finished(exit_code: int):
            self.window.enable_actions(True)
            if exit_code == 0:
                self.window.append_log(f"\n{success_message}")
                self.window.set_progress(100, 100, "Complete")
                # Refresh data after successful operation
                self.refresh_all()
            else:
                self.window.append_log(f"\nCommand failed with exit code {exit_code}")
                self.window.set_progress(0, 100, "Failed")
        
        def on_error(error: str):
            self.window.enable_actions(True)
            self.window.append_log(f"\nError: {error}")
            self.window.set_progress(0, 100, "Error")
        
        self.executor.execute(
            args,
            on_log=on_log,
            on_progress=on_progress,
            on_finished=on_finished,
            on_error=on_error,
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
                self.refresh_all()
            
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
