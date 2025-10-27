"""Artists view with search capabilities.

This view displays aggregated artist statistics with:
- Artist name
- Track count (total tracks by this artist)
- Album count (distinct albums)
- Playlist count (how many playlists contain tracks from this artist)
- Coverage percentage (matched vs total tracks)
- Search across artist names
"""

from __future__ import annotations
from typing import Optional
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableView, QHeaderView, QLineEdit, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, QSortFilterProxyModel, QModelIndex, Signal
import logging

from ..components.link_delegate import LinkDelegate
from ..models import BaseTableModel

logger = logging.getLogger(__name__)


class ArtistsProxyModel(QSortFilterProxyModel):
    """Proxy model for filtering artists by search text."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_text = ""  # Search in artist name
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.setDynamicSortFilter(True)

    def set_search_text(self, text: str):
        """Filter artists by search text."""
        self.beginFilterChange()
        self._search_text = text.strip()
        self.invalidateFilter()
        self.endFilterChange()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        """Determine if row matches current filters."""
        model = self.sourceModel()
        if not model:
            return True

        # Get row data
        row_data = model.get_row_data(source_row)
        if not row_data:
            return False

        artist = (row_data.get("artist") or "").lower()

        # Apply search filter
        if self._search_text:
            search_lower = self._search_text.lower()
            if search_lower not in artist:
                return False

        return True


class ArtistsView(QWidget):
    """View for browsing artists with search.

    This view displays aggregated artist data with:
    - Artist name
    - Track count (total tracks by this artist)
    - Album count (distinct albums)
    - Playlist count (number of playlists containing tracks from this artist)
    - Coverage (percentage of matched tracks)

    Filters:
    - Search box (searches artist name)

    Signals:
        artist_selected: Emitted when an artist is selected or cleared (artist_name or None)
    """

    # Signal emitted when artist is selected (artist_name) or cleared (None)
    artist_selected = Signal(object)  # artist_name: Optional[str]

    def __init__(self, source_model: BaseTableModel, parent: Optional[QWidget] = None):
        """Initialize artists view.

        Args:
            source_model: ArtistsModel instance
            parent: Parent widget
        """
        super().__init__(parent)

        # Create proxy model for filtering
        self.proxy_model = ArtistsProxyModel()
        self.proxy_model.setSourceModel(source_model)

        # Build UI
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Filter bar
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)

        # Search box
        filter_layout.addWidget(QLabel("Search:"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search artist...")
        self.search_box.textChanged.connect(self._on_search_changed)
        filter_layout.addWidget(self.search_box, stretch=1)

        layout.addLayout(filter_layout)

        # Table view
        self.table = QTableView()
        self.table.setObjectName("artistsTable")
        self.table.setModel(self.proxy_model)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.setTextElideMode(Qt.ElideRight)
        self.table.setWordWrap(False)

        # Set compact row height to match other tables
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.verticalHeader().setMinimumSectionSize(22)

        # Configure column resizing
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)

        # Set initial column widths
        # Columns: Artist, Tracks, Albums, Playlists, Coverage
        self._set_initial_column_widths()

        # Enable mouse tracking for hover effects
        self.table.setMouseTracking(True)

        # Set up link delegate for clickable artist names
        link_delegate = LinkDelegate(provider="spotify", parent=self.table)
        self.table.setItemDelegateForColumn(0, link_delegate)  # Artist

        # Connect selection signal
        selection_model = self.table.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(self._on_selection_changed)

        layout.addWidget(self.table)

    def _set_initial_column_widths(self):
        """Set intelligent initial column widths."""
        # Column 0 = Artist (wide)
        # Column 1 = Tracks (narrow)
        # Column 2 = Albums (narrow)
        # Column 3 = Playlists (narrow)
        # Column 4 = Coverage (medium)
        # Column 5 = Relevance (narrow, stretches)
        self.table.setColumnWidth(0, 250)  # Artist
        self.table.setColumnWidth(1, 80)  # Tracks
        self.table.setColumnWidth(2, 80)  # Albums
        self.table.setColumnWidth(3, 80)  # Playlists
        self.table.setColumnWidth(4, 120)  # Coverage
        # Column 5 (Relevance) stretches automatically

    def _on_search_changed(self, text: str):
        """Handle search text change."""
        self.proxy_model.set_search_text(text)

    def _on_selection_changed(self, selected, deselected):
        """Handle artist selection change."""
        selection = self.table.selectionModel()
        if selection and selection.hasSelection():
            proxy_row = selection.selectedRows()[0].row()
            source_index = self.proxy_model.mapToSource(self.proxy_model.index(proxy_row, 0))
            source_row = source_index.row()

            # Get artist from source model
            source_model = self.proxy_model.sourceModel()
            if hasattr(source_model, "get_row_data"):
                row_data = source_model.get_row_data(source_row)
                if row_data:
                    artist_name = row_data.get("artist")
                    if artist_name:
                        self.artist_selected.emit(artist_name)

    def _on_clear_clicked(self):
        """Handle clear filter button click."""
        # Clear selection
        self.table.clearSelection()
        # Clear search
        self.search_box.clear()
        # Emit clear signal
        self.artist_selected.emit(None)

    def clear_selection(self):
        """Public method to clear selection and filters (for coordinator)."""
        self._on_clear_clicked()

    def select_artist(self, artist_name: str):
        """Select artist by name in the table (for coordinator).

        Args:
            artist_name: Artist name to select
        """
        # Search through proxy model for matching artist
        proxy = self.proxy_model
        for row in range(proxy.rowCount()):
            index = proxy.index(row, 0)  # Artist column
            if index.data() == artist_name:
                # Select this row
                self.table.selectRow(row)
                self.table.scrollTo(index)
                return

        # Artist not found - clear selection
        self.table.clearSelection()
