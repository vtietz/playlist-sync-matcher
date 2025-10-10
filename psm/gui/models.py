"""Qt table models backed by DataFacade.

All models use DatabaseInterface exclusively via DataFacade.
"""
from __future__ import annotations
from typing import Any, List, Dict, Optional
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
import logging

from .utils.formatters import (
    format_boolean_check,
    extract_confidence,
    get_quality_status_text,
    format_score_percentage,
    get_confidence_tooltip,
    get_quality_tooltip,
)

logger = logging.getLogger(__name__)


class BaseTableModel(QAbstractTableModel):
    """Base class for table models with common functionality."""
    
    def __init__(self, columns: List[tuple], parent=None):
        """Initialize base model.
        
        Args:
            columns: List of (column_name, column_title) tuples
            parent: Parent QObject
        """
        super().__init__(parent)
        self.columns = columns
        self.data_rows: List[Dict[str, Any]] = []
    
    def rowCount(self, parent=QModelIndex()):
        """Get row count."""
        return len(self.data_rows)
    
    def columnCount(self, parent=QModelIndex()):
        """Get column count."""
        return len(self.columns)
    
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        """Get header data."""
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            if 0 <= section < len(self.columns):
                return self.columns[section][1]  # Column title
        return None
    
    def data(self, index, role=Qt.DisplayRole):
        """Get cell data."""
        if not index.isValid():
            return None
        
        row = index.row()
        col = index.column()
        
        if 0 <= row < len(self.data_rows) and 0 <= col < len(self.columns):
            col_name = self.columns[col][0]
            value = self.data_rows[row].get(col_name)
            
            if role == Qt.DisplayRole:
                # Format for display
                if isinstance(value, float):
                    return f"{value:.1f}"
                elif value is None:
                    return ""
                return str(value)
            
            elif role == Qt.ToolTipRole:
                # Show full text in tooltip for long strings
                if isinstance(value, str) and len(value) > 50:
                    return value
                return None
            
            elif role == Qt.UserRole:
                # Return raw value for sorting
                # Convert None to empty string for consistent sorting
                if value is None:
                    return ""
                # Keep numbers as numbers for numeric sorting
                if isinstance(value, (int, float)):
                    return value
                # Keep booleans as booleans for filtering
                if isinstance(value, bool):
                    return value
                # Strings as lowercase for case-insensitive sorting
                if isinstance(value, str):
                    return value.lower()
                return value
            
            elif role == Qt.UserRole + 1:
                # Return link item type for delegate
                return self._get_link_type(col_name)
            
            elif role == Qt.UserRole + 2:
                # Return link item ID for delegate
                return self._get_link_id(col_name, row)
        
        return None
    
    def _get_link_type(self, col_name: str) -> Optional[str]:
        """Get link type for column.
        
        Args:
            col_name: Column name
            
        Returns:
            Link type ("track", "album", "artist", "playlist") or None
        """
        # Map column names to link types
        link_map = {
            'name': 'track',
            'artist': 'artist',
            'album': 'album',
        }
        return link_map.get(col_name)
    
    def _get_link_id(self, col_name: str, row: int) -> Optional[str]:
        """Get link ID for column and row.
        
        Args:
            col_name: Column name
            row: Row index
            
        Returns:
            Spotify ID or None
        """
        if 0 <= row < len(self.data_rows):
            row_data = self.data_rows[row]
            
            # Map column names to ID fields
            id_map = {
                'name': 'id',         # Track ID
                'artist': 'artist_id',
                'album': 'album_id',
            }
            
            id_field = id_map.get(col_name)
            if id_field:
                return row_data.get(id_field)
        
        return None
    
    def set_data(self, rows: List[Dict[str, Any]]):
        """Update model data.
        
        Args:
            rows: New data rows
        """
        self.beginResetModel()
        self.data_rows = rows
        self.endResetModel()
    
    def get_row_data(self, row: int) -> Optional[Dict[str, Any]]:
        """Get data for a specific row.
        
        Args:
            row: Row index
            
        Returns:
            Row data dict or None
        """
        if 0 <= row < len(self.data_rows):
            return self.data_rows[row]
        return None


class PlaylistsModel(BaseTableModel):
    """Model for playlists master table."""
    
    def __init__(self, parent=None):
        columns = [
            ('name', 'Name'),
            ('owner_name', 'Owner'),
            ('coverage', 'Coverage'),
            ('relevance', 'Relevance'),
        ]
        super().__init__(columns, parent)
    
    def data(self, index, role=Qt.DisplayRole):
        """Override to format Coverage column as '86% (19/22)' and provide link data."""
        if not index.isValid():
            return None
        
        row = index.row()
        col = index.column()
        
        if 0 <= row < len(self.data_rows) and 0 <= col < len(self.columns):
            col_name = self.columns[col][0]
            
            # Special formatting for Coverage column
            if col_name == 'coverage' and role == Qt.DisplayRole:
                row_data = self.data_rows[row]
                coverage_pct = row_data.get('coverage', 0)
                matched = row_data.get('matched_count', 0)
                total = row_data.get('track_count', 0)
                return f"{coverage_pct}% ({matched}/{total})"
            
            # Link data for Name column (playlist)
            if col_name == 'name' and role == Qt.UserRole + 1:
                return 'playlist'
            
            if col_name == 'name' and role == Qt.UserRole + 2:
                row_data = self.data_rows[row]
                return row_data.get('id')  # Playlist ID
            
            # Use base class for everything else
            return super().data(index, role)
        
        return None


class PlaylistDetailModel(BaseTableModel):
    """Model for playlist detail table (tracks in a playlist)."""
    
    def __init__(self, parent=None):
        columns = [
            ('position', '#'),
            ('name', 'Track'),
            ('artist', 'Artist'),
            ('album', 'Album'),
            ('local_path', 'Local File'),
        ]
        super().__init__(columns, parent)


class UnmatchedTracksModel(BaseTableModel):
    """Model for unmatched tracks table."""
    
    def __init__(self, parent=None):
        columns = [
            ('name', 'Track'),
            ('artist', 'Artist'),
            ('album', 'Album'),
            ('year', 'Year'),
            ('isrc', 'ISRC'),
        ]
        super().__init__(columns, parent)


class MatchedTracksModel(BaseTableModel):
    """Model for matched tracks table."""
    
    def __init__(self, parent=None):
        columns = [
            ('name', 'Track'),
            ('artist', 'Artist'),
            ('album', 'Album'),
            ('local_path', 'Local File'),
            ('score', 'Score'),
            ('method', 'Method'),
        ]
        super().__init__(columns, parent)


class PlaylistCoverageModel(BaseTableModel):
    """Model for playlist coverage table."""
    
    def __init__(self, parent=None):
        columns = [
            ('name', 'Playlist'),
            ('total', 'Total'),
            ('matched', 'Matched'),
            ('coverage_pct', 'Coverage %'),
        ]
        super().__init__(columns, parent)


class UnmatchedAlbumsModel(BaseTableModel):
    """Model for unmatched albums table."""
    
    def __init__(self, parent=None):
        columns = [
            ('artist', 'Artist'),
            ('album', 'Album'),
            ('total', 'Total'),
            ('matched', 'Matched'),
            ('missing', 'Missing'),
            ('percent_complete', '% Complete'),
        ]
        super().__init__(columns, parent)


class LikedTracksModel(BaseTableModel):
    """Model for liked tracks table."""
    
    def __init__(self, parent=None):
        columns = [
            ('name', 'Track'),
            ('artist', 'Artist'),
            ('album', 'Album'),
            ('local_path', 'Local File'),
            ('added_at', 'Added'),
        ]
        super().__init__(columns, parent)


class UnifiedTracksModel(BaseTableModel):
    """Model for unified tracks view with all tracks and filtering metadata.
    
    Column order optimized for readability:
    - Track, Artist, Album, Year (core metadata first)
    - Matched, Confidence, Quality (match status and quality indicators)
    - Local File (match info)
    - Playlist Count (number of playlists containing this track)
    - Playlists (comma-separated list of playlists containing this track)
    
    Performance optimization:
    - Playlists column starts empty and is populated lazily for visible rows
    - Use update_playlists_for_rows() to batch-load playlist data
    """
    
    def __init__(self, parent=None):
        columns = [
            ('name', 'Track'),
            ('artist', 'Artist'),
            ('album', 'Album'),
            ('year', 'Year'),
            ('matched', 'Matched'),
            ('confidence', 'Confidence'),
            ('quality', 'Quality'),
            ('local_path', 'Local File'),
            ('playlist_count', '#PL'),
            ('playlists', 'Playlists'),
        ]
        super().__init__(columns, parent)
        # Cache for playlists data (track_id -> playlist names string)
        self._playlists_cache: Dict[str, str] = {}
    
    def update_playlists_for_rows(self, row_indices: List[int], playlists_data: Dict[str, str]):
        """Update playlists column for specific rows (lazy loading).
        
        Args:
            row_indices: List of row indices to update
            playlists_data: Dict mapping track_id -> comma-separated playlist names
        """
        if not row_indices:
            return
        
        # Find playlists column index
        playlists_col = None
        for i, (col_name, _) in enumerate(self.columns):
            if col_name == 'playlists':
                playlists_col = i
                break
        
        if playlists_col is None:
            return
        
        # Update cache and data
        for row_idx in row_indices:
            if 0 <= row_idx < len(self.data_rows):
                track_id = self.data_rows[row_idx].get('id')
                if track_id and track_id in playlists_data:
                    playlists_str = playlists_data[track_id]
                    self.data_rows[row_idx]['playlists'] = playlists_str
                    self._playlists_cache[track_id] = playlists_str
        
        # Emit dataChanged for the playlists column only
        if row_indices:
            min_row = min(row_indices)
            max_row = max(row_indices)
            top_left = self.index(min_row, playlists_col)
            bottom_right = self.index(max_row, playlists_col)
            self.dataChanged.emit(top_left, bottom_right, [Qt.DisplayRole])
    
    def set_data(self, rows: List[Dict[str, Any]]):
        """Update model data (override to preserve playlists cache).
        
        Args:
            rows: New data rows
        """
        # Restore cached playlists for tracks we've already loaded
        for row in rows:
            track_id = row.get('id')
            if track_id and track_id in self._playlists_cache:
                row['playlists'] = self._playlists_cache[track_id]
        
        super().set_data(rows)
    
    # Streaming API for non-blocking large dataset loading
    def load_data_async_start(self, total_count: Optional[int] = None):
        """Start async data loading - clears model and prepares for chunked appends.
        
        For large datasets (>5k rows), use this instead of set_data() to avoid UI freezes.
        Call load_data_async_append() repeatedly with chunks, then complete normally.
        
        Args:
            total_count: Expected total rows (for progress tracking)
        """
        # Clear existing data
        self.beginResetModel()
        self.data_rows = []
        self._is_streaming = True
        self._cancelled = False
        self._total_count = total_count
        self.endResetModel()
        logger.debug(f"UnifiedTracksModel: Started async loading (expecting {total_count} rows)")
    
    def load_data_async_append(self, chunk_rows: List[Dict[str, Any]]):
        """Append a chunk of rows during async loading.
        
        Uses beginInsertRows/endInsertRows for incremental updates instead of model reset.
        Restores cached playlists data for each row before insertion.
        
        Args:
            chunk_rows: Chunk of rows to append
        """
        if self._cancelled:
            logger.debug("UnifiedTracksModel: Append cancelled")
            return
        
        if not chunk_rows:
            return
        
        # Restore cached playlists for tracks we've already loaded
        for row in chunk_rows:
            track_id = row.get('id')
            if track_id and track_id in self._playlists_cache:
                row['playlists'] = self._playlists_cache[track_id]
        
        # Insert rows incrementally
        start_row = len(self.data_rows)
        end_row = start_row + len(chunk_rows) - 1
        
        self.beginInsertRows(QModelIndex(), start_row, end_row)
        self.data_rows.extend(chunk_rows)
        self.endInsertRows()
        
        logger.debug(f"UnifiedTracksModel: Appended {len(chunk_rows)} rows (total: {len(self.data_rows)})")
    
    def load_data_async_cancel(self):
        """Cancel ongoing async loading.
        
        Sets flag to stop the streaming loop cleanly before next append.
        """
        self._cancelled = True
        self._is_streaming = False
        logger.debug("UnifiedTracksModel: Async loading cancelled")
    
    def load_data_async_complete(self):
        """Complete async loading and clean up streaming state."""
        self._is_streaming = False
        self._cancelled = False
        logger.debug(f"UnifiedTracksModel: Async loading complete ({len(self.data_rows)} rows)")
    
    @property
    def is_streaming(self) -> bool:
        """Check if currently streaming data."""
        return getattr(self, '_is_streaming', False)
    
    def data(self, index, role=Qt.DisplayRole):
        """Get cell data with special formatting for matched, confidence, and quality columns."""
        if not index.isValid():
            return None
        
        row = index.row()
        col = index.column()
        
        if 0 <= row < len(self.data_rows) and 0 <= col < len(self.columns):
            col_name = self.columns[col][0]
            value = self.data_rows[row].get(col_name)
            row_data = self.data_rows[row]
            
            if role == Qt.DisplayRole:
                # Format matched column with check/cross
                if col_name == 'matched':
                    if isinstance(value, bool):
                        return format_boolean_check(value)
                    return ""
                
                # Format confidence column
                elif col_name == 'confidence':
                    # Only show confidence if track is matched
                    if row_data.get('matched'):
                        method = row_data.get('method')
                        if method:
                            return extract_confidence(method)
                    return ""
                
                # Format quality column (only for matched tracks)
                elif col_name == 'quality':
                    if row_data.get('matched'):
                        missing_count = row_data.get('missing_metadata_count', 0)
                        bitrate_kbps = row_data.get('bitrate_kbps')
                        return get_quality_status_text(missing_count, bitrate_kbps)
                    return ""
            
            # UserRole returns raw values for filtering/sorting
            elif role == Qt.UserRole:
                # For confidence, return the extracted value for sorting
                if col_name == 'confidence':
                    if row_data.get('matched'):
                        method = row_data.get('method')
                        if method:
                            return extract_confidence(method)
                    return ""
                
                # For quality, return the text for sorting
                elif col_name == 'quality':
                    if row_data.get('matched'):
                        missing_count = row_data.get('missing_metadata_count', 0)
                        bitrate_kbps = row_data.get('bitrate_kbps')
                        return get_quality_status_text(missing_count, bitrate_kbps)
                    return ""
            
            # ToolTipRole provides helpful hints
            elif role == Qt.ToolTipRole:
                # Confidence tooltip
                if col_name == 'confidence' and row_data.get('matched'):
                    method = row_data.get('method')
                    if method:
                        return get_confidence_tooltip(method)
                
                # Quality tooltip
                elif col_name == 'quality' and row_data.get('matched'):
                    missing_count = row_data.get('missing_metadata_count', 0)
                    bitrate_kbps = row_data.get('bitrate_kbps')
                    # Try to determine which fields are missing
                    missing_fields = []
                    if not row_data.get('title'):
                        missing_fields.append('title')
                    if not row_data.get('artist'):
                        missing_fields.append('artist')
                    if not row_data.get('album'):
                        missing_fields.append('album')
                    if not row_data.get('year'):
                        missing_fields.append('year')
                    return get_quality_tooltip(missing_count, bitrate_kbps, missing_fields)
        
        # Fall back to base implementation for all other columns
        return super().data(index, role)


class AlbumsModel(BaseTableModel):
    """Model for albums aggregated view with coverage statistics."""
    
    def __init__(self, parent=None):
        columns = [
            ('album', 'Album'),
            ('artist', 'Artist'),
            ('track_count', 'Tracks'),
            ('playlist_count', 'Playlists'),
            ('coverage', 'Coverage'),  # Format: "75% (75/100)"
            ('relevance', 'Relevance'),
        ]
        super().__init__(columns, parent)


class ArtistsModel(BaseTableModel):
    """Model for artists aggregated view with coverage statistics."""
    
    def __init__(self, parent=None):
        columns = [
            ('artist', 'Artist'),
            ('track_count', 'Tracks'),
            ('album_count', 'Albums'),
            ('playlist_count', 'Playlists'),
            ('coverage', 'Coverage'),  # Format: "75% (75/100)"
            ('relevance', 'Relevance'),
        ]
        super().__init__(columns, parent)
