"""Albums view with filtering and search capabilities.

This view displays aggregated album statistics with:
- Album and artist names
- Track count per album
- Playlist count (how many playlists contain tracks from this album)
- Coverage percentage (matched vs total tracks)
- Filter by artist
- Search across artist and album names
"""
from __future__ import annotations
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableView, QHeaderView, QLineEdit, QHBoxLayout, QLabel, QComboBox
)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QModelIndex
from PySide6.QtGui import QFont
import logging

from ..components.link_delegate import LinkDelegate
from ..models import BaseTableModel

logger = logging.getLogger(__name__)


class AlbumsProxyModel(QSortFilterProxyModel):
    """Proxy model for filtering albums by artist and search text."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._artist_filter = ""  # Filter by artist name
        self._search_text = ""    # Search in artist + album names
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.setDynamicSortFilter(True)
    
    def set_artist_filter(self, artist: str):
        """Filter albums by artist name."""
        self.beginFilterChange()
        self._artist_filter = artist.strip()
        self.invalidateFilter()
        self.endFilterChange()
    
    def set_search_text(self, text: str):
        """Filter albums by search text (searches artist + album)."""
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
        album = (row_data.get('album') or '').lower()
        
        # Apply artist filter
        if self._artist_filter:
            if self._artist_filter.lower() not in artist:
                return False
        
        # Apply search filter (searches both artist and album)
        if self._search_text:
            search_lower = self._search_text.lower()
            if search_lower not in artist and search_lower not in album:
                return False
        
        return True


class AlbumsView(QWidget):
    """View for browsing albums with filtering and search.
    
    This view displays aggregated album data with:
    - Album name
    - Artist name
    - Track count (total tracks in this album)
    - Playlist count (number of playlists containing tracks from this album)
    - Coverage (percentage of matched tracks)
    
    Filters:
    - Artist dropdown (filter by artist)
    - Search box (searches artist + album name)
    """
    
    def __init__(
        self,
        source_model: BaseTableModel,
        parent: Optional[QWidget] = None
    ):
        """Initialize albums view.
        
        Args:
            source_model: AlbumsModel instance
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Create proxy model for filtering
        self.proxy_model = AlbumsProxyModel()
        self.proxy_model.setSourceModel(source_model)
        
        # Build UI
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Filter bar
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)
        
        # Artist filter
        filter_layout.addWidget(QLabel("Artist:"))
        self.artist_combo = QComboBox()
        self.artist_combo.setEditable(False)
        self.artist_combo.setMinimumWidth(150)
        self.artist_combo.addItem("All Artists", "")
        self.artist_combo.currentIndexChanged.connect(self._on_artist_filter_changed)
        filter_layout.addWidget(self.artist_combo)
        
        # Search box
        filter_layout.addWidget(QLabel("Search:"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search artist or album...")
        self.search_box.textChanged.connect(self._on_search_changed)
        filter_layout.addWidget(self.search_box, stretch=1)
        
        layout.addLayout(filter_layout)
        
        # Table view
        self.table = QTableView()
        self.table.setObjectName("albumsTable")
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
        # Columns: Album, Artist, Tracks, Playlists, Coverage
        self._set_initial_column_widths()
        
        # Enable mouse tracking for hover effects
        self.table.setMouseTracking(True)
        
        layout.addWidget(self.table)
    
    def _set_initial_column_widths(self):
        """Set intelligent initial column widths."""
        # Column 0 = Album (wide)
        # Column 1 = Artist (medium)
        # Column 2 = Tracks (narrow)
        # Column 3 = Playlists (narrow)
        # Column 4 = Coverage (medium, stretches)
        self.table.setColumnWidth(0, 250)  # Album
        self.table.setColumnWidth(1, 200)  # Artist
        self.table.setColumnWidth(2, 80)   # Tracks
        self.table.setColumnWidth(3, 80)   # Playlists
        # Column 4 (Coverage) stretches automatically
    
    def _on_artist_filter_changed(self, index: int):
        """Handle artist filter selection change."""
        artist = self.artist_combo.itemData(index)
        self.proxy_model.set_artist_filter(artist or "")
    
    def _on_search_changed(self, text: str):
        """Handle search text change."""
        self.proxy_model.set_search_text(text)
    
    def populate_filter_options(self):
        """Populate artist filter dropdown from visible data."""
        # Get unique artists from source model
        source_model = self.proxy_model.sourceModel()
        if not source_model:
            return
        
        artists = set()
        for row in range(source_model.rowCount()):
            row_data = source_model.get_row_data(row)
            if row_data:
                artist = row_data.get('artist')
                if artist:
                    artists.add(artist)
        
        # Save current selection
        current_artist = self.artist_combo.currentData()
        
        # Rebuild dropdown
        self.artist_combo.clear()
        self.artist_combo.addItem("All Artists", "")
        
        for artist in sorted(artists):
            self.artist_combo.addItem(artist, artist)
        
        # Restore selection if it still exists
        if current_artist:
            index = self.artist_combo.findData(current_artist)
            if index >= 0:
                self.artist_combo.setCurrentIndex(index)
