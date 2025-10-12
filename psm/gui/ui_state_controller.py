"""UiStateController - Centralized UI state management for button enable/disable logic.

This controller encapsulates all UI state logic, eliminating scattered enable/disable
calls throughout MainWindow. It maintains state flags and provides methods to update
button states based on application state.

State Flags:
- is_running: True when a CLI command is executing
- has_track_selection: True when a track is selected in tracks view
- selected_playlist_id: ID of currently selected playlist

Responsibilities:
- Track application execution state
- Coordinate button enable/disable logic
- Centralize conditional UI state updates
- Provide single source of truth for UI state
"""
from __future__ import annotations
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class UiStateController:
    """Centralized controller for UI button enable/disable state management.

    This controller owns the state flags that determine which buttons should be
    enabled or disabled. It provides methods to update state and apply changes
    to UI components.

    Usage:
        controller = UiStateController(toolbar, playlists_tab, btn_diagnose)
        controller.set_running(True)  # Disable most buttons
        controller.set_track_selection(True)  # Track selected
        controller.update_all_states()  # Apply current state to all buttons

    State Management:
        - Buttons are enabled/disabled based on multiple state flags
        - Track actions require: not running AND track selected
        - Playlist actions require: not running AND playlist selected
        - Toolbar actions require: not running (except cancel/watch)
    """

    def __init__(
        self,
        toolbar=None,
        playlists_tab=None,
        btn_diagnose=None,
        btn_match_one=None
    ):
        """Initialize UI state controller.

        Args:
            toolbar: ActionsToolbar instance (for workflow buttons)
            playlists_tab: PlaylistsTab instance (for per-playlist buttons)
            btn_diagnose: QPushButton for track diagnosis
            btn_match_one: QPushButton for matching single track
        """
        # Component references
        self._toolbar = toolbar
        self._playlists_tab = playlists_tab
        self._btn_diagnose = btn_diagnose
        self._btn_match_one = btn_match_one

        # State flags (single source of truth)
        self._is_running: bool = False
        self._has_track_selection: bool = False
        self._selected_playlist_id: Optional[str] = None

    # State accessors

    @property
    def is_running(self) -> bool:
        """Check if a command is currently running."""
        return self._is_running

    @property
    def has_track_selection(self) -> bool:
        """Check if a track is currently selected."""
        return self._has_track_selection

    @property
    def selected_playlist_id(self) -> Optional[str]:
        """Get the currently selected playlist ID."""
        return self._selected_playlist_id

    # State mutators

    def set_running(self, running: bool):
        """Set execution running state.

        When running:
        - Most action buttons are disabled
        - Cancel button is enabled

        Args:
            running: True if command is running, False if ready
        """
        self._is_running = running
        logger.debug(f"UI state: is_running={running}")

    def set_track_selection(self, has_selection: bool):
        """Set track selection state.

        Track actions are only enabled when:
        1. Not running
        2. Track is selected

        Args:
            has_selection: True if track is selected
        """
        self._has_track_selection = has_selection
        logger.debug(f"UI state: has_track_selection={has_selection}")

    def set_selected_playlist(self, playlist_id: Optional[str]):
        """Set selected playlist ID.

        Playlist actions are only enabled when:
        1. Not running
        2. Playlist is selected

        Args:
            playlist_id: ID of selected playlist, or None
        """
        self._selected_playlist_id = playlist_id
        logger.debug(f"UI state: selected_playlist_id={playlist_id}")

    # State update methods

    def update_all_states(self):
        """Update all button states based on current flags.

        This is the master update method that applies current state to all
        managed UI components. Call this after any state change.
        """
        self._update_toolbar_state()
        self._update_playlist_actions_state()
        self._update_track_actions_state()

    def _update_toolbar_state(self):
        """Update toolbar button states."""
        if self._toolbar:
            enabled = not self._is_running
            self._toolbar.setEnabledForWorkflow(enabled)
            logger.debug(f"Toolbar buttons: enabled={enabled}")

    def _update_playlist_actions_state(self):
        """Update per-playlist action button states.

        Playlist actions enabled when:
        1. Not running
        2. Playlist is selected
        """
        should_enable = not self._is_running and self._selected_playlist_id is not None

        if self._playlists_tab:
            self._playlists_tab.enable_playlist_actions(should_enable)
            logger.debug(f"Playlist actions: enabled={should_enable}")

    def _update_track_actions_state(self):
        """Update per-track action button states.

        Track actions enabled when:
        1. Not running
        2. Track is selected
        """
        should_enable = not self._is_running and self._has_track_selection

        if self._btn_diagnose:
            self._btn_diagnose.setEnabled(should_enable)
        if self._btn_match_one:
            self._btn_match_one.setEnabled(should_enable)

        logger.debug(f"Track actions: enabled={should_enable} (running={self._is_running}, has_selection={self._has_track_selection})")

    # Convenience methods (higher-level state changes)

    def on_execution_started(self):
        """Handle execution started - disable most actions.

        Convenience method that:
        1. Sets running state to True
        2. Updates all button states
        """
        self.set_running(True)
        self.update_all_states()

    def on_execution_finished(self):
        """Handle execution finished - re-enable appropriate actions.

        Convenience method that:
        1. Sets running state to False
        2. Updates all button states (respecting selection states)
        """
        self.set_running(False)
        self.update_all_states()

    def on_playlist_selected(self, playlist_id: Optional[str]):
        """Handle playlist selection change.

        Args:
            playlist_id: ID of newly selected playlist, or None
        """
        self.set_selected_playlist(playlist_id)
        self._update_playlist_actions_state()

    def on_track_selection_changed(self, has_selection: bool):
        """Handle track selection change.

        Args:
            has_selection: True if track is now selected
        """
        self.set_track_selection(has_selection)
        self._update_track_actions_state()

    def enable_actions(self, enabled: bool):
        """Legacy compatibility method - enable/disable action buttons.

        This provides backward compatibility with old enable_actions(bool) pattern.
        Prefer using set_running() + update_all_states() for new code.

        Args:
            enabled: True to enable, False to disable
        """
        self.set_running(not enabled)
        self.update_all_states()
