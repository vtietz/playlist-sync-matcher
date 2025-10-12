"""Tracks tab builder - encapsulates unified tracks view and track actions."""
from __future__ import annotations
from typing import TYPE_CHECKING
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from PySide6.QtCore import Signal

if TYPE_CHECKING:
    pass


class TracksTab(QWidget):
    """Tracks tab containing UnifiedTracksView and track action buttons.

    Encapsulates:
    - UnifiedTracksView (table with filtering)
    - Track action buttons (Diagnose Selected Track)

    Exposes:
    - unified_tracks_view: Reference to the view
    - btn_diagnose: Diagnose button reference

    Signals:
        diagnose_clicked: User clicked diagnose button
        track_selected(track_id): Track selected in table (passthrough from view)
    """

    # Signals
    diagnose_clicked = Signal()
    track_selected = Signal(str)  # track_id

    def __init__(self, unified_tracks_model, parent=None):
        """Initialize tracks tab.

        Args:
            unified_tracks_model: UnifiedTracksModel instance
            parent: Parent widget
        """
        super().__init__(parent)

        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Import here to avoid circular dependency
        from ..views.unified_tracks_view import UnifiedTracksView

        # Create unified tracks view
        self.unified_tracks_view = UnifiedTracksView(unified_tracks_model)
        layout.addWidget(self.unified_tracks_view)

        # Create track action buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(5)

        self.btn_diagnose = QPushButton("Diagnose Selected Track")
        self.btn_diagnose.setEnabled(False)  # Disabled until track selected

        buttons_layout.addWidget(self.btn_diagnose)
        buttons_layout.addStretch()

        layout.addLayout(buttons_layout)

        # Connect signals
        self.btn_diagnose.clicked.connect(self.diagnose_clicked.emit)

        # Forward track_selected signal from view
        self.unified_tracks_view.track_selected.connect(self.track_selected.emit)

    def enable_track_actions(self, enabled: bool):
        """Enable/disable track action buttons.

        Args:
            enabled: True to enable, False to disable
        """
        self.btn_diagnose.setEnabled(enabled)
