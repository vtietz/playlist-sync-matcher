"""Controller modules for GUI orchestration.

This package contains specialized controllers that decompose the responsibilities
of the monolithic MainController into cohesive, testable units.
"""
from .main_orchestrator import MainOrchestrator
from .db_auto_refresh_controller import DbAutoRefreshController
from .data_refresh_controller import DataRefreshController
from .selection_sync_controller import SelectionSyncController
from .command_controller import CommandController
from .watch_mode_controller import WatchModeController

# Compatibility alias for imports from the package
MainController = MainOrchestrator

__all__ = [
    'MainOrchestrator',
    'MainController',  # Compatibility export
    'DbAutoRefreshController',
    'DataRefreshController',
    'SelectionSyncController',
    'CommandController',
    'WatchModeController',
]
