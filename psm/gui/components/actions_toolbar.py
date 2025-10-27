"""ActionsToolbar - Encapsulates the main workflow toolbar.

Extracts ~120 lines of toolbar creation from MainWindow to keep it focused.
Provides a clean API for enabling/disabling workflow buttons and setting watch mode.
"""

from PySide6.QtWidgets import QToolBar, QPushButton, QWidget, QSizePolicy
from PySide6.QtCore import Signal, Qt
from typing import Optional


class ActionsToolbar(QToolBar):
    """Main toolbar with workflow buttons and watch mode toggle.

    Signals:
        buildClicked: Build all steps clicked
        pullClicked: Pull clicked
        scanClicked: Scan clicked
        matchClicked: Match clicked
        reportClicked: Report clicked
        exportClicked: Export clicked
        openReportsClicked: Open Reports clicked
        watchToggled(bool): Watch Mode toggled (checked state)
    """

    # Signals
    buildClicked = Signal()
    pullClicked = Signal()
    scanClicked = Signal()
    matchClicked = Signal()
    reportClicked = Signal()
    exportClicked = Signal()
    openReportsClicked = Signal()
    refreshClicked = Signal()  # NEW: Manual refresh button
    watchToggled = Signal(bool)
    cancelClicked = Signal()  # NEW: Cancel currently running action

    def __init__(self, parent=None):
        """Initialize the actions toolbar.

        Args:
            parent: Parent widget (typically MainWindow)
        """
        super().__init__("Actions", parent)
        self.setObjectName("actionsToolbar")
        self.setMovable(False)

        # Track which action is running for cancel functionality
        self._running_action: Optional[str] = None

        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        """Build the toolbar UI with all buttons."""
        # Build button - bright blue
        self._btn_build = QPushButton("▶️  Build (all steps)")
        self._btn_build.setToolTip("Run all steps: Pull, Scan, Match, Report, Export")
        self._btn_build.setStyleSheet(self._get_build_button_style())

        # Individual step buttons - darker blue
        self._btn_pull = QPushButton("⬇️  Pull")
        self._btn_pull.setToolTip("Pull playlists from Spotify")
        self._btn_pull.setStyleSheet(self._get_step_button_style())

        self._btn_scan = QPushButton("🔍  Scan")
        self._btn_scan.setToolTip("Scan local music library")
        self._btn_scan.setStyleSheet(self._get_step_button_style())

        self._btn_match = QPushButton("🎯  Match")
        self._btn_match.setToolTip("Match Spotify tracks with local files")
        self._btn_match.setStyleSheet(self._get_step_button_style())

        self._btn_report = QPushButton("📊  Report")
        self._btn_report.setToolTip("Generate matching reports")
        self._btn_report.setStyleSheet(self._get_step_button_style())

        self._btn_export = QPushButton("💾  Export")
        self._btn_export.setToolTip("Export playlists to M3U files")
        self._btn_export.setStyleSheet(self._get_step_button_style())

        # Open Reports button - default style
        self._btn_open_reports = QPushButton("📁  Open Reports")
        self._btn_open_reports.setToolTip("Open reports folder")

        # Refresh button - same blue style as other workflow buttons
        self._btn_refresh = QPushButton("🔄  Refresh")
        self._btn_refresh.setToolTip("Reload all data from database\n(Use if you ran CLI commands externally)")
        self._btn_refresh.setStyleSheet(self._get_step_button_style())

        # Add left-side workflow buttons
        self.addWidget(self._btn_build)
        self.addWidget(self._btn_pull)
        self.addWidget(self._btn_scan)
        self.addWidget(self._btn_match)
        self.addWidget(self._btn_export)
        self.addWidget(self._btn_report)
        self.addWidget(self._btn_open_reports)
        self.addSeparator()
        self.addWidget(self._btn_refresh)

        # Add spacer to push Watch Mode to the right
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.addWidget(spacer)

        # Watch Mode button - right-aligned, checkable
        self._btn_watch = QPushButton("👁️  Watch Mode")
        self._btn_watch.setCheckable(True)
        self._btn_watch.setToolTip("Toggle Watch Mode - automatically rebuild when files change")
        self.addWidget(self._btn_watch)

    def _connect_signals(self):
        """Connect internal button signals to public signals."""
        # Wrap signals to track which button was clicked
        self._btn_build.clicked.connect(lambda: self._on_button_clicked(self._btn_build, self.buildClicked))
        self._btn_pull.clicked.connect(lambda: self._on_button_clicked(self._btn_pull, self.pullClicked))
        self._btn_scan.clicked.connect(lambda: self._on_button_clicked(self._btn_scan, self.scanClicked))
        self._btn_match.clicked.connect(lambda: self._on_button_clicked(self._btn_match, self.matchClicked))
        self._btn_report.clicked.connect(lambda: self._on_button_clicked(self._btn_report, self.reportClicked))
        self._btn_export.clicked.connect(lambda: self._on_button_clicked(self._btn_export, self.exportClicked))
        self._btn_open_reports.clicked.connect(self.openReportsClicked.emit)
        self._btn_refresh.clicked.connect(self.refreshClicked.emit)
        self._btn_watch.toggled.connect(self.watchToggled.emit)

    def _on_button_clicked(self, button: QPushButton, signal: Signal):
        """Track button click and emit signal or cancel if button is running.

        If the button is currently highlighted (running), clicking it again
        will cancel the action instead of starting a new one.

        Args:
            button: The button that was clicked
            signal: The signal to emit for starting the action
        """
        # Check if this button is currently running (highlighted orange)
        # If so, cancel instead of starting
        button_action_map = {
            self._btn_build: "build",
            self._btn_pull: "pull",
            self._btn_scan: "scan",
            self._btn_match: "match",
            self._btn_export: "export",
            self._btn_report: "report",
            self._btn_refresh: "refresh",
        }

        action_name = button_action_map.get(button)

        if action_name and action_name == self._running_action:
            # Button is running - cancel it
            self.cancelClicked.emit()
            return

        # Button is not running - start the action
        signal.emit()

    def setEnabledForWorkflow(self, enabled: bool):
        """Enable or disable all workflow buttons.

        This should be called when starting/stopping long-running operations
        to prevent concurrent execution. Open Reports stays enabled as it
        doesn't execute CLI commands. Refresh is disabled during data loading
        to prevent overlapping refresh operations.

        Note: The running button is kept enabled by setActionState() when
        state is 'running', allowing users to click it to cancel.

        Args:
            enabled: True to enable buttons, False to disable
        """
        self._btn_build.setEnabled(enabled)
        self._btn_pull.setEnabled(enabled)
        self._btn_scan.setEnabled(enabled)
        self._btn_match.setEnabled(enabled)
        self._btn_report.setEnabled(enabled)
        self._btn_export.setEnabled(enabled)
        self._btn_refresh.setEnabled(enabled)  # Disable during data loading
        # Note: _btn_open_reports and _btn_watch intentionally stay enabled
        # Watch can be toggled even during operations

    def setWatchMode(self, enabled: bool):
        """Set the watch mode toggle state.

        Args:
            enabled: True to check the watch mode button, False to uncheck
        """
        # Block signals to prevent triggering watchToggled during programmatic changes
        self._btn_watch.blockSignals(True)
        self._btn_watch.setChecked(enabled)
        self._btn_watch.blockSignals(False)

    def highlightBuildStep(self, step: str):
        """Highlight a specific build step button during multi-step Build execution.

        Called when Build command is running to show which step is active.
        The Build button remains highlighted (set by _on_button_clicked),
        and this method additionally highlights the current step button.

        Args:
            step: Step name ('pull', 'scan', 'match', 'export', 'report') or None to clear
        """
        # Map step names to buttons
        step_buttons = {
            "pull": self._btn_pull,
            "scan": self._btn_scan,
            "match": self._btn_match,
            "export": self._btn_export,
            "report": self._btn_report,
        }

        # Clear previous step highlighting (restore all step buttons to disabled gray)
        for btn in step_buttons.values():
            if btn.isEnabled():  # Don't change enabled buttons (shouldn't happen during build)
                continue
            # Apply disabled style (buttons are disabled during build)
            btn.setStyleSheet(self._get_step_button_style())

        # Highlight the current step if specified
        if step and step in step_buttons:
            self._apply_active_style(step_buttons[step])

    def _apply_active_style(self, button: QPushButton):
        """Apply dark orange active styling to button.

        Preserves the button's original padding to prevent size changes.

        Args:
            button: Button to highlight as active
        """
        # Determine padding based on button type to maintain size consistency
        if button == self._btn_build or button == self._btn_refresh:
            padding = "8px 16px"
        else:
            # Step buttons use smaller padding
            padding = "6px 12px"

        # Dark orange background for active/running state
        active_style = f"""
            QPushButton {{
                background-color: #ff8c00;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 4px;
                padding: {padding};
            }}
            QPushButton:disabled {{
                background-color: #cc7000;
                color: #f0f0f0;
            }}
        """
        button.setStyleSheet(active_style)

    def _restore_button_style(self, button: QPushButton):
        """Restore original button styling after operation completes.

        Args:
            button: Button to restore styling for
        """
        # Determine which style category this button belongs to
        if button == self._btn_build:
            button.setStyleSheet(self._get_build_button_style())
        else:
            # All step buttons (Pull, Scan, Match, Report, Export, Refresh)
            button.setStyleSheet(self._get_step_button_style())

    def _get_build_button_style(self) -> str:
        """Get stylesheet for Build button (bright blue).

        Returns:
            QSS stylesheet string
        """
        return """
            QPushButton {
                background-color: #1a73e8;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #1557b0;
            }
            QPushButton:disabled {
                background-color: #2d2d2d;
                color: #666666;
            }
        """

    def _get_step_button_style(self) -> str:
        """Get stylesheet for step buttons (darker blue).

        Returns:
            QSS stylesheet string
        """
        return """
            QPushButton {
                background-color: #0d47a1;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #0a3777;
            }
            QPushButton:disabled {
                background-color: #2d2d2d;
                color: #666666;
            }
        """

    def _get_error_style(self, button: QPushButton) -> str:
        """Get error (red) style with button-appropriate padding.

        Args:
            button: Button to style (determines padding)

        Returns:
            QSS stylesheet string
        """
        padding = "8px 16px" if button in [self._btn_build, self._btn_refresh] else "6px 12px"
        return f"""
            QPushButton {{
                background-color: #d93025;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 4px;
                padding: {padding};
            }}
            QPushButton:disabled {{
                background-color: #a52519;
                color: #f0f0f0;
            }}
        """

    def _get_button_for_action(self, action_name: str) -> Optional[QPushButton]:
        """Map action name to corresponding button.

        Args:
            action_name: Action name from CLI command (e.g., 'pull', 'scan', 'match')

        Returns:
            Corresponding button or None if not mapped
        """
        action_map = {
            "build": self._btn_build,
            "pull": self._btn_pull,
            "scan": self._btn_scan,
            "match": self._btn_match,
            "export": self._btn_export,
            "report": self._btn_report,
        }
        return action_map.get(action_name)

    def setActionState(self, action_name: str, state: str):
        """Set visual state for an action button.

        Args:
            action_name: Action name ('pull', 'scan', 'match', 'export', 'report', 'build')
            state: State to apply ('idle', 'running', 'error')
        """
        button = self._get_button_for_action(action_name)
        if not button:
            # Not all commands have toolbar buttons (e.g., diagnose, config)
            # This is expected and not an error
            return

        if state == "running":
            # Reset all buttons to idle state before starting new action
            # This clears any previous error states
            self.resetAllActionStates()

            self._running_action = action_name
            self._apply_active_style(button)
            button.setEnabled(True)  # Keep button enabled for cancellation
            original_tooltip = button.toolTip().replace(" (Click to cancel)", "")
            button.setToolTip(f"{original_tooltip} (Click to cancel)")
        elif state == "error":
            self._running_action = None
            button.setStyleSheet(self._get_error_style(button))
            button.setCursor(Qt.ArrowCursor)
            button.setToolTip(button.toolTip().replace(" (Click to cancel)", ""))
        elif state == "idle":
            self._running_action = None
            self._restore_button_style(button)
            button.setCursor(Qt.ArrowCursor)
            button.setToolTip(button.toolTip().replace(" (Click to cancel)", ""))

    def resetAllActionStates(self):
        """Reset all action buttons to their default (idle) states."""
        self._running_action = None
        for button in [
            self._btn_build,
            self._btn_pull,
            self._btn_scan,
            self._btn_match,
            self._btn_export,
            self._btn_report,
        ]:
            self._restore_button_style(button)
            button.setCursor(Qt.ArrowCursor)
            button.setToolTip(button.toolTip().replace(" (Click to cancel)", ""))
