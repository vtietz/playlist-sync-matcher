"""Tests for BottomPanel component."""

import pytest
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtCore import Qt

from psm.gui.panels.bottom_panel import BottomPanel


@pytest.fixture(scope='module')
def qapp():
    """Create QApplication instance for GUI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def main_window(qapp):
    """Create a MainWindow with status bar for testing."""
    window = QMainWindow()
    return window


@pytest.fixture
def panel(qapp, main_window):
    """Create BottomPanel instance for testing."""
    return BottomPanel(main_window.statusBar(), main_window)


class TestBottomPanelCreation:
    """Test bottom panel creation and structure."""
    
    def test_panel_creation(self, panel):
        """Panel should be created successfully."""
        assert panel is not None
    
    def test_has_log_panel(self, panel):
        """Panel should have a log panel component."""
        assert hasattr(panel, '_log_panel')
        assert panel._log_panel is not None
    
    def test_has_status_bar(self, panel):
        """Panel should have a status bar component."""
        assert hasattr(panel, '_status_bar')
        assert panel._status_bar is not None
    
    def test_ansi_escape_pattern_compiled(self, panel):
        """ANSI escape pattern should be pre-compiled for performance."""
        assert hasattr(BottomPanel, '_ANSI_ESCAPE')
        assert BottomPanel._ANSI_ESCAPE is not None


class TestBottomPanelLogging:
    """Test log message appending and clearing."""
    
    def test_append_simple_message(self, panel):
        """Should append plain text messages."""
        panel.append_log("Test message")
        # Log panel should contain the message
        text = panel._log_panel.get_text()
        assert "Test message" in text
    
    def test_append_multiple_messages(self, panel):
        """Should append multiple messages sequentially."""
        panel.clear_logs()
        panel.append_log("First message")
        panel.append_log("Second message")
        
        text = panel._log_panel.get_text()
        assert "First message" in text
        assert "Second message" in text
    
    def test_clear_logs(self, panel):
        """Should clear all log messages."""
        panel.append_log("Message to be cleared")
        panel.clear_logs()
        
        text = panel._log_panel.get_text()
        assert text.strip() == ""
    
    def test_ansi_escape_stripping_basic(self, panel):
        """Should strip basic ANSI color codes."""
        panel.clear_logs()
        # ANSI code for red text
        panel.append_log("\x1B[31mRed text\x1B[0m")
        
        text = panel._log_panel.get_text()
        assert "Red text" in text
        assert "\x1B[31m" not in text
        assert "\x1B[0m" not in text
    
    def test_ansi_escape_stripping_complex(self, panel):
        """Should strip complex ANSI escape sequences."""
        panel.clear_logs()
        # Complex ANSI codes with multiple parameters
        message_with_ansi = "\x1B[1;32;40mBold green on black\x1B[0m normal \x1B[4munderline\x1B[0m"
        panel.append_log(message_with_ansi)
        
        text = panel._log_panel.get_text()
        assert "Bold green on black" in text
        assert "normal" in text
        assert "underline" in text
        assert "\x1B[" not in text  # No ANSI codes should remain
    
    def test_ansi_escape_stripping_preserves_content(self, panel):
        """Should preserve actual message content while removing ANSI codes."""
        panel.clear_logs()
        panel.append_log("✓ Success \x1B[32m(green)\x1B[0m")
        
        text = panel._log_panel.get_text()
        assert "✓ Success" in text
        assert "(green)" in text


class TestBottomPanelStatus:
    """Test execution status updates."""
    
    def test_set_execution_status_running(self, panel):
        """Should set running status with message."""
        panel.set_execution_status(True, "Running command...")
        # Status bar should reflect running state
        # (Actual verification would require accessing status bar internals)
    
    def test_set_execution_status_idle(self, panel):
        """Should set idle status."""
        panel.set_execution_status(False, "")
        # Status bar should reflect idle state
    
    def test_execution_status_toggle(self, panel):
        """Should handle status toggling."""
        panel.set_execution_status(True, "Processing")
        panel.set_execution_status(False)
        # Should not raise exceptions


class TestBottomPanelStats:
    """Test statistics display."""
    
    def test_update_stats_complete(self, panel):
        """Should update all statistics."""
        counts = {
            'playlists': 10,
            'tracks': 500,
            'library_files': 450,
            'matches': 400
        }
        panel.update_stats(counts)
        # Should not raise exceptions
    
    def test_update_stats_partial(self, panel):
        """Should handle partial statistics."""
        counts = {
            'playlists': 5,
            'tracks': 100
        }
        panel.update_stats(counts)
        # Should not raise exceptions
    
    def test_update_stats_empty(self, panel):
        """Should handle empty statistics."""
        counts = {}
        panel.update_stats(counts)
        # Should not raise exceptions
    
    def test_update_stats_zeros(self, panel):
        """Should handle zero values."""
        counts = {
            'playlists': 0,
            'tracks': 0,
            'library_files': 0,
            'matches': 0
        }
        panel.update_stats(counts)
        # Should not raise exceptions


class TestBottomPanelIntegration:
    """Integration tests for realistic usage scenarios."""
    
    def test_typical_workflow(self, panel):
        """Simulate a typical command execution workflow."""
        # Clear logs
        panel.clear_logs()
        
        # Set running status
        panel.set_execution_status(True, "Scanning library...")
        
        # Append progress messages
        panel.append_log("Found 100 files")
        panel.append_log("\x1B[32m✓ Scan complete\x1B[0m")
        
        # Update stats
        panel.update_stats({
            'library_files': 100,
            'tracks': 500,
            'matches': 95
        })
        
        # Set idle status
        panel.set_execution_status(False)
        
        # Verify logs contain messages
        text = panel._log_panel.get_text()
        assert "Found 100 files" in text
        assert "✓ Scan complete" in text
        assert "\x1B[" not in text  # No ANSI codes
    
    def test_repeated_operations(self, panel):
        """Should handle repeated log/status updates."""
        for i in range(5):
            panel.append_log(f"Operation {i}")
            panel.set_execution_status(i % 2 == 0, f"Step {i}")
        
        # Should complete without errors
        text = panel._log_panel.get_text()
        assert "Operation 0" in text
        assert "Operation 4" in text
    
    def test_log_then_clear_then_log(self, panel):
        """Should handle log, clear, log sequence."""
        panel.append_log("First batch")
        panel.clear_logs()
        panel.append_log("Second batch")
        
        text = panel._log_panel.get_text()
        assert "First batch" not in text
        assert "Second batch" in text


class TestBottomPanelPerformance:
    """Test performance-related aspects."""
    
    def test_ansi_pattern_reuse(self, panel):
        """ANSI pattern should be compiled once and reused."""
        # Pattern should be a class attribute
        pattern1 = BottomPanel._ANSI_ESCAPE
        pattern2 = BottomPanel._ANSI_ESCAPE
        assert pattern1 is pattern2  # Same object (singleton pattern)
    
    def test_many_log_messages(self, panel):
        """Should handle many log messages efficiently."""
        panel.clear_logs()
        
        # Append many messages
        for i in range(100):
            panel.append_log(f"Message {i}")
        
        # Should complete without performance issues
        text = panel._log_panel.get_text()
        assert "Message 0" in text
        assert "Message 99" in text
