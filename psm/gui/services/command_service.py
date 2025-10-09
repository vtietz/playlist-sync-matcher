"""Command execution service with standardized lifecycle.

This service encapsulates CLI command execution with a consistent lifecycle:
1. Pre-execution: disable actions, clear log, set progress
2. Execution: stream logs/progress via callbacks
3. Post-execution: enable actions, show result, refresh data

This follows the Single Responsibility Principle by extracting command
execution orchestration from controllers.
"""
from __future__ import annotations
from typing import Callable, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class CommandCallbacks:
    """Callbacks for command lifecycle events.
    
    This data class groups all callbacks to simplify the execute() signature
    and make the contract explicit.
    """
    on_log: Callable[[str], None]
    on_progress: Callable[[int, int, str], None]
    on_finished: Callable[[int], None]
    on_error: Callable[[str], None]
    on_success: Optional[Callable[[], None]] = None


class CommandService:
    """Service for executing CLI commands with standardized lifecycle.
    
    This service:
    - Enforces single command execution (reentrancy protection)
    - Provides consistent pre/post execution hooks
    - Normalizes error messages for common issues
    - Delegates actual subprocess execution to CliExecutor
    
    Example:
        service = CommandService(executor, enable_actions_callback)
        service.execute(
            ['pull'],
            callbacks,
            success_message="✓ Pull completed"
        )
    """
    
    def __init__(
        self,
        executor,  # CliExecutor instance
        enable_actions: Callable[[bool], None]
    ):
        """Initialize command service.
        
        Args:
            executor: CliExecutor instance for running commands
            enable_actions: Callback to enable/disable UI actions
        """
        self.executor = executor
        self.enable_actions = enable_actions
        self._log_buffer = []  # Buffer to capture log output for error detection
    
    def execute(
        self,
        args: list[str],
        on_log: Callable[[str], None],
        on_progress: Callable[[int, int, str], None],
        on_success: Optional[Callable[[], None]] = None,
        success_message: str = "✓ Command completed"
    ):
        """Execute CLI command with standardized lifecycle.
        
        Args:
            args: Command arguments (e.g., ['pull', '--force'])
            on_log: Callback for log lines
            on_progress: Callback for progress updates (current, total, message)
            on_success: Optional callback invoked after successful execution
            success_message: Message to log on success
        """
        # Guard against overlapping commands
        if self.executor.is_running():
            on_log("\n⚠ Another command is already running. Please wait...")
            return
        
        # Clear log buffer for new command
        self._log_buffer.clear()
        
        # Pre-execution: disable actions
        self.enable_actions(False)
        
        def on_log_with_capture(line: str):
            """Log callback that also captures to buffer for error analysis."""
            self._log_buffer.append(line)
            on_log(line)
        
        def on_finished(exit_code: int):
            """Handle command completion."""
            self.enable_actions(True)
            
            if exit_code == 0:
                # Success path
                on_log(f"\n{success_message}")
                if on_success:
                    on_success()
            else:
                # Failure path with enhanced error messaging
                on_log(f"\n✗ Command failed with exit code {exit_code}")
                
                # Analyze captured logs for known error patterns
                self._provide_error_hints(on_log)
                
                on_log("\n📋 See log output above for details.")
        
        def on_error(error: str):
            """Handle command error."""
            self.enable_actions(True)
            on_log(f"\n✗ Error: {error}")
        
        # Execute via executor
        self.executor.execute(
            args,
            on_log=on_log_with_capture,
            on_progress=on_progress,
            on_finished=on_finished,
            on_error=on_error,
        )
    
    def is_running(self) -> bool:
        """Check if a command is currently running.
        
        Returns:
            True if command is executing
        """
        return self.executor.is_running()
    
    def stop_current(self):
        """Stop the currently running command."""
        self.executor.stop_current()
    
    def _provide_error_hints(self, on_log: Callable[[str], None]):
        """Analyze log buffer and provide helpful error hints.
        
        Args:
            on_log: Callback to send hint messages
        """
        log_text = '\n'.join(self._log_buffer)
        
        # Known error pattern: MatchingConfig 'strategies' argument
        if "unexpected keyword argument 'strategies'" in log_text or \
           "MatchingConfig" in log_text and "strategies" in log_text:
            on_log(
                "\n💡 Hint: Configuration mismatch detected. "
                "This may be due to CLI/service schema differences. "
                "Try using 'All' actions (Pull All, Match All, Export All) instead of 'Selected' actions."
            )
            return
        
        # Known error pattern: File not found / path issues
        if "FileNotFoundError" in log_text or "No such file or directory" in log_text:
            on_log(
                "\n💡 Hint: File or directory not found. "
                "Ensure all required files exist and paths are correct."
            )
            return
        
        # Known error pattern: Permission denied
        if "PermissionError" in log_text or "Permission denied" in log_text:
            on_log(
                "\n💡 Hint: Permission denied. "
                "Check file permissions or try running with appropriate access rights."
            )
            return
        
        # Known error pattern: Authentication/token issues
        if "authentication" in log_text.lower() or "token" in log_text.lower() or \
           "unauthorized" in log_text.lower():
            on_log(
                "\n💡 Hint: Authentication issue detected. "
                "Check your Spotify credentials and ensure tokens are valid."
            )
            return
        
        # Known error pattern: Database locked
        if "database is locked" in log_text.lower():
            on_log(
                "\n💡 Hint: Database is locked. "
                "Close other applications accessing the database and try again."
            )
            return


