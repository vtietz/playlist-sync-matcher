"""Main orchestrator coordinating all GUI controllers."""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional
from PySide6.QtCore import QObject, QTimer
from pathlib import Path
import logging

from .db_auto_refresh_controller import DbAutoRefreshController
from .data_refresh_controller import DataRefreshController
from .selection_sync_controller import SelectionSyncController
from .command_controller import CommandController
from .watch_mode_controller import WatchModeController
from ..services.action_state_manager import ActionStateManager

if TYPE_CHECKING:
    from ..main_window import MainWindow
    from ..data_facade import DataFacade
    from ..runner import CliExecutor

logger = logging.getLogger(__name__)


class MainOrchestrator(QObject):
    """Main orchestrator coordinating all GUI controllers.

    This class replaces the monolithic MainController by delegating to
    specialized controllers, each with a single responsibility:

    - DbAutoRefreshController: Database change detection and loader gating
    - DataRefreshController: Async data loading and refresh operations
    - SelectionSyncController: Left panel selection <-> FilterStore sync
    - CommandController: CLI command execution and action handlers
    - WatchModeController: Watch mode lifecycle and event-driven refreshes

    The orchestrator's job is minimal: initialize controllers, wire them together,
    and expose a compatibility API for MainWindow.
    """

    def __init__(
        self,
        window: MainWindow,
        facade: DataFacade,
        executor: CliExecutor,
        facade_factory=None,
        parent: Optional[QObject] = None
    ):
        """Initialize orchestrator and all controllers.

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
        self.facade_factory = facade_factory or (lambda: facade)

        # Set up database monitor
        self._db_monitor = self._setup_db_monitor()

        # Create action state manager for button colorization
        self.action_state_manager = ActionStateManager(
            on_state_change=self._on_action_state_change
        )

        # Initialize controllers
        self.data_refresh = DataRefreshController(
            window=window,
            facade=facade,
            facade_factory=self.facade_factory,
            db_monitor=self._db_monitor,
            parent=self
        )

        self.selection_sync = SelectionSyncController(
            window=window,
            facade=facade,
            facade_factory=self.facade_factory,
            db_monitor=self._db_monitor,
            parent=self
        )

        self.command = CommandController(
            window=window,
            executor=executor,
            db_monitor=self._db_monitor,
            data_refresh=self.data_refresh,
            parent=self
        )

        # Pass action state manager to command controller
        self.command.command_service.action_state_manager = self.action_state_manager

        self.watch_mode = WatchModeController(
            window=window,
            executor=executor,
            db_monitor=self._db_monitor,
            data_refresh=self.data_refresh,
            parent=self
        )

        # Wire cross-controller dependencies
        self.data_refresh.set_selection_sync_controller(self.selection_sync)

        # Wire watch mode controller to command controller for better messaging
        self.command.set_watch_mode_controller(self.watch_mode)

        # Initial data load - use async to avoid blocking UI
        QTimer.singleShot(0, self.data_refresh.refresh_all_async)

    def _setup_db_monitor(self) -> Optional[DbAutoRefreshController]:
        """Set up automatic database change detection.

        Returns:
            DbAutoRefreshController instance, or None if setup failed
        """
        try:
            # Get DB path from active connection
            from psm.db import DatabaseInterface
            db_obj: DatabaseInterface = self.facade.db

            # Try to get path from db object (implementation-specific attributes)
            if hasattr(db_obj, '_db_path'):
                db_path = Path(db_obj._db_path).resolve()  # type: ignore
            elif hasattr(db_obj, 'path'):
                db_path = Path(db_obj.path).resolve()  # type: ignore
            else:
                # Fallback to config
                from psm.config import load_config
                config = load_config()
                db_path = Path(config['database']['path']).resolve()

            # Create controller - it will create DatabaseChangeDetector internally
            monitor = DbAutoRefreshController(
                db_path=db_path,
                get_write_epoch=lambda: self.facade.db.get_meta('last_write_epoch') or '0',
                on_change_detected=self._on_external_db_change
            )

            return monitor

        except Exception as e:
            logger.warning(f"Could not set up database monitor: {e}")
            return None

    def _on_external_db_change(self):
        """Callback when external database change is detected."""
        watch_status = " [watch mode]" if self.watch_mode.is_active else ""

        # Try to get write source for better logging
        try:
            write_source = self.facade.db.get_meta('last_write_source') or 'unknown'
            self.window.append_log(f"🔄 Database changed externally ({write_source}), auto-refreshing...{watch_status}")
        except Exception:
            self.window.append_log(f"🔄 Database changed externally, auto-refreshing...{watch_status}")

        # Trigger fast refresh
        self.data_refresh.refresh_tracks_only_async()

    # Compatibility methods for MainWindow and existing code

    def refresh_all_async(self):
        """Refresh all data asynchronously (compatibility method)."""
        self.data_refresh.refresh_all_async()

    def refresh_tracks_only_async(self):
        """Fast refresh tracks only (compatibility method)."""
        self.data_refresh.refresh_tracks_only_async()

    def ensure_filter_options_loaded(self):
        """Ensure filter options are loaded (compatibility method)."""
        self.data_refresh.ensure_filter_options_loaded()

    def set_playlist_filter(self, playlist_name: Optional[str]):
        """Set playlist filter (compatibility method)."""
        self.selection_sync.set_playlist_filter(playlist_name)

    def set_playlist_filter_async(self, playlist_name: Optional[str]):
        """Set playlist filter async (compatibility method)."""
        self.selection_sync.set_playlist_filter_async(playlist_name)

    def _on_action_state_change(self, action_name: str, state: str):
        """Handle action state changes from ActionStateManager.

        This callback is triggered when an action's state changes (running, success, error, idle).
        It updates button colors in the toolbar and handles Build sub-step highlighting.

        Args:
            action_name: Action name ('pull', 'scan', etc.) or 'build:step' for sub-steps
                        or 'playlist:action' for per-playlist actions
            state: New state ('idle', 'running', 'success', 'error')
        """
        # Handle Build sub-step highlighting
        if action_name.startswith('build:'):
            sub_step = action_name.split(':', 1)[1]
            if sub_step == 'clear':
                # Clear all sub-step highlighting
                self.window.toolbar.highlightBuildStep(None)
            else:
                # Highlight specific sub-step
                self.window.toolbar.highlightBuildStep(sub_step)
        # Handle per-playlist actions (left panel buttons)
        elif action_name.startswith('playlist:'):
            playlist_action = action_name.split(':', 1)[1]  # e.g., 'pull', 'match', 'export'
            self._set_playlist_button_state(playlist_action, state)
        # Handle per-track actions (tracks panel buttons)
        elif action_name.endswith(':track'):
            self._set_track_button_state(action_name, state)
        else:
            # Regular action state change - update toolbar button
            self.window.toolbar.setActionState(action_name, state)

    def _set_playlist_button_state(self, action: str, state: str):
        """Set state styling for per-playlist action buttons.

        Args:
            action: Playlist action ('pull', 'match', 'export')
            state: State ('idle', 'running', 'success', 'error')
        """
        # Get the playlists tab from left panel
        if not hasattr(self.window, 'left_panel') or not hasattr(self.window.left_panel, 'playlists_tab'):
            return

        playlists_tab = self.window.left_panel.playlists_tab

        # Map action to button
        button_map = {
            'pull': getattr(playlists_tab, 'btn_pull_one', None),
            'match': getattr(playlists_tab, 'btn_match_one', None),
            'export': getattr(playlists_tab, 'btn_export_one', None),
        }

        button = button_map.get(action)
        if not button:
            return

        # Apply state styling (reuse toolbar styling logic)
        if state == 'running':
            button.setStyleSheet(self._get_button_running_style())
        elif state == 'error':
            button.setStyleSheet(self._get_button_error_style())
        elif state == 'idle':
            button.setStyleSheet("")  # Clear custom styling (return to default blue)

    def _set_track_button_state(self, action_name: str, state: str):
        """Set state styling for per-track action buttons in tracks panel.

        Args:
            action_name: Action name like 'match:track', 'diagnose:track'
            state: State ('idle', 'running', 'error')
        """
        # Extract base action from 'match:track' → 'match'
        base_action = action_name.split(':')[0]

        # Get tracks panel from main window
        if not hasattr(self.window, 'tracks_panel'):
            return

        tracks_panel = self.window.tracks_panel

        # Map action to button
        button_map = {
            'match': getattr(tracks_panel, 'btn_match_one', None),
            'diagnose': getattr(tracks_panel, 'btn_diagnose', None),
        }

        button = button_map.get(base_action)
        if not button:
            return

        # Apply state styling (reuse same styles as playlist buttons)
        if state == 'running':
            button.setStyleSheet(self._get_button_running_style())
        elif state == 'error':
            button.setStyleSheet(self._get_button_error_style())
        elif state == 'idle':
            button.setStyleSheet("")  # Clear custom styling (return to default blue)

    def _get_button_running_style(self) -> str:
        """Get running (orange) button style."""
        return """
            QPushButton {
                background-color: #ff8c00;
                color: white;
                font-weight: bold;
            }
            QPushButton:disabled {
                background-color: #cc7000;
                color: #f0f0f0;
            }
        """

    def _get_button_error_style(self) -> str:
        """Get error (red) button style."""
        return """
            QPushButton {
                background-color: #d93025;
                color: white;
                font-weight: bold;
            }
            QPushButton:disabled {
                background-color: #a52519;
                color: #f0f0f0;
            }
        """
