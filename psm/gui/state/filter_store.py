"""FilterStore - Single source of truth for filter state.

This module implements a simple state store pattern for managing filter state
across the GUI. It provides unidirectional data flow:

    User Action → FilterStore.set_state() → filterChanged signal → Views update

Benefits:
- ✅ Single source of truth for all filter state
- ✅ Unidirectional data flow (easy to reason about)
- ✅ Automatic loop prevention via state deduplication
- ✅ Simple to test (state in, state out)
- ✅ Scales well as filter dimensions grow

Architecture:
    ┌─────────────┐
    │ FilterStore │  (owns FilterState, emits filterChanged)
    └──────┬──────┘
           │ filterChanged(FilterState)
           ├────────────────┬────────────────┬────────────────┐
           ▼                ▼                ▼                ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │ Playlists│    │  Albums  │    │ Artists  │    │  Tracks  │
    │   View   │    │   View   │    │   View   │    │   View   │
    └──────────┘    └──────────┘    └──────────┘    └──────────┘
           │                │                │                │
           └────────────────┴────────────────┴────────────────┘
                          User actions → store.set_state()

State Policy:
- Only ONE filter dimension active at a time (playlist XOR album XOR artist)
- Setting a new dimension clears others (e.g., selecting album clears playlist)
- None/null values mean "no filter" (cleared state)
- State is immutable - always create new FilterState, never mutate

Loop Prevention:
- State deduplication: Only emit filterChanged if new_state != current_state
- Views use QSignalBlocker when applying programmatic updates
- No reentrancy guards needed - state dedup handles it naturally
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Set
from PySide6.QtCore import QObject, Signal
import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FilterState:
    """Immutable filter state.

    Policy: Only ONE dimension active at a time.
    - If playlist_name is set, album/artist should be None
    - If album_name is set, it can be used alone or with artist_name, playlist should be None
    - If artist_name is set alone, album/playlist should be None

    Attributes:
        playlist_name: Filter by playlist (None = no playlist filter)
        album_name: Filter by album (can be used alone or with artist_name)
        artist_name: Filter by artist (None = no artist filter)
        track_ids: Set of track IDs for playlist filter (cached for performance)
    """

    playlist_name: Optional[str] = None
    album_name: Optional[str] = None
    artist_name: Optional[str] = None
    track_ids: Set[str] = field(default_factory=set)

    def __post_init__(self):
        """Validate state invariants."""
        # Album filter can be used alone or with artist (no longer requires artist)

        # Only one dimension active (album and artist together count as one: "album")
        dimensions_set = sum(
            [
                self.playlist_name is not None,
                self.album_name is not None,
                self.artist_name is not None and self.album_name is None,
            ]
        )
        if dimensions_set > 1:
            raise ValueError(
                "Only one filter dimension allowed at a time: "
                f"playlist={self.playlist_name}, "
                f"album={self.album_name}, "
                f"artist={self.artist_name}"
            )

    @property
    def is_cleared(self) -> bool:
        """Check if all filters are cleared."""
        return self.playlist_name is None and self.album_name is None and self.artist_name is None

    @property
    def active_dimension(self) -> Optional[str]:
        """Get the active filter dimension name."""
        if self.playlist_name:
            return "playlist"
        elif self.album_name:
            return "album"
        elif self.artist_name:
            return "artist"
        return None

    def with_playlist(self, playlist_name: Optional[str], track_ids: Set[str] = None) -> FilterState:
        """Create new state with playlist filter (clears album/artist)."""
        return FilterState(playlist_name=playlist_name, album_name=None, artist_name=None, track_ids=track_ids or set())

    def with_album(self, album_name: Optional[str], artist_name: Optional[str]) -> FilterState:
        """Create new state with album filter (clears playlist)."""
        return FilterState(playlist_name=None, album_name=album_name, artist_name=artist_name, track_ids=set())

    def with_artist(self, artist_name: Optional[str]) -> FilterState:
        """Create new state with artist filter (clears playlist/album)."""
        return FilterState(playlist_name=None, album_name=None, artist_name=artist_name, track_ids=set())

    def cleared(self) -> FilterState:
        """Create new cleared state."""
        return FilterState()


class FilterStore(QObject):
    """Single source of truth for filter state.

    All views subscribe to filterChanged and update themselves.
    All user actions call set_state to update the store.

    State deduplication prevents loops:
    - Only emits filterChanged if new_state != current_state
    - Views should use QSignalBlocker when applying programmatic updates

    Example usage:
        # Create store
        store = FilterStore()

        # Subscribe views
        store.filterChanged.connect(tracks_view.on_filter_changed)
        store.filterChanged.connect(playlists_view.on_filter_changed)

        # User selects playlist
        track_ids = data_facade.get_track_ids_for_playlist("My Playlist")
        new_state = store.state.with_playlist("My Playlist", track_ids)
        store.set_state(new_state)

        # filterChanged emitted → all views update
    """

    # Signal emitted when filter state changes
    filterChanged = Signal(FilterState)

    def __init__(self, parent=None):
        """Initialize with cleared state."""
        super().__init__(parent)
        self._state = FilterState()
        logger.debug("FilterStore initialized with cleared state")

    @property
    def state(self) -> FilterState:
        """Get current filter state (immutable)."""
        return self._state

    def set_state(self, new_state: FilterState):
        """Set new filter state.

        Only emits filterChanged if state actually changed (deduplication).

        Args:
            new_state: New filter state to apply
        """
        if new_state == self._state:
            logger.debug("State unchanged, skipping emission")
            return

        old_dimension = self._state.active_dimension
        new_dimension = new_state.active_dimension

        self._state = new_state

        logger.info(
            f"Filter state changed: {old_dimension or 'none'} → {new_dimension or 'none'} "
            f"(playlist={new_state.playlist_name}, "
            f"album={new_state.album_name}, "
            f"artist={new_state.artist_name})"
        )

        self.filterChanged.emit(self._state)

    def clear(self):
        """Clear all filters."""
        self.set_state(FilterState())

    def set_playlist(self, playlist_name: Optional[str], track_ids: Set[str] = None):
        """Convenience method to set playlist filter."""
        new_state = self._state.with_playlist(playlist_name, track_ids or set())
        self.set_state(new_state)

    def set_album(self, album_name: Optional[str], artist_name: Optional[str]):
        """Convenience method to set album filter."""
        new_state = self._state.with_album(album_name, artist_name)
        self.set_state(new_state)

    def set_artist(self, artist_name: Optional[str]):
        """Convenience method to set artist filter."""
        new_state = self._state.with_artist(artist_name)
        self.set_state(new_state)
