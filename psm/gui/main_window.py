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
    QTabWidget, QPushButton,
    QLabel, QMessageBox, QToolBar, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QItemSelectionModel, QSettings
from PySide6.QtGui import QFont
import logging

from .components import SortFilterTable, LogPanel, StatusBar
from .components.link_delegate import LinkDelegate
from .components.folder_delegate import FolderDelegate
from .components.playlist_filter_bar import PlaylistFilterBar
from .components.playlist_proxy_model import PlaylistProxyModel
from .views import UnifiedTracksView, AlbumsView, ArtistsView
from .models import (
    PlaylistsModel, PlaylistDetailModel, UnmatchedTracksModel,
    MatchedTracksModel, PlaylistCoverageModel, UnmatchedAlbumsModel,
    LikedTracksModel, UnifiedTracksModel, AlbumsModel, ArtistsModel
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
    on_analyze_clicked = Signal()
    on_diagnose_clicked = Signal(str)  # track_id
    on_pull_one_clicked = Signal()
    on_match_one_clicked = Signal()
    on_export_one_clicked = Signal()
    on_watch_toggled = Signal(bool)
    on_cancel_clicked = Signal()  # Cancel current command
    
    def __init__(self):
        """Initialize main window."""
        super().__init__()
        
        # Settings for persistent state (stored in INI format)
        self.settings = QSettings("vtietz", "PlaylistSyncMatcher")
        
        self.setWindowTitle("Playlist Sync Matcher")
        self.resize(1400, 900)
        self.setMinimumSize(800, 600)  # Allow reducing window size to reasonable minimum
        
        # Track selected playlist
        self._selected_playlist_id: Optional[str] = None
        
        # Track running state (for gating auto-diagnose and UI actions)
        self._is_running: bool = False
        
        # Create models
        self.playlists_model = PlaylistsModel(self)
        self.playlist_detail_model = PlaylistDetailModel(self)
        self.unmatched_tracks_model = UnmatchedTracksModel(self)
        self.matched_tracks_model = MatchedTracksModel(self)
        self.coverage_model = PlaylistCoverageModel(self)
        self.unmatched_albums_model = UnmatchedAlbumsModel(self)
        self.liked_tracks_model = LikedTracksModel(self)
        self.unified_tracks_model = UnifiedTracksModel(self)
        self.albums_model = AlbumsModel(self)
        self.artists_model = ArtistsModel(self)
        
        # Build UI
        self._create_ui()
        
        # Restore window state after UI is created
        self._restore_window_state()
    
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
        
        # Bottom: Log and status bar
        bottom_widget = self._create_bottom_panel()
        layout.addWidget(bottom_widget)
        
        # Connect cancel button (after status bar is created)
        self.status_bar_component.connect_cancel(self.on_cancel_clicked.emit)
        
        layout.setStretch(0, 3)
        layout.setStretch(1, 1)
    
    def _create_toolbar(self):
        """Create the action toolbar for general actions."""
        toolbar = QToolBar("Actions")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        # General library/system actions
        self.btn_scan = QPushButton("Scan Library")
        self.btn_build = QPushButton("Build")
        self.btn_analyze = QPushButton("Analyze Quality")
        self.btn_report = QPushButton("Generate Reports")
        self.btn_open_reports = QPushButton("Open Reports")
        
        # Watch mode toggle
        self.btn_watch = QPushButton("Start Watch Mode")
        self.btn_watch.setCheckable(True)
        
        # Add to toolbar
        toolbar.addWidget(self.btn_scan)
        toolbar.addWidget(self.btn_build)
        toolbar.addWidget(self.btn_analyze)
        toolbar.addWidget(self.btn_report)
        toolbar.addWidget(self.btn_open_reports)
        
        # Add spacer to push Watch Mode button to the right
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)
        
        toolbar.addWidget(self.btn_watch)
        
        # Connect signals
        self.btn_scan.clicked.connect(self.on_scan_clicked.emit)
        self.btn_build.clicked.connect(self.on_build_clicked.emit)
        self.btn_analyze.clicked.connect(self.on_analyze_clicked.emit)
        self.btn_report.clicked.connect(self.on_report_clicked.emit)
        self.btn_open_reports.clicked.connect(self.on_open_reports_clicked.emit)
        self.btn_watch.toggled.connect(self._on_watch_button_toggled)
    
    def _create_playlists_widget(self) -> QWidget:
        """Create the left panel with tabs for Playlists, Albums, and Artists."""
        # Create tab widget
        tab_widget = QTabWidget()
        tab_widget.setObjectName("leftTabs")
        
        # Tab 1: Playlists
        playlists_tab = self._create_playlists_tab()
        tab_widget.addTab(playlists_tab, "Playlists")
        
        # Tab 2: Albums
        albums_tab = self._create_albums_tab()
        tab_widget.addTab(albums_tab, "Albums")
        
        # Tab 3: Artists
        artists_tab = self._create_artists_tab()
        tab_widget.addTab(artists_tab, "Artists")
        
        return tab_widget
    
    def _create_playlists_tab(self) -> QWidget:
        """Create the playlists tab content."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)  # Add small margins
        
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
        
        # Set compact row height to match tracks table
        self.playlists_table_view.verticalHeader().setDefaultSectionSize(22)
        self.playlists_table_view.verticalHeader().setMinimumSectionSize(22)
        
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
        
        # Add buttons to layout
        buttons_layout.addWidget(self.btn_pull)
        buttons_layout.addWidget(self.btn_match)
        buttons_layout.addWidget(self.btn_export)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.btn_pull_one)
        buttons_layout.addWidget(self.btn_match_one)
        buttons_layout.addWidget(self.btn_export_one)
        
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
        
        return widget
    
    def _create_albums_tab(self) -> QWidget:
        """Create the albums tab content."""
        # Create albums view with model
        self.albums_view = AlbumsView(self.albums_model)
        return self.albums_view
    
    def _create_artists_tab(self) -> QWidget:
        """Create the artists tab content."""
        # Create artists view with model
        self.artists_view = ArtistsView(self.artists_model)
        return self.artists_view
    
    def _create_right_panel(self) -> QWidget:
        """Create the right panel with tabs for Tracks."""
        # Create tab widget
        tab_widget = QTabWidget()
        tab_widget.setObjectName("rightTabs")
        
        # Tab 1: Tracks
        tracks_tab = self._create_tracks_tab()
        tab_widget.addTab(tracks_tab, "Tracks")
        
        return tab_widget
    
    def _create_tracks_tab(self) -> QWidget:
        """Create the tracks tab content."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)  # Add small margins
        
        # Single unified tracks view (replaces all tabs)
        self.unified_tracks_view = UnifiedTracksView(self.unified_tracks_model)
        # Note: Filter options are now populated on-demand from visible data
        layout.addWidget(self.unified_tracks_view)
        
        # Connect track selection to enable/disable track actions
        selection_model = self.unified_tracks_view.tracks_table.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(self._on_track_selection_changed)
        
        # Auto-run diagnosis when track is selected
        self.unified_tracks_view.track_selected.connect(self._on_track_auto_diagnose)
        
        # Add track action buttons below the table
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(5)
        
        # Track-specific action
        self.btn_diagnose = QPushButton("Diagnose Selected Track")
        self.btn_diagnose.setEnabled(False)  # Disabled until a track is selected
        
        buttons_layout.addWidget(self.btn_diagnose)
        buttons_layout.addStretch()
        
        layout.addLayout(buttons_layout)
        
        # Connect signals
        self.btn_diagnose.clicked.connect(self._on_diagnose_clicked)
        
        return widget
    
    def _on_diagnose_clicked(self):
        """Handle diagnose button click - emit signal with selected track ID."""
        # Get selected track from unified tracks view
        selected_indexes = self.unified_tracks_view.tracks_table.selectionModel().selectedRows()
        if not selected_indexes:
            return
        
        # Map proxy index to source index
        proxy_index = selected_indexes[0]
        source_index = self.unified_tracks_view.proxy_model.mapToSource(proxy_index)
        source_row = source_index.row()
        
        # Get track data from source model
        track_data = self.unified_tracks_model.get_row_data(source_row)
        if track_data:
            track_id = track_data.get('id')
            if track_id:
                self.on_diagnose_clicked.emit(track_id)
    
    def _on_track_auto_diagnose(self, track_id: str):
        """Auto-run diagnosis when a track is selected.
        
        Skips execution if a command is currently running.
        
        Args:
            track_id: ID of selected track
        """
        # Don't auto-diagnose if a command is running
        if self._is_running:
            return
        
        if track_id:
            # Emit diagnose signal to run diagnosis in background
            self.on_diagnose_clicked.emit(track_id)
    
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
        """Create the bottom panel with log."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Use LogPanel component
        self.log_panel = LogPanel(title="Log", max_height=200, font_size=9)
        layout.addWidget(self.log_panel)
        
        # Initialize status bar component
        self.status_bar_component = StatusBar(self.statusBar())
        
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
    
    def update_albums(self, albums: List[Dict[str, Any]]):
        """Update albums table.
        
        Args:
            albums: List of album dicts with aggregated statistics
        """
        self.albums_model.set_data(albums)
        # Default sort by playlist count (column 3) descending, then track count (column 2) descending
        self.albums_view.table.sortByColumn(3, Qt.DescendingOrder)
    
    def update_artists(self, artists: List[Dict[str, Any]]):
        """Update artists table.
        
        Args:
            artists: List of artist dicts with aggregated statistics
        """
        self.artists_model.set_data(artists)
        # Default sort by playlist count (column 3) descending, then track count (column 1) descending
        self.artists_view.table.sortByColumn(3, Qt.DescendingOrder)
    
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
        self.status_bar_component.update_stats(counts)
    
    # Log and progress methods
    
    def append_log(self, message: str):
        """Append message to log with ANSI color code stripping.
        
        Args:
            message: Log message (may contain ANSI escape codes)
        """
        # Strip ANSI escape codes for better readability in GUI
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        clean_message = ansi_escape.sub('', message)
        self.log_panel.append(clean_message)
    
    def clear_logs(self):
        """Clear the log window."""
        self.log_panel.clear()
    
    def set_execution_status(self, running: bool, message: str = ""):
        """Set execution status indicator and track running state.
        
        Args:
            running: True if command is running, False if ready
            message: Optional status message (displayed when running)
        """
        self._is_running = running
        self.status_bar_component.set_execution_status(running, message)
    
    # UI state methods
    
    def enable_actions(self, enabled: bool):
        """Enable/disable action buttons (except cancel button).
        
        Args:
            enabled: True to enable, False to disable
        """
        # Toolbar buttons
        self.btn_scan.setEnabled(enabled)
        self.btn_build.setEnabled(enabled)
        self.btn_analyze.setEnabled(enabled)
        self.btn_report.setEnabled(enabled)
        self.btn_watch.setEnabled(enabled)
        # Note: btn_open_reports stays enabled (no CLI execution)
        
        # Playlist action buttons
        self.btn_pull.setEnabled(enabled)
        self.btn_match.setEnabled(enabled)
        self.btn_export.setEnabled(enabled)
        
        # Per-playlist actions only if playlist selected
        if enabled and self._selected_playlist_id:
            self.enable_playlist_actions(True)
        else:
            self.enable_playlist_actions(False)
        
        # Per-track actions
        self.enable_track_actions(enabled)
    
    def enable_playlist_actions(self, enabled: bool):
        """Enable/disable per-playlist action buttons.
        
        Args:
            enabled: True to enable, False to disable
        """
        self.btn_pull_one.setEnabled(enabled)
        self.btn_match_one.setEnabled(enabled)
        self.btn_export_one.setEnabled(enabled)
    
    def enable_track_actions(self, enabled: bool):
        """Enable/disable per-track action buttons.
        
        Args:
            enabled: True to enable, False to disable
        """
        self.btn_diagnose.setEnabled(enabled)
    
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
    
    def _on_track_selection_changed(self, selected, deselected):
        """Handle track selection change.
        
        Args:
            selected: QItemSelection of selected items
            deselected: QItemSelection of deselected items
        """
        # Enable/disable track actions based on selection
        has_selection = self.unified_tracks_view.tracks_table.selectionModel().hasSelection()
        self.enable_track_actions(has_selection)
    
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
    
    def closeEvent(self, event):
        """Handle window close event - save state.
        
        Args:
            event: QCloseEvent
        """
        self._save_window_state()
        super().closeEvent(event)
    
    def _save_window_state(self):
        """Save window geometry, splitter positions, and column widths."""
        # Save window geometry and state
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        
        # Save main splitter position
        self.settings.setValue("mainSplitter", self.main_splitter.saveState())
        
        # Save playlists table column widths
        playlists_header = self.playlists_table_view.horizontalHeader()
        playlists_widths = []
        for col in range(playlists_header.count()):
            playlists_widths.append(playlists_header.sectionSize(col))
        self.settings.setValue("playlistsColumnWidths", playlists_widths)
        
        # Save unified tracks table column widths
        tracks_header = self.unified_tracks_view.tracks_table.horizontalHeader()
        tracks_widths = []
        for col in range(tracks_header.count()):
            tracks_widths.append(tracks_header.sectionSize(col))
        self.settings.setValue("tracksColumnWidths", tracks_widths)
        
        logger.info("Window state saved")
    
    def _restore_window_state(self):
        """Restore window geometry, splitter positions, and column widths."""
        # Restore window geometry and state
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        
        window_state = self.settings.value("windowState")
        if window_state:
            self.restoreState(window_state)
        
        # Restore main splitter position (deferred until after show event)
        splitter_state = self.settings.value("mainSplitter")
        if splitter_state:
            self.main_splitter.restoreState(splitter_state)
        
        # Restore playlists table column widths
        playlists_widths = self.settings.value("playlistsColumnWidths")
        if playlists_widths:
            playlists_header = self.playlists_table_view.horizontalHeader()
            for col, width in enumerate(playlists_widths):
                if col < playlists_header.count():
                    # Convert to int (QSettings may return strings)
                    playlists_header.resizeSection(col, int(width))
        
        # Restore unified tracks table column widths
        tracks_widths = self.settings.value("tracksColumnWidths")
        if tracks_widths:
            tracks_header = self.unified_tracks_view.tracks_table.horizontalHeader()
            for col, width in enumerate(tracks_widths):
                if col < tracks_header.count():
                    # Convert to int (QSettings may return strings)
                    tracks_header.resizeSection(col, int(width))
        
        logger.info("Window state restored")
