"""CLI package bootstrap.

Defines root group (`cli`) in helpers and imports submodules so their
decorators register commands. Keep this file minimal to avoid circular
imports and duplication.
"""
# Use absolute imports for PyInstaller frozen executable compatibility
from psm.cli.helpers import cli  # root group
from psm.cli import core  # noqa: F401
from psm.cli import playlists  # noqa: F401
from psm.cli import playlist_cmds  # noqa: F401

__all__ = ["cli"]
