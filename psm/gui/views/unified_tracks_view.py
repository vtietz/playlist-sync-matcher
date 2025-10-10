"""Unified tracks view combining filter bar and sortable table.

This view composition demonstrates the architecture guidelines:
- FilterBar component for user filtering inputs
- Custom proxy model for multi-criteria filtering
- SortFilterTable component for data display
- Clean signals-based communication
- No business logic (just UI composition)
- Lazy playlist loading for performance
"""
from __future__ import annotations
from typing import Optional, List, Dict, Any, Callable, Set
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Signal, Qt, QTimer, QPoint, QSignalBlocker
from PySide6.QtGui import QFont
import logging

from ..components import FilterBar, UnifiedTracksProxyModel
from ..components.link_delegate import LinkDelegate
from ..components.folder_delegate import FolderDelegate
from ..models import BaseTableModel
from PySide6.QtWidgets import QTableView, QHeaderView

logger = logging.getLogger(__name__)


class UnifiedTracksView(QWidget):
    """Unified view for all tracks with filtering capabilities.
    
    This view composes:
    - FilterBar for status/search filtering
    - Custom proxy model for playlist/status/search filtering
    - QTableView for displaying filtered tracks
    
    The view is purely compositional - it doesn't contain business logic,
    just wires filter changes to proxy model methods.
    
    Playlist filtering is handled externally via set_playlist_filter().
    
    Example:
        model = UnifiedTracksModel()
        view = UnifiedTracksView(model)
        view.set_playlist_filter("My Playlist")
    """
    
    # Signal emitted when a track is selected
    track_selected = Signal(str)  # track_id
    
    def __init__(
        self,
        source_model: BaseTableModel,
        parent: Optional[QWidget] = None
    ):
        """Initialize unified tracks view.
        
        Args:
            source_model: Table model for tracks data
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Create filter bar
        self.filter_bar = FilterBar()
        self.filter_bar.filter_changed.connect(self._apply_filters)
        # Note: Filter options populated globally via populate_filter_options(),
        # no longer rescanned from visible rows (performance optimization)
        
        # Create custom proxy model for filtering
        self.proxy_model = UnifiedTracksProxyModel()
        self.proxy_model.setSourceModel(source_model)
        
        # Create tracks table
        self.tracks_table = QTableView()
        self.tracks_table.setObjectName("tracksTable")  # For stylesheet targeting
        self.tracks_table.setModel(self.proxy_model)
        self.tracks_table.setSortingEnabled(True)
        self.tracks_table.setSelectionBehavior(QTableView.SelectRows)
        self.tracks_table.setSelectionMode(QTableView.SingleSelection)
        
        # Enable text eliding (truncate with "..." for overflow)
        self.tracks_table.setTextElideMode(Qt.ElideRight)
        self.tracks_table.setWordWrap(False)  # Disable word wrapping to ensure eliding works
        
        # Performance optimizations for large datasets
        # Note: setUniformItemSizes() is for QListView, not QTableView
        # For QTableView, uniform row heights are achieved via vertical header
        self.tracks_table.verticalHeader().setDefaultSectionSize(22)  # Fixed row height
        self.tracks_table.verticalHeader().setMinimumSectionSize(22)  # Prevent smaller rows
        
        # Enable scrollbars when content exceeds view
        self.tracks_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.tracks_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Configure column resizing: Interactive mode with last column stretch
        header = self.tracks_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        
        # Set intelligent initial column widths
        # Columns: Playlist, Owner, Track, Artist, Album, Year, Matched, Local File
        self._set_initial_column_widths()
        
        # Apply link delegate to linkable columns (Track, Artist, Album)
        link_delegate = LinkDelegate(provider="spotify", parent=self.tracks_table)
        # Column 0 = Track, 1 = Artist, 2 = Album
        self.tracks_table.setItemDelegateForColumn(0, link_delegate)  # Track
        self.tracks_table.setItemDelegateForColumn(1, link_delegate)  # Artist
        self.tracks_table.setItemDelegateForColumn(2, link_delegate)  # Album
        
        # Apply folder delegate to Local File column (column 7, was 5 before adding Confidence/Quality)
        folder_delegate = FolderDelegate(parent=self.tracks_table)
        self.tracks_table.setItemDelegateForColumn(7, folder_delegate)  # Local File
        
        # Enable mouse tracking for hover effects
        self.tracks_table.setMouseTracking(True)
        
        # Lazy playlist loading
        self._playlist_fetch_callback: Optional[Callable[[List[str]], Dict[str, str]]] = None
        self._playlist_track_ids_callback: Optional[Callable[[str], Set[str]]] = None  # Get track IDs for playlist name
        self._playlists_loaded = False
        self._lazy_load_timer = QTimer()
        self._lazy_load_timer.setSingleShot(True)
        self._lazy_load_timer.timeout.connect(self._load_visible_playlists)
        
        # Trigger lazy load when scrolling stops
        self.tracks_table.verticalScrollBar().valueChanged.connect(
            lambda: self._lazy_load_timer.start(200)  # 200ms after scroll stops
        )
        
        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.filter_bar)
        layout.addWidget(self.tracks_table)
        
        # Connect table selection to signal
        selection_model = self.tracks_table.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(self._on_selection_changed)
    
    def on_store_filter_changed(self, state):
        """Handle FilterStore state changes (single source of truth).
        
        Updates proxy model and FilterBar to reflect new filter state.
        Uses QSignalBlocker to prevent re-emission loops.
        
        Args:
            state: FilterState with playlist_name, album_name, artist_name, track_ids
        """
        from ..state import FilterState
        
        logger.debug(f"UnifiedTracksView.on_store_filter_changed: {state.active_dimension}")
        
        # Update proxy model filters based on active dimension
        with QSignalBlocker(self.filter_bar):
            if state.playlist_name:
                # Playlist filter active
                self.proxy_model.set_playlist_filter(state.playlist_name, state.track_ids)
                self.filter_bar.set_playlist_filter(state.playlist_name)
                # Clear other dimension filters
                self.filter_bar.set_artist_filter(None)
                self.filter_bar.set_album_filter(None)
                self.proxy_model.set_artist_filter(None)
                self.proxy_model.set_album_filter(None)
                
            elif state.album_name and state.artist_name:
                # Album filter active (requires artist context, but don't show artist in FilterBar)
                self.proxy_model.set_album_filter(state.album_name)
                self.filter_bar.set_album_filter(state.album_name)
                # Don't set artist filter in FilterBar - user wants to see album only
                self.filter_bar.set_artist_filter(None)
                # Clear playlist filter
                self.filter_bar.set_playlist_filter(None)
                self.proxy_model.set_playlist_filter(None, None)
                # Note: We keep artist_name in state for context, but don't filter proxy by artist
                self.proxy_model.set_artist_filter(None)
                
            elif state.artist_name:
                # Artist-only filter active
                self.proxy_model.set_artist_filter(state.artist_name)
                self.filter_bar.set_artist_filter(state.artist_name)
                # Clear other dimension filters
                self.filter_bar.set_playlist_filter(None)
                self.filter_bar.set_album_filter(None)
                self.proxy_model.set_playlist_filter(None, None)
                self.proxy_model.set_album_filter(None)
                
            else:
                # No filter active - clear all dimension filters
                self.filter_bar.set_playlist_filter(None)
                self.filter_bar.set_artist_filter(None)
                self.filter_bar.set_album_filter(None)
                self.proxy_model.set_playlist_filter(None, None)
                self.proxy_model.set_artist_filter(None)
                self.proxy_model.set_album_filter(None)
        
        logger.info(f"Filter applied: {state.active_dimension}, visible rows: {self.proxy_model.rowCount()}")
    
    def _apply_filters(self):
        """Apply current filter settings to the proxy model.
        
        Note: Playlist filtering is handled by FilterStore, not here.
        This method only handles non-dimensional filters (status, search, etc.).
        """
        # Get non-dimensional filter state from filter bar
        status_filter = self.filter_bar.get_track_filter()
        search_text = self.filter_bar.get_search_text()
        year_filter = self.filter_bar.get_year_filter()
        confidence_filter = self.filter_bar.get_confidence_filter()
        quality_filter = self.filter_bar.get_quality_filter()
        
        # Apply to proxy model
        # Note: Playlist, artist, album filters managed by FilterStore via on_store_filter_changed()
        self.proxy_model.set_status_filter(status_filter)
        self.proxy_model.set_year_filter(year_filter)
        self.proxy_model.set_confidence_filter(confidence_filter)
        self.proxy_model.set_quality_filter(quality_filter)
        self.proxy_model.set_search_text_debounced(search_text, delay_ms=300)
    
    def _on_selection_changed(self, selected, deselected):
        """Handle track selection change.
        
        Args:
            selected: QItemSelection of selected items
            deselected: QItemSelection of deselected items
        """
        selection = self.tracks_table.selectionModel()
        if selection and selection.hasSelection():
            proxy_row = selection.selectedRows()[0].row()
            source_index = self.proxy_model.mapToSource(
                self.proxy_model.index(proxy_row, 0)
            )
            source_row = source_index.row()
            
            # Access source model's get_row_data if available
            source_model = self.proxy_model.sourceModel()
            if hasattr(source_model, 'get_row_data'):
                track_data = source_model.get_row_data(source_row)
                if track_data and 'id' in track_data:
                    self.track_selected.emit(track_data['id'])
    
    def clear_filters(self):
        """Reset all filters to default state."""
        self.filter_bar.clear_filters()
        self.proxy_model.set_playlist_filter(None, None)
        self.proxy_model.set_status_filter("all")
        self.proxy_model.set_artist_filter(None)
        self.proxy_model.set_album_filter(None)
        self.proxy_model.set_year_filter(None)
        self.proxy_model.set_search_text_immediate("")
    
    def populate_filter_options(
        self,
        playlists: List[str],
        artists: List[str],
        albums: List[str],
        years: List[int]
    ):
        """Populate filter dropdown options.
        
        Args:
            playlists: List of unique playlist names
            artists: List of unique artist names
            albums: List of unique album names
            years: List of unique years
        """
        self.filter_bar.populate_filter_options(playlists, artists, albums, years)
    
    def populate_filter_options_from_visible_data(self):
        """Populate filter options from currently visible (filtered) rows.
        
        This provides dynamic filtering - only showing options that are
        actually present in the current filtered dataset.
        """
        artists = set()
        albums = set()
        years = set()
        
        # Extract unique values from visible rows in the proxy model
        for row in range(self.proxy_model.rowCount()):
            # Map proxy row to source row
            proxy_index = self.proxy_model.index(row, 0)
            source_index = self.proxy_model.mapToSource(proxy_index)
            source_row = source_index.row()
            
            # Get row data from source model
            source_model = self.proxy_model.sourceModel()
            if hasattr(source_model, 'get_row_data'):
                row_data = source_model.get_row_data(source_row)
                if row_data:
                    # Extract artist
                    artist = row_data.get('artist')
                    if artist:
                        artists.add(artist)
                    
                    # Extract album
                    album = row_data.get('album')
                    if album:
                        albums.add(album)
                    
                    # Extract year
                    year = row_data.get('year')
                    if year:
                        try:
                            years.add(int(year))
                        except (ValueError, TypeError):
                            pass
        
        # Update filter options with visible data (playlists stay global, not filtered)
        playlists = []  # Playlists populated separately, not from visible data
        self.filter_bar.populate_filter_options(
            playlists,  # Keep existing playlist options
            sorted(artists),
            sorted(albums),
            sorted(years, reverse=True)  # Years descending
        )
    
    def _set_initial_column_widths(self):
        """Set intelligent initial column widths.
        
        Column strategy:
        - Text fields (Track, Artist, Album, Local File, Playlists): More space
        - Short fields (Year, Matched, Confidence, Quality): Less space
        """
        # Column indices from UnifiedTracksModel:
        # 0: Track, 1: Artist, 2: Album, 3: Year, 4: Matched, 5: Confidence, 6: Quality, 7: Local File, 8: Playlists
        header = self.tracks_table.horizontalHeader()
        
        # Set initial widths (in pixels)
        # These are reasonable defaults that will be user-adjustable
        header.resizeSection(0, 250)  # Track - large (most important)
        header.resizeSection(1, 180)  # Artist - medium
        header.resizeSection(2, 200)  # Album - medium-large
        header.resizeSection(3, 60)   # Year - small
        header.resizeSection(4, 70)   # Matched - small (✓/✗)
        header.resizeSection(5, 95)   # Confidence - small-medium (CERTAIN/HIGH/etc)
        header.resizeSection(6, 95)   # Quality - small-medium (EXCELLENT/GOOD/etc)
        header.resizeSection(7, 350)  # Local File - large (file paths)
        # Column 8 (Playlists) stretches to fill remaining space
    
    def resize_columns_to_contents(self):
        """Resize table columns to fit contents (with performance gating).
        
        Only performs resize for small datasets to avoid performance hit.
        For large datasets, relies on initial column widths and user resizing.
        """
        # Gate resizing for large datasets (> 1000 rows visible)
        if self.proxy_model.rowCount() > 1000:
            logger.debug(f"Skipping resizeColumnsToContents for {self.proxy_model.rowCount()} rows (performance)")
            return
        
        # Only resize if we have data, otherwise keep initial widths
        if self.proxy_model.rowCount() > 0:
            self.tracks_table.resizeColumnsToContents()
            # Re-apply maximum widths for small columns to prevent them getting too wide
            header = self.tracks_table.horizontalHeader()
            # Ensure Year, Matched, Confidence, and Quality columns don't get too wide
            if header.sectionSize(3) > 80:
                header.resizeSection(3, 80)   # Year max 80px
            if header.sectionSize(4) > 70:
                header.resizeSection(4, 70)   # Matched max 70px (✓/✗)
            if header.sectionSize(5) > 110:
                header.resizeSection(5, 110)  # Confidence max 110px
            if header.sectionSize(6) > 110:
                header.resizeSection(6, 110)  # Quality max 110px
    
    def show_loading(self):
        """Show loading overlay (removed - no longer needed)."""
        pass
    
    def hide_loading(self):
        """Hide loading overlay (removed - no longer needed)."""
        pass
    
    def eventFilter(self, obj, event):
        """Filter events (loading overlay removed).
        
        Args:
            obj: Event source object
            event: Event to filter
            
        Returns:
            bool: True if event handled, False otherwise
        """
        return super().eventFilter(obj, event)
    
    def set_playlist_fetch_callback(self, callback: Callable[[List[str]], Dict[str, str]]):
        """Set callback for fetching playlist names for track IDs.
        
        Args:
            callback: Function that takes list of track_ids and returns
                     dict mapping track_id -> comma-separated playlist names
        """
        self._playlist_fetch_callback = callback
    
    def _load_visible_playlists(self):
        """Load playlist names for currently visible rows (lazy loading)."""
        if not self._playlist_fetch_callback:
            return
        
        # Skip if playlists already loaded
        if self._playlists_loaded:
            return
        
        # Get visible rows
        visible_rows = self._get_visible_source_rows()
        if not visible_rows:
            return
        
        # Get track IDs for visible rows
        source_model = self.proxy_model.sourceModel()
        if not hasattr(source_model, 'get_row_data'):
            return
        
        track_ids = []
        for row_idx in visible_rows:
            row_data = source_model.get_row_data(row_idx)
            if row_data and 'id' in row_data:
                track_id = row_data['id']
                # Only fetch if playlists column is empty
                if not row_data.get('playlists'):
                    track_ids.append(track_id)
        
        if not track_ids:
            return
        
        logger.debug(f"Lazy loading playlists for {len(track_ids)} visible tracks")
        
        # Fetch playlist data
        try:
            playlists_data = self._playlist_fetch_callback(track_ids)
            
            # Update model
            if hasattr(source_model, 'update_playlists_for_rows'):
                source_model.update_playlists_for_rows(visible_rows, playlists_data)
        except Exception as e:
            logger.error(f"Error loading playlists: {e}")
    
    def _get_visible_source_rows(self) -> List[int]:
        """Get list of source model row indices currently visible in viewport.
        
        Returns:
            List of source model row indices
        """
        source_rows = []
        
        # Get viewport's visible rect
        viewport = self.tracks_table.viewport()
        visible_rect = viewport.rect()
        
        # Iterate through visible proxy rows
        for y in range(0, visible_rect.height(), 22):  # 22px row height
            index = self.tracks_table.indexAt(visible_rect.topLeft() + self.tracks_table.viewport().pos() + QPoint(0, y))
            if index.isValid():
                proxy_row = index.row()
                source_index = self.proxy_model.mapToSource(self.proxy_model.index(proxy_row, 0))
                source_row = source_index.row()
                if source_row not in source_rows:
                    source_rows.append(source_row)
        
        return source_rows
    
    def trigger_lazy_playlist_load(self):
        """Manually trigger lazy loading of playlists for visible rows."""
        self._playlists_loaded = False
        self._load_visible_playlists()
