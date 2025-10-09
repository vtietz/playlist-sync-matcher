"""Reusable log panel component with emoji support.

This component provides a consistent log display widget with:
- Emoji-capable font (Segoe UI Emoji)
- Plain text mode for performance
- Clear/append API
- Optional maximum height control
"""
from __future__ import annotations
from typing import Optional
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLabel
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt
import logging

logger = logging.getLogger(__name__)


class LogPanel(QWidget):
    """Reusable log display widget with emoji support.
    
    This widget provides a read-only text display optimized for showing
    CLI output with Unicode characters and emojis.
    
    Example:
        log_panel = LogPanel(title="Command Output", max_height=200)
        log_panel.append("✓ Operation completed")
        log_panel.clear()
    """
    
    def __init__(
        self,
        title: Optional[str] = None,
        max_height: Optional[int] = None,
        font_size: int = 9,
        parent: Optional[QWidget] = None
    ):
        """Initialize log panel.
        
        Args:
            title: Optional title label above log
            max_height: Optional maximum height in pixels
            font_size: Font size for log text (default: 9)
            parent: Parent widget
        """
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Optional title
        if title:
            title_label = QLabel(title)
            title_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
            layout.addWidget(title_label)
        
        # Log text display
        self.log_text = QTextEdit()
        self.log_text.setObjectName("logWindow")  # For stylesheet targeting
        self.log_text.setReadOnly(True)
        self.log_text.setAcceptRichText(False)  # Plain text mode for performance
        
        # Set emoji-capable font for Unicode character support
        emoji_font = QFont("Segoe UI Emoji", font_size)
        self.log_text.setFont(emoji_font)
        
        # Optional height limit
        if max_height:
            self.log_text.setMaximumHeight(max_height)
        
        layout.addWidget(self.log_text)
    
    def append(self, text: str):
        """Append text to log.
        
        Args:
            text: Text to append (supports Unicode/emoji)
        """
        self.log_text.append(text)
    
    def clear(self):
        """Clear all log content."""
        self.log_text.clear()
    
    def set_text(self, text: str):
        """Set log content, replacing existing text.
        
        Args:
            text: New log content
        """
        self.log_text.setPlainText(text)
    
    def get_text(self) -> str:
        """Get current log content.
        
        Returns:
            Plain text content of log
        """
        return self.log_text.toPlainText()

