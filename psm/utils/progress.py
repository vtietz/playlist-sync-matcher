"""Standardized progress logging for CLI and GUI parsing.

This module provides consistent progress output formats that can be
reliably parsed by the GUI progress parser.

Format Standards:
- Step progress: "[1/4] Operation name"
- Item progress: "Progress: 123/456 items (27%)"
- Completion: "✓ Operation completed in 1.23s"
- Status: "→ Status message"
- Warning: "⚠ Warning message"
- Error: "✗ Error message"
"""
import time
from typing import Optional


class ProgressLogger:
    """Standardized progress logger for CLI operations.

    Provides consistent output formatting for step-based operations,
    item-by-item progress, and completion markers.

    Examples:
        >>> progress = ProgressLogger()
        >>> progress.step(1, 4, "Scanning library")
        [1/4] Scanning library

        >>> progress.items(150, 500, "tracks matched")
        Progress: 150/500 tracks matched (30%)

        >>> progress.complete("Library scan", 2.5)
        ✓ Library scan completed in 2.5s
    """

    def __init__(self):
        """Initialize progress logger."""
        self._start_time: Optional[float] = None
        self._current_operation: Optional[str] = None

    def start(self, operation: str):
        """Mark start of an operation.

        Args:
            operation: Name of operation starting
        """
        self._start_time = time.time()
        self._current_operation = operation
        print(f"→ {operation}...")

    def step(self, current: int, total: int, name: str):
        """Log a step in a multi-step operation.

        Args:
            current: Current step number (1-indexed)
            total: Total number of steps
            name: Name of current step

        Example:
            >>> progress.step(2, 5, "Matching tracks")
            [2/5] Matching tracks
        """
        print(f"[{current}/{total}] {name}")

    def items(self, current: int, total: int, item_type: str = "items"):
        """Log progress through a collection of items.

        Args:
            current: Number of items processed
            total: Total number of items
            item_type: Type of items being processed (e.g., "tracks", "playlists")

        Example:
            >>> progress.items(150, 500, "tracks")
            Progress: 150/500 tracks (30%)
        """
        if total > 0:
            percent = int((current / total) * 100)
            print(f"Progress: {current}/{total} {item_type} ({percent}%)")
        else:
            # Indeterminate progress (total unknown)
            print(f"Progress: {current} {item_type} processed")

    def status(self, message: str):
        """Log a status message.

        Args:
            message: Status message

        Example:
            >>> progress.status("Found 42 playlists")
            → Found 42 playlists
        """
        print(f"→ {message}")

    def complete(self, operation: Optional[str] = None, elapsed: Optional[float] = None):
        """Log completion of an operation.

        Args:
            operation: Name of completed operation (uses current if None)
            elapsed: Elapsed time in seconds (auto-calculated if None)

        Example:
            >>> progress.complete("Library scan", 2.5)
            ✓ Library scan completed in 2.5s
        """
        op = operation or self._current_operation or "Operation"

        if elapsed is None and self._start_time is not None:
            elapsed = time.time() - self._start_time

        if elapsed is not None:
            print(f"✓ {op} completed in {elapsed:.1f}s")
        else:
            print(f"✓ {op} completed")

        # Reset state
        self._start_time = None
        self._current_operation = None

    def warning(self, message: str):
        """Log a warning message.

        Args:
            message: Warning message

        Example:
            >>> progress.warning("3 playlists skipped")
            ⚠ 3 playlists skipped
        """
        print(f"⚠ {message}")

    def error(self, message: str):
        """Log an error message.

        Args:
            message: Error message

        Example:
            >>> progress.error("Failed to connect to Spotify")
            ✗ Failed to connect to Spotify
        """
        print(f"✗ {message}")


# Global singleton instance for convenience
_default_progress = ProgressLogger()


def start(operation: str):
    """Start an operation (uses default logger)."""
    _default_progress.start(operation)


def step(current: int, total: int, name: str):
    """Log a step (uses default logger)."""
    _default_progress.step(current, total, name)


def items(current: int, total: int, item_type: str = "items"):
    """Log item progress (uses default logger)."""
    _default_progress.items(current, total, item_type)


def status(message: str):
    """Log status (uses default logger)."""
    _default_progress.status(message)


def complete(operation: Optional[str] = None, elapsed: Optional[float] = None):
    """Log completion (uses default logger)."""
    _default_progress.complete(operation, elapsed)


def warning(message: str):
    """Log warning (uses default logger)."""
    _default_progress.warning(message)


def error(message: str):
    """Log error (uses default logger)."""
    _default_progress.error(message)
