"""Shared utilities for CLI and GUI.

This module contains utilities that are used by both CLI and GUI components,
without importing click (which is CLI-only).
"""

from __future__ import annotations
from pathlib import Path
from ..db import Database


def get_db(cfg):
    """Get database instance from config.

    Args:
        cfg: Configuration dictionary

    Returns:
        Database instance
    """
    return Database(Path(cfg["database"]["path"]))
