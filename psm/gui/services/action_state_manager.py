"""ActionStateManager - Tracks CLI command execution state and drives button colorization.

This service listens to command lifecycle events and log output to determine
action states (running, success, error) and publish them for UI updates.
"""

from typing import Optional, Callable
import re
import logging

logger = logging.getLogger(__name__)


class ActionStateManager:
    """Manages action execution state based on command lifecycle and log parsing.

    Responsibilities:
    - Track which action is currently running
    - Parse log output to detect progress, completion, and errors
    - Publish state changes via callbacks for UI updates
    - Handle multi-step Build command with sub-step tracking
    """

    def __init__(self, on_state_change: Optional[Callable[[str, str], None]] = None):
        """Initialize the action state manager.

        Args:
            on_state_change: Callback(action_name, state) called when state changes
                           state values: 'idle', 'running', 'success', 'error'
        """
        self.on_state_change = on_state_change
        self._current_action: Optional[str] = None
        self._current_sub_step: Optional[str] = None
        self._is_build_command = False

        # Patterns for detecting step completion in logs
        self._completion_patterns = {
            'pull': re.compile(r'Pull complete|Pulled \d+ playlist', re.IGNORECASE),
            'scan': re.compile(r'Scan complete|Scanned \d+ file', re.IGNORECASE),
            'match': re.compile(r'Match complete|Matched \d+ track', re.IGNORECASE),
            'export': re.compile(r'Export complete|Exported \d+ playlist', re.IGNORECASE),
            'report': re.compile(r'Report.* generated|Generated \d+ report', re.IGNORECASE),
            'build': re.compile(r'Build complete', re.IGNORECASE),
        }

        # Patterns for detecting errors
        self._error_pattern = re.compile(r'✗|Error|Failed|Exception', re.IGNORECASE)

    def set_action_running(self, action_name: str):
        """Mark an action as started/running.

        Args:
            action_name: Action being executed ('pull', 'scan', 'match', 'export', 'report', 'build')
        """
        self._current_action = action_name
        self._is_build_command = (action_name == 'build')
        self._current_sub_step = None

        logger.debug(f"Action started: {action_name}")

        if self.on_state_change:
            self.on_state_change(action_name, 'running')

            # For Build command, highlight Pull as the first step
            if self._is_build_command:
                self._current_sub_step = 'pull'
                self.on_state_change('build:pull', 'running')

    def process_log_line(self, line: str):
        """Process a log line to detect state changes.

        Detects:
        - Step completions (triggers next sub-step for Build)
        - Errors (sets error state)
        - Build sub-step transitions

        Args:
            line: Log line from CLI output
        """
        if not self._current_action:
            return

        # Check for errors
        if self._error_pattern.search(line):
            # Don't immediately set error state - wait for process exit code
            # This prevents false positives from error messages in success output
            logger.debug(f"Error pattern detected in log: {line[:100]}")

        # For Build command, detect sub-step transitions
        if self._is_build_command and self.on_state_change:
            # Check each step's completion pattern
            for step, pattern in self._completion_patterns.items():
                if step == 'build':
                    continue  # Skip the build-complete pattern here

                if pattern.search(line):
                    logger.debug(f"Build sub-step completed: {step}")
                    # Determine next step
                    next_step = self._get_next_build_step(step)
                    if next_step:
                        self._current_sub_step = next_step
                        # Emit sub-step change (using special naming for Build steps)
                        self.on_state_change(f'build:{next_step}', 'running')
                    break

    def set_action_finished(self, action_name: str, success: bool):
        """Mark an action as finished with success or error state.

        Args:
            action_name: Action that finished
            success: True if exit code == 0, False otherwise
        """
        if action_name != self._current_action:
            logger.warning(f"Finished action '{action_name}' doesn't match current '{self._current_action}'")

        logger.debug(f"Action finished: {action_name}, success={success}")

        if self.on_state_change:
            # On completion, return to idle state (original blue color)
            # Show error state only if command failed
            state = 'idle' if success else 'error'
            self.on_state_change(action_name, state)

            # Clear Build sub-step highlighting if it was a Build command
            if self._is_build_command:
                self.on_state_change('build:clear', 'idle')

        self._current_action = None
        self._current_sub_step = None
        self._is_build_command = False

    def _get_next_build_step(self, completed_step: str) -> Optional[str]:
        """Determine the next step in Build sequence after a step completes.

        Build sequence: pull → scan → match → export → report

        Args:
            completed_step: Step that just completed

        Returns:
            Next step name or None if this was the last step
        """
        build_sequence = ['pull', 'scan', 'match', 'export', 'report']
        try:
            current_index = build_sequence.index(completed_step)
            if current_index < len(build_sequence) - 1:
                return build_sequence[current_index + 1]
        except ValueError:
            pass
        return None

    def reset(self):
        """Reset state manager to idle."""
        self._current_action = None
        self._current_sub_step = None
        self._is_build_command = False
