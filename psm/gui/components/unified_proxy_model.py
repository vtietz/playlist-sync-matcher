"""Custom proxy model for unified tracks filtering.

This proxy model enables filtering by:
- Playlist name (from playlist selection, uses track ID set for efficiency)
- Match status (Matched/Unmatched)
- Artist, Album, Year (exact match)
- Text search across all fields

Qt6 Pattern:
- Uses beginFilterChange() / invalidateFilter() / endFilterChange() pattern
- Per Qt6 docs, these methods are NOT deprecated despite PySide6 warnings
- See: https://doc.qt.io/qtforpython-6/PySide6/QtCore/QSortFilterProxyModel.html
- The deprecation warnings are false positives in PySide6>=6.6.0
"""
from __future__ import annotations
from typing import Optional, Set
from PySide6.QtCore import QSortFilterProxyModel, Qt, QTimer
import logging

logger = logging.getLogger(__name__)


class UnifiedTracksProxyModel(QSortFilterProxyModel):
    """Proxy model with multi-criteria filtering for unified tracks.
    
    Filters by:
    - Playlist name (uses pre-fetched track ID set for efficiency)
    - Match status (Yes/No in 'Matched' column)
    - Artist, Album, Year (exact match filters)
    - Text search (wildcard across all columns)
    
    Optimized for performance:
    - Uses UserRole to access raw values (avoids string formatting)
    - Caches column indices to avoid repeated lookups
    - Minimizes allocations in hot path
    - Playlist filtering via track ID set (avoids lazy-loaded column)
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Filter criteria
        self._playlist_filter: Optional[str] = None
        self._playlist_track_ids: Optional[Set[str]] = None  # Track IDs in selected playlist
        self._status_filter: str = "all"  # "all", "matched", "unmatched"
        self._artist_filter: Optional[str] = None
        self._album_filter: Optional[str] = None
        self._year_filter: Optional[int] = None
        self._confidence_filter: Optional[str] = None
        self._quality_filter: Optional[str] = None
        self._search_text: str = ""
        
        # Cached column indices (populated on first filter)
        self._col_cache: Optional[dict] = None
        
        # Debounce timer for search
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._apply_search_filter)
        self._pending_search_text: Optional[str] = None
        
        # Configure proxy
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.setSortRole(Qt.UserRole)
        self.setDynamicSortFilter(True)  # Enable automatic filter/sort reevaluation
    
    def _get_column_indices(self, source_model) -> dict:
        """Get and cache column indices by header name.
        
        Args:
            source_model: Source model
            
        Returns:
            Dict mapping header name to column index
        """
        if self._col_cache is not None:
            return self._col_cache
        
        cols = {}
        for col in range(source_model.columnCount()):
            header = source_model.headerData(col, Qt.Horizontal, Qt.DisplayRole)
            if header:
                cols[header] = col
        
        self._col_cache = cols
        return cols
    
    def set_playlist_filter(self, playlist_name: Optional[str], track_ids: Optional[Set[str]] = None):
        """Set playlist filter.
        
        Args:
            playlist_name: Playlist name to filter by, or None for all playlists
            track_ids: Set of track IDs in the playlist (for efficient filtering)
        """
        self.beginFilterChange()
        self._playlist_filter = playlist_name
        self._playlist_track_ids = track_ids
        self._col_cache = None  # Invalidate cache when source model might change
        self.invalidateFilter()
        self.endFilterChange()
    
    def set_status_filter(self, status: str):
        """Set match status filter.
        
        Args:
            status: "all", "matched", or "unmatched"
        """
        self.beginFilterChange()
        self._status_filter = status
        self.invalidateFilter()
        self.endFilterChange()
    
    def set_artist_filter(self, artist: Optional[str]):
        """Set artist filter.
        
        Args:
            artist: Artist name to filter by, or None for all artists
        """
        self.beginFilterChange()
        self._artist_filter = artist
        self.invalidateFilter()
        self.endFilterChange()
    
    def set_album_filter(self, album: Optional[str]):
        """Set album filter.
        
        Args:
            album: Album name to filter by, or None for all albums
        """
        self.beginFilterChange()
        self._album_filter = album
        self.invalidateFilter()
        self.endFilterChange()
    
    def set_year_filter(self, year: Optional[int]):
        """Set year filter.
        
        Args:
            year: Year to filter by, or None for all years
        """
        self.beginFilterChange()
        self._year_filter = year
        self.invalidateFilter()
        self.endFilterChange()
    
    def set_confidence_filter(self, confidence: Optional[str]):
        """Set confidence filter.
        
        Args:
            confidence: Confidence level to filter by (CERTAIN/HIGH/MODERATE/LOW), or None for all
        """
        self.beginFilterChange()
        self._confidence_filter = confidence
        self.invalidateFilter()
        self.endFilterChange()
    
    def set_quality_filter(self, quality: Optional[str]):
        """Set quality filter.
        
        Args:
            quality: Quality level to filter by (EXCELLENT/GOOD/PARTIAL/POOR), or None for all
        """
        self.beginFilterChange()
        self._quality_filter = quality
        self.invalidateFilter()
        self.endFilterChange()
    
    def set_search_text_debounced(self, text: str, delay_ms: int = 300):
        """Set search text with debouncing.
        
        Args:
            text: Search text
            delay_ms: Debounce delay in milliseconds
        """
        self._pending_search_text = text
        self._search_timer.stop()
        self._search_timer.start(delay_ms)
    
    def _apply_search_filter(self):
        """Apply the pending search filter after debounce."""
        if self._pending_search_text is not None:
            self.beginFilterChange()
            self._search_text = self._pending_search_text
            self._pending_search_text = None
            self.invalidateFilter()
            self.endFilterChange()
    
    def set_search_text_immediate(self, text: str):
        """Set search text immediately without debouncing.
        
        Args:
            text: Search text
        """
        self.beginFilterChange()
        self._search_text = text
        self.invalidateFilter()
        self.endFilterChange()
    
    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        """Determine if row passes all filter criteria.
        
        Optimized to use UserRole for raw values and cached column indices.
        
        Args:
            source_row: Row index in source model
            source_parent: Parent index in source model
            
        Returns:
            True if row should be visible
        """
        source_model = self.sourceModel()
        if not source_model:
            return True
        
        try:
            # Early exit: Filter by playlist (check track ID via get_row_data)
            if self._playlist_track_ids is not None:
                # Use get_row_data to access the 'id' field directly (no header lookup needed)
                if hasattr(source_model, 'get_row_data'):
                    row_data = source_model.get_row_data(source_row)
                    track_id = row_data.get('id') if row_data else None
                    if track_id not in self._playlist_track_ids:
                        return False
        
            # Get cached column indices for other filters
            cols = self._get_column_indices(source_model)
            
            # Early exit: Filter by match status (use UserRole for bool)
            if self._status_filter != "all":
                matched_col = cols.get('Matched')
                if matched_col is not None:
                    index = source_model.index(source_row, matched_col, source_parent)
                    # Use UserRole to get boolean value
                    matched = source_model.data(index, Qt.UserRole)
                    if self._status_filter == "matched" and not matched:
                        return False
                    elif self._status_filter == "unmatched" and matched:
                        return False
            
            # Early exit: Filter by artist (use UserRole for case-insensitive)
            if self._artist_filter:
                artist_col = cols.get('Artist')
                if artist_col is not None:
                    index = source_model.index(source_row, artist_col, source_parent)
                    # Use DisplayRole for exact match
                    artist = source_model.data(index, Qt.DisplayRole) or ''
                    if artist != self._artist_filter:
                        return False
            
            # Early exit: Filter by album (use UserRole for case-insensitive)
            if self._album_filter:
                album_col = cols.get('Album')
                if album_col is not None:
                    index = source_model.index(source_row, album_col, source_parent)
                    # Use DisplayRole for exact match
                    album = source_model.data(index, Qt.DisplayRole) or ''
                    if album != self._album_filter:
                        return False
            
            # Early exit: Filter by year (use UserRole for int comparison)
            if self._year_filter is not None:
                year_col = cols.get('Year')
                if year_col is not None:
                    index = source_model.index(source_row, year_col, source_parent)
                    # Use UserRole to get raw int value
                    year_value = source_model.data(index, Qt.UserRole)
                    # UserRole returns empty string for None, so check both
                    if year_value == "" or year_value is None:
                        return False
                    if year_value != self._year_filter:
                        return False
            
            # Early exit: Filter by confidence (use UserRole for exact match)
            if self._confidence_filter:
                confidence_col = cols.get('Confidence')
                if confidence_col is not None:
                    index = source_model.index(source_row, confidence_col, source_parent)
                    # Use UserRole to get confidence level
                    confidence = source_model.data(index, Qt.UserRole) or ''
                    if confidence != self._confidence_filter:
                        return False
            
            # Early exit: Filter by quality (use UserRole for exact match)
            if self._quality_filter:
                quality_col = cols.get('Quality')
                if quality_col is not None:
                    index = source_model.index(source_row, quality_col, source_parent)
                    # Use UserRole to get quality level
                    quality = source_model.data(index, Qt.UserRole) or ''
                    if quality != self._quality_filter:
                        return False
            
            # Early exit: Filter by search text (use UserRole for lowercase comparison)
            if self._search_text:
                search_lower = self._search_text.lower()
                
                # Search across relevant columns (use DisplayRole for strings)
                found = False
                for col_name in ['Track', 'Artist', 'Album', 'Playlists', 'Local File']:
                    col_idx = cols.get(col_name)
                    if col_idx is not None:
                        index = source_model.index(source_row, col_idx, source_parent)
                        # Use DisplayRole, convert to lowercase
                        value = source_model.data(index, Qt.DisplayRole) or ''
                        if search_lower in str(value).lower():
                            found = True
                            break
                
                if not found:
                    return False
            
            return True
            
        except Exception as e:
            logger.warning(f"Error in filterAcceptsRow: {e}")
            return True
