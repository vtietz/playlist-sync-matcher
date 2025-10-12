"""Controller for watch mode lifecycle and event handling."""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional
from PySide6.QtCore import QObject, QTimer
import logging

if TYPE_CHECKING:
    from ..main_window import MainWindow
    from ..runner import CliExecutor
    from .db_auto_refresh_controller import DbAutoRefreshController
    from .data_refresh_controller import DataRefreshController

logger = logging.getLogger(__name__)


class WatchModeController(QObject):
    """Manages watch mode lifecycle and event-driven refreshes.

    Responsibilities:
    - Start/stop watch mode execution
    - Parse watch mode output for completion markers
    - Trigger event-driven refreshes on rebuild completion
    - Coordinate with database monitor during watch mode
    - Update UI state (button labels, action enable/disable)
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

        # Track watch mode state
        self._watch_mode_active = False

        # Connect signal
        self.window.on_watch_toggled.connect(self._on_watch_toggled)

    def _on_watch_toggled(self, enabled: bool):
        """Handle watch mode toggle.

        Args:
            enabled: True if watch mode enabled
        """
        if enabled:
            logger.info("Starting watch mode...")
            self._watch_mode_active = True  # Allow auto-refresh during watch mode
            if self._db_monitor:
                self._db_monitor.set_watch_mode(True)
                self._db_monitor.set_command_running(True)  # Watch is a long-running command

            self.window.clear_logs()
            self.window.set_execution_status(True, "⌚ Watch mode active")  # Show watch indicator in status
            self.window.enable_actions(False)
            self.window.set_watch_mode(True)  # Update button label immediately

            def on_log(line: str):
                """Handle log output from watch mode.

                Detects completion markers and triggers fast refresh to show updates.
                """
                self.window.append_log(line)

                # Event-driven refresh: detect watch mode completion markers
                # This ensures GUI updates even if mtime polling misses brief WAL changes
                completion_markers = [
                    'Incremental rebuild',  # Watch mode rebuild completed
                    'Database sync',         # DB sync operation
                    '✓ Match completed',     # Match operation finished
                    '✓ Build completed',     # Build step finished
                    'changes detected',      # File change detected (debounced trigger)
                ]

                if any(marker in line for marker in completion_markers):
                    # Schedule fast refresh after short delay to let DB writes finish
                    logger.debug(f"Watch completion marker detected: {line.strip()}")
                    if self._data_refresh:
                        QTimer.singleShot(250, self._data_refresh.refresh_tracks_only_async)

            def on_progress(current: int, total: int, message: str):
                # Ignore progress updates in watch mode - just keep showing "Running: Watch mode"
                pass

            def on_finished(exit_code: int):
                self._watch_mode_active = False  # Disable watch mode flag
                if self._db_monitor:
                    self._db_monitor.set_watch_mode(False)
                    self._db_monitor.set_command_running(False)  # Watch command completed
                self.window.set_watch_mode(False)
                self.window.enable_actions(True)
                self.window.set_execution_status(False)  # Set to Ready
                self.window.append_log("\nWatch mode stopped")
                if self._data_refresh:
                    self._data_refresh.refresh_all_async()  # Async refresh after watch mode stops

            def on_error(error: str):
                self._watch_mode_active = False  # Disable watch mode flag
                if self._db_monitor:
                    self._db_monitor.set_watch_mode(False)
                    self._db_monitor.set_command_running(False)  # Watch command failed
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
            self._watch_mode_active = False  # Disable watch mode flag
            if self._db_monitor:
                self._db_monitor.set_watch_mode(False)
                self._db_monitor.set_command_running(False)  # Watch command stopped
            self.executor.stop_current()

    @property
    def is_active(self) -> bool:
        """Check if watch mode is currently active.

        Returns:
            True if watch mode is running
        """
        return self._watch_mode_active
