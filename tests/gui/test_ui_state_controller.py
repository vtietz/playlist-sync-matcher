"""Tests for UiStateController component."""

import pytest
from PySide6.QtWidgets import QApplication, QPushButton

from psm.gui.ui_state_controller import UiStateController


@pytest.fixture(scope='module')
def qapp():
    """Create QApplication instance for GUI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class MockToolbar:
    """Mock ActionsToolbar for testing."""
    
    def __init__(self):
        self.workflow_enabled = True
    
    def setEnabledForWorkflow(self, enabled: bool):
        """Mock setEnabledForWorkflow method."""
        self.workflow_enabled = enabled


class MockPlaylistsTab:
    """Mock PlaylistsTab for testing."""
    
    def __init__(self):
        self.playlist_actions_enabled = False
    
    def enable_playlist_actions(self, enabled: bool):
        """Mock enable_playlist_actions method."""
        self.playlist_actions_enabled = enabled


@pytest.fixture
def mock_toolbar():
    """Create mock toolbar."""
    return MockToolbar()


@pytest.fixture
def mock_playlists_tab():
    """Create mock playlists tab."""
    return MockPlaylistsTab()


@pytest.fixture
def mock_btn_diagnose(qapp):
    """Create mock diagnose button."""
    return QPushButton("Diagnose")


@pytest.fixture
def ui_state(mock_toolbar, mock_playlists_tab, mock_btn_diagnose):
    """Create UiStateController instance for testing."""
    return UiStateController(
        toolbar=mock_toolbar,
        playlists_tab=mock_playlists_tab,
        btn_diagnose=mock_btn_diagnose
    )


class TestUiStateControllerCreation:
    """Test UI state controller creation."""
    
    def test_controller_creation(self, ui_state):
        """Controller should be created successfully."""
        assert ui_state is not None
    
    def test_initial_running_state(self, ui_state):
        """Initial running state should be False."""
        assert ui_state.is_running is False
    
    def test_initial_track_selection_state(self, ui_state):
        """Initial track selection state should be False."""
        assert ui_state.has_track_selection is False
    
    def test_initial_playlist_selection_state(self, ui_state):
        """Initial playlist selection should be None."""
        assert ui_state.selected_playlist_id is None


class TestUiStateControllerStateMutators:
    """Test state mutation methods."""
    
    def test_set_running_true(self, ui_state):
        """Should set running state to True."""
        ui_state.set_running(True)
        assert ui_state.is_running is True
    
    def test_set_running_false(self, ui_state):
        """Should set running state to False."""
        ui_state.set_running(False)
        assert ui_state.is_running is False
    
    def test_set_track_selection_true(self, ui_state):
        """Should set track selection to True."""
        ui_state.set_track_selection(True)
        assert ui_state.has_track_selection is True
    
    def test_set_track_selection_false(self, ui_state):
        """Should set track selection to False."""
        ui_state.set_track_selection(False)
        assert ui_state.has_track_selection is False
    
    def test_set_selected_playlist(self, ui_state):
        """Should set selected playlist ID."""
        ui_state.set_selected_playlist("playlist_123")
        assert ui_state.selected_playlist_id == "playlist_123"
    
    def test_clear_selected_playlist(self, ui_state):
        """Should clear selected playlist."""
        ui_state.set_selected_playlist("playlist_123")
        ui_state.set_selected_playlist(None)
        assert ui_state.selected_playlist_id is None


class TestUiStateControllerToolbarUpdates:
    """Test toolbar button state updates."""
    
    def test_toolbar_enabled_when_not_running(self, ui_state, mock_toolbar):
        """Toolbar should be enabled when not running."""
        ui_state.set_running(False)
        ui_state._update_toolbar_state()
        assert mock_toolbar.workflow_enabled is True
    
    def test_toolbar_disabled_when_running(self, ui_state, mock_toolbar):
        """Toolbar should be disabled when running."""
        ui_state.set_running(True)
        ui_state._update_toolbar_state()
        assert mock_toolbar.workflow_enabled is False


class TestUiStateControllerPlaylistActionUpdates:
    """Test playlist action button state updates."""
    
    def test_playlist_actions_disabled_when_no_selection(self, ui_state, mock_playlists_tab):
        """Playlist actions should be disabled when no playlist selected."""
        ui_state.set_running(False)
        ui_state.set_selected_playlist(None)
        ui_state._update_playlist_actions_state()
        assert mock_playlists_tab.playlist_actions_enabled is False
    
    def test_playlist_actions_enabled_when_selected_and_not_running(self, ui_state, mock_playlists_tab):
        """Playlist actions should be enabled when playlist selected and not running."""
        ui_state.set_running(False)
        ui_state.set_selected_playlist("playlist_123")
        ui_state._update_playlist_actions_state()
        assert mock_playlists_tab.playlist_actions_enabled is True
    
    def test_playlist_actions_disabled_when_running(self, ui_state, mock_playlists_tab):
        """Playlist actions should be disabled when running, even with selection."""
        ui_state.set_running(True)
        ui_state.set_selected_playlist("playlist_123")
        ui_state._update_playlist_actions_state()
        assert mock_playlists_tab.playlist_actions_enabled is False


class TestUiStateControllerTrackActionUpdates:
    """Test track action button state updates."""
    
    def test_track_actions_disabled_when_no_selection(self, ui_state, mock_btn_diagnose):
        """Track actions should be disabled when no track selected."""
        ui_state.set_running(False)
        ui_state.set_track_selection(False)
        ui_state._update_track_actions_state()
        assert mock_btn_diagnose.isEnabled() is False
    
    def test_track_actions_enabled_when_selected_and_not_running(self, ui_state, mock_btn_diagnose):
        """Track actions should be enabled when track selected and not running."""
        ui_state.set_running(False)
        ui_state.set_track_selection(True)
        ui_state._update_track_actions_state()
        assert mock_btn_diagnose.isEnabled() is True
    
    def test_track_actions_disabled_when_running(self, ui_state, mock_btn_diagnose):
        """Track actions should be disabled when running, even with selection."""
        ui_state.set_running(True)
        ui_state.set_track_selection(True)
        ui_state._update_track_actions_state()
        assert mock_btn_diagnose.isEnabled() is False


class TestUiStateControllerUpdateAllStates:
    """Test update_all_states method."""
    
    def test_update_all_states_when_not_running(self, ui_state, mock_toolbar, mock_playlists_tab, mock_btn_diagnose):
        """All buttons should reflect current state after update_all_states."""
        ui_state.set_running(False)
        ui_state.set_track_selection(True)
        ui_state.set_selected_playlist("playlist_123")
        ui_state.update_all_states()
        
        assert mock_toolbar.workflow_enabled is True
        assert mock_playlists_tab.playlist_actions_enabled is True
        assert mock_btn_diagnose.isEnabled() is True
    
    def test_update_all_states_when_running(self, ui_state, mock_toolbar, mock_playlists_tab, mock_btn_diagnose):
        """All buttons should be disabled when running."""
        ui_state.set_running(True)
        ui_state.set_track_selection(True)
        ui_state.set_selected_playlist("playlist_123")
        ui_state.update_all_states()
        
        assert mock_toolbar.workflow_enabled is False
        assert mock_playlists_tab.playlist_actions_enabled is False
        assert mock_btn_diagnose.isEnabled() is False


class TestUiStateControllerConvenienceMethods:
    """Test convenience methods for common state transitions."""
    
    def test_on_execution_started(self, ui_state, mock_toolbar):
        """Should set running and update all states."""
        ui_state.on_execution_started()
        assert ui_state.is_running is True
        assert mock_toolbar.workflow_enabled is False
    
    def test_on_execution_finished(self, ui_state, mock_toolbar):
        """Should clear running and update all states."""
        ui_state.set_running(True)
        ui_state.on_execution_finished()
        assert ui_state.is_running is False
        assert mock_toolbar.workflow_enabled is True
    
    def test_on_playlist_selected(self, ui_state, mock_playlists_tab):
        """Should update playlist selection and actions."""
        ui_state.set_running(False)
        ui_state.on_playlist_selected("playlist_123")
        assert ui_state.selected_playlist_id == "playlist_123"
        assert mock_playlists_tab.playlist_actions_enabled is True
    
    def test_on_track_selection_changed(self, ui_state, mock_btn_diagnose):
        """Should update track selection and actions."""
        ui_state.set_running(False)
        ui_state.on_track_selection_changed(True)
        assert ui_state.has_track_selection is True
        assert mock_btn_diagnose.isEnabled() is True
    
    def test_enable_actions_true(self, ui_state, mock_toolbar):
        """enable_actions(True) should set not running and enable buttons."""
        ui_state.enable_actions(True)
        assert ui_state.is_running is False
        assert mock_toolbar.workflow_enabled is True
    
    def test_enable_actions_false(self, ui_state, mock_toolbar):
        """enable_actions(False) should set running and disable buttons."""
        ui_state.enable_actions(False)
        assert ui_state.is_running is True
        assert mock_toolbar.workflow_enabled is False


class TestUiStateControllerIntegration:
    """Integration tests for realistic workflows."""
    
    def test_typical_execution_workflow(self, ui_state, mock_toolbar, mock_btn_diagnose):
        """Simulate typical command execution workflow."""
        # Initial state: ready, track selected
        ui_state.set_track_selection(True)
        ui_state.update_all_states()
        assert mock_toolbar.workflow_enabled is True
        assert mock_btn_diagnose.isEnabled() is True
        
        # Start execution
        ui_state.on_execution_started()
        assert mock_toolbar.workflow_enabled is False
        assert mock_btn_diagnose.isEnabled() is False
        
        # Finish execution
        ui_state.on_execution_finished()
        assert mock_toolbar.workflow_enabled is True
        assert mock_btn_diagnose.isEnabled() is True  # Still selected
    
    def test_playlist_selection_workflow(self, ui_state, mock_playlists_tab):
        """Simulate playlist selection workflow."""
        # No selection initially
        ui_state.update_all_states()
        assert mock_playlists_tab.playlist_actions_enabled is False
        
        # Select playlist
        ui_state.on_playlist_selected("playlist_123")
        assert mock_playlists_tab.playlist_actions_enabled is True
        
        # Deselect playlist
        ui_state.on_playlist_selected(None)
        assert mock_playlists_tab.playlist_actions_enabled is False
    
    def test_mixed_state_updates(self, ui_state, mock_toolbar, mock_playlists_tab, mock_btn_diagnose):
        """Test complex state changes."""
        # Setup: not running, both selections active
        ui_state.set_running(False)
        ui_state.set_track_selection(True)
        ui_state.set_selected_playlist("playlist_123")
        ui_state.update_all_states()
        
        assert mock_toolbar.workflow_enabled is True
        assert mock_playlists_tab.playlist_actions_enabled is True
        assert mock_btn_diagnose.isEnabled() is True
        
        # Clear track selection (but keep playlist)
        ui_state.on_track_selection_changed(False)
        assert mock_btn_diagnose.isEnabled() is False
        assert mock_playlists_tab.playlist_actions_enabled is True  # Unchanged
