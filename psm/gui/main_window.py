"""Main window for the GUI application.

Assembles all UI components using composition:
- SortFilterTable for all tabular data
- LogPanel for command output
- Toolbar for actions
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTabWidget, QPushButton, QProgressBar,
    QLabel, QMessageBox, QToolBar
)
from PySide6.QtCore import Qt, Signal, QItemSelectionModel
from PySide6.QtGui import QFont
import logging

from .components import SortFilterTable, LogPanel
from .components.link_delegate import LinkDelegate
from .components.folder_delegate import FolderDelegate
from .components.playlist_filter_bar import PlaylistFilterBar
from .components.playlist_proxy_model import PlaylistProxyModel
from .views import UnifiedTracksView
from .models import (
    PlaylistsModel, PlaylistDetailModel, UnmatchedTracksModel,
    MatchedTracksModel, PlaylistCoverageModel, UnmatchedAlbumsModel,
    LikedTracksModel, UnifiedTracksModel
)

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window."""
    
    # Signals
    on_playlist_selected = Signal(str)  # playlist_id
    on_playlist_filter_requested = Signal(str)  # playlist_name for filtering unified tracks
    on_pull_clicked = Signal()
    on_scan_clicked = Signal()
    on_match_clicked = Signal()
    on_export_clicked = Signal()
    on_report_clicked = Signal()
    on_open_reports_clicked = Signal()
    on_build_clicked = Signal()
    on_pull_one_clicked = Signal()
    on_match_one_clicked = Signal()
    on_export_one_clicked = Signal()
    on_watch_toggled = Signal(bool)
    
    def __init__(self):
        """Initialize main window."""
        super().__init__()
        
        self.setWindowTitle("Playlist Sync Matcher")
        self.resize(1400, 900)
        self.setMinimumSize(800, 600)  # Allow reducing window size to reasonable minimum
        
        # Track selected playlist
        self._selected_playlist_id: Optional[str] = None
        
        # Create models
        self.playlists_model = PlaylistsModel(self)
        self.playlist_detail_model = PlaylistDetailModel(self)
        self.unmatched_tracks_model = UnmatchedTracksModel(self)
        self.matched_tracks_model = MatchedTracksModel(self)
        self.coverage_model = PlaylistCoverageModel(self)
        self.unmatched_albums_model = UnmatchedAlbumsModel(self)
        self.liked_tracks_model = LikedTracksModel(self)
        self.unified_tracks_model = UnifiedTracksModel(self)
        
        # Build UI
        self._create_ui()
    
    def _create_ui(self):
        """Create the main UI layout."""
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create toolbar
        self._create_toolbar()
        
        # Main splitter: left (playlists) | right (tabs + detail)
        main_splitter = QSplitter(Qt.Horizontal)
        
        # Left: Playlists master table
        playlists_widget = self._create_playlists_widget()
        main_splitter.addWidget(playlists_widget)
        
        # Right: Tabs and detail
        right_widget = self._create_right_panel()
        main_splitter.addWidget(right_widget)
        
        # Allow user to resize, but set reasonable constraints
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 2)
        
        # Set collapsible to False so panels can't be completely hidden
        main_splitter.setCollapsible(0, False)
        main_splitter.setCollapsible(1, False)
        
        # Store reference for later size adjustments
        self.main_splitter = main_splitter
        
        layout.addWidget(main_splitter)
        
        # Bottom: Log and progress
        bottom_widget = self._create_bottom_panel()
        layout.addWidget(bottom_widget)
        
        layout.setStretch(0, 3)
        layout.setStretch(1, 1)
    
    def _create_toolbar(self):
        """Create the action toolbar for general actions."""
        toolbar = QToolBar("Actions")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        # General library actions (stay in toolbar)
        self.btn_scan = QPushButton("Scan Library")
        self.btn_build = QPushButton("Build")
        self.btn_report = QPushButton("Generate Reports")
        self.btn_open_reports = QPushButton("Open Reports")
        
        # Add to toolbar
        toolbar.addWidget(self.btn_scan)
        toolbar.addWidget(self.btn_build)
        toolbar.addWidget(self.btn_report)
        toolbar.addWidget(self.btn_open_reports)
        
        # Connect signals
        self.btn_scan.clicked.connect(self.on_scan_clicked.emit)
        self.btn_build.clicked.connect(self.on_build_clicked.emit)
        self.btn_report.clicked.connect(self.on_report_clicked.emit)
        self.btn_open_reports.clicked.connect(self.on_open_reports_clicked.emit)
    
    def _create_playlists_widget(self) -> QWidget:
        """Create the playlists master table widget with filter bar."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
        
        # Add label for cleaner look
        label = QLabel("Playlists")
        label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        layout.addWidget(label)
        
        # Add filter bar
        self.playlist_filter_bar = PlaylistFilterBar()
        self.playlist_filter_bar.filter_changed.connect(self._apply_playlist_filters)
        self.playlist_filter_bar.filter_options_needed.connect(self._populate_playlist_filter_options)
        layout.addWidget(self.playlist_filter_bar)
        
        # Create custom proxy model for filtering
        self.playlist_proxy_model = PlaylistProxyModel()
        self.playlist_proxy_model.setSourceModel(self.playlists_model)
        
        # Create table view manually (not using SortFilterTable since we have custom proxy)
        from PySide6.QtWidgets import QTableView, QHeaderView
        self.playlists_table_view = QTableView()
        self.playlists_table_view.setObjectName("playlistsTable")
        self.playlists_table_view.setModel(self.playlist_proxy_model)
        self.playlists_table_view.setSortingEnabled(True)
        self.playlists_table_view.setSelectionBehavior(QTableView.SelectRows)
        self.playlists_table_view.setSelectionMode(QTableView.SingleSelection)
        
        # Enable text eliding for long playlist names
        self.playlists_table_view.setTextElideMode(Qt.ElideRight)
        self.playlists_table_view.setWordWrap(False)
        
        # Configure column resizing
        header = self.playlists_table_view.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.Interactive)
        
        # Set intelligent column widths for playlists
        # Columns: Name, Owner, Coverage
        self.playlists_table_view.setColumnWidth(0, 250)  # Name
        self.playlists_table_view.setColumnWidth(1, 120)  # Owner
        self.playlists_table_view.setColumnWidth(2, 120)  # Coverage
        
        # Apply link delegate to Name column (column 0 = playlist link)
        link_delegate = LinkDelegate(provider="spotify", parent=self.playlists_table_view)
        self.playlists_table_view.setItemDelegateForColumn(0, link_delegate)
        
        # Enable mouse tracking for hover effects
        self.playlists_table_view.setMouseTracking(True)
        
        # Connect selection signal
        selection_model = self.playlists_table_view.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(self._on_playlist_selection_changed)
        
        layout.addWidget(self.playlists_table_view)
        
        # Add playlist action buttons below the table
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
        
        # Watch mode toggle
        self.btn_watch = QPushButton("Start Watch Mode")
        self.btn_watch.setCheckable(True)
        
        # Add buttons to layout
        buttons_layout.addWidget(self.btn_pull)
        buttons_layout.addWidget(self.btn_match)
        buttons_layout.addWidget(self.btn_export)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.btn_pull_one)
        buttons_layout.addWidget(self.btn_match_one)
        buttons_layout.addWidget(self.btn_export_one)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.btn_watch)
        
        layout.addLayout(buttons_layout)
        
        # Initially disable per-playlist actions
        self.enable_playlist_actions(False)
        
        # Connect signals
        self.btn_pull.clicked.connect(self.on_pull_clicked.emit)
        self.btn_match.clicked.connect(self.on_match_clicked.emit)
        self.btn_export.clicked.connect(self.on_export_clicked.emit)
        
        self.btn_pull_one.clicked.connect(self.on_pull_one_clicked.emit)
        self.btn_match_one.clicked.connect(self.on_match_one_clicked.emit)
        self.btn_export_one.clicked.connect(self.on_export_one_clicked.emit)
        
        self.btn_watch.toggled.connect(self._on_watch_button_toggled)
        
        return widget
    
    def _create_right_panel(self) -> QWidget:
        """Create the right panel with unified tracks view."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Add header label
        label = QLabel("Tracks")
        label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        layout.addWidget(label)
        
        # Single unified tracks view (replaces all tabs)
        self.unified_tracks_view = UnifiedTracksView(self.unified_tracks_model)
        # Note: Filter options are now populated on-demand from visible data
        layout.addWidget(self.unified_tracks_view)
        
        return widget
    
    def _create_playlist_detail_widget(self) -> QWidget:
        """Create the playlist detail widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.detail_label = QLabel("Select a playlist to view details")
        layout.addWidget(self.detail_label)
        
        # Use SortFilterTable component
        self.detail_table = SortFilterTable(
            source_model=self.playlist_detail_model,
            stretch_columns=True
        )
        
        # Apply link delegate to linkable columns in playlist detail
        # Columns: 0=#, 1=Track, 2=Artist, 3=Album, 4=Local File
        link_delegate = LinkDelegate(provider="spotify", parent=self.detail_table.table_view)
        self.detail_table.table_view.setItemDelegateForColumn(1, link_delegate)  # Track
        self.detail_table.table_view.setItemDelegateForColumn(2, link_delegate)  # Artist
        self.detail_table.table_view.setItemDelegateForColumn(3, link_delegate)  # Album
        
        # Apply folder delegate to Local File column
        folder_delegate = FolderDelegate(parent=self.detail_table.table_view)
        self.detail_table.table_view.setItemDelegateForColumn(4, folder_delegate)  # Local File
        
        # Enable mouse tracking for hover effects
        self.detail_table.table_view.setMouseTracking(True)
        
        layout.addWidget(self.detail_table)
        
        return widget
    
    def _create_bottom_panel(self) -> QWidget:
        """Create the bottom panel with log and progress."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Progress bar
        progress_layout = QHBoxLayout()
        self.progress_label = QLabel("Ready")
        self.progress_label.setFont(QFont("Segoe UI Emoji", 9))  # Support emoji in progress messages
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        
        layout.addLayout(progress_layout)
        
        # Use LogPanel component
        self.log_panel = LogPanel(title="Log", max_height=200, font_size=9)
        layout.addWidget(self.log_panel)
        
        # Status bar
        self.status_label = QLabel("Ready")
        self.status_label.setFont(QFont("Segoe UI Emoji", 9))  # Support emoji in status messages
        self.statusBar().addWidget(self.status_label)
        
        return widget
    
    # Data update methods
    
    def update_playlists(self, playlists: List[Dict[str, Any]]):
        """Update playlists table.
        
        Args:
            playlists: List of playlist dicts
        """
        self.playlists_model.set_data(playlists)
        
        # Resize columns to fit content
        self.playlists_table_view.resizeColumnsToContents()
        
        # Restore preferred column widths (resizeColumnsToContents might make them too wide)
        self.playlists_table_view.setColumnWidth(0, max(250, self.playlists_table_view.columnWidth(0)))
        self.playlists_table_view.setColumnWidth(1, max(120, self.playlists_table_view.columnWidth(1)))
        
        # Default sort by name (column 0) alphabetically
        self.playlists_table_view.sortByColumn(0, Qt.AscendingOrder)
        
        # No auto-selection - user can click to select/deselect
    
    def update_playlist_detail(self, tracks: List[Dict[str, Any]]):
        """Update playlist detail table.
        
        DEPRECATED: This method is no longer used since tabs were removed.
        Kept for backward compatibility with controllers.
        
        Args:
            tracks: List of track dicts
        """
        pass  # No-op - detail table no longer exists
    
    def update_unmatched_tracks(self, tracks: List[Dict[str, Any]]):
        """Update unmatched tracks table."""
        self.unmatched_tracks_model.set_data(tracks)
    
    def update_matched_tracks(self, tracks: List[Dict[str, Any]]):
        """Update matched tracks table."""
        self.matched_tracks_model.set_data(tracks)
    
    def update_coverage(self, coverage: List[Dict[str, Any]]):
        """Update coverage table."""
        self.coverage_model.set_data(coverage)
    
    def update_unmatched_albums(self, albums: List[Dict[str, Any]]):
        """Update unmatched albums table."""
        self.unmatched_albums_model.set_data(albums)
    
    def update_liked_tracks(self, tracks: List[Dict[str, Any]]):
        """Update liked tracks table."""
        self.liked_tracks_model.set_data(tracks)
    
    def update_unified_tracks(self, tracks: List[Dict[str, Any]], playlists: List[Dict[str, Any]]):
        """Update unified tracks view with data and filter options.
        
        Args:
            tracks: List of all tracks with metadata
            playlists: List of playlists for filtering (no longer used - filtering via left panel)
        """
        self.unified_tracks_model.set_data(tracks)
        # No longer call set_playlists - playlist filtering is handled by left panel selection
        self.unified_tracks_view.resize_columns_to_contents()
    
    def populate_track_filter_options(
        self,
        artists: List[str],
        albums: List[str],
        years: List[int]
    ):
        """Populate filter dropdown options in unified tracks view.
        
        Args:
            artists: List of unique artist names
            albums: List of unique album names
            years: List of unique years
        """
        self.unified_tracks_view.populate_filter_options(artists, albums, years)
    
    def update_status_counts(self, counts: Dict[str, int]):
        """Update status bar with counts.
        
        Args:
            counts: Dict with playlists, tracks, library_files, matches counts
        """
        status = (
            f"Playlists: {counts.get('playlists', 0)} | "
            f"Tracks: {counts.get('tracks', 0)} | "
            f"Library: {counts.get('library_files', 0)} | "
            f"Matches: {counts.get('matches', 0)} | "
            f"Liked: {counts.get('liked', 0)}"
        )
        self.status_label.setText(status)
    
    # Log and progress methods
    
    def append_log(self, message: str):
        """Append message to log.
        
        Args:
            message: Log message
        """
        self.log_panel.append(message)
    
    def clear_logs(self):
        """Clear the log window."""
        self.log_panel.clear()
    
    def set_progress(self, current: int, total: int, message: str):
        """Update progress bar.
        
        Args:
            current: Current value
            total: Total value (0 for indeterminate)
            message: Progress message
        """
        if total == 0:
            # Indeterminate progress
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(current)
        
        self.progress_label.setText(message)
    
    # UI state methods
    
    def enable_actions(self, enabled: bool):
        """Enable/disable action buttons.
        
        Args:
            enabled: True to enable, False to disable
        """
        self.btn_pull.setEnabled(enabled)
        self.btn_scan.setEnabled(enabled)
        self.btn_match.setEnabled(enabled)
        self.btn_export.setEnabled(enabled)
        self.btn_report.setEnabled(enabled)
        self.btn_build.setEnabled(enabled)
        
        # Per-playlist actions only if playlist selected
        if enabled and self._selected_playlist_id:
            self.enable_playlist_actions(True)
        else:
            self.enable_playlist_actions(False)
    
    def enable_playlist_actions(self, enabled: bool):
        """Enable/disable per-playlist action buttons.
        
        Args:
            enabled: True to enable, False to disable
        """
        self.btn_pull_one.setEnabled(enabled)
        self.btn_match_one.setEnabled(enabled)
        self.btn_export_one.setEnabled(enabled)
    
    def set_watch_mode(self, enabled: bool):
        """Set watch mode state.
        
        Args:
            enabled: True if watch mode enabled
        """
        self.btn_watch.setChecked(enabled)
        if enabled:
            self.btn_watch.setText("Stop Watch Mode")
        else:
            self.btn_watch.setText("Start Watch Mode")
    
    def get_selected_playlist_id(self) -> Optional[str]:
        """Get currently selected playlist ID.
        
        Returns:
            Playlist ID or None
        """
        return self._selected_playlist_id
    
    # Event handlers
    
    def _on_playlist_selection_changed(self, selected, deselected):
        """Handle playlist selection change.
        
        Simple behavior: Only show tracks when a playlist is selected.
        
        Args:
            selected: QItemSelection of selected items
            deselected: QItemSelection of deselected items
        """
        # Extract playlist data directly from 'selected' parameter to avoid timing issues
        # Qt provides both 'selected' and 'deselected' specifically so we don't need to
        # query the selection model, which may not be fully updated when this signal fires
        
        if selected.isEmpty():
            return
        
        proxy_indexes = selected.indexes()
        if not proxy_indexes:
            return
        
        # Find index for column 0 (we need the first column for row data)
        proxy_index = None
        for idx in proxy_indexes:
            if idx.column() == 0:
                proxy_index = idx
                break
        
        if not proxy_index:
            return
        
        # Map proxy index to source model
        source_index = self.playlist_proxy_model.mapToSource(proxy_index)
        source_row = source_index.row()
        
        # Get row data from source model
        playlist_data = self.playlists_model.get_row_data(source_row)
        
        if not playlist_data:
            return
        
        # Playlist selected - apply filter to show only this playlist's tracks
        self._selected_playlist_id = playlist_data.get('id')
        playlist_name = playlist_data.get('name')
        
        # Request filter via signal (controller will fetch track IDs)
        self.on_playlist_filter_requested.emit(playlist_name)
        
        # Emit signal for other components
        if self._selected_playlist_id:
            self.on_playlist_selected.emit(self._selected_playlist_id)
    
    def _apply_playlist_filters(self):
        """Apply current playlist filter settings to the proxy model."""
        # Get filter state from filter bar
        owner_filter = self.playlist_filter_bar.get_owner_filter()
        search_text = self.playlist_filter_bar.get_search_text()
        
        # Apply to proxy model
        self.playlist_proxy_model.set_owner_filter(owner_filter)
        self.playlist_proxy_model.set_search_text(search_text)
    
    def _populate_playlist_filter_options(self):
        """Populate playlist filter options from visible data."""
        # Extract unique owner names from visible playlists
        owners = set()
        for row in range(self.playlists_model.rowCount()):
            row_data = self.playlists_model.get_row_data(row)
            if row_data:
                owner_name = row_data.get('owner_name')
                if owner_name:
                    owners.add(owner_name)
        
        # Populate filter bar
        self.playlist_filter_bar.populate_owner_options(sorted(owners))
    
    def _on_watch_button_toggled(self, checked: bool):
        """Handle watch button toggle.
            checked: True if checked
        """
        self.on_watch_toggled.emit(checked)
    
    def showEvent(self, event):
        """Handle window show event - set initial splitter sizes.
        
        Args:
            event: QShowEvent
        """
        super().showEvent(event)
        
        # Set splitter sizes after window is shown (only on first show)
        if not hasattr(self, '_splitter_initialized'):
            self._splitter_initialized = True
            # Use actual window width for calculation
            window_width = self.width()
            # Set 400px minimum for playlists, rest for tracks
            # This ensures playlist panel is wide enough to read names
            playlist_width = max(400, window_width // 3)
            tracks_width = window_width - playlist_width
            self.main_splitter.setSizes([playlist_width, tracks_width])
