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
        
        if role == Qt.DisplayRole:
            row = index.row()
            col = index.column()
            
            if 0 <= row < len(self.data_rows) and 0 <= col < len(self.columns):
                col_name = self.columns[col][0]
                value = self.data_rows[row].get(col_name)
                
                # Format special types
                if isinstance(value, float):
                    return f"{value:.1f}"
                elif value is None:
                    return ""
                
                return str(value)
        
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
            ('track_count', 'Tracks'),
        ]
        super().__init__(columns, parent)


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
