"""Generic filter bar component with owner filter and search.

This is a simpler, reusable filter bar component that can be used
for playlists or other views that need owner filtering and text search.
"""
from __future__ import annotations
from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel
)
from PySide6.QtCore import Signal
import logging

from .debounced_search_field import DebouncedSearchField
from .searchable_combobox import SearchableComboBox

logger = logging.getLogger(__name__)


class PlaylistFilterBar(QWidget):
    """Filter bar for playlists with owner filter and search.

    This component provides:
    - Owner dropdown filter
    - Text search (searches playlist name and owner name)

    Signals:
        filter_changed: Emitted when any filter changes (no parameters)
        filter_options_needed: Emitted when user opens dropdown (load data on demand)
    """

    # Signal emitted when any filter changes
    filter_changed = Signal()
    # Signal emitted when user is about to interact with filter dropdowns
    filter_options_needed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize playlist filter bar.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        # Create filter widgets
        self.owner_combo = SearchableComboBox(all_text="All Owners")
        self.owner_combo.currentIndexChanged.connect(self._on_filter_changed)

        # Load filter options when user clicks the dropdown
        original_owner_showPopup = self.owner_combo.showPopup
        def owner_showPopup():
            self.filter_options_needed.emit()
            original_owner_showPopup()
        self.owner_combo.showPopup = owner_showPopup

        # Search field
        self.search_field = DebouncedSearchField(debounce_ms=500)
        self.search_field.setPlaceholderText("Search playlists...")
        self.search_field.debouncedTextChanged.connect(self._on_filter_changed)

        # Layout - Two rows
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)  # Add padding around filter panels
        main_layout.setSpacing(8)  # Increase spacing between rows

        # First row: Owner filter
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(10)

        row1_layout.addWidget(QLabel("Owner:"))
        row1_layout.addWidget(self.owner_combo)
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

    def get_owner_filter(self) -> Optional[str]:
        """Get selected owner filter.

        Returns:
            Owner name or None if "All Owners" selected
        """
        return self.owner_combo.get_selected_value()

    def get_search_text(self) -> str:
        """Get search text.

        Returns:
            Search text (may be empty)
        """
        return self.search_field.text().strip()

    def populate_owner_options(self, owners: List[str]):
        """Populate owner dropdown options from data.

        Args:
            owners: List of unique owner names
        """
        # Populate searchable combobox (it handles selection preservation)
        self.owner_combo.populate_items(owners, sort=True)

    def clear_filters(self):
        """Reset all filters to default state."""
        self.owner_combo.clear_selection()
        self.search_field.clear()


__all__ = ['PlaylistFilterBar']
