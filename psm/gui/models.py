"""Qt table models backed by DataFacade.

All models use DatabaseInterface exclusively via DataFacade.
"""
from __future__ import annotations
from typing import Any, List, Dict, Optional
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
import logging

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
        ]
        super().__init__(columns, parent)
    
    def data(self, index, role=Qt.DisplayRole):
        """Override to format Coverage column as '86% (19/22)'."""
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
    - Matched, Local File (match status)
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
            ('local_path', 'Local File'),
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
    
    def data(self, index, role=Qt.DisplayRole):
        """Get cell data with special formatting for matched column."""
        if not index.isValid():
            return None
        
        row = index.row()
        col = index.column()
        
        if 0 <= row < len(self.data_rows) and 0 <= col < len(self.columns):
            col_name = self.columns[col][0]
            value = self.data_rows[row].get(col_name)
            
            # Special handling for matched column (bool -> Yes/No for display)
            if col_name == 'matched' and role == Qt.DisplayRole:
                if isinstance(value, bool):
                    return "Yes" if value else "No"
                # Legacy string format (backward compatibility)
                return str(value) if value is not None else ""
            
            # UserRole returns raw boolean for filtering
            if col_name == 'matched' and role == Qt.UserRole:
                if isinstance(value, bool):
                    return value
                # Legacy string format - convert to bool
                if isinstance(value, str):
                    return value.lower() == "yes"
                return False
        
        # Use parent implementation for all other cases
        return super().data(index, role)
