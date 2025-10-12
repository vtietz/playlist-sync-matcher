"""Track streaming service for incremental UI updates.

This service handles chunked loading of large track datasets to prevent UI freezes.
It manages chunk scheduling, progress updates, sorting state, and finalization.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, List, Dict, Any, Optional
from PySide6.QtCore import QTimer, Qt
import logging

if TYPE_CHECKING:
    from ..components.unified_tracks_view import UnifiedTracksView
    from ..models import UnifiedTracksModel
    from ..state.filter_store import FilterState

logger = logging.getLogger(__name__)


class TrackStreamingService:
    """Service for streaming large track datasets to UI without blocking.

    Chunks tracks into smaller batches and appends them incrementally via QTimer,
    allowing the event loop to process UI updates between chunks.

    Key features:
    - Configurable chunk size and delay for performance tuning
    - Automatic sorting disable/enable during streaming
    - Progress updates via callback
    - Pending sort application after completion
    - Lazy playlist loading trigger after finalization
    """

    # Performance tuning constants
    CHUNK_SIZE = 500  # Rows per chunk (reduced from 1000 for better responsiveness)
    CHUNK_DELAY_MS = 16  # ~60fps yield between chunks

    def __init__(
        self,
        view: UnifiedTracksView,
        model: UnifiedTracksModel,
        on_progress: Optional[callable] = None,
        on_complete: Optional[callable] = None
    ):
        """Initialize streaming service.

        Args:
            view: UnifiedTracksView instance
            model: UnifiedTracksModel instance
            on_progress: Optional callback(current, total, message) for progress updates
            on_complete: Optional callback() invoked when streaming finishes
        """
        self.view = view
        self.model = model
        self.on_progress = on_progress
        self.on_complete = on_complete

        # State for current streaming operation
        self._chunk_iterator: List[List[Dict[str, Any]]] = []
        self._current_chunk_index = 0
        self._total_count = 0
        self._is_streaming = False

    def start_streaming(
        self,
        tracks: List[Dict[str, Any]],
        filter_state: FilterState,
        pending_sort: Optional[tuple[int, Qt.SortOrder]] = None
    ):
        """Start streaming tracks to the UI.

        Args:
            tracks: List of all track dicts to load
            filter_state: Current filter state (for pre-filtering)
            pending_sort: Optional (column, order) tuple to apply after completion
        """
        # Pre-filter by playlist track_ids if active
        if filter_state.active_dimension == 'playlist' and filter_state.track_ids:
            logger.debug(f"Pre-filtering {len(tracks)} tracks by playlist filter ({len(filter_state.track_ids)} IDs)")
            tracks = [row for row in tracks if row.get('id') in filter_state.track_ids]
            logger.debug(f"After pre-filtering: {len(tracks)} tracks")

        self._total_count = len(tracks)
        self._current_chunk_index = 0
        self._is_streaming = True
        self._pending_sort = pending_sort

        # Prepare chunked iterator
        self._chunk_iterator = [
            tracks[i:i + self.CHUNK_SIZE]
            for i in range(0, len(tracks), self.CHUNK_SIZE)
        ]

        # Disable sorting and dynamic filtering during streaming
        self.view.tracks_table.setSortingEnabled(False)
        self.view.proxy_model.setDynamicSortFilter(False)

        # Start streaming
        self.model.load_data_async_start(self._total_count)

        # Set streaming flag on view to gate lazy playlist loading
        self.view._is_streaming = True

        # Update initial progress
        if self.on_progress:
            self.on_progress(0, self._total_count, f"Loading tracks (0/{self._total_count})...")

        # Start chunking
        QTimer.singleShot(0, self._append_next_chunk)

    def _append_next_chunk(self):
        """Append next chunk via QTimer callback."""
        if self._current_chunk_index >= len(self._chunk_iterator):
            # Streaming complete
            self._finalize_streaming()
            return

        chunk = self._chunk_iterator[self._current_chunk_index]
        self.model.load_data_async_append(chunk)

        self._current_chunk_index += 1
        rows_loaded = min(self._current_chunk_index * self.CHUNK_SIZE, self._total_count)

        # Update progress
        if self.on_progress:
            self.on_progress(rows_loaded, self._total_count, f"Loading tracks ({rows_loaded}/{self._total_count})...")

        # Schedule next chunk (yield to event loop for ~60fps)
        QTimer.singleShot(self.CHUNK_DELAY_MS, self._append_next_chunk)

    def _finalize_streaming(self):
        """Finalize streaming: re-enable sorting, trigger lazy load, etc."""
        self.model.load_data_async_complete()
        self.view._is_streaming = False
        self._is_streaming = False

        # Re-enable sorting and apply last sort column
        self.view.proxy_model.setDynamicSortFilter(True)
        self.view.tracks_table.setSortingEnabled(True)

        # Apply sort: use pending (restored) sort if available, otherwise default to Track name A-Z
        if self._pending_sort is not None:
            sort_col, sort_order = self._pending_sort
            self.view.tracks_table.sortByColumn(sort_col, sort_order)
            logger.debug(f"Applied pending sort: column={sort_col}, order={sort_order}")
        elif self.view.tracks_table.horizontalHeader().sortIndicatorSection() == -1:
            # No sort indicator and no pending sort - apply default
            self.view.tracks_table.sortByColumn(0, Qt.AscendingOrder)  # Sort by Track name A-Z

        # Trigger lazy playlist loading for visible rows
        QTimer.singleShot(100, self.view.trigger_lazy_playlist_load)

        logger.info(f"Streaming complete: {self._total_count} tracks loaded")

        # Invoke completion callback
        if self.on_complete:
            self.on_complete()

    def is_streaming(self) -> bool:
        """Check if streaming is currently active.

        Returns:
            True if streaming is in progress
        """
        return self._is_streaming
