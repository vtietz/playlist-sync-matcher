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
