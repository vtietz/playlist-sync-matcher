"""Searchable ComboBox component with autocomplete and limited dropdown height.

Provides a user-friendly dropdown that allows typing to search/filter items,
with a fixed maximum height to prevent overwhelming dropdowns with thousands of entries.
"""

from __future__ import annotations
from typing import Optional, List
from PySide6.QtWidgets import QComboBox, QCompleter
from PySide6.QtCore import Qt
import logging

logger = logging.getLogger(__name__)


class SearchableComboBox(QComboBox):
    """ComboBox with search/autocomplete and limited dropdown height.

    Features:
    - Editable with autocomplete/filtering as you type
    - Limited dropdown height (shows ~15 items max with scrolling)
    - Always includes "All ..." option at index 0
    - Case-insensitive searching
    - Preserves selection across populate() calls

    Usage:
        combo = SearchableComboBox(all_text="All Artists")
        combo.populate_items(["Artist 1", "Artist 2", ...])
        combo.currentIndexChanged.connect(handler)

        # Get selected value (None if "All ..." selected)
        value = combo.get_selected_value()
    """

    def __init__(self, all_text: str = "All", parent: Optional[QComboBox] = None):
        """Initialize searchable combobox.

        Args:
            all_text: Text for "clear filter" option (e.g., "All Artists", "All Albums")
            parent: Parent widget
        """
        super().__init__(parent)

        self._all_text = all_text

        # Make editable for search functionality
        self.setEditable(True)

        # Set up autocomplete
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)  # Don't let user add items
        completer = QCompleter(self)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setCompleter(completer)

        # Limit dropdown height to ~15 items
        self.setMaxVisibleItems(15)

        # Add initial "All" option
        self.addItem(self._all_text)

        # When user selects from dropdown, update line edit to show selection
        self.activated.connect(self._on_activated)

        # Validate selection when user finishes editing
        self.lineEdit().editingFinished.connect(self._on_editing_finished)

    def _on_activated(self, index: int):
        """Handle user selection from dropdown.

        When user selects from dropdown (or completer popup), this ensures
        the line edit text matches the selected item exactly.

        Args:
            index: Selected index
        """
        # Update current index to match selection
        self.setCurrentIndex(index)
        # Also update text to match (important when user typed partial text)
        if index >= 0:
            self.setEditText(self.itemText(index))

    def _on_editing_finished(self):
        """Handle when user finishes typing (focus lost or Enter pressed).

        Validates that the typed text matches an actual item in the list.
        If not found, resets to current selection or "All".
        """
        typed_text = self.currentText().strip()

        # Find exact match (case-insensitive)
        index = self.findText(typed_text, Qt.MatchFlag.MatchFixedString)

        if index >= 0:
            # Found exact match - select it
            if self.currentIndex() != index:
                self.setCurrentIndex(index)
        else:
            # No match - reset to current valid selection or "All"
            current_index = self.currentIndex()
            if current_index >= 0 and current_index < self.count():
                # Restore the last valid selection
                self.setEditText(self.itemText(current_index))
            else:
                # No valid selection - reset to "All"
                self.setCurrentIndex(0)

    def populate_items(self, items: List[str], sort: bool = True):
        """Populate dropdown with items.

        Preserves current selection if it exists in new items.
        Always includes "All ..." option at index 0.

        Args:
            items: List of items to display (excluding "All" option)
            sort: Whether to sort items alphabetically (default: True)
        """
        # Save current selection
        current_text = self.currentText()

        # Clear and repopulate
        self.clear()
        self.addItem(self._all_text)

        # Sort if requested
        if sort:
            items = sorted(items)

        self.addItems(items)

        # Update completer model
        self.completer().setModel(self.model())

        # Restore selection if it still exists
        idx = self.findText(current_text)
        if idx >= 0:
            self.setCurrentIndex(idx)
        else:
            self.setCurrentIndex(0)  # Default to "All"

    def get_selected_value(self) -> Optional[str]:
        """Get selected value.

        Returns only values that exist in the dropdown list, not arbitrary user input.

        Returns:
            Selected item text, or None if "All ..." is selected or invalid text entered
        """
        # Get current index (not text, to avoid issues with user typing)
        index = self.currentIndex()

        # Index 0 is always "All ..."
        if index <= 0:
            return None

        # Return the actual item text at this index
        text = self.itemText(index)
        return None if text == self._all_text else text

    def set_selected_value(self, value: Optional[str]):
        """Programmatically set selected value.

        Args:
            value: Value to select, or None to select "All ..."
        """
        if value is None:
            self.setCurrentIndex(0)
        else:
            idx = self.findText(value)
            if idx >= 0:
                self.setCurrentIndex(idx)
            else:
                # Value not found - default to "All"
                self.setCurrentIndex(0)

    def clear_selection(self):
        """Reset to "All ..." option."""
        self.setCurrentIndex(0)

    def get_all_text(self) -> str:
        """Get the "All ..." text for this combobox.

        Returns:
            The "All" option text (e.g., "All Artists")
        """
        return self._all_text


__all__ = ["SearchableComboBox"]
