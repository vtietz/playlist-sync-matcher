"""Watch service for monitoring filesystem changes in library paths.

This module provides filesystem watching functionality using the watchdog library.
It implements debounced event processing to avoid event storms when many files
are modified simultaneously.
"""

from __future__ import annotations
import logging
import time
from pathlib import Path
from threading import Timer, Lock
from typing import Callable, List, Set, Dict, Any
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

logger = logging.getLogger(__name__)


class DebouncedLibraryWatcher(FileSystemEventHandler):
    """Filesystem event handler with debouncing for library changes.
    
    Collects filesystem events and batches them together, calling the callback
    only after a quiet period (debounce_seconds) has elapsed.
    
    This prevents event storms when many files are modified simultaneously
    (e.g., copying an entire album folder).
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        on_change_callback: Callable[[List[Path]], None],
        debounce_seconds: float = 2.0
    ):
        """Initialize the debounced watcher.
        
        Args:
            config: Configuration dict containing library settings
            on_change_callback: Function to call with list of changed file paths
            debounce_seconds: Seconds to wait after last event before processing
        """
        self.config = config
        self.on_change = on_change_callback
        self.debounce_seconds = debounce_seconds
        self.timer: Timer | None = None
        self.pending_paths: Set[Path] = set()
        self.lock = Lock()
        
        # Get configuration
        lib_cfg = config.get('library', {})
        self.extensions = tuple(lib_cfg.get('extensions', ['.mp3', '.flac', '.m4a']))
        self.ignore_patterns = lib_cfg.get('ignore_patterns', [])
        
        logger.debug(f"Initialized watcher with debounce={debounce_seconds}s, extensions={self.extensions}")
    
    def on_any_event(self, event: FileSystemEvent) -> None:
        """Handle any filesystem event.
        
        Filters events and adds relevant files to the pending queue.
        Resets the debounce timer on each event.
        """
        # Ignore directory events
        if event.is_directory:
            return
        
        path = Path(event.src_path)
        
        # Filter by extension
        if not path.suffix.lower() in self.extensions:
            logger.debug(f"[watch] Ignoring {event.event_type}: {path} (wrong extension)")
            return
        
        # Filter temporary files
        if self._is_temp_file(path):
            logger.debug(f"[watch] Ignoring {event.event_type}: {path} (temp file)")
            return
        
        # Filter by ignore patterns
        if self._matches_ignore_pattern(path):
            logger.debug(f"[watch] Ignoring {event.event_type}: {path} (matches ignore pattern)")
            return
        
        logger.info(f"[watch] {event.event_type}: {path}")
        
        with self.lock:
            self.pending_paths.add(path)
            
            # Reset debounce timer
            if self.timer:
                self.timer.cancel()
            self.timer = Timer(self.debounce_seconds, self._process_changes)
            self.timer.start()
    
    def _is_temp_file(self, path: Path) -> bool:
        """Check if file is a temporary file that should be ignored."""
        temp_extensions = {'.tmp', '.part', '.download', '.crdownload'}
        return path.suffix.lower() in temp_extensions
    
    def _matches_ignore_pattern(self, path: Path) -> bool:
        """Check if path matches any ignore pattern."""
        path_str = str(path)
        for pattern in self.ignore_patterns:
            if pattern in path_str:
                return True
        return False
    
    def _process_changes(self) -> None:
        """Process accumulated changes after debounce period."""
        with self.lock:
            if not self.pending_paths:
                return
            
            paths_to_process = list(self.pending_paths)
            self.pending_paths.clear()
        
        logger.info(f"[watch] Processing {len(paths_to_process)} changed file(s) after debounce...")
        
        try:
            self.on_change(paths_to_process)
        except Exception as e:
            logger.error(f"[watch] Error processing changes: {e}", exc_info=True)
    
    def flush(self) -> None:
        """Immediately process any pending changes without waiting for debounce."""
        with self.lock:
            if self.timer:
                self.timer.cancel()
                self.timer = None
        
        if self.pending_paths:
            self._process_changes()


class LibraryWatcher:
    """High-level library filesystem watcher.
    
    Manages the watchdog Observer and provides a clean interface for
    starting/stopping filesystem monitoring.
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        on_change_callback: Callable[[List[Path]], None],
        debounce_seconds: float = 2.0
    ):
        """Initialize the library watcher.
        
        Args:
            config: Configuration dict containing library settings
            on_change_callback: Function to call when files change
            debounce_seconds: Debounce period in seconds
        """
        self.config = config
        self.debounce_seconds = debounce_seconds
        self.on_change = on_change_callback
        self.observer: Observer | None = None
        self.handler: DebouncedLibraryWatcher | None = None
        self._running = False
    
    def start(self) -> None:
        """Start watching library paths for changes."""
        if self._running:
            logger.warning("Watcher already running")
            return
        
        lib_cfg = self.config.get('library', {})
        paths = lib_cfg.get('paths', [])
        
        if not paths:
            raise ValueError("No library paths configured")
        
        # Ensure paths is a list
        if isinstance(paths, str):
            paths = [paths]
        
        self.handler = DebouncedLibraryWatcher(
            self.config,
            self.on_change,
            self.debounce_seconds
        )
        
        self.observer = Observer()
        
        for path_str in paths:
            path = Path(path_str)
            if not path.exists():
                logger.warning(f"Library path does not exist: {path}")
                continue
            
            self.observer.schedule(self.handler, str(path), recursive=True)
            logger.info(f"Watching: {path}")
        
        self.observer.start()
        self._running = True
        logger.info(f"Watch mode active (debounce={self.debounce_seconds}s)")
    
    def stop(self) -> None:
        """Stop watching for changes."""
        if not self._running:
            return
        
        logger.info("Stopping watch mode...")
        
        # Flush any pending changes
        if self.handler:
            self.handler.flush()
        
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5.0)
        
        self._running = False
        logger.info("Watch mode stopped")
    
    def is_running(self) -> bool:
        """Check if watcher is currently running."""
        return self._running
    
    def __enter__(self) -> LibraryWatcher:
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.stop()


__all__ = ["LibraryWatcher", "DebouncedLibraryWatcher"]
