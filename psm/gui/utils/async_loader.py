"""Asynchronous data loading for GUI to prevent freezing.

This module provides worker threads for loading data without blocking the UI.

NOTE: For SQLite databases, functions passed to AsyncDataLoader should NOT
use existing database connections (thread safety). Instead, they should create
new connections or use a thread-safe connection pool.
"""

from __future__ import annotations
from typing import Callable, Any, Optional
from PySide6.QtCore import QThread, Signal
import logging

logger = logging.getLogger(__name__)


class AsyncDataLoader(QThread):
    """Worker thread for loading data asynchronously.

    This prevents the GUI from freezing during expensive operations like:
    - Loading all tracks
    - Getting unique filter values
    - Database queries

    Signals:
        finished: Emitted when loading completes successfully (data: Any)
        error: Emitted when loading fails (error_msg: str)
        progress: Emitted to update progress (current: int, total: int)

    Example:
        def load_tracks():
            return facade.list_all_tracks_unified()

        loader = AsyncDataLoader(load_tracks)
        loader.finished.connect(lambda data: model.set_data(data))
        loader.error.connect(lambda msg: logger.error(msg))
        loader.start()
    """

    # Signals
    finished = Signal(object)  # data
    error = Signal(str)  # error_msg
    progress = Signal(int, int)  # current, total

    def __init__(self, load_func: Callable[[], Any], parent: Optional[QThread] = None):
        """Initialize async loader.

        Args:
            load_func: Function to call in background thread (should return data)
            parent: Parent QObject
        """
        super().__init__(parent)
        self.load_func = load_func
        self._should_stop = False

    def run(self):
        """Execute loading function in background thread."""
        try:
            logger.debug(f"AsyncDataLoader starting: {self.load_func.__name__}")

            # Check if we should stop before starting
            if self._should_stop:
                logger.debug("AsyncDataLoader cancelled before start")
                return

            # Execute the loading function
            result = self.load_func()

            # Check if we should stop before emitting result
            if self._should_stop:
                logger.debug("AsyncDataLoader cancelled before finish")
                return

            # Emit result
            logger.debug(f"AsyncDataLoader finished: {self.load_func.__name__}")
            self.finished.emit(result)

        except Exception as e:
            logger.error(f"AsyncDataLoader error in {self.load_func.__name__}: {e}", exc_info=True)
            self.error.emit(str(e))

    def stop(self):
        """Request the loader to stop (graceful shutdown)."""
        self._should_stop = True


class MultiAsyncLoader(QThread):
    """Worker thread for loading multiple datasets in parallel.

    This is useful when you need to load multiple independent datasets
    (e.g., tracks + playlists + filter options) without blocking the UI.

    Signals:
        all_finished: Emitted when all loaders complete (results: dict)
        error: Emitted when any loader fails (error_msg: str)
        item_finished: Emitted when one item completes (key: str, data: Any)

    Example:
        loaders = {
            'tracks': lambda: facade.list_all_tracks_unified(),
            'playlists': lambda: facade.list_playlists(),
            'artists': lambda: facade.get_unique_artists(),
        }

        loader = MultiAsyncLoader(loaders)
        loader.all_finished.connect(lambda results: update_ui(results))
        loader.start()
    """

    # Signals
    all_finished = Signal(dict)  # {key: data}
    error = Signal(str)  # error_msg
    item_finished = Signal(str, object)  # key, data

    def __init__(self, load_funcs: dict[str, Callable[[], Any]], parent: Optional[QThread] = None):
        """Initialize multi-loader.

        Args:
            load_funcs: Dict of {key: load_function} to execute
            parent: Parent QObject
        """
        super().__init__(parent)
        self.load_funcs = load_funcs
        self._should_stop = False

    def run(self):
        """Execute all loading functions sequentially in background thread."""
        try:
            results = {}

            for key, func in self.load_funcs.items():
                if self._should_stop:
                    logger.debug(f"MultiAsyncLoader cancelled at {key}")
                    return

                logger.debug(f"MultiAsyncLoader loading: {key}")
                data = func()
                results[key] = data

                # Emit individual completion
                self.item_finished.emit(key, data)

            # Emit all results
            if not self._should_stop:
                logger.debug("MultiAsyncLoader finished all")
                self.all_finished.emit(results)

        except Exception as e:
            logger.error(f"MultiAsyncLoader error: {e}", exc_info=True)
            self.error.emit(str(e))

    def stop(self):
        """Request the loader to stop (graceful shutdown)."""
        self._should_stop = True
