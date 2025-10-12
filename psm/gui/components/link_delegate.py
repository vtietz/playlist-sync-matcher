"""Custom delegate for rendering clickable link icons in table cells.

Adds a small link icon (🔗) next to linkable items that opens the item
in the streaming provider (Spotify) when clicked.
"""
from __future__ import annotations
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem
from PySide6.QtCore import Qt, QRect, QUrl, QSize
from PySide6.QtGui import QPainter, QPen, QColor, QDesktopServices
import logging

from ...providers.links import get_link_generator

logger = logging.getLogger(__name__)


class LinkDelegate(QStyledItemDelegate):
    """Delegate that adds clickable link icons to table cells with IDs.

    For cells that have associated IDs (track_id, album_id, artist_id, playlist_id),
    this delegate renders a small link icon (🔗) that can be clicked to open
    the item in Spotify.

    The delegate looks for special data roles:
    - Qt.UserRole + 1 = item type ("track", "album", "artist", "playlist")
    - Qt.UserRole + 2 = item ID (Spotify ID string)
    """

    ICON_SIZE = 14  # Size of the link icon
    ICON_PADDING = 4  # Padding around the icon

    def __init__(self, provider: str = "spotify", parent=None):
        """Initialize delegate.

        Args:
            provider: Streaming provider name (default: "spotify")
            parent: Parent widget
        """
        super().__init__(parent)
        self._provider = provider
        self._link_gen = get_link_generator(provider)
        self._hover_index = None

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        """Paint the cell with text and optional link icon.

        Args:
            painter: QPainter for rendering
            option: Style options
            index: Model index
        """
        # Let the base class paint the text
        super().paint(painter, option, index)

        # Check if this cell has link data
        item_type = index.data(Qt.UserRole + 1)  # "track", "album", "artist", "playlist"
        item_id = index.data(Qt.UserRole + 2)     # Spotify ID

        if item_type and item_id:
            # Draw a small link icon on the right side
            icon_rect = self._get_icon_rect(option.rect)

            # Draw icon background on hover
            if self._hover_index == index:
                painter.save()
                painter.setBrush(QColor(26, 115, 232, 40))  # Light blue
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(icon_rect.adjusted(-2, -2, 2, 2), 3, 3)
                painter.restore()

            # Draw the link icon
            painter.save()
            pen = QPen(QColor(26, 115, 232))  # Blue color
            painter.setPen(pen)
            painter.setFont(option.font)
            painter.drawText(icon_rect, Qt.AlignCenter, "🔗")
            painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        """Calculate size hint including space for link icon.

        Args:
            option: Style options
            index: Model index

        Returns:
            Recommended size for the cell
        """
        size = super().sizeHint(option, index)

        # Add space for the link icon if this cell has link data
        item_type = index.data(Qt.UserRole + 1)
        item_id = index.data(Qt.UserRole + 2)

        if item_type and item_id:
            size.setWidth(size.width() + self.ICON_SIZE + self.ICON_PADDING * 2)

        return size

    def editorEvent(self, event, model, option: QStyleOptionViewItem, index):
        """Handle mouse events for clicking the link icon.

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
                item_type = index.data(Qt.UserRole + 1)
                item_id = index.data(Qt.UserRole + 2)

                if item_type and item_id:
                    self._open_link(item_type, item_id)
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
        """Calculate the rectangle for the link icon.

        Args:
            cell_rect: Full cell rectangle

        Returns:
            Rectangle for the icon
        """
        # Position icon on the right side of the cell
        x = cell_rect.right() - self.ICON_SIZE - self.ICON_PADDING
        y = cell_rect.center().y() - self.ICON_SIZE // 2
        return QRect(x, y, self.ICON_SIZE, self.ICON_SIZE)

    def _open_link(self, item_type: str, item_id: str):
        """Open the streaming provider link in the default browser.

        Args:
            item_type: Type of item ("track", "album", "artist", "playlist")
            item_id: Spotify ID
        """
        try:
            # Generate URL based on type
            if item_type == "track":
                url = self._link_gen.track_url(item_id)
            elif item_type == "album":
                url = self._link_gen.album_url(item_id)
            elif item_type == "artist":
                url = self._link_gen.artist_url(item_id)
            elif item_type == "playlist":
                url = self._link_gen.playlist_url(item_id)
            else:
                logger.warning(f"Unknown item type for link: {item_type}")
                return

            logger.info(f"Opening {item_type} link: {url}")
            QDesktopServices.openUrl(QUrl(url))
        except Exception as e:
            logger.error(f"Failed to open link for {item_type} {item_id}: {e}")


__all__ = ['LinkDelegate']
