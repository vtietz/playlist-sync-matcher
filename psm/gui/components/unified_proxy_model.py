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
        
        Optimized with fast-path for "no filters active" and direct dict access.
        
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
            # FAST PATH: If no filters are active, accept immediately
            # This avoids ALL expensive data() calls when showing "All Songs"
            if (self._playlist_track_ids is None and
                self._status_filter == "all" and
                not self._artist_filter and
                not self._album_filter and
                self._year_filter is None and
                not self._confidence_filter and
                not self._quality_filter and
                not self._search_text):
                return True
            
            # Get row data once (direct dict access - much faster than repeated data() calls)
            row_data = None
            if hasattr(source_model, 'get_row_data'):
                row_data = source_model.get_row_data(source_row)
                if not row_data:
                    return True  # If no data, show the row
            
            # Early exit: Filter by playlist (check track ID)
            if self._playlist_track_ids is not None:
                track_id = row_data.get('id') if row_data else None
                if track_id not in self._playlist_track_ids:
                    return False
        
            # Early exit: Filter by match status
            if self._status_filter != "all" and row_data:
                matched = row_data.get('matched', False)
                if self._status_filter == "matched" and not matched:
                    return False
                elif self._status_filter == "unmatched" and matched:
                    return False
            
            # Early exit: Filter by artist (exact match)
            if self._artist_filter and row_data:
                artist = row_data.get('artist', '')
                if artist != self._artist_filter:
                    return False
            
            # Early exit: Filter by album (exact match)
            if self._album_filter and row_data:
                album = row_data.get('album', '')
                if album != self._album_filter:
                    return False
            
            # Early exit: Filter by year
            if self._year_filter is not None and row_data:
                year_value = row_data.get('year')
                if year_value is None or year_value != self._year_filter:
                    return False
            
            # Early exit: Filter by confidence
            if self._confidence_filter and row_data:
                # Extract confidence from method field
                method = row_data.get('method', '')
                confidence = ''
                if method and '-' in method:
                    confidence = method.split('-')[0].strip()
                if confidence != self._confidence_filter:
                    return False
            
            # Early exit: Filter by quality
            if self._quality_filter and row_data:
                # Extract quality from method field
                method = row_data.get('method', '')
                quality = ''
                if method and '-' in method:
                    parts = method.split('-')
                    if len(parts) > 1:
                        quality = parts[1].strip()
                if quality != self._quality_filter:
                    return False
            
            # Early exit: Filter by search text
            if self._search_text and row_data:
                search_lower = self._search_text.lower()
                
                # Search across relevant fields (direct dict access)
                found = False
                for field in ['name', 'artist', 'album', 'playlists', 'local_path']:
                    value = row_data.get(field, '')
                    if value and search_lower in str(value).lower():
                        found = True
                        break
                
                if not found:
                    return False
            
            return True
            
        except Exception as e:
            logger.warning(f"Error in filterAcceptsRow: {e}")
            return True
