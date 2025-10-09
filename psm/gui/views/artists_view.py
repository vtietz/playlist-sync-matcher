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
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableView, QHeaderView, QLineEdit, QHBoxLayout, QLabel
)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QModelIndex
from PySide6.QtGui import QFont
import logging

from ..components.link_delegate import LinkDelegate
from ..models import BaseTableModel

logger = logging.getLogger(__name__)


class ArtistsProxyModel(QSortFilterProxyModel):
    """Proxy model for filtering artists by search text."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_text = ""    # Search in artist name
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
        
        artist = (row_data.get('artist') or '').lower()
        
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
    """
    
    def __init__(
        self,
        source_model: BaseTableModel,
        parent: Optional[QWidget] = None
    ):
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
        
        layout.addWidget(self.table)
    
    def _set_initial_column_widths(self):
        """Set intelligent initial column widths."""
        # Column 0 = Artist (wide)
        # Column 1 = Tracks (narrow)
        # Column 2 = Albums (narrow)
        # Column 3 = Playlists (narrow)
        # Column 4 = Coverage (medium, stretches)
        self.table.setColumnWidth(0, 250)  # Artist
        self.table.setColumnWidth(1, 80)   # Tracks
        self.table.setColumnWidth(2, 80)   # Albums
        self.table.setColumnWidth(3, 80)   # Playlists
        # Column 4 (Coverage) stretches automatically
    
    def _on_search_changed(self, text: str):
        """Handle search text change."""
        self.proxy_model.set_search_text(text)
