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
    QWidget, QVBoxLayout, QTableView, QHeaderView, QLineEdit, QHBoxLayout, QLabel, QComboBox, QPushButton
)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QModelIndex, Signal
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
    
    Signals:
        album_selected: Emitted when an album is selected or cleared (album_name, artist_name or None, None)
    """
    
    # Signal emitted when album is selected (album_name, artist_name) or cleared (None, None)
    album_selected = Signal(object, object)  # (album_name: Optional[str], artist_name: Optional[str])
    
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
        
        # Filter bar - Artist filter on first line
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
        filter_layout.addStretch(1)  # Push to left
        
        layout.addLayout(filter_layout)
        
        # Search bar on second line
        search_layout = QHBoxLayout()
        search_layout.setSpacing(10)
        
        # Search box
        search_layout.addWidget(QLabel("Search:"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search artist or album...")
        self.search_box.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.search_box, stretch=1)
        
        layout.addLayout(search_layout)
        
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
        
        # Connect selection signal
        selection_model = self.table.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(self._on_selection_changed)
        
        layout.addWidget(self.table)
    
    def _set_initial_column_widths(self):
        """Set intelligent initial column widths."""
        # Column 0 = Album (wide)
        # Column 1 = Artist (medium)
        # Column 2 = Tracks (narrow)
        # Column 3 = Playlists (narrow)
        # Column 4 = Coverage (medium)
        # Column 5 = Relevance (narrow, stretches)
        self.table.setColumnWidth(0, 250)  # Album
        self.table.setColumnWidth(1, 200)  # Artist
        self.table.setColumnWidth(2, 80)   # Tracks
        self.table.setColumnWidth(3, 80)   # Playlists
        self.table.setColumnWidth(4, 120)  # Coverage
        # Column 5 (Relevance) stretches automatically
    
    def _on_artist_filter_changed(self, index: int):
        """Handle artist filter selection change."""
        artist = self.artist_combo.itemData(index)
        self.proxy_model.set_artist_filter(artist or "")
    
    def _on_search_changed(self, text: str):
        """Handle search text change."""
        self.proxy_model.set_search_text(text)
    
    def _on_selection_changed(self, selected, deselected):
        """Handle album selection change."""
        selection = self.table.selectionModel()
        if selection and selection.hasSelection():
            proxy_row = selection.selectedRows()[0].row()
            source_index = self.proxy_model.mapToSource(
                self.proxy_model.index(proxy_row, 0)
            )
            source_row = source_index.row()
            
            # Get album and artist from source model
            source_model = self.proxy_model.sourceModel()
            if hasattr(source_model, 'get_row_data'):
                row_data = source_model.get_row_data(source_row)
                if row_data:
                    album_name = row_data.get('album')
                    artist_name = row_data.get('artist')
                    if album_name and artist_name:
                        self.album_selected.emit(album_name, artist_name)
    
    def _on_clear_clicked(self):
        """Handle clear filter button click."""
        # Clear selection
        self.table.clearSelection()
        # Clear filters
        self.artist_combo.setCurrentIndex(0)
        self.search_box.clear()
        # Emit clear signal
        self.album_selected.emit(None, None)
    
    def clear_selection(self):
        """Public method to clear selection and filters (for coordinator)."""
        self._on_clear_clicked()
    
    def select_album(self, album_name: str, artist_name: str):
        """Select album by name and artist in the table (for coordinator).
        
        Args:
            album_name: Album name to select
            artist_name: Artist name to match
        """
        # Search through proxy model for matching album+artist
        proxy = self.proxy_model
        for row in range(proxy.rowCount()):
            album_index = proxy.index(row, 0)  # Album column
            artist_index = proxy.index(row, 1)  # Artist column
            
            if album_index.data() == album_name and artist_index.data() == artist_name:
                # Select this row
                self.table.selectRow(row)
                self.table.scrollTo(album_index)
                return
        
        # Album not found - clear selection
        self.table.clearSelection()
    
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
