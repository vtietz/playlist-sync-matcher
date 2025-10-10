"""Left panel with Playlists, Artists, and Albums tabs.

This panel encapsulates the entire left sidebar of the main window,
containing tabbed views for playlists, artists, and albums.
"""
from __future__ import annotations
from typing import TYPE_CHECKING
from PySide6.QtWidgets import QWidget, QTabWidget
from PySide6.QtCore import Signal, QItemSelection
import logging

if TYPE_CHECKING:
    from psm.gui.models import PlaylistsModel, AlbumsModel, ArtistsModel
    from psm.gui.components.playlist_filter_bar import PlaylistFilterBar
    from psm.gui.components.playlist_proxy_model import PlaylistProxyModel

from psm.gui.tabs import PlaylistsTab
from psm.gui.views import AlbumsView, ArtistsView

logger = logging.getLogger(__name__)


class LeftPanel(QWidget):
    """Left sidebar panel with Playlists, Artists, and Albums tabs.
    
    This panel encapsulates:
    - Tab widget with 3 tabs (Playlists, Artists, Albums)
    - PlaylistsTab with table, filter bar, and action buttons
    - ArtistsView with artists table
    - AlbumsView with albums table
    
    Signals:
        playlist_selection_changed(QItemSelection, QItemSelection): Playlist selection changed (selected, deselected)
        pull_one_clicked: Pull selected playlist
        match_one_clicked: Match selected playlist
        export_one_clicked: Export selected playlist
    
    Example:
        left_panel = LeftPanel(
            playlists_model, albums_model, artists_model,
            playlist_proxy_model, playlist_filter_bar
        )
        left_panel.playlist_selection_changed.connect(handler)
    """
    
    # Signals
    playlist_selection_changed = Signal(QItemSelection, QItemSelection)  # selected, deselected
    pull_one_clicked = Signal()
    match_one_clicked = Signal()
    export_one_clicked = Signal()
    
    def __init__(
        self,
        playlists_model: PlaylistsModel,
        albums_model: AlbumsModel,
        artists_model: ArtistsModel,
        playlist_proxy_model: PlaylistProxyModel,
        playlist_filter_bar: PlaylistFilterBar,
        parent: QWidget = None
    ):
        """Initialize left panel.
        
        Args:
            playlists_model: Playlists data model
            albums_model: Albums data model
            artists_model: Artists data model
            playlist_proxy_model: Proxy model for playlist filtering
            playlist_filter_bar: Filter bar for playlists
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Store models
        self._playlists_model = playlists_model
        self._albums_model = albums_model
        self._artists_model = artists_model
        self._playlist_proxy_model = playlist_proxy_model
        self._playlist_filter_bar = playlist_filter_bar
        
        # Create UI
        self._create_ui()
    
    def _create_ui(self):
        """Create the tab widget and tabs."""
        from PySide6.QtWidgets import QVBoxLayout
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("leftTabs")
        
        # Tab 1: Playlists
        self.playlists_tab = self._create_playlists_tab()
        self.tab_widget.addTab(self.playlists_tab, "Playlists")
        
        # Tab 2: Artists (swapped order with Albums)
        self.artists_view = self._create_artists_tab()
        self.tab_widget.addTab(self.artists_view, "Artists")
        
        # Tab 3: Albums
        self.albums_view = self._create_albums_tab()
        self.tab_widget.addTab(self.albums_view, "Albums")
        
        layout.addWidget(self.tab_widget)
    
    def _create_playlists_tab(self) -> PlaylistsTab:
        """Create the playlists tab content."""
        # Create playlists tab using builder
        playlists_tab = PlaylistsTab(
            playlists_model=self._playlists_model,
            playlist_proxy_model=self._playlist_proxy_model,
            playlist_filter_bar=self._playlist_filter_bar,
            parent=self
        )
        
        # Wire signals from tab to panel
        playlists_tab.selection_changed.connect(self.playlist_selection_changed.emit)
        playlists_tab.pull_one_clicked.connect(self.pull_one_clicked.emit)
        playlists_tab.match_one_clicked.connect(self.match_one_clicked.emit)
        playlists_tab.export_one_clicked.connect(self.export_one_clicked.emit)
        
        return playlists_tab
    
    def _create_albums_tab(self) -> AlbumsView:
        """Create the albums tab content."""
        return AlbumsView(self._albums_model)
    
    def _create_artists_tab(self) -> ArtistsView:
        """Create the artists tab content."""
        return ArtistsView(self._artists_model)
    
    # Public API for accessing child components
    
    @property
    def playlists_table_view(self):
        """Get playlists table view."""
        return self.playlists_tab.table_view
    
    @property
    def btn_pull_one(self):
        """Get pull one button."""
        return self.playlists_tab.btn_pull_one
    
    @property
    def btn_match_one(self):
        """Get match one button."""
        return self.playlists_tab.btn_match_one
    
    @property
    def btn_export_one(self):
        """Get export one button."""
        return self.playlists_tab.btn_export_one
    
    def current_tab_index(self) -> int:
        """Get current tab index.
        
        Returns:
            Current tab index (0=Playlists, 1=Artists, 2=Albums)
        """
        return self.tab_widget.currentIndex()
    
    def set_current_tab(self, index: int):
        """Set current tab by index.
        
        Args:
            index: Tab index to activate (0=Playlists, 1=Artists, 2=Albums)
        """
        self.tab_widget.setCurrentIndex(index)
