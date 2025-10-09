"""Debounced search field component.

A reusable QLineEdit with built-in debouncing for search functionality.
"""
from __future__ import annotations
from typing import Optional
from PySide6.QtWidgets import QLineEdit
from PySide6.QtCore import Signal, QTimer
import logging

logger = logging.getLogger(__name__)


class DebouncedSearchField(QLineEdit):
    """Search field with debounced text change events.
    
    This component wraps QLineEdit and provides a debounced textChanged signal
    that only fires after the user stops typing for a specified delay.
    
    This is useful for search fields where you don't want to trigger filtering
    on every keystroke, but only after the user has finished typing.
    
    Signals:
        debouncedTextChanged: Emitted after the debounce delay (with text as parameter)
    
    Example:
        search = DebouncedSearchField(debounce_ms=500)
        search.setPlaceholderText("Search...")
        search.debouncedTextChanged.connect(lambda text: apply_filter(text))
    """
    
    # Signal emitted after debounce delay
    debouncedTextChanged = Signal(str)
    
    def __init__(
        self,
        debounce_ms: int = 500,
        parent: Optional[QLineEdit] = None
    ):
        """Initialize debounced search field.
        
        Args:
            debounce_ms: Delay in milliseconds before emitting debouncedTextChanged
            parent: Parent widget
        """
        super().__init__(parent)
        
        self._debounce_ms = debounce_ms
        
        # Create debounce timer
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._on_debounce_timeout)
        
        # Connect to native textChanged signal
        self.textChanged.connect(self._on_text_changed)
        
        # Enable clear button by default (common for search fields)
        self.setClearButtonEnabled(True)
    
    def _on_text_changed(self, text: str):
        """Handle native text changed event.
        
        Args:
            text: New text value
        """
        # Restart the debounce timer
        self._debounce_timer.start(self._debounce_ms)
    
    def _on_debounce_timeout(self):
        """Handle debounce timer timeout."""
        # Emit the debounced signal with current text
        self.debouncedTextChanged.emit(self.text())
    
    def set_debounce_delay(self, ms: int):
        """Change the debounce delay.
        
        Args:
            ms: New delay in milliseconds
        """
        self._debounce_ms = ms
    
    def get_debounce_delay(self) -> int:
        """Get current debounce delay.
        
        Returns:
            Delay in milliseconds
        """
        return self._debounce_ms


__all__ = ['DebouncedSearchField']
