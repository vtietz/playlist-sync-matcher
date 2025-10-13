"""CLI subprocess runner for executing long-running operations.

Spawns CLI commands as subprocesses and streams logs/progress back to GUI.
"""
from __future__ import annotations
import os
import subprocess
import sys
import logging
from typing import Optional, Callable, List
from PySide6.QtCore import QObject, QThread, Signal

from .progress_parser import parse_progress

logger = logging.getLogger(__name__)


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
            # Build command: python -m psm.cli <args>
            cmd = [sys.executable, '-m', 'psm.cli'] + self.command_args

            logger.info(f"Running command: {' '.join(cmd)}")

            # Set environment to force UTF-8 encoding for subprocess
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'  # Force UTF-8 encoding for Python subprocess
            env['PSM_SKIP_FIRST_RUN_CHECK'] = '1'  # Skip first-run .env check when running from GUI

            # Start subprocess with line-buffered output and UTF-8 encoding
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True,
                encoding='utf-8',  # Force UTF-8 to handle Unicode characters
                errors='replace',  # Replace unencodable characters instead of crashing
                env=env,  # Pass modified environment
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
