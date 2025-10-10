"""Artists tab builder - thin wrapper around ArtistsView."""
from __future__ import annotations
from typing import TYPE_CHECKING
from PySide6.QtWidgets import QWidget, QVBoxLayout

if TYPE_CHECKING:
    from ..models.artists_model import ArtistsModel
    from ..views.artists_view import ArtistsView


class ArtistsTab(QWidget):
    """Artists tab containing ArtistsView.
    
    Thin wrapper that exposes the artists view for external access.
    
    Attributes:
        artists_view: ArtistsView instance
    """
    
    def __init__(self, artists_model, parent=None):
        """Initialize artists tab.
        
        Args:
            artists_model: ArtistsModel instance
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Import here to avoid circular dependency
        from ..views.artists_view import ArtistsView
        
        # Create artists view
        self.artists_view = ArtistsView(artists_model)
        layout.addWidget(self.artists_view)
