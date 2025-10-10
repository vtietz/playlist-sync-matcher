"""BottomPanel - Encapsulates log display and status bar.

Extracts logging and status management from MainWindow to keep it focused.
Provides a clean API for appending logs, clearing logs, and updating status.
"""

from __future__ import annotations
from typing import Dict
from PySide6.QtWidgets import QWidget, QVBoxLayout
import re

from ..components import LogPanel, StatusBar


class BottomPanel(QWidget):
    """Bottom panel with log output and status bar.
    
    Combines LogPanel (for command output) and StatusBar (for statistics
    and execution status) into a single cohesive panel.
    """
    
    # ANSI escape code pattern (compiled once for performance)
    _ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    
    def __init__(self, status_bar_widget, parent=None):
        """Initialize the bottom panel.
        
        Args:
            status_bar_widget: QStatusBar widget from MainWindow (required for StatusBar component)
            parent: Parent widget (typically MainWindow)
        """
        super().__init__(parent)
        
        self._build_ui(status_bar_widget)
    
    def _build_ui(self, status_bar_widget):
        """Build the panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # Remove margins for seamless integration
        
        # Log panel - scrollable text area for command output
        self._log_panel = LogPanel(title="Log", max_height=200, font_size=9)
        layout.addWidget(self._log_panel)
        
        # Status bar - statistics and execution status
        self._status_bar = StatusBar(status_bar_widget)
    
    def append_log(self, message: str):
        """Append message to log with ANSI color code stripping.
        
        ANSI escape codes are automatically removed for better readability
        in the GUI environment.
        
        Args:
            message: Log message (may contain ANSI escape codes from CLI commands)
        """
        # Strip ANSI escape codes
        clean_message = self._ANSI_ESCAPE.sub('', message)
        self._log_panel.append(clean_message)
    
    def clear_logs(self):
        """Clear all log messages."""
        self._log_panel.clear()
    
    def set_execution_status(self, running: bool, message: str = ""):
        """Set execution status indicator.
        
        Args:
            running: True if command is executing, False if idle
            message: Optional status message (displayed when running)
        """
        self._status_bar.set_execution_status(running, message)
    
    def update_stats(self, counts: Dict[str, int]):
        """Update status bar statistics.
        
        Args:
            counts: Dict with entity counts:
                - playlists: Number of playlists
                - tracks: Number of tracks  
                - library_files: Number of library files scanned
                - matches: Number of matched tracks
        """
        self._status_bar.update_stats(counts)
    
    def connect_cancel(self, callback):
        """Connect callback to cancel button clicked signal.
        
        Delegates to the internal StatusBar component.
        
        Args:
            callback: Callable to invoke when cancel button is clicked
        """
        self._status_bar.connect_cancel(callback)
