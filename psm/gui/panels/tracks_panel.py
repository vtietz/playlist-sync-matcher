"""TracksPanel component - Unified tracks view with filtering and diagnosis.

This panel encapsulates:
- UnifiedTracksView (filter bar + sortable table)
- Track selection handling
- Diagnose button for selected tracks
- Signal delegation for track actions
"""
from __future__ import annotations
from typing import Optional, List, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton
)
from PySide6.QtCore import Signal
import logging

from ..views import UnifiedTracksView
from ..models import UnifiedTracksModel
from ..state import FilterStore

logger = logging.getLogger(__name__)


class TracksPanel(QWidget):
    """Panel for unified tracks view with diagnosis capabilities.

    Responsibilities:
    - Encapsulate UnifiedTracksView
    - Track selection state management
    - Diagnose button enable/disable based on selection
    - Signal delegation for track actions

    Signals:
    - track_selected(str): Emitted when a track is selected (track_id)
    - diagnose_clicked(str): Emitted when diagnose button clicked (track_id)
    - manual_match_clicked(str): Emitted when manual match button clicked (track_id)
    - remove_match_clicked(str): Emitted when remove match button clicked (track_id)
    - selection_changed(): Emitted when track selection changes (for UI state updates)

    Properties:
    - unified_tracks_view: Access to UnifiedTracksView
    - tracks_table: Access to QTableView
    - filter_bar: Access to FilterBar
    - proxy_model: Access to UnifiedTracksProxyModel
    - btn_diagnose: Access to diagnose button
    - btn_manual_match: Access to manual match button
    - btn_remove_match: Access to remove match button
    """

    # Signals
    track_selected = Signal(str)  # track_id
    diagnose_clicked = Signal(str)  # track_id
    match_one_clicked = Signal(str)  # track_id - match a single selected track
    manual_match_clicked = Signal(str)  # track_id - manually override match for selected track
    remove_match_clicked = Signal(str)  # track_id - remove match for selected track
    selection_changed = Signal()  # Emitted when selection changes (for parent to update state)

    def __init__(
        self,
        unified_tracks_model: UnifiedTracksModel,
        filter_store: FilterStore,
        parent: Optional[QWidget] = None
    ):
        """Initialize tracks panel.

        Args:
            unified_tracks_model: Model for unified tracks data
            filter_store: Centralized filter state store
            parent: Parent widget
        """
        super().__init__(parent)

        # Store model reference
        self._model = unified_tracks_model
        self._filter_store = filter_store

        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)  # Add small margins

        # Create unified tracks view
        self.unified_tracks_view = UnifiedTracksView(unified_tracks_model)
        layout.addWidget(self.unified_tracks_view)

        # Wire FilterStore to UnifiedTracksView (single source of truth)
        filter_store.filterChanged.connect(self.unified_tracks_view.on_store_filter_changed)

        # Wire FilterBar user actions to FilterStore (bidirectional filtering)
        # When user changes filter dropdowns, FilterStore is updated → emits filterChanged → view updates
        # Note: These connections should be made by parent (MainWindow) to avoid tight coupling
        # We just expose the filter_bar property for wiring

        # Connect track selection to enable/disable track actions
        selection_model = self.unified_tracks_view.tracks_table.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(self._on_selection_changed)

        # Delegate track_selected signal from view
        self.unified_tracks_view.track_selected.connect(self.track_selected.emit)

        # Create track action buttons layout
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(5)

        # Match Selected Track button
        self.btn_match_one = QPushButton("Match Selected Track")
        self.btn_match_one.setEnabled(False)  # Disabled until a track is selected
        self.btn_match_one.clicked.connect(self._on_match_one_clicked)
        self.btn_match_one.setToolTip("Match the selected track with local files")

        # Track-specific action button
        self.btn_diagnose = QPushButton("Diagnose Selected Track")
        self.btn_diagnose.setEnabled(False)  # Disabled until a track is selected
        self.btn_diagnose.clicked.connect(self._on_diagnose_clicked)

        # Manual Match button
        self.btn_manual_match = QPushButton("Manual Match")
        self.btn_manual_match.setEnabled(False)  # Disabled until a track is selected
        self.btn_manual_match.clicked.connect(self._on_manual_match_clicked)
        self.btn_manual_match.setToolTip("Manually override the matched file for the selected track")

        # Remove Match button
        self.btn_remove_match = QPushButton("Remove Match")
        self.btn_remove_match.setEnabled(False)  # Disabled until a track is selected
        self.btn_remove_match.clicked.connect(self._on_remove_match_clicked)
        self.btn_remove_match.setToolTip("Remove the match for the selected track (manual or automatic)")

        buttons_layout.addWidget(self.btn_match_one)
        buttons_layout.addWidget(self.btn_diagnose)
        buttons_layout.addWidget(self.btn_manual_match)
        buttons_layout.addWidget(self.btn_remove_match)
        buttons_layout.addStretch()

        layout.addLayout(buttons_layout)

    @property
    def tracks_table(self):
        """Access to tracks table view."""
        return self.unified_tracks_view.tracks_table

    @property
    def filter_bar(self):
        """Access to filter bar."""
        return self.unified_tracks_view.filter_bar

    @property
    def proxy_model(self):
        """Access to proxy model."""
        return self.unified_tracks_view.proxy_model

    def _on_selection_changed(self, selected, deselected):
        """Handle track selection changes.

        Args:
            selected: Selected items
            deselected: Deselected items
        """
        has_selection = self.tracks_table.selectionModel().hasSelection()
        has_match = self._selected_track_has_match()
        
        # Note: btn_match_one, btn_diagnose, btn_manual_match, and btn_remove_match are managed by UiStateController
        # but we still enable/disable them here for immediate feedback when selection changes
        # UiStateController will override if a command is running
        self.btn_match_one.setEnabled(has_selection)
        self.btn_diagnose.setEnabled(has_selection)
        self.btn_manual_match.setEnabled(has_selection)
        # Remove Match only enabled when track is selected AND has an existing match
        self.btn_remove_match.setEnabled(has_selection and has_match)

        # Emit selection_changed signal for parent to update state
        self.selection_changed.emit()

    def _on_diagnose_clicked(self):
        """Handle diagnose button click - emit signal with selected track ID."""
        track_id = self._get_selected_track_id()

        if not track_id:
            # Get track data for diagnostic logging
            selected_indexes = self.tracks_table.selectionModel().selectedRows()
            if selected_indexes:
                proxy_index = selected_indexes[0]
                source_index = self.proxy_model.mapToSource(proxy_index)
                track_data = self._model.get_row_data(source_index.row())
                if track_data:
                    logger.warning(
                        f"Diagnose clicked but no track_id resolved. "
                        f"Available keys: {list(track_data.keys())}, "
                        f"id={track_data.get('id')}, track_id={track_data.get('track_id')}"
                    )
                else:
                    logger.warning("Diagnose clicked but track_data is None")
            else:
                logger.warning("Diagnose clicked but no track selected")
        else:
            logger.info(f"Emitting diagnose_clicked signal with track_id: {track_id}")
            self.diagnose_clicked.emit(track_id)

    def _on_match_one_clicked(self):
        """Handle match one button click - emit signal with selected track ID."""
        track_id = self._get_selected_track_id()

        if not track_id:
            # Get track data for diagnostic logging
            selected_indexes = self.tracks_table.selectionModel().selectedRows()
            if selected_indexes:
                proxy_index = selected_indexes[0]
                source_index = self.proxy_model.mapToSource(proxy_index)
                track_data = self._model.get_row_data(source_index.row())
                if track_data:
                    logger.warning(
                        f"Match one clicked but no track_id resolved. "
                        f"Available keys: {list(track_data.keys())}, "
                        f"id={track_data.get('id')}, track_id={track_data.get('track_id')}"
                    )
                else:
                    logger.warning("Match one clicked but track_data is None")
            else:
                logger.warning("Match one clicked but no track selected")
        else:
            logger.info(f"Emitting match_one_clicked signal with track_id: {track_id}")
            self.match_one_clicked.emit(track_id)

    def _on_manual_match_clicked(self):
        """Handle manual match button click - emit signal with selected track ID."""
        track_id = self._get_selected_track_id()

        if not track_id:
            # Get track data for diagnostic logging
            selected_indexes = self.tracks_table.selectionModel().selectedRows()
            if selected_indexes:
                proxy_index = selected_indexes[0]
                source_index = self.proxy_model.mapToSource(proxy_index)
                track_data = self._model.get_row_data(source_index.row())
                if track_data:
                    logger.warning(
                        f"Manual match clicked but no track_id resolved. "
                        f"Available keys: {list(track_data.keys())}, "
                        f"id={track_data.get('id')}, track_id={track_data.get('track_id')}"
                    )
                else:
                    logger.warning("Manual match clicked but track_data is None")
            else:
                logger.warning("Manual match clicked but no track selected")
        else:
            logger.info(f"Emitting manual_match_clicked signal with track_id: {track_id}")
            self.manual_match_clicked.emit(track_id)

    def _on_remove_match_clicked(self):
        """Handle remove match button click - emit signal with selected track ID."""
        track_id = self._get_selected_track_id()

        if not track_id:
            # Get track data for diagnostic logging
            selected_indexes = self.tracks_table.selectionModel().selectedRows()
            if selected_indexes:
                proxy_index = selected_indexes[0]
                source_index = self.proxy_model.mapToSource(proxy_index)
                track_data = self._model.get_row_data(source_index.row())
                if track_data:
                    logger.warning(
                        f"Remove match clicked but no track_id resolved. "
                        f"Available keys: {list(track_data.keys())}, "
                        f"id={track_data.get('id')}, track_id={track_data.get('track_id')}"
                    )
                else:
                    logger.warning("Remove match clicked but track_data is None")
            else:
                logger.warning("Remove match clicked but no track selected")
        else:
            logger.info(f"Emitting remove_match_clicked signal with track_id: {track_id}")
            self.remove_match_clicked.emit(track_id)

    def _get_selected_track_id(self) -> Optional[str]:
        """Get the track ID of the currently selected track.

        Returns:
            Track ID if a track is selected, None otherwise
        """
        selected_indexes = self.tracks_table.selectionModel().selectedRows()
        if not selected_indexes:
            return None

        # Map proxy index to source index
        proxy_index = selected_indexes[0]
        source_index = self.proxy_model.mapToSource(proxy_index)
        source_row = source_index.row()

        # Get track data from source model
        track_data = self._model.get_row_data(source_row)
        if not track_data:
            return None

        # Robust identifier resolution: handle both 'id' and 'track_id' keys
        # Selection uses 'id', but some paths may use 'track_id'
        track_id = track_data.get('id') or track_data.get('track_id')
        return track_id

    def _selected_track_has_match(self) -> bool:
        """Check if the currently selected track has a match.

        Returns:
            True if selected track has a match (local_path is not empty), False otherwise
        """
        selected_indexes = self.tracks_table.selectionModel().selectedRows()
        if not selected_indexes:
            logger.debug("_selected_track_has_match: No selection")
            return False

        # Map proxy index to source index
        proxy_index = selected_indexes[0]
        source_index = self.proxy_model.mapToSource(proxy_index)
        source_row = source_index.row()

        # Get track data from source model
        track_data = self._model.get_row_data(source_row)
        if not track_data:
            logger.debug(f"_selected_track_has_match: No track data for row {source_row}")
            return False

        # Check if local_path is not empty (track has a match)
        local_path = track_data.get('local_path', '')
        has_match = bool(local_path)
        logger.debug(f"_selected_track_has_match: local_path='{local_path}', has_match={has_match}")
        return has_match

    def has_selection(self) -> bool:
        """Check if a track is currently selected.

        Returns:
            True if a track is selected, False otherwise
        """
        selection_model = self.tracks_table.selectionModel()
        return selection_model.hasSelection() if selection_model else False

    def refresh_button_states(self):
        """Re-evaluate and update button states based on current selection.
        
        Called when execution finishes to ensure buttons reflect current state.
        """
        has_selection = self.has_selection()
        has_match = self._selected_track_has_match() if has_selection else False
        
        self.btn_match_one.setEnabled(has_selection)
        self.btn_diagnose.setEnabled(has_selection)
        self.btn_manual_match.setEnabled(has_selection)
        self.btn_remove_match.setEnabled(has_selection and has_match)

    def update_tracks(self, tracks: List[Dict[str, Any]], playlists: List[Dict[str, Any]]):
        """Update tracks data in the model.

        Args:
            tracks: List of track dictionaries
            playlists: List of playlist dictionaries (for filter options)
        """
        self._model.set_data(tracks)

    def populate_filter_options(
        self,
        playlists: List[str],
        artists: List[str],
        albums: List[str],
        years: List[str]
    ):
        """Populate filter dropdown options.

        Args:
            playlists: List of playlist names
            artists: List of artist names
            albums: List of album names
            years: List of years
        """
        self.unified_tracks_view.populate_filter_options(playlists, artists, albums, years)
