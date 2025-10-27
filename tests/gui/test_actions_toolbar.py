"""Tests for ActionsToolbar component."""

import pytest
from PySide6.QtWidgets import QApplication

from psm.gui.components.actions_toolbar import ActionsToolbar


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for GUI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def toolbar(qapp):
    """Create ActionsToolbar instance for testing."""
    return ActionsToolbar()


class TestActionsToolbarCreation:
    """Test toolbar creation and structure."""

    def test_toolbar_has_correct_object_name(self, toolbar):
        """Toolbar should have actionsToolbar object name."""
        assert toolbar.objectName() == "actionsToolbar"

    def test_toolbar_is_not_movable(self, toolbar):
        """Toolbar should not be movable by user."""
        assert not toolbar.isMovable()

    def test_all_workflow_buttons_exist(self, toolbar):
        """All workflow buttons should be created."""
        # Internal buttons exist (private attributes)
        assert hasattr(toolbar, "_btn_build")
        assert hasattr(toolbar, "_btn_pull")
        assert hasattr(toolbar, "_btn_scan")
        assert hasattr(toolbar, "_btn_match")
        assert hasattr(toolbar, "_btn_report")
        assert hasattr(toolbar, "_btn_export")
        assert hasattr(toolbar, "_btn_open_reports")
        assert hasattr(toolbar, "_btn_watch")

    def test_watch_button_is_checkable(self, toolbar):
        """Watch Mode button should be checkable."""
        assert toolbar._btn_watch.isCheckable()

    def test_other_buttons_not_checkable(self, toolbar):
        """Non-watch buttons should not be checkable."""
        assert not toolbar._btn_build.isCheckable()
        assert not toolbar._btn_pull.isCheckable()
        assert not toolbar._btn_scan.isCheckable()


class TestActionsToolbarSignals:
    """Test signal emission from toolbar buttons."""

    def test_build_button_emits_signal(self, toolbar):
        """Build button should emit buildClicked signal."""
        signal_received = []
        toolbar.buildClicked.connect(lambda: signal_received.append(True))
        toolbar._btn_build.click()
        QApplication.processEvents()
        assert len(signal_received) == 1

    def test_pull_button_emits_signal(self, toolbar):
        """Pull button should emit pullClicked signal."""
        signal_received = []
        toolbar.pullClicked.connect(lambda: signal_received.append(True))
        toolbar._btn_pull.click()
        QApplication.processEvents()
        assert len(signal_received) == 1

    def test_scan_button_emits_signal(self, toolbar):
        """Scan button should emit scanClicked signal."""
        signal_received = []
        toolbar.scanClicked.connect(lambda: signal_received.append(True))
        toolbar._btn_scan.click()
        QApplication.processEvents()
        assert len(signal_received) == 1

    def test_match_button_emits_signal(self, toolbar):
        """Match button should emit matchClicked signal."""
        signal_received = []
        toolbar.matchClicked.connect(lambda: signal_received.append(True))
        toolbar._btn_match.click()
        QApplication.processEvents()
        assert len(signal_received) == 1

    def test_report_button_emits_signal(self, toolbar):
        """Report button should emit reportClicked signal."""
        signal_received = []
        toolbar.reportClicked.connect(lambda: signal_received.append(True))
        toolbar._btn_report.click()
        QApplication.processEvents()
        assert len(signal_received) == 1

    def test_export_button_emits_signal(self, toolbar):
        """Export button should emit exportClicked signal."""
        signal_received = []
        toolbar.exportClicked.connect(lambda: signal_received.append(True))
        toolbar._btn_export.click()
        QApplication.processEvents()
        assert len(signal_received) == 1

    def test_open_reports_button_emits_signal(self, toolbar):
        """Open Reports button should emit openReportsClicked signal."""
        signal_received = []
        toolbar.openReportsClicked.connect(lambda: signal_received.append(True))
        toolbar._btn_open_reports.click()
        QApplication.processEvents()
        assert len(signal_received) == 1

    def test_watch_toggle_emits_signal_with_state(self, toolbar):
        """Watch Mode toggle should emit watchToggled signal with state."""
        signals_received = []
        toolbar.watchToggled.connect(lambda checked: signals_received.append(checked))

        # Toggle on
        toolbar._btn_watch.setChecked(True)
        QApplication.processEvents()
        assert len(signals_received) == 1
        assert signals_received[0] is True

        # Toggle off
        toolbar._btn_watch.setChecked(False)
        QApplication.processEvents()
        assert len(signals_received) == 2
        assert signals_received[1] is False


class TestActionsToolbarEnablement:
    """Test button enablement/disablement."""

    def test_set_enabled_for_workflow_disables_all_except_open_reports(self, toolbar):
        """setEnabledForWorkflow(False) should disable all workflow buttons."""
        toolbar.setEnabledForWorkflow(False)

        assert not toolbar._btn_build.isEnabled()
        assert not toolbar._btn_pull.isEnabled()
        assert not toolbar._btn_scan.isEnabled()
        assert not toolbar._btn_match.isEnabled()
        assert not toolbar._btn_report.isEnabled()
        assert not toolbar._btn_export.isEnabled()

        # Open Reports and Watch Mode should stay enabled
        assert toolbar._btn_open_reports.isEnabled()
        assert toolbar._btn_watch.isEnabled()  # Watch can be toggled even during operations

    def test_set_enabled_for_workflow_enables_all(self, toolbar):
        """setEnabledForWorkflow(True) should enable all workflow buttons."""
        # First disable
        toolbar.setEnabledForWorkflow(False)

        # Then enable
        toolbar.setEnabledForWorkflow(True)

        assert toolbar._btn_build.isEnabled()
        assert toolbar._btn_pull.isEnabled()
        assert toolbar._btn_scan.isEnabled()
        assert toolbar._btn_match.isEnabled()
        assert toolbar._btn_report.isEnabled()
        assert toolbar._btn_export.isEnabled()
        assert toolbar._btn_watch.isEnabled()
        assert toolbar._btn_open_reports.isEnabled()

    def test_disabled_buttons_do_not_emit_signals(self, toolbar):
        """Disabled buttons should not emit signals when clicked."""
        toolbar.setEnabledForWorkflow(False)

        signal_received = []
        toolbar.buildClicked.connect(lambda: signal_received.append(True))
        toolbar._btn_build.click()
        QApplication.processEvents()

        # Signal should not be emitted from disabled button
        assert len(signal_received) == 0


class TestActionsToolbarWatchMode:
    """Test watch mode state management."""

    def test_set_watch_mode_checks_button(self, toolbar):
        """setWatchMode(True) should check the watch button."""
        toolbar.setWatchMode(True)
        assert toolbar._btn_watch.isChecked()

    def test_set_watch_mode_unchecks_button(self, toolbar):
        """setWatchMode(False) should uncheck the watch button."""
        toolbar._btn_watch.setChecked(True)  # First check it
        toolbar.setWatchMode(False)
        assert not toolbar._btn_watch.isChecked()

    def test_set_watch_mode_blocks_signals(self, toolbar):
        """setWatchMode() should not emit watchToggled signal."""
        signals_received = []
        toolbar.watchToggled.connect(lambda checked: signals_received.append(checked))

        # Programmatic state change should not emit signal
        toolbar.setWatchMode(True)
        QApplication.processEvents()
        assert len(signals_received) == 0

        toolbar.setWatchMode(False)
        QApplication.processEvents()
        assert len(signals_received) == 0

    def test_manual_toggle_emits_signal(self, toolbar):
        """Manual user toggle should emit watchToggled signal."""
        signals_received = []
        toolbar.watchToggled.connect(lambda checked: signals_received.append(checked))

        # Simulate user click (not blocked)
        toolbar._btn_watch.click()
        QApplication.processEvents()
        assert len(signals_received) == 1


class TestActionsToolbarButtonText:
    """Test button text and tooltips."""

    def test_build_button_has_emoji_and_text(self, toolbar):
        """Build button should have emoji icon and descriptive text."""
        text = toolbar._btn_build.text()
        assert "▶️" in text
        assert "Build" in text

    def test_all_buttons_have_tooltips(self, toolbar):
        """All buttons should have helpful tooltips."""
        assert toolbar._btn_build.toolTip()
        assert toolbar._btn_pull.toolTip()
        assert toolbar._btn_scan.toolTip()
        assert toolbar._btn_match.toolTip()
        assert toolbar._btn_report.toolTip()
        assert toolbar._btn_export.toolTip()
        assert toolbar._btn_open_reports.toolTip()
        assert toolbar._btn_watch.toolTip()

    def test_step_buttons_have_emojis(self, toolbar):
        """Step buttons should have emoji icons."""
        assert "⬇️" in toolbar._btn_pull.text()
        assert "🔍" in toolbar._btn_scan.text()
        assert "🎯" in toolbar._btn_match.text()
        assert "📊" in toolbar._btn_report.text()
        assert "💾" in toolbar._btn_export.text()
        assert "📁" in toolbar._btn_open_reports.text()
        assert "👁️" in toolbar._btn_watch.text()


class TestActionsToolbarIntegration:
    """Integration tests for realistic usage scenarios."""

    def test_workflow_disable_enable_cycle(self, toolbar):
        """Simulate a command execution cycle."""
        # Start enabled
        assert toolbar._btn_build.isEnabled()

        # Disable for command execution
        toolbar.setEnabledForWorkflow(False)
        assert not toolbar._btn_build.isEnabled()

        # Re-enable after completion
        toolbar.setEnabledForWorkflow(True)
        assert toolbar._btn_build.isEnabled()

    def test_watch_mode_toggle_during_disabled_state(self, toolbar):
        """Watch mode state changes should work even when disabled."""
        toolbar.setEnabledForWorkflow(False)

        # Should still be able to change state programmatically
        toolbar.setWatchMode(True)
        assert toolbar._btn_watch.isChecked()

        toolbar.setWatchMode(False)
        assert not toolbar._btn_watch.isChecked()
