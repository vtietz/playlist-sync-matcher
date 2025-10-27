"""Toolbar component for main actions."""

from __future__ import annotations
from PySide6.QtWidgets import QToolBar, QPushButton, QWidget, QSizePolicy
from PySide6.QtCore import Signal


class ToolbarWidget(QToolBar):
    """Main actions toolbar with standard application commands.

    Provides buttons for:
    - Library actions: Scan, Build, Analyze Quality, Reports
    - Watch mode toggle

    Signals:
        scan_clicked: Scan library requested
        build_clicked: Build requested
        analyze_clicked: Analyze quality requested
        report_clicked: Generate reports requested
        open_reports_clicked: Open reports folder requested
        watch_toggled(bool): Watch mode toggled (True=start, False=stop)
    """

    # Signals
    scan_clicked = Signal()
    build_clicked = Signal()
    analyze_clicked = Signal()
    report_clicked = Signal()
    open_reports_clicked = Signal()
    watch_toggled = Signal(bool)

    def __init__(self, parent=None):
        """Initialize toolbar.

        Args:
            parent: Parent widget
        """
        super().__init__("Actions", parent)
        self.setMovable(False)

        # Create buttons
        self.btn_scan = QPushButton("Scan Library")
        self.btn_build = QPushButton("Build")
        self.btn_analyze = QPushButton("Analyze Quality")
        self.btn_report = QPushButton("Generate Reports")
        self.btn_open_reports = QPushButton("Open Reports")

        # Watch mode toggle
        self.btn_watch = QPushButton("Start Watch Mode")
        self.btn_watch.setCheckable(True)

        # Add to toolbar
        self.addWidget(self.btn_scan)
        self.addWidget(self.btn_build)
        self.addWidget(self.btn_analyze)
        self.addWidget(self.btn_report)
        self.addWidget(self.btn_open_reports)

        # Add spacer to push Watch Mode button to the right
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.addWidget(spacer)

        self.addWidget(self.btn_watch)

        # Connect internal signals
        self.btn_scan.clicked.connect(self.scan_clicked.emit)
        self.btn_build.clicked.connect(self.build_clicked.emit)
        self.btn_analyze.clicked.connect(self.analyze_clicked.emit)
        self.btn_report.clicked.connect(self.report_clicked.emit)
        self.btn_open_reports.clicked.connect(self.open_reports_clicked.emit)
        self.btn_watch.toggled.connect(self.watch_toggled.emit)

    def enable_actions(self, enabled: bool):
        """Enable/disable action buttons (except open reports).

        Args:
            enabled: True to enable, False to disable
        """
        self.btn_scan.setEnabled(enabled)
        self.btn_build.setEnabled(enabled)
        self.btn_analyze.setEnabled(enabled)
        self.btn_report.setEnabled(enabled)
        self.btn_watch.setEnabled(enabled)
        # btn_open_reports stays enabled (no CLI execution)
