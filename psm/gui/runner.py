"""CLI subprocess runner for executing long-running operations.

Spawns CLI commands as subprocesses and streams logs/progress back to GUI.
"""

from __future__ import annotations
import os
import subprocess
import sys
import logging
import platform
from pathlib import Path
from typing import Optional, Callable, List
from PySide6.QtCore import QObject, QThread, Signal

from .progress_parser import parse_progress

logger = logging.getLogger(__name__)


def _get_cli_command() -> tuple[list[str], str | None]:
    """Get the appropriate CLI command based on frozen/source mode.

    Returns:
        Tuple of (command_prefix, error_message)
        - command_prefix: List to prepend to CLI args (e.g., ['python', '-m', 'psm.cli'] or ['psm-cli.exe'])
        - error_message: Error message if CLI cannot be found, None if OK
    """
    # Check if running as PyInstaller frozen executable
    if getattr(sys, "frozen", False):
        # Running as frozen executable - need to find sibling CLI binary
        gui_exe = Path(sys.executable)

        # Determine CLI binary name based on platform
        if platform.system() == "Windows":
            cli_name = "psm-cli.exe"
        else:
            cli_name = "psm-cli"

        # Look for CLI binary in same directory as GUI
        cli_path = gui_exe.parent / cli_name

        if not cli_path.exists():
            error_msg = (
                f"CLI executable not found: {cli_path}\n\n"
                f"The GUI requires '{cli_name}' to be present in the same directory "
                f"as the GUI executable.\n\n"
                f"Please ensure both files are kept together:\n"
                f"  - {gui_exe.name}\n"
                f"  - {cli_name}\n\n"
                f"See README.md Installation section for download instructions."
            )
            return ([], error_msg)

        logger.info(f"Using CLI executable: {cli_path}")
        return ([str(cli_path)], None)
    else:
        # Running from source - use python -m psm.cli
        return ([sys.executable, "-m", "psm.cli"], None)


class CliRunner(QThread):
    """Background thread for running CLI commands via subprocess."""

    # Signals
    log_line = Signal(str)  # Emitted for each output line
    progress_update = Signal(int, int, str)  # (current, total, message)
    finished = Signal(int)  # Exit code
    error = Signal(str)  # Error message

    def __init__(self, command_args: List[str], parent: Optional[QObject] = None):
        """Initialize CLI runner.

        Args:
            command_args: CLI command arguments (e.g., ['pull', '--all'])
            parent: Parent QObject
        """
        super().__init__(parent)
        self.command_args = command_args
        self.process: Optional[subprocess.Popen] = None
        self._stop_requested = False

    def run(self):
        """Execute the CLI command and stream output."""
        try:
            # Get CLI command based on frozen/source mode
            cli_prefix, error_msg = _get_cli_command()

            if error_msg:
                # CLI executable not found
                logger.error(error_msg)
                self.error.emit(error_msg)
                self.finished.emit(1)
                return

            # Build full command: [cli_prefix...] + command_args
            cmd = cli_prefix + self.command_args

            logger.info(f"Running command: {' '.join(cmd)}")

            # Set environment to force UTF-8 encoding for subprocess
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"  # Force UTF-8 encoding for Python subprocess
            env["PSM_SKIP_FIRST_RUN_CHECK"] = "1"  # Skip first-run .env check when running from GUI

            # Platform-specific subprocess options
            creation_flags = 0
            if platform.system() == "Windows" and getattr(sys, "frozen", False):
                # On Windows frozen mode, suppress console window
                # Note: CLI spec must have console=True to allow stdout/stderr pipes
                creation_flags = subprocess.CREATE_NO_WINDOW

            # Start subprocess with line-buffered output and UTF-8 encoding
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True,
                encoding="utf-8",  # Force UTF-8 to handle Unicode characters
                errors="replace",  # Replace unencodable characters instead of crashing
                env=env,  # Pass modified environment
                creationflags=creation_flags,  # Suppress console on Windows frozen
            )

            # Stream output line by line
            for line in self.process.stdout:
                if self._stop_requested:
                    break

                line = line.rstrip()
                if line:
                    # Emit log line
                    self.log_line.emit(line)

                    # Parse for progress
                    progress = parse_progress(line)
                    if progress:
                        current, total, message = progress
                        self.progress_update.emit(current, total, message)

            # Wait for process completion
            exit_code = self.process.wait()

            if self._stop_requested:
                logger.info("Command cancelled by user")
                self.finished.emit(-1)
            else:
                logger.info(f"Command completed with exit code {exit_code}")
                self.finished.emit(exit_code)

        except Exception as e:
            logger.exception("Error running CLI command")
            self.error.emit(str(e))
            self.finished.emit(-1)

    def stop(self):
        """Request to stop the running command."""
        self._stop_requested = True
        if self.process and self.process.poll() is None:
            logger.info("Terminating subprocess...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Process didn't terminate, killing...")
                self.process.kill()


class CliExecutor:
    """Manages CLI command execution via runners.

    Provides a simple API for GUI to execute commands and handle results.
    """

    def __init__(self):
        """Initialize executor."""
        self.current_runner: Optional[CliRunner] = None

    def is_running(self) -> bool:
        """Check if a command is currently running.

        Returns:
            True if command is running
        """
        return self.current_runner is not None and self.current_runner.isRunning()

    def execute(
        self,
        command_args: List[str],
        on_log: Optional[Callable[[str], None]] = None,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
        on_finished: Optional[Callable[[int], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> CliRunner:
        """Execute a CLI command with callbacks.

        Args:
            command_args: CLI command arguments
            on_log: Callback for log lines
            on_progress: Callback for progress updates
            on_finished: Callback for completion
            on_error: Callback for errors

        Returns:
            CliRunner instance

        Raises:
            RuntimeError: If another command is already running
        """
        if self.is_running():
            raise RuntimeError("Another command is already running")

        runner = CliRunner(command_args)

        # Connect callbacks
        if on_log:
            runner.log_line.connect(on_log)
        if on_progress:
            runner.progress_update.connect(on_progress)
        if on_finished:
            runner.finished.connect(on_finished)
            runner.finished.connect(self._on_runner_finished)
        if on_error:
            runner.error.connect(on_error)

        self.current_runner = runner
        runner.start()

        return runner

    def _on_runner_finished(self):
        """Handle runner completion."""
        self.current_runner = None

    def stop_current(self):
        """Stop the currently running command."""
        if self.current_runner and self.current_runner.isRunning():
            self.current_runner.stop()

    def was_cancelled(self) -> bool:
        """Check if the last command was cancelled by user.

        Returns:
            True if command was stopped by user, False otherwise
        """
        if self.current_runner:
            return self.current_runner._stop_requested
        return False
