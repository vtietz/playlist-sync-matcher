"""Filter bar component for unified tracks view.

This component provides filtering controls for:
- Track status (All/Matched/Unmatched)
- Owner, Artist, Album, Year filters
- Text search across all fields
"""
from __future__ import annotations
from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QComboBox
)
from PySide6.QtCore import Signal, QSignalBlocker
import logging

from .debounced_search_field import DebouncedSearchField
from .searchable_combobox import SearchableComboBox

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

        # Searchable comboboxes with autocomplete
        self.playlist_combo = SearchableComboBox(all_text="All Playlists")
        self.playlist_combo.currentIndexChanged.connect(self._on_filter_changed)
        # Load filter options when user clicks the dropdown
        original_playlist_showPopup = self.playlist_combo.showPopup
        def playlist_showPopup():
            self.filter_options_needed.emit()
            original_playlist_showPopup()
        self.playlist_combo.showPopup = playlist_showPopup

        self.artist_combo = SearchableComboBox(all_text="All Artists")
        self.artist_combo.currentIndexChanged.connect(self._on_filter_changed)
        # Load filter options when user clicks the dropdown
        original_artist_showPopup = self.artist_combo.showPopup
        def artist_showPopup():
            self.filter_options_needed.emit()
            original_artist_showPopup()
        self.artist_combo.showPopup = artist_showPopup

        self.album_combo = SearchableComboBox(all_text="All Albums")
        self.album_combo.currentIndexChanged.connect(self._on_filter_changed)
        # Load filter options when user clicks the dropdown
        original_album_showPopup = self.album_combo.showPopup
        def album_showPopup():
            self.filter_options_needed.emit()
            original_album_showPopup()
        self.album_combo.showPopup = album_showPopup

        self.year_combo = SearchableComboBox(all_text="All Years")
        self.year_combo.currentIndexChanged.connect(self._on_filter_changed)
        # Load filter options when user clicks the dropdown
        original_year_showPopup = self.year_combo.showPopup
        def year_showPopup():
            self.filter_options_needed.emit()
            original_year_showPopup()
        self.year_combo.showPopup = year_showPopup

        # Confidence filter (for matched tracks)
        self.confidence_combo = QComboBox()
        self.confidence_combo.addItems(["All Confidence", "CERTAIN", "HIGH", "MODERATE", "LOW"])
        self.confidence_combo.currentIndexChanged.connect(self._on_filter_changed)

        # Quality filter (for matched tracks)
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["All Quality", "EXCELLENT", "GOOD", "PARTIAL", "POOR"])
        self.quality_combo.currentIndexChanged.connect(self._on_filter_changed)

        # Row 2: Search field (with debouncing)
        self.search_field = DebouncedSearchField(debounce_ms=500)
        self.search_field.setPlaceholderText("Search tracks, albums, artists...")
        self.search_field.debouncedTextChanged.connect(lambda text: self._on_filter_changed())

        # Layout - Two rows
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)  # Add padding around filter panels
        main_layout.setSpacing(8)  # Increase spacing between rows

        # First row: Status and metadata filters
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(10)

        row1_layout.addWidget(QLabel("Playlist:"))
        row1_layout.addWidget(self.playlist_combo, stretch=1)

        row1_layout.addWidget(QLabel("Artist:"))
        row1_layout.addWidget(self.artist_combo, stretch=1)

        row1_layout.addWidget(QLabel("Album:"))
        row1_layout.addWidget(self.album_combo, stretch=1)

        row1_layout.addWidget(QLabel("Year:"))
        row1_layout.addWidget(self.year_combo, stretch=1)

        row1_layout.addWidget(QLabel("Matched:"))
        row1_layout.addWidget(self.track_status_combo, stretch=1)

        row1_layout.addWidget(QLabel("Confidence:"))
        row1_layout.addWidget(self.confidence_combo, stretch=1)

        row1_layout.addWidget(QLabel("Quality:"))
        row1_layout.addWidget(self.quality_combo, stretch=1)

        # No stretch at end - widgets distribute evenly

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

    def get_playlist_filter(self) -> Optional[str]:
        """Get selected playlist filter.

        Returns:
            Playlist name or None if "All Playlists" selected
        """
        return self.playlist_combo.get_selected_value()

    def get_artist_filter(self) -> Optional[str]:
        """Get selected artist filter.

        Returns:
            Artist name or None if "All Artists" selected
        """
        return self.artist_combo.get_selected_value()

    def get_album_filter(self) -> Optional[str]:
        """Get selected album filter.

        Returns:
            Album name or None if "All Albums" selected
        """
        return self.album_combo.get_selected_value()

    def get_year_filter(self) -> Optional[int]:
        """Get selected year filter.

        Returns:
            Year as integer or None if "All Years" selected
        """
        text = self.year_combo.get_selected_value()
        if text is None:
            return None
        try:
            return int(text)
        except (ValueError, TypeError):
            return None

    def get_confidence_filter(self) -> Optional[str]:
        """Get selected confidence filter.

        Returns:
            Confidence level or None if "All Confidence" selected
        """
        text = self.confidence_combo.currentText()
        return None if text == "All Confidence" else text

    def get_quality_filter(self) -> Optional[str]:
        """Get selected quality filter.

        Returns:
            Quality level or None if "All Quality" selected
        """
        text = self.quality_combo.currentText()
        return None if text == "All Quality" else text

    def populate_filter_options(
        self,
        playlists: List[str],
        artists: List[str],
        albums: List[str],
        years: List[int]
    ):
        """Populate filter dropdown options from data.

        Args:
            playlists: List of unique playlist names
            artists: List of unique artist names
            albums: List of unique album names
            years: List of unique years
        """
        # Populate searchable comboboxes (they handle selection preservation)
        self.playlist_combo.populate_items(playlists, sort=True)
        self.artist_combo.populate_items(artists, sort=True)
        self.album_combo.populate_items(albums, sort=True)
        # Sort years descending (newest first)
        year_items = [str(y) for y in sorted(years, reverse=True)]
        self.year_combo.populate_items(year_items, sort=False)

    def clear_filters(self):
        """Reset all filters to default state."""
        self.track_status_combo.setCurrentIndex(0)
        self.playlist_combo.clear_selection()
        self.artist_combo.clear_selection()
        self.album_combo.clear_selection()
        self.year_combo.clear_selection()
        self.confidence_combo.setCurrentIndex(0)
        self.quality_combo.setCurrentIndex(0)
        self.search_field.clear()

    def set_playlist_filter(self, playlist_name: Optional[str]):
        """Programmatically set playlist filter (for bidirectional sync).

        Idempotent: No-op if current selection already matches target.
        Uses QSignalBlocker to prevent re-emission loops.

        Args:
            playlist_name: Playlist name to select, or None to clear
        """
        # Check if already set (idempotency)
        if self.playlist_combo.get_selected_value() == playlist_name:
            return

        # Block signals during programmatic update
        with QSignalBlocker(self.playlist_combo):
            self.playlist_combo.set_selected_value(playlist_name)

    def set_artist_filter(self, artist_name: Optional[str]):
        """Programmatically set artist filter (for bidirectional sync).

        Idempotent: No-op if current selection already matches target.
        Uses QSignalBlocker to prevent re-emission loops.

        Args:
            artist_name: Artist name to select, or None to clear
        """
        # Check if already set (idempotency)
        if self.artist_combo.get_selected_value() == artist_name:
            return

        # Block signals during programmatic update
        with QSignalBlocker(self.artist_combo):
            self.artist_combo.set_selected_value(artist_name)

    def set_album_filter(self, album_name: Optional[str]):
        """Programmatically set album filter (for bidirectional sync).

        Idempotent: No-op if current selection already matches target.
        Uses QSignalBlocker to prevent re-emission loops.

        Args:
            album_name: Album name to select, or None to clear
        """
        # Check if already set (idempotency)
        if self.album_combo.get_selected_value() == album_name:
            return

        # Block signals during programmatic update
        with QSignalBlocker(self.album_combo):
            self.album_combo.set_selected_value(album_name)
