"""Playlist filter async loader service.

Handles asynchronous loading of playlist track IDs for filter application.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Callable, Optional
import logging

from ..utils.async_loader import MultiAsyncLoader

if TYPE_CHECKING:
    from ..state.filter_store import FilterStore
    from ..data_facade import DataFacade

logger = logging.getLogger(__name__)


class PlaylistFilterLoader:
    """Service for async loading of playlist track IDs.
    
    Loads track IDs in background thread using facade_factory to avoid
    blocking the UI when user selects a playlist for filtering.
    """
    
    def __init__(
        self,
        filter_store: FilterStore,
        facade_factory: Callable[[], DataFacade],
        on_loader_count_changed: Optional[Callable[[int], None]] = None
    ):
        """Initialize playlist filter loader.
        
        Args:
            filter_store: FilterStore instance to publish results to
            facade_factory: Factory to create thread-safe facade instances
            on_loader_count_changed: Optional callback when loader count changes
        """
        self.filter_store = filter_store
        self.facade_factory = facade_factory
        self.on_loader_count_changed = on_loader_count_changed
        self._active_loader: Optional[MultiAsyncLoader] = None
    
    def load_async(
        self,
        playlist_name: str,
        on_complete: Optional[Callable[[str, int], None]] = None,
        on_error: Optional[Callable[[str], None]] = None
    ):
        """Load playlist track IDs asynchronously.
        
        Args:
            playlist_name: Name of playlist to load
            on_complete: Optional callback(playlist_name, track_count)
            on_error: Optional callback(error_msg)
        """
        # Cancel any existing loader
        if self._active_loader:
            self._active_loader.stop()
            self._active_loader.wait()
            self._active_loader = None
            if self.on_loader_count_changed:
                self.on_loader_count_changed(0)
        
        logger.debug(f"Started async loading of track IDs for playlist: {playlist_name}")
        
        # Define loading function using facade_factory for thread safety
        load_funcs = {
            'track_ids': lambda: self.facade_factory().get_track_ids_for_playlist(playlist_name)
        }
        
        def _on_loaded(results):
            """Handle successful load."""
            track_ids = results.get('track_ids', set())
            track_count = len(track_ids)
            
            logger.info(f"Loaded {track_count} tracks for playlist '{playlist_name}'")
            
            # Publish to FilterStore
            self.filter_store.set_playlist_filter(playlist_name, track_ids)
            
            # Cleanup
            self._active_loader = None
            if self.on_loader_count_changed:
                self.on_loader_count_changed(0)
            
            # Invoke callback
            if on_complete:
                on_complete(playlist_name, track_count)
        
        def _on_error(error_msg):
            """Handle loading error."""
            logger.error(f"Failed to load playlist tracks: {error_msg}")
            
            # Cleanup
            self._active_loader = None
            if self.on_loader_count_changed:
                self.on_loader_count_changed(0)
            
            # Invoke callback
            if on_error:
                on_error(error_msg)
        
        # Create and start loader
        loader = MultiAsyncLoader(load_funcs)
        loader.all_finished.connect(_on_loaded)
        loader.error.connect(_on_error)
        
        self._active_loader = loader
        if self.on_loader_count_changed:
            self.on_loader_count_changed(1)
        
        loader.start()
    
    def cancel(self):
        """Cancel any active loading operation."""
        if self._active_loader:
            self._active_loader.stop()
            self._active_loader.wait()
            self._active_loader = None
            if self.on_loader_count_changed:
                self.on_loader_count_changed(0)
