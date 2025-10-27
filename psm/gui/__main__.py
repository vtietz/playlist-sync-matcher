"""Entry point for the GUI application.

Usage:
    python -m psm.gui
"""

import sys

if __name__ == "__main__":
    # Use absolute import for PyInstaller compatibility
    from psm.gui.app import main

    sys.exit(main())
