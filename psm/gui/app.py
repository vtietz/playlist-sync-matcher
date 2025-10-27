"""Qt application bootstrap.

Sets up QApplication, loads configuration and database, and launches main window.
"""

import sys
import logging
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from psm.config import load_typed_config
from psm.cli.shared import get_db
from .main_window import MainWindow
from .data_facade import DataFacade
from .runner import CliExecutor
from .controllers import MainOrchestrator

logger = logging.getLogger(__name__)


def setup_logging():
    """Configure logging for the GUI."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def load_resources():
    """Load Qt resources (stylesheets, icons, etc.)."""
    # Try to load custom stylesheet
    resources_dir = Path(__file__).parent / "resources"
    style_file = resources_dir / "style.qss"

    if style_file.exists():
        try:
            with open(style_file, "r") as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Failed to load stylesheet: {e}")

    return ""


def apply_app_icon(app: QApplication) -> None:
    """Set application/window icon if available.

    Looks for `psm/gui/resources/icon.png` (preferred cross‑platform) or `icon.ico`.
    Safe no‑op if files are missing.
    """
    resources_dir = Path(__file__).parent / "resources"
    for name in ("psm-icon.png", "psm-icon.ico", "ps-icon.ico", "icon.png", "icon.ico"):
        p = resources_dir / name
        if p.exists():
            try:
                app.setWindowIcon(QIcon(str(p)))
                break
            except Exception as e:
                logger.warning(f"Failed to set window icon from {p}: {e}")


def main() -> int:
    """Main entry point for GUI application.

    Returns:
        Exit code
    """
    setup_logging()
    logger.info("Starting Playlist Sync Matcher GUI...")

    # Check for first run before creating Qt application
    from ..utils.first_run import check_env_exists

    if not check_env_exists():
        # Need to show GUI dialog, so create minimal QApplication
        app = QApplication([])
        from ..utils.first_run import check_first_run_gui

        if not check_first_run_gui():
            logger.info("User needs to configure .env file. Exiting.")
            return 1

    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("Playlist Sync Matcher")
    app.setOrganizationName("PSM")

    # Set high DPI scaling
    app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # Use native system theme/style
    # This ensures the app respects dark mode settings on Windows/macOS/Linux
    app.setStyle("Fusion")  # Fusion style works well with both light and dark themes

    # Load custom stylesheet (uses palette colors that adapt to system theme)
    stylesheet = load_resources()
    if stylesheet:
        app.setStyleSheet(stylesheet)

    # Set application/window icon if provided in resources
    apply_app_icon(app)

    db = None
    try:
        # Load config and database
        logger.info("Loading configuration...")
        config = load_typed_config()
        config_dict = config.to_dict()

        logger.info("Opening database...")
        db = get_db(config_dict)

        # Get provider from config
        provider = config_dict.get("provider", "spotify")

        # Create data facade
        facade = DataFacade(db, provider=provider)

        # Create facade factory for thread-safe background loads
        # Each background thread gets a fresh DB connection to avoid SQLite threading issues
        def facade_factory():
            """Create a new facade with fresh DB connection for background threads."""
            thread_db = get_db(config_dict)
            return DataFacade(thread_db, provider=provider)

        # Create CLI executor
        executor = CliExecutor()

        # Create main window
        window = MainWindow()

        # Create controller (wires everything together and loads data)
        controller = MainOrchestrator(window, facade, executor, facade_factory)

        # Store controller reference in window (for FilterBar -> Controller communication)
        window.set_controller(controller)

        # Show window
        window.show()

        logger.info("GUI ready")

        # Run event loop
        return app.exec()

    except Exception as e:
        logger.exception("Failed to start GUI")
        QMessageBox.critical(
            None,
            "Startup Error",
            f"Failed to start application:\n\n{str(e)}\n\n"
            f"Make sure the database and configuration are properly set up.",
        )
        return 1
    finally:
        # Cleanup
        if db is not None:
            db.close()


if __name__ == "__main__":
    sys.exit(main())
