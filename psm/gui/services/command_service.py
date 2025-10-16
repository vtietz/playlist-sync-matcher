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

from .action_state_manager import ActionStateManager

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
    - Allows read-only commands during watch mode (diagnose, config get, etc.)
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

    # Commands that are read-only and safe to run during watch mode
    READ_ONLY_COMMANDS = {
        'diagnose',      # Track matching diagnostics (reads DB only)
        'config',        # Configuration viewing/editing
        'db',            # Database queries (if using query subcommand)
        '--version',     # Version info
        '--help',        # Help text
    }

    def __init__(
        self,
        executor,  # CliExecutor instance
        enable_actions: Callable[[bool], None],
        watch_mode_controller=None,  # Optional WatchModeController for state checking
        action_state_manager: Optional[ActionStateManager] = None  # Optional ActionStateManager for button states
    ):
        """Initialize command service.

        Args:
            executor: CliExecutor instance for running commands
            enable_actions: Callback to enable/disable UI actions
            watch_mode_controller: Optional watch mode controller to check if watch is active
            action_state_manager: Optional action state manager for button colorization
        """
        self.executor = executor
        self.enable_actions = enable_actions
        self.watch_mode_controller = watch_mode_controller
        self.action_state_manager = action_state_manager
        self._log_buffer = []  # Buffer to capture log output for error detection

    def _is_read_only_command(self, args: list[str]) -> bool:
        """Check if command is read-only and safe during watch mode.

        Args:
            args: Command arguments (e.g., ['diagnose', 'track_id'])

        Returns:
            True if command is read-only, False otherwise
        """
        if not args:
            return False

        # Check first argument against whitelist
        command = args[0]
        return command in self.READ_ONLY_COMMANDS

    def _extract_action_name(self, args: list[str]) -> Optional[str]:
        """Extract semantic action name from CLI arguments.

        Creates unique action names to distinguish between different button contexts:
        - 'match' → Toolbar "Match All" button
        - 'match:track' → Tracks panel "Match Selected Track" button
        - 'playlist:match' → Left panel "Match Selected" button

        Args:
            args: Command arguments (e.g., ['match'], ['match', '--track-id', '123'])

        Returns:
            Action name string or None if no command
        """
        if not args:
            return None

        command = args[0]

        # Handle playlist-scoped commands (already working correctly)
        if command == 'playlist' and len(args) >= 2:
            return f"playlist:{args[1]}"  # 'playlist:pull', 'playlist:match', 'playlist:export'

        # Handle diagnose command (takes track_id as positional argument)
        # Format: ['diagnose', 'track_id'] or ['diagnose', '--some-flag', 'track_id']
        if command == 'diagnose' and len(args) >= 2:
            # Has a positional argument (track_id) → per-track action
            return "diagnose:track"

        # Handle per-track commands (detected by --track-id flag)
        if '--track-id' in args:
            return f"{command}:track"  # 'match:track', etc.

        # Handle per-playlist commands (detected by --playlist-id flag)
        if '--playlist-id' in args:
            return f"{command}:playlist"  # 'pull:playlist', 'match:playlist', etc.

        # Generic command (toolbar buttons)
        return command  # 'match', 'pull', 'scan', 'export', 'report', 'build', 'refresh'

    def execute(
        self,
        args: list[str],
        on_log: Callable[[str], None],
        on_execution_status: Callable[[bool, str], None],
        on_success: Optional[Callable[[], None]] = None,
        success_message: str = "✓ Command completed"
    ):
        """Execute CLI command with standardized lifecycle.

        Args:
            args: Command arguments (e.g., ['pull', '--force'])
            on_log: Callback for log lines
            on_execution_status: Callback for execution status (running: bool, message: str)
            on_success: Optional callback invoked after successful execution
            success_message: Message to log on success
        """
        # Extract action name for state tracking (parameter-aware)
        action_name = self._extract_action_name(args)

        # Check if this is a read-only command that can run during watch mode
        is_read_only = self._is_read_only_command(args)

        # Guard against overlapping commands (but allow read-only during watch mode)
        if self.executor.is_running():
            # Check if watch mode is active
            if self.watch_mode_controller and self.watch_mode_controller.is_active:
                # Allow read-only commands during watch mode
                if is_read_only:
                    on_log(f"\n💡 Running read-only command '{args[0]}' while watch mode is active...")
                    # Don't return - allow execution to proceed
                else:
                    on_log("\n⌚ Watch mode is active. Stop watch to run commands that modify data.")
                    on_log("💡 Tip: Read-only commands like 'diagnose' can run during watch mode.")
                    return
            else:
                # Another command (not watch mode) is running
                on_log("\n⚠ Another command is already running. Please wait...")
                return

        # Clear log buffer for new command
        self._log_buffer.clear()

        # Pre-execution: disable actions and set running status
        self.enable_actions(False)
        on_execution_status(True, ' '.join(args))  # Show command being run

        # Notify ActionStateManager that action is starting
        if self.action_state_manager and action_name:
            self.action_state_manager.set_action_running(action_name)

        def on_log_with_capture(line: str):
            """Log callback that also captures to buffer for error analysis."""
            self._log_buffer.append(line)
            on_log(line)

            # Forward to ActionStateManager for progress tracking
            if self.action_state_manager:
                self.action_state_manager.process_log_line(line)

        def on_finished(exit_code: int):
            """Handle command completion."""
            self.enable_actions(True)
            on_execution_status(False, "")  # Set to Ready

            # Check if command was cancelled by user
            was_cancelled = self.executor.was_cancelled()

            # Notify ActionStateManager that action finished
            if self.action_state_manager and action_name:
                # Treat cancellation as success (return to idle, not error)
                self.action_state_manager.set_action_finished(
                    action_name,
                    success=(exit_code == 0 or was_cancelled)
                )

            if exit_code == 0:
                # Success path
                on_log(f"\n{success_message}")
                if on_success:
                    on_success()
            elif was_cancelled:
                # Cancellation path - not an error
                on_log("\n⚠ Command cancelled by user")
            else:
                # Failure path with enhanced error messaging
                on_log(f"\n✗ Command failed with exit code {exit_code}")

                # Analyze captured logs for known error patterns
                self._provide_error_hints(on_log)

                on_log("\n📋 See log output above for details.")

        def on_error(error: str):
            """Handle command error."""
            self.enable_actions(True)
            on_execution_status(False, "")  # Set to Ready
            on_log(f"\n✗ Error: {error}")

        # Execute via executor (note: executor still expects on_progress callback)
        # We pass a no-op lambda since we're not using progress bars anymore
        self.executor.execute(
            args,
            on_log=on_log_with_capture,
            on_progress=lambda c, t, m: None,  # No-op: we use execution status instead
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
