"""Reusable sortable and filterable table component.

This component encapsulates a QTableView with QSortFilterProxyModel to provide:
- Clickable headers for sorting (with proper numeric/text sorting via Qt.UserRole)
- Text filtering across columns
- Value filtering for specific columns
- Clean API for common table operations
"""
from __future__ import annotations
from typing import Optional, List, Any
from PySide6.QtWidgets import QTableView, QHeaderView, QWidget, QVBoxLayout
from PySide6.QtCore import Qt, QSortFilterProxyModel, QAbstractTableModel
import logging

logger = logging.getLogger(__name__)


class SortFilterTable(QWidget):
    """Reusable table widget with sorting and filtering support.

    This component wraps a QTableView with a QSortFilterProxyModel to provide
    sortable columns and filtering capabilities out of the box.

    Example:
        model = MyTableModel()
        table = SortFilterTable(model)
        table.set_default_sort(0, Qt.AscendingOrder)
        table.set_text_filter("search term")
    """

    def __init__(
        self,
        source_model: QAbstractTableModel,
        stretch_columns: bool = True,
        selection_mode: QTableView.SelectionMode = QTableView.SingleSelection,
        parent: Optional[QWidget] = None
    ):
        """Initialize sortable/filterable table.

        Args:
            source_model: The source table model
            stretch_columns: If True, columns stretch to fill 100% width
            selection_mode: Row selection mode
            parent: Parent widget
        """
        super().__init__(parent)

        self.source_model = source_model

        # Create proxy model for sorting/filtering
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(source_model)
        self.proxy_model.setSortRole(Qt.UserRole)  # Use raw values for sorting
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)

        # Create table view
        self.table_view = QTableView()
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSortingEnabled(True)  # Enable clickable headers
        self.table_view.setSelectionBehavior(QTableView.SelectRows)
        self.table_view.setSelectionMode(selection_mode)

        # Configure column stretching and resizing
        header = self.table_view.horizontalHeader()
        if stretch_columns:
            # Allow interactive resizing while stretching last column to fill space
            header.setStretchLastSection(True)
            header.setSectionResizeMode(QHeaderView.Interactive)
        else:
            header.setSectionResizeMode(QHeaderView.Interactive)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table_view)

    def set_default_sort(self, column: int, order: Qt.SortOrder = Qt.AscendingOrder):
        """Set default sort column and order.

        Args:
            column: Column index to sort by
            order: Sort order (Qt.AscendingOrder or Qt.DescendingOrder)
        """
        self.table_view.sortByColumn(column, order)

    def set_text_filter(self, text: str):
        """Filter rows by text across all columns.

        Args:
            text: Filter text (case-insensitive)
        """
        self.proxy_model.setFilterWildcard(text)

    def set_column_filter(self, column: int, text: str):
        """Filter specific column by text.

        Args:
            column: Column index to filter
            text: Filter text (case-insensitive)
        """
        self.proxy_model.setFilterKeyColumn(column)
        self.proxy_model.setFilterWildcard(text)

    def clear_filters(self):
        """Clear all active filters."""
        self.proxy_model.setFilterWildcard("")
        self.proxy_model.setFilterKeyColumn(-1)  # All columns

    def get_selected_row_data(self) -> Optional[Any]:
        """Get data for currently selected row.

        Returns:
            Row data from source model, or None if no selection
        """
        selection = self.table_view.selectionModel()
        if selection and selection.hasSelection():
            proxy_row = selection.selectedRows()[0].row()
            source_index = self.proxy_model.mapToSource(
                self.proxy_model.index(proxy_row, 0)
            )
            source_row = source_index.row()

            # Access source model's get_row_data if available
            if hasattr(self.source_model, 'get_row_data'):
                return self.source_model.get_row_data(source_row)

        return None

    def resize_columns_to_contents(self):
        """Resize all columns to fit their contents."""
        self.table_view.resizeColumnsToContents()

    def set_column_widths(self, widths: List[int]):
        """Set specific column widths.

        Args:
            widths: List of column widths in pixels. Use -1 to skip a column.
        """
        header = self.table_view.horizontalHeader()
        for col, width in enumerate(widths):
            if width > 0:
                header.resizeSection(col, width)

    def selection_model(self):
        """Get the table's selection model.

        Returns:
            QItemSelectionModel for monitoring selections
        """
        return self.table_view.selectionModel()

