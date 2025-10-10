"""Albums tab builder - thin wrapper around AlbumsView."""
from __future__ import annotations
from typing import TYPE_CHECKING
from PySide6.QtWidgets import QWidget, QVBoxLayout

if TYPE_CHECKING:
    from ..models.albums_model import AlbumsModel
    from ..views.albums_view import AlbumsView


class AlbumsTab(QWidget):
    """Albums tab containing AlbumsView.
    
    Thin wrapper that exposes the albums view for external access.
    
    Attributes:
        albums_view: AlbumsView instance
    """
    
    def __init__(self, albums_model, parent=None):
        """Initialize albums tab.
        
        Args:
            albums_model: AlbumsModel instance
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Import here to avoid circular dependency
        from ..views.albums_view import AlbumsView
        
        # Create albums view
        self.albums_view = AlbumsView(albums_model)
        layout.addWidget(self.albums_view)
