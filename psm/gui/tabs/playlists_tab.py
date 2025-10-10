"""PlaylistsTab - Encapsulates playlist tab creation logic.

Extracts ~110 lines of UI construction from MainWindow to keep it focused.
Follows composition pattern: builds UI, exposes signals and widgets.
"""

from __future__ import annotations
from typing import TYPE_CHECKING
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableView, QHeaderView
)
from PySide6.QtCore import Qt, Signal, QItemSelection, QSignalBlocker, QItemSelectionModel

if TYPE_CHECKING:
    from ..models import PlaylistsModel
    from ..components.playlist_filter_bar import PlaylistFilterBar
    from ..components.playlist_proxy_model import PlaylistProxyModel
    from ..components.link_delegate import LinkDelegate


class PlaylistsTab(QWidget):
    """Playlists tab with table, filters, and action buttons.
    
    Signals:
        selection_changed(QItemSelection, QItemSelection): Emitted when playlist selection changes (selected, deselected)
        pull_all_clicked: Pull all playlists
        match_all_clicked: Match all playlists
        export_all_clicked: Export all playlists
        pull_one_clicked: Pull selected playlist
        match_one_clicked: Match selected playlist
        export_one_clicked: Export selected playlist
    """
    
    # Signals
    selection_changed = Signal(QItemSelection, QItemSelection)  # selected, deselected
    pull_all_clicked = Signal()
    match_all_clicked = Signal()
    export_all_clicked = Signal()
    pull_one_clicked = Signal()
    match_one_clicked = Signal()
    export_one_clicked = Signal()
    
    def __init__(
        self,
        playlists_model,
        playlist_proxy_model,
        playlist_filter_bar,
        parent=None
    ):
        """Initialize playlists tab.
        
        Args:
            playlists_model: PlaylistsModel instance
            playlist_proxy_model: PlaylistProxyModel instance
            playlist_filter_bar: PlaylistFilterBar instance
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.playlists_model = playlists_model
        self.playlist_proxy_model = playlist_proxy_model
        self.playlist_filter_bar = playlist_filter_bar
        
        self._create_ui()
    
    def _create_ui(self):
        """Create the tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Add filter bar
        layout.addWidget(self.playlist_filter_bar)
        
        # Create table view
        self.table_view = self._create_table_view()
        layout.addWidget(self.table_view)
        
        # Add action buttons
        buttons_layout = self._create_buttons()
        layout.addLayout(buttons_layout)
    
    def _create_table_view(self) -> QTableView:
        """Create and configure playlists table view."""
        from ..components.link_delegate import LinkDelegate
        
        table = QTableView()
        table.setObjectName("playlistsTable")
        table.setModel(self.playlist_proxy_model)
        table.setSortingEnabled(True)
        table.setSelectionBehavior(QTableView.SelectRows)
        table.setSelectionMode(QTableView.SingleSelection)
        
        # Enable text eliding for long playlist names
        table.setTextElideMode(Qt.ElideRight)
        table.setWordWrap(False)
        
        # Set compact row height to match tracks table
        table.verticalHeader().setDefaultSectionSize(22)
        table.verticalHeader().setMinimumSectionSize(22)
        
        # Configure column resizing
        header = table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.Interactive)
        
        # Set intelligent column widths
        # Columns: Name, Owner, Coverage, Relevance
        table.setColumnWidth(0, 250)  # Name
        table.setColumnWidth(1, 120)  # Owner
        table.setColumnWidth(2, 120)  # Coverage
        table.setColumnWidth(3, 80)   # Relevance
        
        # Apply link delegate to Name column
        link_delegate = LinkDelegate(provider="spotify", parent=table)
        table.setItemDelegateForColumn(0, link_delegate)
        
        # Enable mouse tracking for hover effects
        table.setMouseTracking(True)
        
        # Connect selection signal - forward Qt's selected/deselected parameters
        selection_model = table.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(self.selection_changed)
        
        return table
    
    def _create_buttons(self) -> QHBoxLayout:
        """Create action buttons layout."""
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(5)
        
        # Global playlist actions
        self.btn_pull = QPushButton("Pull All")
        self.btn_match = QPushButton("Match All")
        self.btn_export = QPushButton("Export All")
        
        # Per-playlist actions
        self.btn_pull_one = QPushButton("Pull Selected")
        self.btn_match_one = QPushButton("Match Selected")
        self.btn_export_one = QPushButton("Export Selected")
        
        # Add buttons to layout
        buttons_layout.addWidget(self.btn_pull)
        buttons_layout.addWidget(self.btn_match)
        buttons_layout.addWidget(self.btn_export)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.btn_pull_one)
        buttons_layout.addWidget(self.btn_match_one)
        buttons_layout.addWidget(self.btn_export_one)
        
        # Initially disable per-playlist actions
        self.enable_playlist_actions(False)
        
        # Connect signals
        self.btn_pull.clicked.connect(self.pull_all_clicked.emit)
        self.btn_match.clicked.connect(self.match_all_clicked.emit)
        self.btn_export.clicked.connect(self.export_all_clicked.emit)
        
        self.btn_pull_one.clicked.connect(self.pull_one_clicked.emit)
        self.btn_match_one.clicked.connect(self.match_one_clicked.emit)
        self.btn_export_one.clicked.connect(self.export_one_clicked.emit)
        
        return buttons_layout
    
    def enable_playlist_actions(self, enabled: bool):
        """Enable/disable per-playlist action buttons.
        
        Args:
            enabled: True to enable, False to disable
        """
        self.btn_pull_one.setEnabled(enabled)
        self.btn_match_one.setEnabled(enabled)
        self.btn_export_one.setEnabled(enabled)
    
    def get_selected_playlist_id(self) -> str:
        """Get selected playlist ID.
        
        Returns:
            Playlist ID or empty string if no selection
        """
        selection = self.table_view.selectionModel()
        if not selection or not selection.hasSelection():
            return ""
        
        selected_rows = selection.selectedRows()
        if not selected_rows:
            return ""
        
        # Get playlist ID from first column of selected row
        proxy_index = selected_rows[0]
        source_index = self.playlist_proxy_model.mapToSource(proxy_index)
        source_row = source_index.row()
        
        # Get ID from the model
        if hasattr(self.playlists_model, 'get_row_data'):
            row_data = self.playlists_model.get_row_data(source_row)
            if row_data:
                return row_data.get('id', '')
        
        return ""
    
    def select_playlist(self, playlist_name: str):
        """Programmatically select a playlist by name.
        
        Uses QSignalBlocker to prevent re-emission of selection_changed signal
        (prevents infinite loops when FilterStore triggers this).
        
        Args:
            playlist_name: Playlist name to select
        """
        # Find row with matching playlist name
        for row in range(self.playlist_proxy_model.rowCount()):
            proxy_index = self.playlist_proxy_model.index(row, 0)
            source_index = self.playlist_proxy_model.mapToSource(proxy_index)
            source_row = source_index.row()
            
            # Get playlist data
            row_data = self.playlists_model.get_row_data(source_row)
            if row_data and (row_data.get('name') == playlist_name or row_data.get('id') == playlist_name):
                # Found it - select with signal blocking
                selection_model = self.table_view.selectionModel()
                if selection_model:
                    with QSignalBlocker(selection_model):
                        selection_model.clearSelection()
                        selection_model.select(
                            proxy_index,
                            QItemSelectionModel.Select | QItemSelectionModel.Rows
                        )
                        self.table_view.scrollTo(proxy_index)
                return
        
        # Not found - clear selection
        selection_model = self.table_view.selectionModel()
        if selection_model:
            with QSignalBlocker(selection_model):
                selection_model.clearSelection()
