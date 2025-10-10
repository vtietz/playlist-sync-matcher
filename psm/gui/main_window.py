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
from .tabs import PlaylistsTab
from .state import FilterStore, FilterState
from .models import (
    PlaylistsModel, PlaylistDetailModel, UnmatchedTracksModel,
    MatchedTracksModel, PlaylistCoverageModel, UnmatchedAlbumsModel,
    LikedTracksModel, UnifiedTracksModel, AlbumsModel, ArtistsModel
)

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window."""
    
    # Signals
    # Legacy signals removed: on_playlist_selected, on_playlist_filter_requested
    # FilterStore is now the single source of truth for filter state
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
        
        # Centralized state flags for button enable/disable logic
        # These flags are the single source of truth for UI state management
        # When adding new conditional buttons, update the corresponding _update_*_state() method
        self._is_running: bool = False          # True when a CLI command is executing
        self._has_track_selection: bool = False  # True when a track is selected in tracks view
        
        # Pending sort states (restored from settings, applied after data loads)
        self._pending_playlists_sort: Optional[tuple] = None  # (column, Qt.SortOrder)
        self._pending_tracks_sort: Optional[tuple] = None
        self._pending_albums_sort: Optional[tuple] = None
        self._pending_artists_sort: Optional[tuple] = None
        
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
        
        # Create FilterStore BEFORE UI (UI components will wire to it)
        self.filter_store = FilterStore(self)
        
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
        main_splitter.setChildrenCollapsible(False)  # Prevent panels from collapsing completely
        main_splitter.setHandleWidth(4)  # Make splitter handle more visible/grabbable
        
        # Left: Playlists master table
        playlists_widget = self._create_playlists_widget()
        main_splitter.addWidget(playlists_widget)
        
        # Right: Tabs and detail
        right_widget = self._create_right_panel()
        main_splitter.addWidget(right_widget)
        
        # Allow user to resize, but set reasonable constraints
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 2)
        
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
        toolbar.setObjectName("actionsToolbar")  # Fix QMainWindow::saveState() warning
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
        
        # Tab 2: Artists (swapped order with Albums)
        artists_tab = self._create_artists_tab()
        tab_widget.addTab(artists_tab, "Artists")
        
        # Tab 3: Albums
        albums_tab = self._create_albums_tab()
        tab_widget.addTab(albums_tab, "Albums")
        
        return tab_widget
    
    def _create_playlists_tab(self) -> QWidget:
        """Create the playlists tab content using PlaylistsTab builder."""
        # Create filter bar and proxy model (still owned by MainWindow for now)
        self.playlist_filter_bar = PlaylistFilterBar()
        self.playlist_filter_bar.filter_changed.connect(self._apply_playlist_filters)
        self.playlist_filter_bar.filter_options_needed.connect(self._populate_playlist_filter_options)
        
        self.playlist_proxy_model = PlaylistProxyModel()
        self.playlist_proxy_model.setSourceModel(self.playlists_model)
        
        # Create playlists tab using builder
        playlists_tab = PlaylistsTab(
            playlists_model=self.playlists_model,
            playlist_proxy_model=self.playlist_proxy_model,
            playlist_filter_bar=self.playlist_filter_bar,
            parent=self
        )
        
        # Store reference to table view for external access
        self.playlists_table_view = playlists_tab.table_view
        
        # Store reference to buttons for external access
        self.btn_pull = playlists_tab.btn_pull
        self.btn_match = playlists_tab.btn_match
        self.btn_export = playlists_tab.btn_export
        self.btn_pull_one = playlists_tab.btn_pull_one
        self.btn_match_one = playlists_tab.btn_match_one
        self.btn_export_one = playlists_tab.btn_export_one
        
        # Connect tab signals to MainWindow signals
        playlists_tab.selection_changed.connect(self._on_playlist_selection_changed)
        playlists_tab.pull_all_clicked.connect(self.on_pull_clicked.emit)
        playlists_tab.match_all_clicked.connect(self.on_match_clicked.emit)
        playlists_tab.export_all_clicked.connect(self.on_export_clicked.emit)
        playlists_tab.pull_one_clicked.connect(self.on_pull_one_clicked.emit)
        playlists_tab.match_one_clicked.connect(self.on_match_one_clicked.emit)
        playlists_tab.export_one_clicked.connect(self.on_export_one_clicked.emit)
        
        # Store tab reference
        self.playlists_tab = playlists_tab
        
        return playlists_tab
    
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
        
        # Wire FilterStore to UnifiedTracksView (single source of truth)
        self.filter_store.filterChanged.connect(self.unified_tracks_view.on_store_filter_changed)
        
        # Wire FilterBar user actions to FilterStore (bidirectional filtering)
        # When user changes filter dropdowns, update FilterStore → emits filterChanged → view updates
        filter_bar = self.unified_tracks_view.filter_bar
        filter_bar.playlist_combo.currentTextChanged.connect(self._on_filterbar_playlist_changed)
        filter_bar.artist_combo.currentTextChanged.connect(self._on_filterbar_artist_changed)
        filter_bar.album_combo.currentTextChanged.connect(self._on_filterbar_album_changed)
        
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
        
        # Apply sort: use pending (restored) sort if available, otherwise default to name ascending
        if self._pending_playlists_sort is not None:
            sort_col, sort_order = self._pending_playlists_sort
            self.playlists_table_view.sortByColumn(sort_col, sort_order)
            self._pending_playlists_sort = None  # Clear after applying
        else:
            # Default sort by name (column 0) alphabetically
            self.playlists_table_view.sortByColumn(0, Qt.AscendingOrder)
        
        # No auto-selection - user can click to select/deselect
    
    def update_albums(self, albums: List[Dict[str, Any]]):
        """Update albums table.
        
        Args:
            albums: List of album dicts with aggregated statistics
        """
        self.albums_model.set_data(albums)
        
        # Apply sort: use pending (restored) sort if available, otherwise default
        if self._pending_albums_sort is not None:
            sort_col, sort_order = self._pending_albums_sort
            self.albums_view.table.sortByColumn(sort_col, sort_order)
            self._pending_albums_sort = None  # Clear after applying
        else:
            # Default sort by playlist count (column 3) descending
            self.albums_view.table.sortByColumn(3, Qt.DescendingOrder)
    
    def update_artists(self, artists: List[Dict[str, Any]]):
        """Update artists table.
        
        Args:
            artists: List of artist dicts with aggregated statistics
        """
        self.artists_model.set_data(artists)
        
        # Apply sort: use pending (restored) sort if available, otherwise default
        if self._pending_artists_sort is not None:
            sort_col, sort_order = self._pending_artists_sort
            self.artists_view.table.sortByColumn(sort_col, sort_order)
            self._pending_artists_sort = None  # Clear after applying
        else:
            # Default sort by playlist count (column 3) descending
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
        # Get playlist names from playlists model
        playlists = []
        for row in range(self.playlists_model.rowCount()):
            playlist_name = self.playlists_model.index(row, 0).data()
            if playlist_name:
                playlists.append(playlist_name)
        
        self.unified_tracks_view.populate_filter_options(playlists, artists, albums, years)
    
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
    
    def set_controller(self, controller):
        """Set controller reference (called by app.py after controller creation).
        
        Args:
            controller: MainController instance
        """
        self._controller = controller
    
    def enable_actions(self, enabled: bool):
        """Enable/disable action buttons (except cancel button).
        
        Args:
            enabled: True to enable, False to disable
        """
        # Update running state
        self._is_running = not enabled
        logger.debug(f"enable_actions called: enabled={enabled}, _is_running={self._is_running}")
        
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
        
        # Per-track actions - use centralized update
        self._update_track_actions_state()
    
    def enable_playlist_actions(self, enabled: bool):
        """Enable/disable per-playlist action buttons.
        
        Args:
            enabled: True to enable, False to disable
        """
        if hasattr(self, 'playlists_tab'):
            self.playlists_tab.enable_playlist_actions(enabled)
        else:
            # Fallback for initialization phase
            if hasattr(self, 'btn_pull_one'):
                self.btn_pull_one.setEnabled(enabled)
            if hasattr(self, 'btn_match_one'):
                self.btn_match_one.setEnabled(enabled)
            if hasattr(self, 'btn_export_one'):
                self.btn_export_one.setEnabled(enabled)
    
    def enable_track_actions(self, enabled: bool):
        """Enable/disable per-track action buttons (DEPRECATED - use _update_track_actions_state).
        
        This method is deprecated in favor of centralized state management.
        Use _update_track_actions_state() which considers both running state and selection.
        
        Args:
            enabled: True to enable, False to disable
        """
        # Legacy method kept for compatibility, but now delegates to state-based update
        # This is called from _on_track_selection_changed with has_selection as argument
        logger.debug(f"enable_track_actions called: enabled={enabled}")
        self._has_track_selection = enabled
        self._update_track_actions_state()
    
    def _update_track_actions_state(self):
        """Update track action button states based on centralized state.
        
        Track actions should only be enabled when:
        1. No action is running (not _is_running)
        2. AND a track is selected (_has_track_selection)
        
        This is the single source of truth for track action button states.
        """
        should_enable = not self._is_running and self._has_track_selection
        logger.debug(f"Updating track actions: _is_running={self._is_running}, _has_track_selection={self._has_track_selection}, should_enable={should_enable}")
        self.btn_diagnose.setEnabled(should_enable)
    
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
        
        UI-only handler: Tracks selection state and enables/disables buttons.
        Does NOT publish to FilterStore - controller handles that via direct signal connection.
        
        Args:
            selected: QItemSelection of selected items
            deselected: QItemSelection of deselected items
        """
        # Extract playlist data directly from 'selected' parameter to avoid timing issues
        # Qt provides both 'selected' and 'deselected' specifically so we don't need to
        # query the selection model, which may not be fully updated when this signal fires
        
        if selected.isEmpty():
            # No selection - track state and disable actions
            self._selected_playlist_id = None
            self.enable_playlist_actions(False)
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
        
        # Track selected playlist ID for per-playlist actions (Pull Selected, etc.)
        self._selected_playlist_id = playlist_data.get('id')
        
        # Enable per-playlist actions
        self.enable_playlist_actions(True)
        
        # Note: Controller directly subscribes to PlaylistsTab.selection_changed
        # and publishes to FilterStore asynchronously. No signals emitted here.
    
    def _on_filterbar_playlist_changed(self, playlist_name: str):
        """Handle user changing playlist filter in FilterBar.
        
        Args:
            playlist_name: Selected playlist name (or "All Playlists")
        """
        if playlist_name == "All Playlists" or not playlist_name:
            # Clear playlist filter
            self.filter_store.clear()
        else:
            # User selected a playlist from FilterBar - need to fetch track IDs
            # This triggers async load in controller (will be implemented in Step 6)
            # For now, synchronous (freeze still occurs)
            logger.debug(f"FilterBar playlist changed to: {playlist_name}")
            # Delegate to controller which will fetch track IDs and publish to FilterStore
            if hasattr(self, '_controller'):
                self._controller.set_playlist_filter(playlist_name)
    
    def _on_filterbar_artist_changed(self, artist_name: str):
        """Handle user changing artist filter in FilterBar.
        
        Args:
            artist_name: Selected artist name (or "All Artists")
        """
        if artist_name == "All Artists" or not artist_name:
            # Clear artist filter (but keep playlist if set)
            # If playlist is active, don't clear it; if artist/album was active, clear it
            current_state = self.filter_store.state
            if current_state.active_dimension in ("artist", "album"):
                self.filter_store.clear()
        else:
            # Set artist filter (clears playlist filter per one-dimension rule)
            logger.debug(f"FilterBar artist changed to: {artist_name}")
            self.filter_store.set_artist(artist_name)
    
    def _on_filterbar_album_changed(self, album_name: str):
        """Handle user changing album filter in FilterBar.
        
        Args:
            album_name: Selected album name (or "All Albums")
        """
        if album_name == "All Albums" or not album_name:
            # Clear album filter (but keep artist if set)
            current_state = self.filter_store.state
            if current_state.active_dimension == "artist" and current_state.artist_name:
                # Keep artist-only filter
                self.filter_store.set_artist(current_state.artist_name)
            else:
                self.filter_store.clear()
        else:
            # Need artist context to set album filter
            # Get current artist selection from FilterBar
            artist_name = self.unified_tracks_view.filter_bar.get_artist_filter()
            if artist_name and artist_name != "All Artists":
                logger.debug(f"FilterBar album changed to: {album_name} (artist: {artist_name})")
                self.filter_store.set_album(album_name, artist_name)
            else:
                # No artist selected - album filter alone not supported (need artist context)
                logger.warning(f"Album filter '{album_name}' requires artist selection - ignoring")
    
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
        """Save window geometry, splitter positions, column widths, and sort states."""
        # Save window geometry and state
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        
        # Save main splitter position
        self.settings.setValue("mainSplitter", self.main_splitter.saveState())
        
        # Save playlists table column widths and sort state
        playlists_header = self.playlists_table_view.horizontalHeader()
        playlists_widths = []
        for col in range(playlists_header.count()):
            playlists_widths.append(playlists_header.sectionSize(col))
        self.settings.setValue("playlistsColumnWidths", playlists_widths)
        self.settings.setValue("playlistsSortColumn", playlists_header.sortIndicatorSection())
        self.settings.setValue("playlistsSortOrder", int(playlists_header.sortIndicatorOrder()))
        
        # Save unified tracks table column widths and sort state
        tracks_header = self.unified_tracks_view.tracks_table.horizontalHeader()
        tracks_widths = []
        for col in range(tracks_header.count()):
            tracks_widths.append(tracks_header.sectionSize(col))
        self.settings.setValue("tracksColumnWidths", tracks_widths)
        self.settings.setValue("tracksSortColumn", tracks_header.sortIndicatorSection())
        self.settings.setValue("tracksSortOrder", int(tracks_header.sortIndicatorOrder()))
        
        # Save albums table column widths and sort state
        if hasattr(self, 'albums_view'):
            albums_header = self.albums_view.table.horizontalHeader()
            albums_widths = []
            for col in range(albums_header.count()):
                albums_widths.append(albums_header.sectionSize(col))
            self.settings.setValue("albumsColumnWidths", albums_widths)
            self.settings.setValue("albumsSortColumn", albums_header.sortIndicatorSection())
            self.settings.setValue("albumsSortOrder", int(albums_header.sortIndicatorOrder()))
        
        # Save artists table column widths and sort state
        if hasattr(self, 'artists_view'):
            artists_header = self.artists_view.table.horizontalHeader()
            artists_widths = []
            for col in range(artists_header.count()):
                artists_widths.append(artists_header.sectionSize(col))
            self.settings.setValue("artistsColumnWidths", artists_widths)
            self.settings.setValue("artistsSortColumn", artists_header.sortIndicatorSection())
            self.settings.setValue("artistsSortOrder", int(artists_header.sortIndicatorOrder()))
        
        logger.info("Window state saved")
    
    def _restore_window_state(self):
        """Restore window geometry, splitter positions, column widths, and sort states."""
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
        
        # Restore playlists table column widths and sort state
        playlists_widths = self.settings.value("playlistsColumnWidths")
        if playlists_widths:
            playlists_header = self.playlists_table_view.horizontalHeader()
            for col, width in enumerate(playlists_widths):
                if col < playlists_header.count():
                    # Convert to int (QSettings may return strings)
                    playlists_header.resizeSection(col, int(width))
        
        # Restore playlists sort state (must happen after data is loaded)
        playlists_sort_col = self.settings.value("playlistsSortColumn")
        playlists_sort_order = self.settings.value("playlistsSortOrder")
        if playlists_sort_col is not None and playlists_sort_order is not None:
            # Store for later application (after data load)
            self._pending_playlists_sort = (int(playlists_sort_col), Qt.SortOrder(int(playlists_sort_order)))
        
        # Restore unified tracks table column widths
        tracks_widths = self.settings.value("tracksColumnWidths")
        if tracks_widths:
            tracks_header = self.unified_tracks_view.tracks_table.horizontalHeader()
            for col, width in enumerate(tracks_widths):
                if col < tracks_header.count():
                    # Convert to int (QSettings may return strings)
                    tracks_header.resizeSection(col, int(width))
        
        # Restore tracks sort state (stored for application after data load)
        tracks_sort_col = self.settings.value("tracksSortColumn")
        tracks_sort_order = self.settings.value("tracksSortOrder")
        if tracks_sort_col is not None and tracks_sort_order is not None:
            self._pending_tracks_sort = (int(tracks_sort_col), Qt.SortOrder(int(tracks_sort_order)))
        
        # Restore albums table column widths and sort state
        albums_widths = self.settings.value("albumsColumnWidths")
        if albums_widths and hasattr(self, 'albums_view'):
            albums_header = self.albums_view.table.horizontalHeader()
            for col, width in enumerate(albums_widths):
                if col < albums_header.count():
                    # Convert to int (QSettings may return strings)
                    albums_header.resizeSection(col, int(width))
        
        albums_sort_col = self.settings.value("albumsSortColumn")
        albums_sort_order = self.settings.value("albumsSortOrder")
        if albums_sort_col is not None and albums_sort_order is not None:
            self._pending_albums_sort = (int(albums_sort_col), Qt.SortOrder(int(albums_sort_order)))
        
        # Restore artists table column widths and sort state
        artists_widths = self.settings.value("artistsColumnWidths")
        if artists_widths and hasattr(self, 'artists_view'):
            artists_header = self.artists_view.table.horizontalHeader()
            for col, width in enumerate(artists_widths):
                if col < artists_header.count():
                    # Convert to int (QSettings may return strings)
                    artists_header.resizeSection(col, int(width))
        
        artists_sort_col = self.settings.value("artistsSortColumn")
        artists_sort_order = self.settings.value("artistsSortOrder")
        if artists_sort_col is not None and artists_sort_order is not None:
            self._pending_artists_sort = (int(artists_sort_col), Qt.SortOrder(int(artists_sort_order)))
        
        logger.info("Window state restored")
