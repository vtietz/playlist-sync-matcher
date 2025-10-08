"""Main window for the GUI application.

Assembles all UI components: master-detail playlists, report tabs,
action buttons, watch toggle, progress bar, and log window.
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTableView, QTabWidget, QPushButton, QTextEdit, QProgressBar,
    QLabel, QGroupBox, QMessageBox, QToolBar
)
from PySide6.QtCore import Qt, Signal, QModelIndex
import logging

from .models import (
    PlaylistsModel, PlaylistDetailModel, UnmatchedTracksModel,
    MatchedTracksModel, PlaylistCoverageModel, UnmatchedAlbumsModel,
    LikedTracksModel
)

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window."""
    
    # Signals
    on_playlist_selected = Signal(str)  # playlist_id
    on_pull_clicked = Signal()
    on_scan_clicked = Signal()
    on_match_clicked = Signal()
    on_export_clicked = Signal()
    on_report_clicked = Signal()
    on_build_clicked = Signal()
    on_pull_one_clicked = Signal()
    on_match_one_clicked = Signal()
    on_export_one_clicked = Signal()
    on_watch_toggled = Signal(bool)
    on_tab_changed = Signal(str)
    
    def __init__(self):
        """Initialize main window."""
        super().__init__()
        
        self.setWindowTitle("Playlist Sync Matcher")
        self.resize(1400, 900)
        
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
        
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 3)
        
        layout.addWidget(main_splitter)
        
        # Bottom: Log and progress
        bottom_widget = self._create_bottom_panel()
        layout.addWidget(bottom_widget)
        
        layout.setStretch(0, 3)
        layout.setStretch(1, 1)
    
    def _create_toolbar(self):
        """Create the action toolbar."""
        toolbar = QToolBar("Actions")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        # Global actions
        self.btn_pull = QPushButton("Pull All")
        self.btn_scan = QPushButton("Scan Library")
        self.btn_match = QPushButton("Match All")
        self.btn_export = QPushButton("Export All")
        self.btn_report = QPushButton("Generate Reports")
        self.btn_build = QPushButton("Build")
        
        # Watch mode toggle
        self.btn_watch = QPushButton("Start Watch Mode")
        self.btn_watch.setCheckable(True)
        
        # Per-playlist actions
        self.btn_pull_one = QPushButton("Pull Selected")
        self.btn_match_one = QPushButton("Match Selected")
        self.btn_export_one = QPushButton("Export Selected")
        
        # Add to toolbar
        toolbar.addWidget(self.btn_pull)
        toolbar.addWidget(self.btn_scan)
        toolbar.addWidget(self.btn_match)
        toolbar.addWidget(self.btn_export)
        toolbar.addWidget(self.btn_report)
        toolbar.addWidget(self.btn_build)
        toolbar.addSeparator()
        toolbar.addWidget(self.btn_pull_one)
        toolbar.addWidget(self.btn_match_one)
        toolbar.addWidget(self.btn_export_one)
        toolbar.addSeparator()
        toolbar.addWidget(self.btn_watch)
        
        # Initially disable per-playlist actions
        self.enable_playlist_actions(False)
        
        # Connect signals
        self.btn_pull.clicked.connect(self.on_pull_clicked.emit)
        self.btn_scan.clicked.connect(self.on_scan_clicked.emit)
        self.btn_match.clicked.connect(self.on_match_clicked.emit)
        self.btn_export.clicked.connect(self.on_export_clicked.emit)
        self.btn_report.clicked.connect(self.on_report_clicked.emit)
        self.btn_build.clicked.connect(self.on_build_clicked.emit)
        
        self.btn_pull_one.clicked.connect(self.on_pull_one_clicked.emit)
        self.btn_match_one.clicked.connect(self.on_match_one_clicked.emit)
        self.btn_export_one.clicked.connect(self.on_export_one_clicked.emit)
        
        self.btn_watch.toggled.connect(self._on_watch_button_toggled)
    
    def _create_playlists_widget(self) -> QWidget:
        """Create the playlists master table widget."""
        group = QGroupBox("Playlists")
        layout = QVBoxLayout(group)
        
        self.playlists_table = QTableView()
        self.playlists_table.setModel(self.playlists_model)
        self.playlists_table.setSelectionBehavior(QTableView.SelectRows)
        self.playlists_table.setSelectionMode(QTableView.SingleSelection)
        self.playlists_table.selectionModel().selectionChanged.connect(
            self._on_playlist_selection_changed
        )
        
        layout.addWidget(self.playlists_table)
        
        return group
    
    def _create_right_panel(self) -> QWidget:
        """Create the right panel with tabs."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Tabs for different views
        self.tabs = QTabWidget()
        
        # Playlist detail tab
        detail_widget = self._create_playlist_detail_widget()
        self.tabs.addTab(detail_widget, "Playlist Detail")
        
        # Unmatched tracks tab
        unmatched_widget = self._create_table_widget(
            self.unmatched_tracks_model, 
            "Unmatched Tracks"
        )
        self.tabs.addTab(unmatched_widget, "Unmatched Tracks")
        
        # Matched tracks tab
        matched_widget = self._create_table_widget(
            self.matched_tracks_model, 
            "Matched Tracks"
        )
        self.tabs.addTab(matched_widget, "Matched Tracks")
        
        # Coverage tab
        coverage_widget = self._create_table_widget(
            self.coverage_model, 
            "Playlist Coverage"
        )
        self.tabs.addTab(coverage_widget, "Coverage")
        
        # Unmatched albums tab
        albums_widget = self._create_table_widget(
            self.unmatched_albums_model, 
            "Unmatched Albums"
        )
        self.tabs.addTab(albums_widget, "Unmatched Albums")
        
        # Liked tracks tab
        liked_widget = self._create_table_widget(
            self.liked_tracks_model, 
            "Liked Tracks"
        )
        self.tabs.addTab(liked_widget, "Liked Tracks")
        
        self.tabs.currentChanged.connect(self._on_tab_index_changed)
        
        layout.addWidget(self.tabs)
        
        return widget
    
    def _create_playlist_detail_widget(self) -> QWidget:
        """Create the playlist detail widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.detail_label = QLabel("Select a playlist to view details")
        layout.addWidget(self.detail_label)
        
        self.detail_table = QTableView()
        self.detail_table.setModel(self.playlist_detail_model)
        layout.addWidget(self.detail_table)
        
        return widget
    
    def _create_table_widget(self, model, title: str) -> QWidget:
        """Create a generic table widget.
        
        Args:
            model: Table model
            title: Widget title
            
        Returns:
            Widget with table
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        table = QTableView()
        table.setModel(model)
        table.setSelectionBehavior(QTableView.SelectRows)
        
        layout.addWidget(table)
        
        return widget
    
    def _create_bottom_panel(self) -> QWidget:
        """Create the bottom panel with log and progress."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Progress bar
        progress_layout = QHBoxLayout()
        self.progress_label = QLabel("Ready")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        
        layout.addLayout(progress_layout)
        
        # Log window
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setObjectName("logWindow")  # For stylesheet targeting
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        
        log_layout.addWidget(self.log_text)
        
        layout.addWidget(log_group)
        
        # Status bar
        self.status_label = QLabel("Ready")
        self.statusBar().addWidget(self.status_label)
        
        return widget
    
    # Data update methods
    
    def update_playlists(self, playlists: List[Dict[str, Any]]):
        """Update playlists table.
        
        Args:
            playlists: List of playlist dicts
        """
        self.playlists_model.set_data(playlists)
        self.playlists_table.resizeColumnsToContents()
    
    def update_playlist_detail(self, tracks: List[Dict[str, Any]]):
        """Update playlist detail table.
        
        Args:
            tracks: List of track dicts
        """
        self.playlist_detail_model.set_data(tracks)
        self.detail_table.resizeColumnsToContents()
        
        # Update detail label
        if self._selected_playlist_id:
            self.detail_label.setText(
                f"Playlist: {self._selected_playlist_id} ({len(tracks)} tracks)"
            )
    
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
        self.log_text.append(message)
        # Auto-scroll to bottom
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
    
    def clear_logs(self):
        """Clear the log window."""
        self.log_text.clear()
    
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
    
    def get_current_tab(self) -> str:
        """Get current tab name.
        
        Returns:
            Tab name
        """
        index = self.tabs.currentIndex()
        tab_names = [
            'playlist_detail',
            'unmatched_tracks',
            'matched_tracks',
            'coverage',
            'unmatched_albums',
            'liked',
        ]
        if 0 <= index < len(tab_names):
            return tab_names[index]
        return 'unknown'
    
    # Event handlers
    
    def _on_playlist_selection_changed(self, selected, deselected):
        """Handle playlist selection change.
        
        Args:
            selected: QItemSelection of selected items
            deselected: QItemSelection of deselected items
        """
        selection = self.playlists_table.selectionModel()
        if selection.hasSelection():
            row = selection.selectedRows()[0].row()
            playlist_data = self.playlists_model.get_row_data(row)
            if playlist_data:
                self._selected_playlist_id = playlist_data.get('id')
                if self._selected_playlist_id:
                    self.on_playlist_selected.emit(self._selected_playlist_id)
    
    def _on_tab_index_changed(self, index: int):
        """Handle tab change.
        
        Args:
            index: New tab index
        """
        tab_name = self.get_current_tab()
        self.on_tab_changed.emit(tab_name)
    
    def _on_watch_button_toggled(self, checked: bool):
        """Handle watch button toggle.
        
        Args:
            checked: True if checked
        """
        self.on_watch_toggled.emit(checked)
