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
    QLabel, QMessageBox, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QItemSelectionModel
from PySide6.QtGui import QFont
import logging

from .components import SortFilterTable
from .components.actions_toolbar import ActionsToolbar
from .components.link_delegate import LinkDelegate
from .components.folder_delegate import FolderDelegate
from .components.playlist_filter_bar import PlaylistFilterBar
from .components.playlist_proxy_model import PlaylistProxyModel
from .panels import BottomPanel, LeftPanel, TracksPanel
from .state import FilterStore
from .window_state_manager import WindowStateManager
from .filters_controller import FiltersController
from .ui_state_controller import UiStateController
from .model_coordinator import ModelCoordinator

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
    on_refresh_clicked = Signal()  # NEW: Manual refresh
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
        
        # State manager for persistent window state
        self.state_manager = WindowStateManager("vtietz", "PlaylistSyncMatcher")
        
        self.setWindowTitle("Playlist Sync Matcher")
        self.resize(1400, 900)
        self.setMinimumSize(800, 600)  # Allow reducing window size to reasonable minimum
        
        # Track selected playlist
        self._selected_playlist_id: Optional[str] = None
        
        # Create ModelCoordinator to manage all table models
        self.model_coordinator = ModelCoordinator(self)
        
        # Create FilterStore BEFORE UI (UI components will wire to it)
        self.filter_store = FilterStore(self)
        
        # Create FiltersController to manage filter operations
        self.filters_controller = FiltersController(self.filter_store)
        
        # Build UI
        self._create_ui()
        
        # Restore window state after UI is created
        self._restore_window_state()
    
    # ----- Model Property Accessors (for backward compatibility) -----
    
    @property
    def playlists_model(self):
        """Access playlists model via coordinator."""
        return self.model_coordinator.playlists_model
    
    @property
    def playlist_detail_model(self):
        """Access playlist detail model via coordinator."""
        return self.model_coordinator.playlist_detail_model
    
    @property
    def unmatched_tracks_model(self):
        """Access unmatched tracks model via coordinator."""
        return self.model_coordinator.unmatched_tracks_model
    
    @property
    def matched_tracks_model(self):
        """Access matched tracks model via coordinator."""
        return self.model_coordinator.matched_tracks_model
    
    @property
    def coverage_model(self):
        """Access coverage model via coordinator."""
        return self.model_coordinator.coverage_model
    
    @property
    def unmatched_albums_model(self):
        """Access unmatched albums model via coordinator."""
        return self.model_coordinator.unmatched_albums_model
    
    @property
    def liked_tracks_model(self):
        """Access liked tracks model via coordinator."""
        return self.model_coordinator.liked_tracks_model
    
    @property
    def unified_tracks_model(self):
        """Access unified tracks model via coordinator."""
        return self.model_coordinator.unified_tracks_model
    
    @property
    def albums_model(self):
        """Access albums model via coordinator."""
        return self.model_coordinator.albums_model
    
    @property
    def artists_model(self):
        """Access artists model via coordinator."""
        return self.model_coordinator.artists_model
    
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
        
        # Set explicit size constraints to allow flexible resizing
        # This allows the splitter to resize beyond the table's "preferred" width
        main_splitter.setCollapsible(0, False)  # Left panel shouldn't collapse completely
        main_splitter.setCollapsible(1, False)  # Right panel shouldn't collapse completely
        
        # Store reference for later size adjustments
        self.main_splitter = main_splitter
        
        layout.addWidget(main_splitter)
        
        # Bottom: Log and status bar
        bottom_widget = self._create_bottom_panel()
        layout.addWidget(bottom_widget)
        
        # Connect cancel button (after bottom panel is created)
        self.bottom_panel.connect_cancel(self.on_cancel_clicked.emit)
        
        layout.setStretch(0, 3)
        layout.setStretch(1, 1)
        
        # Create UiStateController after all UI components are created
        # This controller manages button enable/disable state based on application state
        self.ui_state = UiStateController(
            toolbar=self.toolbar,
            playlists_tab=self.playlists_tab,
            btn_diagnose=self.btn_diagnose
        )
        
        # Wire up ModelCoordinator with views for sorting/resizing
        self.model_coordinator.set_views(
            playlists_table=self.playlists_table_view,
            albums_view=self.albums_view,
            artists_view=self.artists_view,
            unified_tracks_view=self.unified_tracks_view
        )
    
    def _create_toolbar(self):
        """Create the action toolbar for general actions."""
        self.toolbar = ActionsToolbar(self)
        self.addToolBar(self.toolbar)
        
        # Connect toolbar signals to MainWindow public signals
        self.toolbar.buildClicked.connect(self.on_build_clicked.emit)
        self.toolbar.pullClicked.connect(self.on_pull_clicked.emit)
        self.toolbar.scanClicked.connect(self.on_scan_clicked.emit)
        self.toolbar.matchClicked.connect(self.on_match_clicked.emit)
        self.toolbar.reportClicked.connect(self.on_report_clicked.emit)
        self.toolbar.exportClicked.connect(self.on_export_clicked.emit)
        self.toolbar.openReportsClicked.connect(self.on_open_reports_clicked.emit)
        self.toolbar.refreshClicked.connect(self.on_refresh_clicked.emit)
        self.toolbar.watchToggled.connect(self._on_watch_button_toggled)
    
    def _create_playlists_widget(self) -> QWidget:
        """Create the left panel with tabs for Playlists, Albums, and Artists."""
        # Create filter bar and proxy model (still owned by MainWindow for now)
        self.playlist_filter_bar = PlaylistFilterBar()
        self.playlist_filter_bar.filter_changed.connect(self._apply_playlist_filters)
        self.playlist_filter_bar.filter_options_needed.connect(self._populate_playlist_filter_options)
        
        self.playlist_proxy_model = PlaylistProxyModel()
        self.playlist_proxy_model.setSourceModel(self.playlists_model)
        
        # Create left panel
        self.left_panel = LeftPanel(
            self.playlists_model,
            self.albums_model,
            self.artists_model,
            self.playlist_proxy_model,
            self.playlist_filter_bar,
            self
        )
        
        # Store references for external access (maintain compatibility)
        self.playlists_table_view = self.left_panel.playlists_table_view
        self.playlists_tab = self.left_panel.playlists_tab
        self.albums_view = self.left_panel.albums_view
        self.artists_view = self.left_panel.artists_view
        self.btn_pull_one = self.left_panel.btn_pull_one
        self.btn_match_one = self.left_panel.btn_match_one
        self.btn_export_one = self.left_panel.btn_export_one
        
        # Connect panel signals to MainWindow handlers
        self.left_panel.playlist_selection_changed.connect(self._on_playlist_selection_changed)
        self.left_panel.pull_one_clicked.connect(self.on_pull_one_clicked.emit)
        self.left_panel.match_one_clicked.connect(self.on_match_one_clicked.emit)
        self.left_panel.export_one_clicked.connect(self.on_export_one_clicked.emit)
        
        return self.left_panel
    
    def _create_right_panel(self) -> QWidget:
        """Create the right panel with tabs for Tracks."""
        # Create tab widget
        tab_widget = QTabWidget()
        tab_widget.setObjectName("rightTabs")
        
        # Set minimum width to allow more flexible splitter resizing
        # This overrides Qt's calculated minimum based on table columns
        tab_widget.setMinimumWidth(200)
        
        # Tab 1: Tracks
        tracks_tab = self._create_tracks_tab()
        tab_widget.addTab(tracks_tab, "Tracks")
        
        return tab_widget
    
    def _create_tracks_tab(self) -> QWidget:
        """Create the tracks tab content."""
        # Create TracksPanel (encapsulates UnifiedTracksView + diagnose button)
        self.tracks_panel = TracksPanel(
            self.unified_tracks_model,
            self.filter_store,
            self
        )
        
        # Store references to child components for backward compatibility
        self.unified_tracks_view = self.tracks_panel.unified_tracks_view
        self.btn_diagnose = self.tracks_panel.btn_diagnose
        
        # Wire FilterBar user actions to FilterStore (bidirectional filtering)
        # When user changes filter dropdowns, update FilterStore → emits filterChanged → view updates
        filter_bar = self.tracks_panel.filter_bar
        filter_bar.playlist_combo.currentTextChanged.connect(self._on_filterbar_playlist_changed)
        filter_bar.artist_combo.currentTextChanged.connect(self._on_filterbar_artist_changed)
        filter_bar.album_combo.currentTextChanged.connect(self._on_filterbar_album_changed)
        
        # Connect panel signals
        self.tracks_panel.selection_changed.connect(self._on_track_selection_changed)
        self.tracks_panel.track_selected.connect(self._on_track_auto_diagnose)
        self.tracks_panel.diagnose_clicked.connect(self.on_diagnose_clicked.emit)
        
        return self.tracks_panel
    
    def _on_track_auto_diagnose(self, track_id: str):
        """Auto-run diagnosis when a track is selected.
        
        Skips execution if a command is currently running.
        
        Args:
            track_id: ID of selected track
        """
        # Don't auto-diagnose if a command is running
        if self.ui_state.is_running:
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
        """Create the bottom panel with log and status."""
        self.bottom_panel = BottomPanel(self.statusBar(), self)
        return self.bottom_panel
    
    # Data update methods
    
    def update_playlists(self, playlists: List[Dict[str, Any]]):
        """Update playlists table.
        
        Args:
            playlists: List of playlist dicts
        """
        self.model_coordinator.update_playlists(playlists)
    
    def update_albums(self, albums: List[Dict[str, Any]]):
        """Update albums table.
        
        Args:
            albums: List of album dicts with aggregated statistics
        """
        self.model_coordinator.update_albums(albums)
    
    def update_artists(self, artists: List[Dict[str, Any]]):
        """Update artists table.
        
        Args:
            artists: List of artist dicts with aggregated statistics
        """
        self.model_coordinator.update_artists(artists)
    
    def update_unmatched_tracks(self, tracks: List[Dict[str, Any]]):
        """Update unmatched tracks table."""
        self.model_coordinator.update_unmatched_tracks(tracks)
    
    def update_matched_tracks(self, tracks: List[Dict[str, Any]]):
        """Update matched tracks table."""
        self.model_coordinator.update_matched_tracks(tracks)
    
    def update_coverage(self, coverage: List[Dict[str, Any]]):
        """Update coverage table."""
        self.model_coordinator.update_coverage(coverage)
    
    def update_unmatched_albums(self, albums: List[Dict[str, Any]]):
        """Update unmatched albums table."""
        self.model_coordinator.update_unmatched_albums(albums)
    
    def update_liked_tracks(self, tracks: List[Dict[str, Any]]):
        """Update liked tracks table."""
        self.model_coordinator.update_liked_tracks(tracks)
    
    def update_unified_tracks(self, tracks: List[Dict[str, Any]], playlists: List[Dict[str, Any]]):
        """Update unified tracks view with data and filter options.
        
        Args:
            tracks: List of all tracks with metadata
            playlists: List of playlists (no longer used - kept for compatibility)
        """
        self.model_coordinator.update_unified_tracks(tracks, playlists)
    
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
        self.bottom_panel.update_stats(counts)
    
    # Log and progress methods
    
    def append_log(self, message: str):
        """Append message to log with ANSI color code stripping.
        
        Args:
            message: Log message (may contain ANSI escape codes)
        """
        self.bottom_panel.append_log(message)
    
    def clear_logs(self):
        """Clear the log window."""
        self.bottom_panel.clear_logs()
    
    def set_execution_status(self, running: bool, message: str = ""):
        """Set execution status indicator and track running state.
        
        Args:
            running: True if command is running, False if ready
            message: Optional status message (displayed when running)
        """
        # Delegate to UiStateController
        self.ui_state.set_running(running)
        self.ui_state.update_all_states()
        
        # Update status display
        self.bottom_panel.set_execution_status(running, message)
    
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
        # Delegate to UiStateController
        self.ui_state.enable_actions(enabled)
    
    def enable_playlist_actions(self, enabled: bool):
        """Enable/disable per-playlist action buttons.
        
        Args:
            enabled: True to enable, False to disable
        """
        # Delegate to playlists_tab (UiStateController also manages this)
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
        """Enable/disable per-track action buttons.
        
        Args:
            enabled: True to enable, False to disable
        """
        # Delegate to UiStateController
        self.ui_state.on_track_selection_changed(enabled)
    
    def set_watch_mode(self, enabled: bool):
        """Set watch mode state.
        
        Args:
            enabled: True if watch mode enabled
        """
        # Delegate to toolbar component
        self.toolbar.setWatchMode(enabled)
    
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
        
        import logging
        logger = logging.getLogger(__name__)
        
        if selected.isEmpty():
            # No selection - update state and disable actions
            logger.debug("Playlist selection cleared")
            self._selected_playlist_id = None
            self.ui_state.on_playlist_selected(None)
            return
        
        proxy_indexes = selected.indexes()
        if not proxy_indexes:
            logger.debug("No proxy indexes in selection")
            return
        
        # Find index for column 0 (we need the first column for row data)
        proxy_index = None
        for idx in proxy_indexes:
            if idx.column() == 0:
                proxy_index = idx
                break
        
        if not proxy_index:
            logger.debug("No column 0 index found in selection")
            return
        
        # Map proxy index to source model
        source_index = self.playlist_proxy_model.mapToSource(proxy_index)
        source_row = source_index.row()
        
        # Get row data from source model
        playlist_data = self.playlists_model.get_row_data(source_row)
        
        if not playlist_data:
            logger.debug(f"No playlist data for source row {source_row}")
            return
        
        # Track selected playlist ID and update UI state
        playlist_id = playlist_data.get('id')
        logger.info(f"Playlist selected: {playlist_id} ({playlist_data.get('name', 'Unknown')})")
        self._selected_playlist_id = playlist_id
        self.ui_state.on_playlist_selected(playlist_id)
        
        # Note: Controller directly subscribes to PlaylistsTab.selection_changed
        # and publishes to FilterStore asynchronously. No signals emitted here.
    
    def _on_filterbar_playlist_changed(self, playlist_name: str):
        """Handle user changing playlist filter in FilterBar.
        
        Args:
            playlist_name: Selected playlist name (or "All Playlists")
        """
        # Delegate to filters controller
        if hasattr(self, '_controller'):
            # If controller exists, pass it to handle async loading
            self.filters_controller.handle_playlist_filter_change(
                playlist_name,
                lambda name: self._controller.set_playlist_filter(name)
            )
        else:
            # No controller yet, synchronous handling
            self.filters_controller.handle_playlist_filter_change(playlist_name)
    
    def _on_filterbar_artist_changed(self, artist_name: str):
        """Handle user changing artist filter in FilterBar.
        
        Args:
            artist_name: Selected artist name (or "All Artists")
        """
        self.filters_controller.handle_artist_filter_change(artist_name)
    
    def _on_filterbar_album_changed(self, album_name: str):
        """Handle user changing album filter in FilterBar.
        
        Args:
            album_name: Selected album name (or "All Albums")
        """
        # Get current artist selection from FilterBar for context
        artist_name = self.unified_tracks_view.filter_bar.get_artist_filter()
        self.filters_controller.handle_album_filter_change(album_name, artist_name)
    
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
        # Collect all table headers
        table_headers = {
            "playlists": self.playlists_table_view.horizontalHeader(),
            "tracks": self.unified_tracks_view.tracks_table.horizontalHeader(),
        }
        
        # Add albums and artists headers if they exist
        if hasattr(self, 'albums_view'):
            table_headers["albums"] = self.albums_view.table.horizontalHeader()
        if hasattr(self, 'artists_view'):
            table_headers["artists"] = self.artists_view.table.horizontalHeader()
        
        # Save all state using state manager
        self.state_manager.save_all_window_state(self, self.main_splitter, table_headers)
    
    def _restore_window_state(self):
        """Restore window geometry, splitter positions, column widths, and sort states."""
        # Collect all table headers
        table_headers = {
            "playlists": self.playlists_table_view.horizontalHeader(),
            "tracks": self.unified_tracks_view.tracks_table.horizontalHeader(),
        }
        
        # Add albums and artists headers if they exist
        if hasattr(self, 'albums_view'):
            table_headers["albums"] = self.albums_view.table.horizontalHeader()
        if hasattr(self, 'artists_view'):
            table_headers["artists"] = self.artists_view.table.horizontalHeader()
        
        # Restore all state using state manager
        pending_sorts = self.state_manager.restore_all_window_state(
            self, self.main_splitter, table_headers
        )
        
        # Store pending sorts in ModelCoordinator for application after data load
        if "playlists" in pending_sorts:
            col, order = pending_sorts["playlists"]
            self.model_coordinator.set_pending_playlists_sort(col, order)
        if "tracks" in pending_sorts:
            col, order = pending_sorts["tracks"]
            self.model_coordinator.set_pending_tracks_sort(col, order)
        if "albums" in pending_sorts:
            col, order = pending_sorts["albums"]
            self.model_coordinator.set_pending_albums_sort(col, order)
        if "artists" in pending_sorts:
            col, order = pending_sorts["artists"]
            self.model_coordinator.set_pending_artists_sort(col, order)

