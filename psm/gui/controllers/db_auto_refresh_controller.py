"""Database auto-refresh controller.

Thin adapter around DatabaseChangeDetector providing clean state management
for loader count, command execution, watch mode, suppression, and ignore windows.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Callable, Optional
from pathlib import Path
import logging

from ..database_monitor import DatabaseChangeDetector

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class DbAutoRefreshController:
    """Controller for database change detection and auto-refresh coordination.
    
    Wraps DatabaseChangeDetector and coordinates with other controllers to:
    - Gate polling during data loading (loader count)
    - Gate polling during command execution (except watch mode)
    - Apply ignore windows for read-only operations
    - Trigger refresh callbacks when external changes detected
    """
    
    def __init__(
        self,
        db_path: Path,
        get_write_epoch: Callable[[], str],
        on_change_detected: Callable[[], None]
    ):
        """Initialize auto-refresh controller.
        
        Args:
            db_path: Path to database file
            get_write_epoch: Callback to get current write epoch from DB
            on_change_detected: Callback to invoke when external change detected
        """
        self.detector = DatabaseChangeDetector(
            db_path=db_path,
            get_write_epoch=get_write_epoch,
            on_change_detected=on_change_detected,
            check_interval=2000,  # 2 seconds
            debounce_seconds=1.5
        )
    
    # State management methods (delegate to detector)
    
    def set_loader_count(self, count: int):
        """Update active loader count (gates polling when > 0)."""
        self.detector.set_loader_count(count)
    
    def set_command_running(self, running: bool):
        """Update command execution state (gates polling unless watch mode)."""
        self.detector.set_command_running(running)
    
    def set_watch_mode(self, active: bool):
        """Set watch mode state (allows polling during long-running watch command)."""
        self.detector.set_watch_mode(active)
    
    def set_suppression(self, suppressed: bool):
        """Enable or disable suppression flag (manual control)."""
        self.detector.set_suppression(suppressed)
    
    def set_ignore_window(self, duration_seconds: float):
        """Set ignore window for read-only operations (e.g., 2.5s for filtering)."""
        self.detector.set_ignore_window(duration_seconds)
    
    def update_tracking(self):
        """Update tracked write epoch and mtime after a refresh."""
        self.detector.update_tracking()
    
    def stop(self):
        """Stop the detector and clean up resources."""
        if self.detector:
            self.detector.stop()
