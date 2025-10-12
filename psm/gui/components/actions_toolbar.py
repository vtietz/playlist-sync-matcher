"""ActionsToolbar - Encapsulates the main workflow toolbar.

Extracts ~120 lines of toolbar creation from MainWindow to keep it focused.
Provides a clean API for enabling/disabling workflow buttons and setting watch mode.
"""

from PySide6.QtWidgets import QToolBar, QPushButton, QWidget, QSizePolicy
from PySide6.QtCore import Signal


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
    
    def __init__(self, parent=None):
        """Initialize the actions toolbar.
        
        Args:
            parent: Parent widget (typically MainWindow)
        """
        super().__init__("Actions", parent)
        self.setObjectName("actionsToolbar")
        self.setMovable(False)
        
        self._build_ui()
        self._connect_signals()
    
    def _build_ui(self):
        """Build the toolbar UI with all buttons."""
        # Build button - bright blue
        self._btn_build = QPushButton("▶️  Build (all steps)")
        self._btn_build.setToolTip("Run all steps: Pull, Scan, Match, Report, Export")
        self._btn_build.setStyleSheet("""
            QPushButton {
                background-color: #1a73e8;
                color: white;
                padding: 8px 16px;
                font-weight: bold;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1557b0;
            }
            QPushButton:disabled {
                background-color: #2d2d2d;
                color: #666666;
            }
        """)
        
        # Step button style - darker blue
        step_button_style = """
            QPushButton {
                background-color: #0d47a1;
                color: white;
                padding: 6px 12px;
                font-weight: normal;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background-color: #0a3777;
            }
            QPushButton:disabled {
                background-color: #2d2d2d;
                color: #666666;
            }
        """
        
        # Individual step buttons
        self._btn_pull = QPushButton("⬇️  Pull")
        self._btn_pull.setToolTip("Pull playlists from Spotify")
        self._btn_pull.setStyleSheet(step_button_style)
        
        self._btn_scan = QPushButton("🔍  Scan")
        self._btn_scan.setToolTip("Scan local music library")
        self._btn_scan.setStyleSheet(step_button_style)
        
        self._btn_match = QPushButton("🎯  Match")
        self._btn_match.setToolTip("Match Spotify tracks with local files")
        self._btn_match.setStyleSheet(step_button_style)
        
        self._btn_report = QPushButton("📊  Report")
        self._btn_report.setToolTip("Generate matching reports")
        self._btn_report.setStyleSheet(step_button_style)
        
        self._btn_export = QPushButton("💾  Export")
        self._btn_export.setToolTip("Export playlists to M3U files")
        self._btn_export.setStyleSheet(step_button_style)
        
        # Open Reports button - default style
        self._btn_open_reports = QPushButton("📁  Open Reports")
        self._btn_open_reports.setToolTip("Open reports folder")
        
        # Refresh button - green style
        self._btn_refresh = QPushButton("🔄  Refresh")
        self._btn_refresh.setToolTip("Reload all data from database\n(Use if you ran CLI commands externally)")
        self._btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #0f9d58;
                color: white;
                padding: 6px 12px;
                font-weight: bold;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background-color: #0b7a44;
            }
            QPushButton:disabled {
                background-color: #2d2d2d;
                color: #666666;
            }
        """)
        
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
        self._btn_build.clicked.connect(self.buildClicked.emit)
        self._btn_pull.clicked.connect(self.pullClicked.emit)
        self._btn_scan.clicked.connect(self.scanClicked.emit)
        self._btn_match.clicked.connect(self.matchClicked.emit)
        self._btn_report.clicked.connect(self.reportClicked.emit)
        self._btn_export.clicked.connect(self.exportClicked.emit)
        self._btn_open_reports.clicked.connect(self.openReportsClicked.emit)
        self._btn_refresh.clicked.connect(self.refreshClicked.emit)
        self._btn_watch.toggled.connect(self.watchToggled.emit)
    
    def setEnabledForWorkflow(self, enabled: bool):
        """Enable or disable all workflow buttons.
        
        This should be called when starting/stopping long-running operations
        to prevent concurrent execution. Open Reports stays enabled as it
        doesn't execute CLI commands. Refresh is disabled during data loading
        to prevent overlapping refresh operations.
        
        Args:
            enabled: True to enable buttons, False to disable
        """
        self._btn_build.setEnabled(enabled)
        self._btn_pull.setEnabled(enabled)
        self._btn_scan.setEnabled(enabled)
        self._btn_match.setEnabled(enabled)
        self._btn_report.setEnabled(enabled)
        self._btn_export.setEnabled(enabled)
        self._btn_watch.setEnabled(enabled)
        self._btn_refresh.setEnabled(enabled)  # Disable during data loading
        # Note: _btn_open_reports intentionally stays enabled
    
    def setWatchMode(self, enabled: bool):
        """Set the watch mode toggle state.
        
        Args:
            enabled: True to check the watch mode button, False to uncheck
        """
        # Block signals to prevent triggering watchToggled during programmatic changes
        self._btn_watch.blockSignals(True)
        self._btn_watch.setChecked(enabled)
        self._btn_watch.blockSignals(False)
