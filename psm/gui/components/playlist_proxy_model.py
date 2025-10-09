"""Proxy model for filtering playlists by owner and search text.

This proxy model filters playlist rows based on:
- Owner name filter
- Search text (matches against playlist name and owner name)
"""
from __future__ import annotations
from typing import Optional
from PySide6.QtCore import QSortFilterProxyModel, QModelIndex, Qt
import logging

logger = logging.getLogger(__name__)


class PlaylistProxyModel(QSortFilterProxyModel):
    """Proxy model for filtering playlists.
    
    Supports filtering by:
    - Owner name (exact match)
    - Search text (case-insensitive substring match in name or owner_name)
    """
    
    def __init__(self, parent=None):
        """Initialize playlist proxy model.
        
        Args:
            parent: Parent QObject
        """
        super().__init__(parent)
        
        self._owner_filter: Optional[str] = None
        self._search_text: str = ""
        
        # Use UserRole for sorting (raw values)
        self.setSortRole(Qt.UserRole)
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
    
    def set_owner_filter(self, owner: Optional[str]):
        """Set owner name filter.
        
        Args:
            owner: Owner name to filter by, or None to show all
        """
        self._owner_filter = owner
        self.invalidateFilter()
    
    def set_search_text(self, text: str):
        """Set search text filter.
        
        Args:
            text: Search text (searches name and owner_name columns)
        """
        self._search_text = text.strip().lower()
        self.invalidateFilter()
    
    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        """Determine if a row should be shown based on filters.
        
        Args:
            source_row: Row index in source model
            source_parent: Parent index in source model
            
        Returns:
            True if row should be shown
        """
        source_model = self.sourceModel()
        if source_model is None:
            return True
        
        # Get row data if available (BaseTableModel has get_row_data)
        if hasattr(source_model, 'get_row_data'):
            row_data = source_model.get_row_data(source_row)
            if row_data is None:
                return False
            
            # Apply owner filter
            if self._owner_filter:
                owner_name = row_data.get('owner_name', '')
                if owner_name != self._owner_filter:
                    return False
            
            # Apply search text filter (search in name and owner_name)
            if self._search_text:
                name = (row_data.get('name', '') or '').lower()
                owner_name = (row_data.get('owner_name', '') or '').lower()
                
                # Match if search text is found in either field
                if (self._search_text not in name and 
                    self._search_text not in owner_name):
                    return False
            
            return True
        
        # Fallback: if model doesn't have get_row_data, accept all rows
        return True
    
    def clear_filters(self):
        """Clear all filters."""
        self._owner_filter = None
        self._search_text = ""
        self.invalidateFilter()


__all__ = ['PlaylistProxyModel']
