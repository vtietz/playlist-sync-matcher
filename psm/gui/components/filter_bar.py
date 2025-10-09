"""Filter bar component for unified tracks view.

This component provides filtering controls for:
- Track status (All/Matched/Unmatched)
- Owner, Artist, Album, Year filters
- Text search across all fields
"""
from __future__ import annotations
from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QComboBox, QLineEdit
)
from PySide6.QtCore import Signal, Qt
import logging

logger = logging.getLogger(__name__)


class FilterBar(QWidget):
    """Filter bar widget with comprehensive filtering options.
    
    This component emits signals when filter criteria change, allowing
    parent views to apply filtering to their data models.
    
    Features:
    - Track status filter (All/Matched/Unmatched)
    - Owner, Artist, Album, Year dropdown filters
    - Text search across all fields
    
    Note: Playlist filtering is handled by the playlist selection list,
    not by this filter bar.
    
    Signals:
        filter_changed: Emitted when any filter changes (no parameters)
        
    Example:
        filter_bar = FilterBar()
        filter_bar.filter_changed.connect(lambda: apply_filters())
        filter_bar.populate_filter_options(owners, artists, albums, years)
    """
    
    # Signal emitted when any filter changes
    filter_changed = Signal()
    # Signal emitted when user is about to interact with filter dropdowns (load data on demand)
    filter_options_needed = Signal()
    
    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize filter bar.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Create filter widgets - Row 1: Status and metadata filters
        self.track_status_combo = QComboBox()
        self.track_status_combo.addItems(["All Tracks", "Matched", "Unmatched"])
        self.track_status_combo.currentIndexChanged.connect(self._on_filter_changed)
        
        self.artist_combo = QComboBox()
        self.artist_combo.addItem("All Artists")
        self.artist_combo.currentIndexChanged.connect(self._on_filter_changed)
        # Load filter options when user clicks the dropdown
        original_artist_showPopup = self.artist_combo.showPopup
        def artist_showPopup():
            self.filter_options_needed.emit()
            original_artist_showPopup()
        self.artist_combo.showPopup = artist_showPopup
        
        self.album_combo = QComboBox()
        self.album_combo.addItem("All Albums")
        self.album_combo.currentIndexChanged.connect(self._on_filter_changed)
        # Load filter options when user clicks the dropdown
        original_album_showPopup = self.album_combo.showPopup
        def album_showPopup():
            self.filter_options_needed.emit()
            original_album_showPopup()
        self.album_combo.showPopup = album_showPopup
        
        self.year_combo = QComboBox()
        self.year_combo.addItem("All Years")
        self.year_combo.currentIndexChanged.connect(self._on_filter_changed)
        # Load filter options when user clicks the dropdown
        original_year_showPopup = self.year_combo.showPopup
        def year_showPopup():
            self.filter_options_needed.emit()
            original_year_showPopup()
        self.year_combo.showPopup = year_showPopup
        
        # Row 2: Search field
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search tracks, albums, artists...")
        self.search_field.setClearButtonEnabled(True)
        self.search_field.textChanged.connect(self._on_filter_changed)
        
        # Layout - Two rows
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(5)
        
        # First row: Status and metadata filters
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(10)
        
        row1_layout.addWidget(QLabel("Status:"))
        row1_layout.addWidget(self.track_status_combo)
        
        row1_layout.addWidget(QLabel("Artist:"))
        row1_layout.addWidget(self.artist_combo)
        
        row1_layout.addWidget(QLabel("Album:"))
        row1_layout.addWidget(self.album_combo)
        
        row1_layout.addWidget(QLabel("Year:"))
        row1_layout.addWidget(self.year_combo)
        
        row1_layout.addStretch()
        
        # Second row: Search field
        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(10)
        
        row2_layout.addWidget(QLabel("Search:"))
        row2_layout.addWidget(self.search_field, stretch=1)
        
        main_layout.addLayout(row1_layout)
        main_layout.addLayout(row2_layout)
    
    def _on_filter_changed(self):
        """Internal handler for filter changes."""
        self.filter_changed.emit()
    
    def get_track_filter(self) -> str:
        """Get selected track status filter.
        
        Returns:
            "all", "matched", or "unmatched"
        """
        text = self.track_status_combo.currentText()
        if text == "Matched":
            return "matched"
        elif text == "Unmatched":
            return "unmatched"
        return "all"
    
    def get_search_text(self) -> str:
        """Get search text.
        
        Returns:
            Search text (may be empty)
        """
        return self.search_field.text().strip()
    
    def get_artist_filter(self) -> Optional[str]:
        """Get selected artist filter.
        
        Returns:
            Artist name or None if "All Artists" selected
        """
        text = self.artist_combo.currentText()
        return None if text == "All Artists" else text
    
    def get_album_filter(self) -> Optional[str]:
        """Get selected album filter.
        
        Returns:
            Album name or None if "All Albums" selected
        """
        text = self.album_combo.currentText()
        return None if text == "All Albums" else text
    
    def get_year_filter(self) -> Optional[int]:
        """Get selected year filter.
        
        Returns:
            Year as integer or None if "All Years" selected
        """
        text = self.year_combo.currentText()
        if text == "All Years":
            return None
        try:
            return int(text)
        except (ValueError, TypeError):
            return None
    
    def populate_filter_options(
        self,
        artists: List[str],
        albums: List[str],
        years: List[int]
    ):
        """Populate filter dropdown options from data.
        
        Args:
            artists: List of unique artist names
            albums: List of unique album names
            years: List of unique years
        """
        # Store current selections
        current_artist = self.artist_combo.currentText()
        current_album = self.album_combo.currentText()
        current_year = self.year_combo.currentText()
        
        # Clear and repopulate
        self.artist_combo.clear()
        self.artist_combo.addItem("All Artists")
        self.artist_combo.addItems(sorted(artists))
        
        self.album_combo.clear()
        self.album_combo.addItem("All Albums")
        self.album_combo.addItems(sorted(albums))
        
        self.year_combo.clear()
        self.year_combo.addItem("All Years")
        # Sort years descending (newest first)
        self.year_combo.addItems([str(y) for y in sorted(years, reverse=True)])
        
        # Restore selections if they still exist
        artist_idx = self.artist_combo.findText(current_artist)
        if artist_idx >= 0:
            self.artist_combo.setCurrentIndex(artist_idx)
        
        album_idx = self.album_combo.findText(current_album)
        if album_idx >= 0:
            self.album_combo.setCurrentIndex(album_idx)
        
        year_idx = self.year_combo.findText(current_year)
        if year_idx >= 0:
            self.year_combo.setCurrentIndex(year_idx)
    
    def clear_filters(self):
        """Reset all filters to default state."""
        self.track_status_combo.setCurrentIndex(0)
        self.artist_combo.setCurrentIndex(0)
        self.album_combo.setCurrentIndex(0)
        self.year_combo.setCurrentIndex(0)
        self.search_field.clear()
