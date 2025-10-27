"""Window state persistence manager using QSettings.

This module handles all window state persistence including:
- Window geometry and state
- Splitter positions
- Table column widths
- Table sort states
"""

from __future__ import annotations
from typing import Optional, Tuple, TYPE_CHECKING
from PySide6.QtCore import QSettings, Qt
import logging

if TYPE_CHECKING:
    from PySide6.QtWidgets import QMainWindow, QSplitter, QHeaderView

logger = logging.getLogger(__name__)


class WindowStateManager:
    """Manages window state persistence using QSettings.

    This class encapsulates all QSettings operations for saving and
    restoring window state, including geometry, splitter positions,
    table column widths, and sort states.

    Example:
        manager = WindowStateManager("vtietz", "PlaylistSyncMatcher")
        manager.save_window_geometry(main_window)
        manager.restore_window_geometry(main_window)
    """

    def __init__(self, organization: str, application: str):
        """Initialize state manager.

        Args:
            organization: Organization name for QSettings
            application: Application name for QSettings
        """
        self.settings = QSettings(organization, application)

    def save_window_geometry(self, window: QMainWindow):
        """Save window geometry and state.

        Args:
            window: Main window to save state from
        """
        self.settings.setValue("geometry", window.saveGeometry())
        self.settings.setValue("windowState", window.saveState())

    def restore_window_geometry(self, window: QMainWindow):
        """Restore window geometry and state.

        Args:
            window: Main window to restore state to
        """
        geometry = self.settings.value("geometry")
        if geometry:
            window.restoreGeometry(geometry)

        window_state = self.settings.value("windowState")
        if window_state:
            window.restoreState(window_state)

    def save_splitter_state(self, splitter: QSplitter, key: str = "mainSplitter"):
        """Save splitter position.

        Args:
            splitter: Splitter widget to save state from
            key: Settings key name (default: "mainSplitter")
        """
        self.settings.setValue(key, splitter.saveState())

    def restore_splitter_state(self, splitter: QSplitter, key: str = "mainSplitter"):
        """Restore splitter position.

        Args:
            splitter: Splitter widget to restore state to
            key: Settings key name (default: "mainSplitter")
        """
        splitter_state = self.settings.value(key)
        if splitter_state:
            splitter.restoreState(splitter_state)

    def save_table_state(self, header: QHeaderView, prefix: str):
        """Save table column widths and sort state.

        Args:
            header: Table header to save state from
            prefix: Prefix for settings keys (e.g., "playlists", "tracks")
        """
        # Save column widths
        widths = []
        for col in range(header.count()):
            widths.append(header.sectionSize(col))
        self.settings.setValue(f"{prefix}ColumnWidths", widths)

        # Save sort state
        self.settings.setValue(f"{prefix}SortColumn", header.sortIndicatorSection())
        self.settings.setValue(f"{prefix}SortOrder", header.sortIndicatorOrder().value)

    def restore_table_column_widths(self, header: QHeaderView, prefix: str):
        """Restore table column widths only.

        Args:
            header: Table header to restore widths to
            prefix: Prefix for settings keys (e.g., "playlists", "tracks")
        """
        widths = self.settings.value(f"{prefix}ColumnWidths")
        if widths:
            for col, width in enumerate(widths):
                if col < header.count():
                    # Convert to int (QSettings may return strings)
                    header.resizeSection(col, int(width))

    def get_pending_table_sort(self, prefix: str) -> Optional[Tuple[int, Qt.SortOrder]]:
        """Get saved sort state for later application.

        Sort state is returned as a tuple for application after data load.

        Args:
            prefix: Prefix for settings keys (e.g., "playlists", "tracks")

        Returns:
            Tuple of (column, order) if saved, None otherwise
        """
        sort_col = self.settings.value(f"{prefix}SortColumn")
        sort_order = self.settings.value(f"{prefix}SortOrder")

        if sort_col is not None and sort_order is not None:
            return (int(sort_col), Qt.SortOrder(int(sort_order)))

        return None

    def save_all_window_state(
        self, window: QMainWindow, main_splitter: QSplitter, table_headers: dict[str, QHeaderView]
    ):
        """Save all window state in one call.

        Args:
            window: Main window
            main_splitter: Main splitter widget
            table_headers: Dict mapping prefix -> header (e.g., {"playlists": header})
        """
        self.save_window_geometry(window)
        self.save_splitter_state(main_splitter)

        for prefix, header in table_headers.items():
            self.save_table_state(header, prefix)

        logger.info("Window state saved")

    def restore_all_window_state(
        self, window: QMainWindow, main_splitter: QSplitter, table_headers: dict[str, QHeaderView]
    ) -> dict[str, Optional[Tuple[int, Qt.SortOrder]]]:
        """Restore all window state in one call.

        Args:
            window: Main window
            main_splitter: Main splitter widget
            table_headers: Dict mapping prefix -> header (e.g., {"playlists": header})

        Returns:
            Dict mapping prefix -> pending sort state (for application after data load)
        """
        self.restore_window_geometry(window)
        self.restore_splitter_state(main_splitter)

        pending_sorts = {}
        for prefix, header in table_headers.items():
            self.restore_table_column_widths(header, prefix)
            pending_sort = self.get_pending_table_sort(prefix)
            if pending_sort:
                pending_sorts[prefix] = pending_sort

        logger.info("Window state restored")
        return pending_sorts
