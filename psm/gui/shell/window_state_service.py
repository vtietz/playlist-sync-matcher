"""Service for persisting and restoring window state (geometry, splitters, column widths)."""

from __future__ import annotations
from typing import TYPE_CHECKING
from PySide6.QtCore import QSettings
import logging

if TYPE_CHECKING:
    from PySide6.QtWidgets import QMainWindow, QHeaderView

logger = logging.getLogger(__name__)


class WindowStateService:
    """Handles saving and restoring window geometry, splitters, and column widths.

    Centralizes window state persistence to keep MainWindow focused on composition.
    Uses QSettings for cross-platform storage.

    Example:
        service = WindowStateService()
        service.restore(main_window)  # On startup
        service.save(main_window)      # On close
    """

    def __init__(self, organization: str = "VT", application: str = "SpotifyM3USync"):
        """Initialize window state service.

        Args:
            organization: Organization name for QSettings
            application: Application name for QSettings
        """
        self.settings = QSettings(organization, application)
        logger.debug(f"WindowStateService initialized: {organization}/{application}")

    def save(self, window: QMainWindow) -> None:
        """Save window geometry, splitter positions, and column widths.

        Args:
            window: MainWindow instance with attributes:
                - main_splitter (QSplitter)
                - playlists_table_view (QTableView)
                - unified_tracks_view.tracks_table (QTableView)
        """
        # Save window geometry and state
        self.settings.setValue("geometry", window.saveGeometry())
        self.settings.setValue("windowState", window.saveState())

        # Save main splitter position
        if hasattr(window, "main_splitter"):
            self.settings.setValue("mainSplitter", window.main_splitter.saveState())

        # Save playlists table column widths
        if hasattr(window, "playlists_table_view"):
            self._save_column_widths(window.playlists_table_view.horizontalHeader(), "playlistsColumnWidths")

        # Save unified tracks table column widths
        if hasattr(window, "unified_tracks_view"):
            self._save_column_widths(window.unified_tracks_view.tracks_table.horizontalHeader(), "tracksColumnWidths")

        logger.info("Window state saved")

    def restore(self, window: QMainWindow) -> None:
        """Restore window geometry, splitter positions, and column widths.

        Args:
            window: MainWindow instance (same attributes as save())
        """
        # Restore window geometry and state
        geometry = self.settings.value("geometry")
        if geometry:
            window.restoreGeometry(geometry)

        window_state = self.settings.value("windowState")
        if window_state:
            window.restoreState(window_state)

        # Restore main splitter position
        if hasattr(window, "main_splitter"):
            splitter_state = self.settings.value("mainSplitter")
            if splitter_state:
                window.main_splitter.restoreState(splitter_state)

        # Restore playlists table column widths
        if hasattr(window, "playlists_table_view"):
            self._restore_column_widths(window.playlists_table_view.horizontalHeader(), "playlistsColumnWidths")

        # Restore unified tracks table column widths
        if hasattr(window, "unified_tracks_view"):
            self._restore_column_widths(
                window.unified_tracks_view.tracks_table.horizontalHeader(), "tracksColumnWidths"
            )

        logger.info("Window state restored")

    def _save_column_widths(self, header: QHeaderView, settings_key: str) -> None:
        """Save column widths for a table header.

        Args:
            header: QHeaderView instance
            settings_key: Settings key to store widths under
        """
        widths = []
        for col in range(header.count()):
            widths.append(header.sectionSize(col))
        self.settings.setValue(settings_key, widths)
        logger.debug(f"Saved {len(widths)} column widths to {settings_key}")

    def _restore_column_widths(self, header: QHeaderView, settings_key: str) -> None:
        """Restore column widths for a table header.

        Args:
            header: QHeaderView instance
            settings_key: Settings key to load widths from
        """
        widths = self.settings.value(settings_key)
        if widths:
            for col, width in enumerate(widths):
                if col < header.count():
                    # Convert to int (QSettings may return strings)
                    header.resizeSection(col, int(width))
            logger.debug(f"Restored {len(widths)} column widths from {settings_key}")
