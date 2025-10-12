"""Model Coordinator - Centralized model management and updates.

This module provides the ModelCoordinator class which encapsulates all table
model instances and their update logic, reducing MainWindow's responsibility
for direct model manipulation.
"""

from typing import Any, Dict, List, Optional, Tuple
from PySide6.QtCore import Qt, QObject

from psm.gui.models import (
    PlaylistsModel,
    PlaylistDetailModel,
    UnmatchedTracksModel,
    MatchedTracksModel,
    PlaylistCoverageModel,
    UnmatchedAlbumsModel,
    LikedTracksModel,
    UnifiedTracksModel,
    AlbumsModel,
    ArtistsModel,
)


class ModelCoordinator(QObject):
    """Coordinates all table models and their updates.
    
    Centralizes model instances and update operations, including:
    - Model lifecycle management
    - Data updates with appropriate sorting
    - Column resizing logic
    - Sort state restoration
    
    This eliminates the need for MainWindow to directly manage 10+ models
    and their various update methods.
    """
    
    def __init__(self, parent: QObject = None):
        """Initialize ModelCoordinator with all table models.
        
        Args:
            parent: Parent QObject (typically MainWindow)
        """
        super().__init__(parent)
        
        # Create all models
        self.playlists_model = PlaylistsModel(parent)
        self.playlist_detail_model = PlaylistDetailModel(parent)
        self.unmatched_tracks_model = UnmatchedTracksModel(parent)
        self.matched_tracks_model = MatchedTracksModel(parent)
        self.coverage_model = PlaylistCoverageModel(parent)
        self.unmatched_albums_model = UnmatchedAlbumsModel(parent)
        self.liked_tracks_model = LikedTracksModel(parent)
        self.unified_tracks_model = UnifiedTracksModel(parent)
        self.albums_model = AlbumsModel(parent)
        self.artists_model = ArtistsModel(parent)
        
        # Pending sort states (restored from settings, applied after data loads)
        self._pending_playlists_sort: Optional[Tuple[int, Qt.SortOrder]] = None
        self._pending_tracks_sort: Optional[Tuple[int, Qt.SortOrder]] = None
        self._pending_albums_sort: Optional[Tuple[int, Qt.SortOrder]] = None
        self._pending_artists_sort: Optional[Tuple[int, Qt.SortOrder]] = None
        
        # References to views (set after UI creation)
        self._playlists_table_view = None
        self._albums_view = None
        self._artists_view = None
        self._unified_tracks_view = None
    
    # ----- View References -----
    
    def set_views(self, playlists_table, albums_view, artists_view, unified_tracks_view):
        """Set references to views for column resizing and sorting.
        
        Args:
            playlists_table: PlaylistsTab table view
            albums_view: AlbumsView component
            artists_view: ArtistsView component
            unified_tracks_view: UnifiedTracksView component
        """
        self._playlists_table_view = playlists_table
        self._albums_view = albums_view
        self._artists_view = artists_view
        self._unified_tracks_view = unified_tracks_view
    
    # ----- Sort State Management -----
    
    def set_pending_playlists_sort(self, column: int, order: Qt.SortOrder):
        """Set pending sort for playlists (to be applied after data load)."""
        self._pending_playlists_sort = (column, order)
    
    def set_pending_tracks_sort(self, column: int, order: Qt.SortOrder):
        """Set pending sort for tracks (to be applied after data load)."""
        self._pending_tracks_sort = (column, order)
    
    def get_pending_tracks_sort(self) -> Optional[Tuple[int, Qt.SortOrder]]:
        """Get and clear pending sort for tracks.
        
        Returns:
            Tuple of (column, order) if set, None otherwise.
            Clears the pending sort after returning it.
        """
        pending = self._pending_tracks_sort
        self._pending_tracks_sort = None
        return pending
    
    def set_pending_albums_sort(self, column: int, order: Qt.SortOrder):
        """Set pending sort for albums (to be applied after data load)."""
        self._pending_albums_sort = (column, order)
    
    def set_pending_artists_sort(self, column: int, order: Qt.SortOrder):
        """Set pending sort for artists (to be applied after data load)."""
        self._pending_artists_sort = (column, order)
    
    # ----- Model Update Methods -----
    
    def update_playlists(self, playlists: List[Dict[str, Any]]):
        """Update playlists model with data and apply sorting/resizing.
        
        Args:
            playlists: List of playlist dicts
        """
        self.playlists_model.set_data(playlists)
        
        if self._playlists_table_view is None:
            return
        
        # Don't auto-resize columns - preserve user's column widths
        # Only set minimum widths if columns are too narrow
        self._playlists_table_view.setColumnWidth(0, max(250, self._playlists_table_view.columnWidth(0)))
        self._playlists_table_view.setColumnWidth(1, max(120, self._playlists_table_view.columnWidth(1)))
        
        # Apply sort: use pending (restored) sort if available, otherwise default to name ascending
        if self._pending_playlists_sort is not None:
            sort_col, sort_order = self._pending_playlists_sort
            self._playlists_table_view.sortByColumn(sort_col, sort_order)
            self._pending_playlists_sort = None  # Clear after applying
        else:
            # Default sort by name (column 0) alphabetically
            self._playlists_table_view.sortByColumn(0, Qt.AscendingOrder)
    
    def update_albums(self, albums: List[Dict[str, Any]]):
        """Update albums model with data and apply sorting.
        
        Args:
            albums: List of album dicts with aggregated statistics
        """
        self.albums_model.set_data(albums)
        
        if self._albums_view is None:
            return
        
        # Apply sort: use pending (restored) sort if available, otherwise default
        if self._pending_albums_sort is not None:
            sort_col, sort_order = self._pending_albums_sort
            self._albums_view.table.sortByColumn(sort_col, sort_order)
            self._pending_albums_sort = None  # Clear after applying
        else:
            # Default sort by playlist count (column 3) descending
            self._albums_view.table.sortByColumn(3, Qt.DescendingOrder)
    
    def update_artists(self, artists: List[Dict[str, Any]]):
        """Update artists model with data and apply sorting.
        
        Args:
            artists: List of artist dicts with aggregated statistics
        """
        self.artists_model.set_data(artists)
        
        if self._artists_view is None:
            return
        
        # Apply sort: use pending (restored) sort if available, otherwise default
        if self._pending_artists_sort is not None:
            sort_col, sort_order = self._pending_artists_sort
            self._artists_view.table.sortByColumn(sort_col, sort_order)
            self._pending_artists_sort = None  # Clear after applying
        else:
            # Default sort by playlist count (column 3) descending
            self._artists_view.table.sortByColumn(3, Qt.DescendingOrder)
    
    def update_unmatched_tracks(self, tracks: List[Dict[str, Any]]):
        """Update unmatched tracks model.
        
        Args:
            tracks: List of unmatched track dicts
        """
        self.unmatched_tracks_model.set_data(tracks)
    
    def update_matched_tracks(self, tracks: List[Dict[str, Any]]):
        """Update matched tracks model.
        
        Args:
            tracks: List of matched track dicts
        """
        self.matched_tracks_model.set_data(tracks)
    
    def update_coverage(self, coverage: List[Dict[str, Any]]):
        """Update coverage model.
        
        Args:
            coverage: List of coverage dicts
        """
        self.coverage_model.set_data(coverage)
    
    def update_unmatched_albums(self, albums: List[Dict[str, Any]]):
        """Update unmatched albums model.
        
        Args:
            albums: List of unmatched album dicts
        """
        self.unmatched_albums_model.set_data(albums)
    
    def update_liked_tracks(self, tracks: List[Dict[str, Any]]):
        """Update liked tracks model.
        
        Args:
            tracks: List of liked track dicts
        """
        self.liked_tracks_model.set_data(tracks)
    
    def update_unified_tracks(self, tracks: List[Dict[str, Any]], playlists: List[Dict[str, Any]]):
        """Update unified tracks view with data and resize columns.
        
        Args:
            tracks: List of all tracks with metadata
            playlists: List of playlists (no longer used - kept for compatibility)
        """
        self.unified_tracks_model.set_data(tracks)
        
        if self._unified_tracks_view is None:
            return
        
        # Disabled: Don't auto-resize columns - preserve user's column widths
        # self._unified_tracks_view.resize_columns_to_contents()
