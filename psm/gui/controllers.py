"""Controllers wiring UI events to actions and data updates.

COMPATIBILITY LAYER: This module now delegates to the new modular controller architecture.
The MainController class is a thin wrapper around MainOrchestrator for backward compatibility.

For new code, import directly from psm.gui.controllers package:
    from psm.gui.controllers import MainOrchestrator
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from .controllers import MainOrchestrator

if TYPE_CHECKING:
    from .main_window import MainWindow
    from .data_facade import DataFacade
    from .runner import CliExecutor


class MainController(MainOrchestrator):
    """Main controller - compatibility wrapper around MainOrchestrator.
    
    This class exists solely for backward compatibility with existing code
    that imports MainController from psm.gui.controllers.
    
    All functionality has been delegated to MainOrchestrator and specialized
    sub-controllers. See MainOrchestrator for the new architecture.
    """
    pass
