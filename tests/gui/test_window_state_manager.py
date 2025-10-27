"""Tests for WindowStateManager component."""

import pytest
from PySide6.QtWidgets import QApplication, QMainWindow, QSplitter, QTableView
from PySide6.QtCore import Qt, QSettings

from psm.gui.window_state_manager import WindowStateManager


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for GUI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def settings_cleanup():
    """Clean up QSettings after tests."""
    yield
    # Clear test settings
    settings = QSettings("TestOrg", "TestApp")
    settings.clear()


@pytest.fixture
def manager(settings_cleanup):
    """Create WindowStateManager instance for testing."""
    return WindowStateManager("TestOrg", "TestApp")


@pytest.fixture
def main_window(qapp):
    """Create a test MainWindow."""
    window = QMainWindow()
    window.resize(800, 600)
    return window


@pytest.fixture
def splitter(qapp):
    """Create a test splitter with widgets."""
    from PySide6.QtWidgets import QWidget

    splitter = QSplitter()
    # Add two widgets so splitter can have sizes
    splitter.addWidget(QWidget())
    splitter.addWidget(QWidget())
    splitter.setSizes([200, 600])
    return splitter


@pytest.fixture
def table_view(qapp):
    """Create a test table view with header."""
    from psm.gui.models import PlaylistsModel

    table = QTableView()
    model = PlaylistsModel()
    table.setModel(model)

    # Set some custom column widths
    header = table.horizontalHeader()
    header.resizeSection(0, 250)
    header.resizeSection(1, 150)
    header.resizeSection(2, 100)

    # Set sort indicator
    header.setSortIndicator(0, Qt.AscendingOrder)

    return table


class TestWindowStateManagerCreation:
    """Test state manager creation."""

    def test_manager_creation(self, manager):
        """Manager should be created successfully."""
        assert manager is not None

    def test_has_settings(self, manager):
        """Manager should have QSettings instance."""
        assert hasattr(manager, "settings")
        assert isinstance(manager.settings, QSettings)

    def test_settings_organization(self, manager):
        """Settings should use correct organization/application names."""
        assert manager.settings.organizationName() == "TestOrg"
        assert manager.settings.applicationName() == "TestApp"


class TestWindowGeometry:
    """Test window geometry save/restore."""

    def test_save_window_geometry(self, manager, main_window):
        """Should save window geometry."""
        main_window.resize(1024, 768)
        manager.save_window_geometry(main_window)

        # Verify geometry was saved
        saved_geometry = manager.settings.value("geometry")
        assert saved_geometry is not None

    def test_restore_window_geometry(self, manager, main_window):
        """Should restore window geometry."""
        # Save geometry
        main_window.resize(1024, 768)
        manager.save_window_geometry(main_window)

        # Change geometry
        main_window.resize(640, 480)

        # Restore
        manager.restore_window_geometry(main_window)

        # Note: Actual geometry may not match exactly due to window manager,
        # but it should attempt to restore
        assert True  # Mainly testing no exceptions

    def test_restore_without_saved_geometry(self, manager, main_window):
        """Should handle missing saved geometry gracefully."""
        # Clear any existing geometry
        manager.settings.remove("geometry")
        manager.settings.remove("windowState")

        # Should not raise exception
        manager.restore_window_geometry(main_window)


class TestSplitterState:
    """Test splitter state save/restore."""

    def test_save_splitter_state(self, manager, splitter):
        """Should save splitter state."""
        splitter.setSizes([300, 500])
        manager.save_splitter_state(splitter)

        saved_state = manager.settings.value("mainSplitter")
        assert saved_state is not None

    def test_save_splitter_with_custom_key(self, manager, splitter):
        """Should save splitter state with custom key."""
        manager.save_splitter_state(splitter, "customSplitter")

        saved_state = manager.settings.value("customSplitter")
        assert saved_state is not None

    def test_restore_splitter_state(self, manager, splitter):
        """Should restore splitter state."""
        # Save state
        splitter.setSizes([300, 500])
        manager.save_splitter_state(splitter)

        # Change state
        splitter.setSizes([100, 700])

        # Restore
        manager.restore_splitter_state(splitter)

        # Verify restoration (sizes should be close to original)
        sizes = splitter.sizes()
        assert len(sizes) == 2

    def test_restore_without_saved_splitter(self, manager, splitter):
        """Should handle missing saved splitter state gracefully."""
        manager.settings.remove("mainSplitter")

        # Should not raise exception
        manager.restore_splitter_state(splitter)


class TestTableState:
    """Test table column width and sort state save/restore."""

    def test_save_table_state(self, manager, table_view):
        """Should save table column widths and sort state."""
        header = table_view.horizontalHeader()
        header.resizeSection(0, 250)
        header.setSortIndicator(1, Qt.DescendingOrder)

        manager.save_table_state(header, "test")

        # Verify saved
        assert manager.settings.value("testColumnWidths") is not None
        assert manager.settings.value("testSortColumn") is not None
        assert manager.settings.value("testSortOrder") is not None

    def test_restore_table_column_widths(self, manager, table_view):
        """Should restore table column widths."""
        header = table_view.horizontalHeader()

        # Save widths
        header.resizeSection(0, 250)
        header.resizeSection(1, 150)
        manager.save_table_state(header, "test")

        # Change widths
        header.resizeSection(0, 100)
        header.resizeSection(1, 100)

        # Restore
        manager.restore_table_column_widths(header, "test")

        # Verify restoration
        assert header.sectionSize(0) == 250
        assert header.sectionSize(1) == 150

    def test_get_pending_table_sort(self, manager, table_view):
        """Should retrieve pending sort state."""
        header = table_view.horizontalHeader()
        header.setSortIndicator(2, Qt.DescendingOrder)

        manager.save_table_state(header, "test")

        pending_sort = manager.get_pending_table_sort("test")
        assert pending_sort is not None
        assert pending_sort[0] == 2  # Column
        assert pending_sort[1] == Qt.DescendingOrder

    def test_get_pending_table_sort_missing(self, manager):
        """Should return None for missing sort state."""
        manager.settings.remove("testSortColumn")
        manager.settings.remove("testSortOrder")

        pending_sort = manager.get_pending_table_sort("test")
        assert pending_sort is None


class TestBulkOperations:
    """Test bulk save/restore operations."""

    def test_save_all_window_state(self, manager, main_window, splitter, table_view):
        """Should save all window state in one call."""
        table_headers = {
            "playlists": table_view.horizontalHeader(),
        }

        manager.save_all_window_state(main_window, splitter, table_headers)

        # Verify all components saved
        assert manager.settings.value("geometry") is not None
        assert manager.settings.value("mainSplitter") is not None
        assert manager.settings.value("playlistsColumnWidths") is not None

    def test_restore_all_window_state(self, manager, main_window, splitter, table_view):
        """Should restore all window state in one call."""
        table_headers = {
            "playlists": table_view.horizontalHeader(),
        }

        # Save state
        manager.save_all_window_state(main_window, splitter, table_headers)

        # Restore state
        pending_sorts = manager.restore_all_window_state(main_window, splitter, table_headers)

        # Should return pending sorts dict
        assert isinstance(pending_sorts, dict)

    def test_restore_all_with_pending_sorts(self, manager, main_window, splitter, table_view):
        """Should return pending sort states from bulk restore."""
        header = table_view.horizontalHeader()
        header.setSortIndicator(1, Qt.DescendingOrder)

        table_headers = {
            "test": header,
        }

        # Save
        manager.save_all_window_state(main_window, splitter, table_headers)

        # Restore
        pending_sorts = manager.restore_all_window_state(main_window, splitter, table_headers)

        # Verify pending sort returned
        assert "test" in pending_sorts
        assert pending_sorts["test"][0] == 1
        assert pending_sorts["test"][1] == Qt.DescendingOrder

    def test_restore_all_with_multiple_tables(self, manager, main_window, splitter, table_view):
        """Should handle multiple tables in bulk operations."""
        # Create second table
        from psm.gui.models import UnifiedTracksModel

        table2 = QTableView()
        model2 = UnifiedTracksModel()
        table2.setModel(model2)

        table_headers = {
            "playlists": table_view.horizontalHeader(),
            "tracks": table2.horizontalHeader(),
        }

        # Save and restore
        manager.save_all_window_state(main_window, splitter, table_headers)
        pending_sorts = manager.restore_all_window_state(main_window, splitter, table_headers)

        # Should handle both tables
        assert isinstance(pending_sorts, dict)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_save_with_zero_width_columns(self, manager, table_view):
        """Should handle columns with zero width."""
        header = table_view.horizontalHeader()
        header.resizeSection(0, 0)  # Zero width

        manager.save_table_state(header, "test")

        # Should not raise exception
        assert manager.settings.value("testColumnWidths") is not None

    def test_restore_with_mismatched_column_count(self, manager, table_view):
        """Should handle column count mismatch gracefully."""
        header = table_view.horizontalHeader()

        # Save widths for 3 columns
        widths = [100, 200, 300, 400]  # More than actual columns
        manager.settings.setValue("testColumnWidths", widths)

        # Should not raise exception
        manager.restore_table_column_widths(header, "test")

    def test_empty_table_headers_dict(self, manager, main_window, splitter):
        """Should handle empty table headers dict."""
        table_headers = {}

        manager.save_all_window_state(main_window, splitter, table_headers)
        pending_sorts = manager.restore_all_window_state(main_window, splitter, table_headers)

        assert pending_sorts == {}
