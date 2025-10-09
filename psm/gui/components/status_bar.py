"""Status bar component with stats and execution status.

Provides a clean status bar showing:
- Left: Execution status indicator and cancel button
- Right: Statistics (tracks, playlists, etc.)
"""
from __future__ import annotations
from typing import Dict, Any
from PySide6.QtWidgets import QWidget, QPushButton, QLabel
from PySide6.QtCore import Signal
from PySide6.QtGui import QFont


class StatusBar:
    """Status bar manager for stats and execution status.
    
    This class manages status bar widgets without being a QWidget itself,
    allowing it to work with QMainWindow.statusBar().
    """
    
    # Signal for cancel button clicks
    on_cancel_clicked = Signal()
    
    def __init__(self, status_bar_widget):
        """Initialize status bar components.
        
        Args:
            status_bar_widget: QStatusBar from QMainWindow
        """
        self.status_bar = status_bar_widget
        
        # Status indicator label (left side - shows current state/action)
        self.status_label = QLabel("● Ready")
        self.status_label.setFont(QFont("Segoe UI", 9))
        self.status_label.setStyleSheet("color: #28a745; font-weight: bold;")  # Green
        self.status_bar.addWidget(self.status_label)
        
        # Cancel button (left side - only visible when running)
        self.btn_cancel = QPushButton("✕")
        self.btn_cancel.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.btn_cancel.setFixedWidth(30)  # Small fixed width
        self.btn_cancel.setFixedHeight(20)  # Fixed height
        self.btn_cancel.setVisible(False)  # Hidden by default
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                color: #0066cc;
                font-weight: bold;
                background: #e6f2ff;
                border: 1px solid #0066cc;
                border-radius: 3px;
                padding: 2px;
            }
            QPushButton:hover {
                background: #cce5ff;
            }
        """)
        self.status_bar.addWidget(self.btn_cancel)
        
        # Spacer to push stats to the right
        spacer = QWidget()
        self.status_bar.addWidget(spacer, 1)  # Stretch factor 1
        
        # Stats label (right side)
        self.stats_label = QLabel("")
        self.stats_label.setFont(QFont("Segoe UI Emoji", 9))
        self.status_bar.addPermanentWidget(self.stats_label)
    
    def update_stats(self, counts: Dict[str, Any]):
        """Update statistics display.
        
        Args:
            counts: Dict with 'tracks', 'matches', 'playlists' keys
        """
        tracks = counts.get('tracks', 0)
        matches = counts.get('matches', 0)  # Use 'matches' not 'matched'
        playlists = counts.get('playlists', 0)
        
        match_pct = f"{matches / tracks * 100:.1f}%" if tracks > 0 else "0%"
        self.stats_label.setText(
            f"📀 {tracks} tracks | ✓ {matches} matched ({match_pct}) | 🎵 {playlists} playlists"
        )
    
    def set_execution_status(self, running: bool, message: str = ""):
        """Set execution status indicator.
        
        Args:
            running: True if command is running, False if ready
            message: Optional status message (for running state)
        """
        if running:
            # Show running status (blue) and show cancel button
            status_text = f"● Running{': ' + message if message else ''}"
            self.status_label.setText(status_text)
            self.status_label.setStyleSheet("color: #0066cc; font-weight: bold;")  # Blue
            self.btn_cancel.setVisible(True)
        else:
            # Show ready status (green) and hide cancel button
            self.status_label.setText("● Ready")
            self.status_label.setStyleSheet("color: #28a745; font-weight: bold;")  # Green
            self.btn_cancel.setVisible(False)
    
    def connect_cancel(self, callback):
        """Connect cancel button to callback.
        
        Args:
            callback: Function to call when cancel is clicked
        """
        self.btn_cancel.clicked.connect(callback)


__all__ = ["StatusBar"]
