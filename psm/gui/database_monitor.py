"""Database change detection for GUI auto-refresh.

This module provides automatic detection of external database changes
using write-epoch signals and WAL-aware file monitoring.
"""

from __future__ import annotations
import logging
import time
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QTimer

logger = logging.getLogger(__name__)


class DatabaseChangeDetector:
    """Monitors database for external changes and triggers refresh callbacks.
    
    Uses a two-tier detection strategy:
    1. PRIMARY: Write-epoch meta key (only updated on real writes)
    2. FALLBACK: WAL-aware file mtime (when epoch unavailable)
    
    Includes defense mechanisms:
    - Timestamp-based ignore windows (read-only operations)
    - Boolean suppression flag (GUI-initiated operations)
    - Debounce timer (prevent rapid re-triggers)
    - Active loader detection (prevent concurrent refreshes)
    """
    
    def __init__(
        self,
        db_path: Path,
        get_write_epoch: Callable[[], str],
        on_change_detected: Callable[[], None],
        check_interval: int = 2000,
        debounce_seconds: float = 1.5
    ):
        """Initialize database change detector.
        
        Args:
            db_path: Absolute path to the SQLite database file
            get_write_epoch: Callback to fetch current write epoch from database
            on_change_detected: Callback to invoke when change is detected
            check_interval: Polling interval in milliseconds (default: 2000ms = 2s)
            debounce_seconds: Minimum seconds between refreshes (default: 1.5s)
        """
        self.db_path = db_path
        self.db_wal_path = Path(str(db_path) + "-wal")
        self.get_write_epoch = get_write_epoch
        self.on_change_detected = on_change_detected
        self.debounce_seconds = debounce_seconds
        
        # Tracking state
        self._last_write_epoch = '0'
        self._last_db_mtime = 0.0
        self._last_refresh_at = 0.0
        
        # Control flags
        self._suppress_auto_refresh = False
        self._ignore_changes_until = 0.0
        self._watch_mode_active = False
        self._active_loader_count = 0
        self._command_running = False
        
        # Set up polling timer
        self._timer = QTimer()
        self._timer.timeout.connect(self._check_changes)
        self._timer.start(check_interval)
        
        # Initialize tracking values
        self._initialize_tracking()
        
        logger.info(f"Auto-refresh enabled: write-epoch polling + WAL-aware fallback")
        logger.info(f"  DB path: {self.db_path}")
        logger.info(f"  Check interval: {check_interval}ms")
        logger.info(f"  Debounce: {debounce_seconds}s")
    
    def _initialize_tracking(self):
        """Initialize write epoch and mtime tracking from current DB state."""
        try:
            self._last_write_epoch = self.get_write_epoch()
            logger.info(f"  Initial write epoch: {self._last_write_epoch}")
        except Exception as e:
            logger.debug(f"Could not initialize write epoch: {e}")
            self._last_write_epoch = '0'
        
        try:
            db_mtime = self.db_path.stat().st_mtime if self.db_path.exists() else 0
            wal_mtime = self.db_wal_path.stat().st_mtime if self.db_wal_path.exists() else 0
            self._last_db_mtime = max(db_mtime, wal_mtime)
        except Exception as e:
            logger.debug(f"Could not initialize mtime: {e}")
            self._last_db_mtime = 0.0
    
    def _check_changes(self):
        """Polling callback - check for database changes and trigger refresh if needed."""
        # Skip if database doesn't exist
        if not self.db_path.exists():
            return
        
        # GATE: Skip if ignore window is active
        current_time = time.time()
        if self._ignore_changes_until > current_time:
            logger.debug(f"Auto-refresh skip: ignore window active ({self._ignore_changes_until - current_time:.1f}s remaining)")
            return
        
        # Skip if auto-refresh is suppressed
        if self._suppress_auto_refresh:
            logger.debug("Auto-refresh suppressed (GUI read in progress)")
            return
        
        # Skip if loaders are active
        if self._active_loader_count > 0:
            logger.debug(f"Auto-refresh skip: {self._active_loader_count} loader(s) active")
            return
        
        # Skip if command is running UNLESS watch mode is active
        if self._command_running and not self._watch_mode_active:
            logger.debug("Auto-refresh skip: command running (not watch mode)")
            return
        
        # Debounce: Skip if we refreshed recently
        if current_time - self._last_refresh_at < self.debounce_seconds:
            return
        
        try:
            # PRIMARY: Check write epoch (AUTHORITATIVE when available)
            epoch_available = False
            try:
                current_write_epoch = self.get_write_epoch()
                epoch_available = True
                
                if current_write_epoch != self._last_write_epoch:
                    # Epoch changed - real write occurred
                    logger.info(f"Write epoch changed: {self._last_write_epoch} → {current_write_epoch}")
                    self._last_write_epoch = current_write_epoch
                    self._last_refresh_at = current_time
                    self.on_change_detected()
                    return
                else:
                    # Epoch unchanged - NO REFRESH (even if mtime changed)
                    logger.debug(f"Write epoch unchanged ({current_write_epoch}) - skipping refresh")
                    return
            
            except Exception as e:
                # Write epoch unavailable - fall through to mtime fallback
                logger.debug(f"Write epoch unavailable, using mtime fallback: {e}")
                epoch_available = False
            
            # FALLBACK: WAL-aware mtime checking (only when epoch unavailable)
            if not epoch_available:
                db_mtime = self.db_path.stat().st_mtime
                wal_mtime = self.db_wal_path.stat().st_mtime if self.db_wal_path.exists() else 0
                current_mtime = max(db_mtime, wal_mtime)
                
                if current_mtime > self._last_db_mtime:
                    logger.info(f"External DB change detected (mtime fallback: {current_mtime:.2f} > {self._last_db_mtime:.2f})")
                    self._last_db_mtime = current_mtime
                    self._last_refresh_at = current_time
                    self.on_change_detected()
        
        except Exception as e:
            logger.debug(f"Database polling check failed: {e}")
    
    def update_tracking(self):
        """Update tracked write epoch and mtime after a refresh.
        
        Call this after completing a data refresh to prevent immediate re-trigger.
        """
        try:
            self._last_write_epoch = self.get_write_epoch()
        except Exception as e:
            logger.debug(f"Could not update write epoch: {e}")
        
        try:
            db_mtime = self.db_path.stat().st_mtime if self.db_path.exists() else 0
            wal_mtime = self.db_wal_path.stat().st_mtime if self.db_wal_path.exists() else 0
            self._last_db_mtime = max(db_mtime, wal_mtime)
            self._last_refresh_at = time.time()
            
            logger.debug(f"Updated tracking: epoch={self._last_write_epoch}, mtime={self._last_db_mtime:.2f}")
        except Exception as e:
            logger.debug(f"Could not update tracking: {e}")
    
    # Control methods for external state management
    
    def set_ignore_window(self, duration_seconds: float):
        """Set an ignore window to suppress refresh detection temporarily.
        
        Args:
            duration_seconds: How long to ignore changes (typically 2.5s)
        """
        self._ignore_changes_until = time.time() + duration_seconds
        logger.debug(f"Set {duration_seconds}s ignore window")
    
    def set_suppression(self, suppressed: bool):
        """Enable or disable the suppression flag.
        
        Args:
            suppressed: True to suppress, False to enable
        """
        self._suppress_auto_refresh = suppressed
    
    def set_watch_mode(self, active: bool):
        """Set watch mode state (allows polling during long-running commands).
        
        Args:
            active: True if watch mode is active
        """
        self._watch_mode_active = active
    
    def set_loader_count(self, count: int):
        """Update the count of active loaders.
        
        Args:
            count: Number of active loaders (0 = none)
        """
        self._active_loader_count = count
    
    def set_command_running(self, running: bool):
        """Update command execution state.
        
        Args:
            running: True if a command is running
        """
        self._command_running = running
    
    def stop(self):
        """Stop the polling timer and clean up resources."""
        if self._timer:
            self._timer.stop()
            logger.debug("Database change detector stopped")
