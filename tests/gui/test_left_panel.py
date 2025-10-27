"""Tests for LeftPanel component."""

import pytest
from PySide6.QtWidgets import QApplication

from psm.gui.panels.left_panel import LeftPanel
from psm.gui.models import PlaylistsModel, AlbumsModel, ArtistsModel
from psm.gui.components.playlist_filter_bar import PlaylistFilterBar
from psm.gui.components.playlist_proxy_model import PlaylistProxyModel


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for GUI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def left_panel(qapp):
    """Create LeftPanel instance with all required models and components."""
    # Create models (need to keep references to prevent premature deletion)
    playlists_model = PlaylistsModel()
    albums_model = AlbumsModel()
    artists_model = ArtistsModel()

    # Create filter bar
    playlist_filter_bar = PlaylistFilterBar()

    # Create proxy model
    playlist_proxy_model = PlaylistProxyModel()
    playlist_proxy_model.setSourceModel(playlists_model)

    # Create panel
    panel = LeftPanel(playlists_model, albums_model, artists_model, playlist_proxy_model, playlist_filter_bar)

    # Store references to prevent premature deletion
    panel._test_models = (playlists_model, albums_model, artists_model)
    panel._test_filter_bar = playlist_filter_bar
    panel._test_proxy = playlist_proxy_model

    return panel


class TestLeftPanelCreation:
    """Test left panel creation and structure."""

    def test_panel_creation(self, left_panel):
        """Panel should be created successfully."""
        assert left_panel is not None

    def test_has_tab_widget(self, left_panel):
        """Panel should have a tab widget."""
        assert hasattr(left_panel, "tab_widget")
        assert left_panel.tab_widget is not None

    def test_has_three_tabs(self, left_panel):
        """Panel should have exactly 3 tabs."""
        assert left_panel.tab_widget.count() == 3

    def test_tab_names(self, left_panel):
        """Tabs should have correct names."""
        assert left_panel.tab_widget.tabText(0) == "Playlists"
        assert left_panel.tab_widget.tabText(1) == "Artists"
        assert left_panel.tab_widget.tabText(2) == "Albums"

    def test_has_playlists_tab(self, left_panel):
        """Panel should have playlists tab."""
        assert hasattr(left_panel, "playlists_tab")
        assert left_panel.playlists_tab is not None

    def test_has_albums_view(self, left_panel):
        """Panel should have albums view."""
        assert hasattr(left_panel, "albums_view")
        assert left_panel.albums_view is not None

    def test_has_artists_view(self, left_panel):
        """Panel should have artists view."""
        assert hasattr(left_panel, "artists_view")
        assert left_panel.artists_view is not None


class TestLeftPanelProperties:
    """Test left panel public properties."""

    def test_playlists_table_view_property(self, left_panel):
        """Should provide access to playlists table view."""
        table_view = left_panel.playlists_table_view
        assert table_view is not None
        assert table_view is left_panel.playlists_tab.table_view

    def test_btn_pull_one_property(self, left_panel):
        """Should provide access to pull one button."""
        btn = left_panel.btn_pull_one
        assert btn is not None
        assert btn is left_panel.playlists_tab.btn_pull_one

    def test_btn_match_one_property(self, left_panel):
        """Should provide access to match one button."""
        btn = left_panel.btn_match_one
        assert btn is not None
        assert btn is left_panel.playlists_tab.btn_match_one

    def test_btn_export_one_property(self, left_panel):
        """Should provide access to export one button."""
        btn = left_panel.btn_export_one
        assert btn is not None
        assert btn is left_panel.playlists_tab.btn_export_one


class TestLeftPanelTabSwitching:
    """Test tab switching functionality."""

    def test_current_tab_index_initial(self, left_panel):
        """Initial tab should be Playlists (index 0)."""
        assert left_panel.current_tab_index() == 0

    def test_set_current_tab_artists(self, left_panel):
        """Should switch to Artists tab."""
        left_panel.set_current_tab(1)
        assert left_panel.current_tab_index() == 1

    def test_set_current_tab_albums(self, left_panel):
        """Should switch to Albums tab."""
        left_panel.set_current_tab(2)
        assert left_panel.current_tab_index() == 2

    def test_set_current_tab_back_to_playlists(self, left_panel):
        """Should switch back to Playlists tab."""
        left_panel.set_current_tab(1)
        left_panel.set_current_tab(0)
        assert left_panel.current_tab_index() == 0


class TestLeftPanelSignals:
    """Test signal emissions from panel."""

    def test_playlist_selection_changed_signal_exists(self, left_panel):
        """Panel should have playlist_selection_changed signal."""
        assert hasattr(left_panel, "playlist_selection_changed")

    def test_pull_one_clicked_signal_exists(self, left_panel):
        """Panel should have pull_one_clicked signal."""
        assert hasattr(left_panel, "pull_one_clicked")

    def test_match_one_clicked_signal_exists(self, left_panel):
        """Panel should have match_one_clicked signal."""
        assert hasattr(left_panel, "match_one_clicked")

    def test_export_one_clicked_signal_exists(self, left_panel):
        """Panel should have export_one_clicked signal."""
        assert hasattr(left_panel, "export_one_clicked")

    def test_pull_one_signal_emission(self, left_panel):
        """Should emit pull_one_clicked when playlists tab button clicked."""
        emitted = []
        left_panel.pull_one_clicked.connect(lambda: emitted.append(True))

        # Trigger the signal from playlists tab
        left_panel.playlists_tab.pull_one_clicked.emit()

        assert len(emitted) == 1

    def test_match_one_signal_emission(self, left_panel):
        """Should emit match_one_clicked when playlists tab button clicked."""
        emitted = []
        left_panel.match_one_clicked.connect(lambda: emitted.append(True))

        # Trigger the signal from playlists tab
        left_panel.playlists_tab.match_one_clicked.emit()

        assert len(emitted) == 1

    def test_export_one_signal_emission(self, left_panel):
        """Should emit export_one_clicked when playlists tab button clicked."""
        emitted = []
        left_panel.export_one_clicked.connect(lambda: emitted.append(True))

        # Trigger the signal from playlists tab
        left_panel.playlists_tab.export_one_clicked.emit()

        assert len(emitted) == 1


class TestLeftPanelIntegration:
    """Integration tests for realistic usage scenarios."""

    def test_typical_workflow(self, left_panel):
        """Simulate typical usage workflow."""
        # Start on playlists tab
        assert left_panel.current_tab_index() == 0

        # Access playlists table
        table = left_panel.playlists_table_view
        assert table is not None

        # Switch to artists
        left_panel.set_current_tab(1)
        assert left_panel.current_tab_index() == 1

        # Switch to albums
        left_panel.set_current_tab(2)
        assert left_panel.current_tab_index() == 2

    def test_button_access_from_panel(self, left_panel):
        """Should access all playlist action buttons through panel."""
        assert left_panel.btn_pull_one is not None
        assert left_panel.btn_match_one is not None
        assert left_panel.btn_export_one is not None

        # All buttons should be from the same playlists tab
        assert left_panel.btn_pull_one.parent() == left_panel.playlists_tab
        assert left_panel.btn_match_one.parent() == left_panel.playlists_tab
        assert left_panel.btn_export_one.parent() == left_panel.playlists_tab


class TestLeftPanelEdgeCases:
    """Test edge cases and error handling."""

    def test_multiple_tab_switches(self, left_panel):
        """Should handle multiple rapid tab switches."""
        for i in range(3):
            left_panel.set_current_tab(i)
            assert left_panel.current_tab_index() == i

    def test_set_same_tab_twice(self, left_panel):
        """Should handle setting same tab twice."""
        left_panel.set_current_tab(1)
        left_panel.set_current_tab(1)
        assert left_panel.current_tab_index() == 1
