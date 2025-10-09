"""Custom delegate for rendering clickable folder icons in local file path cells.

Adds a small folder icon (📁) next to local file paths that opens the containing
folder in the system file explorer when clicked.
"""
from __future__ import annotations
from typing import Optional
import os
import subprocess
import platform
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem
from PySide6.QtCore import Qt, QRect, QUrl, QSize
from PySide6.QtGui import QPainter, QPen, QColor, QDesktopServices
import logging

logger = logging.getLogger(__name__)


class FolderDelegate(QStyledItemDelegate):
    """Delegate that adds clickable folder icons to local file path cells.
    
    For cells that contain local file paths (non-empty), this delegate renders
    a small folder icon (📁) that can be clicked to open the containing folder
    in the system file explorer.
    
    The delegate checks Qt.DisplayRole for the file path string.
    """
    
    ICON_SIZE = 14  # Size of the folder icon
    ICON_PADDING = 4  # Padding around the icon
    
    def __init__(self, parent=None):
        """Initialize delegate.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._hover_index = None
    
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        """Paint the cell with text and optional folder icon.
        
        Args:
            painter: QPainter for rendering
            option: Style options
            index: Model index
        """
        # Let the base class paint the text
        super().paint(painter, option, index)
        
        # Check if this cell has a file path
        file_path = index.data(Qt.DisplayRole)
        
        if file_path and isinstance(file_path, str) and file_path.strip():
            # Draw a small folder icon on the right side
            icon_rect = self._get_icon_rect(option.rect)
            
            # Draw icon background on hover
            if self._hover_index == index:
                painter.save()
                painter.setBrush(QColor(255, 165, 0, 40))  # Light orange
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(icon_rect.adjusted(-2, -2, 2, 2), 3, 3)
                painter.restore()
            
            # Draw the folder icon
            painter.save()
            pen = QPen(QColor(255, 140, 0))  # Dark orange
            painter.setPen(pen)
            painter.setFont(option.font)
            painter.drawText(icon_rect, Qt.AlignCenter, "📁")
            painter.restore()
    
    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        """Calculate size hint including space for folder icon.
        
        Args:
            option: Style options
            index: Model index
            
        Returns:
            Recommended size for the cell
        """
        size = super().sizeHint(option, index)
        
        # Add space for the folder icon if this cell has a file path
        file_path = index.data(Qt.DisplayRole)
        if file_path and isinstance(file_path, str) and file_path.strip():
            size.setWidth(size.width() + self.ICON_SIZE + self.ICON_PADDING * 2)
        
        return size
    
    def editorEvent(self, event, model, option: QStyleOptionViewItem, index):
        """Handle mouse events for clicking the folder icon.
        
        Args:
            event: Mouse event
            model: Data model
            option: Style options
            index: Model index
            
        Returns:
            True if event was handled
        """
        # Only handle mouse button release
        if event.type() == event.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            # Check if click was on the icon
            icon_rect = self._get_icon_rect(option.rect)
            if icon_rect.contains(event.pos()):
                file_path = index.data(Qt.DisplayRole)
                
                if file_path and isinstance(file_path, str) and file_path.strip():
                    self._open_folder(file_path)
                    return True
        
        # Track hover for visual feedback
        elif event.type() == event.Type.MouseMove:
            icon_rect = self._get_icon_rect(option.rect)
            if icon_rect.contains(event.pos()):
                if self._hover_index != index:
                    self._hover_index = index
                    # Request repaint
                    if hasattr(self.parent(), 'viewport'):
                        self.parent().viewport().update()
            else:
                if self._hover_index == index:
                    self._hover_index = None
                    if hasattr(self.parent(), 'viewport'):
                        self.parent().viewport().update()
        
        return super().editorEvent(event, model, option, index)
    
    def _get_icon_rect(self, cell_rect: QRect) -> QRect:
        """Calculate the rectangle for the folder icon.
        
        Args:
            cell_rect: Full cell rectangle
            
        Returns:
            Rectangle for the icon
        """
        # Position icon on the right side of the cell
        x = cell_rect.right() - self.ICON_SIZE - self.ICON_PADDING
        y = cell_rect.center().y() - self.ICON_SIZE // 2
        return QRect(x, y, self.ICON_SIZE, self.ICON_SIZE)
    
    def _open_folder(self, file_path: str):
        """Open the folder containing the file in the system file explorer.
        
        Args:
            file_path: Path to the file
        """
        try:
            # Normalize path
            file_path = os.path.normpath(file_path)
            
            # Check if file exists
            if not os.path.exists(file_path):
                logger.warning(f"File does not exist: {file_path}")
                return
            
            # Get the directory containing the file
            if os.path.isfile(file_path):
                folder_path = os.path.dirname(file_path)
            else:
                folder_path = file_path
            
            # Open folder with platform-specific command
            system = platform.system()
            
            if system == "Windows":
                # Windows: Use explorer with /select to highlight the file
                if os.path.isfile(file_path):
                    subprocess.run(["explorer", "/select,", file_path], check=False)
                else:
                    subprocess.run(["explorer", folder_path], check=False)
            elif system == "Darwin":  # macOS
                # macOS: Use open command
                if os.path.isfile(file_path):
                    subprocess.run(["open", "-R", file_path], check=False)
                else:
                    subprocess.run(["open", folder_path], check=False)
            else:  # Linux and others
                # Linux: Use xdg-open (most common)
                # Note: xdg-open doesn't support file selection, only folder opening
                subprocess.run(["xdg-open", folder_path], check=False)
            
            logger.info(f"Opened folder: {folder_path}")
            
        except Exception as e:
            logger.error(f"Failed to open folder for {file_path}: {e}")


__all__ = ['FolderDelegate']
