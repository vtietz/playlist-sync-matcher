"""CLI package bootstrap.

Defines root group (`cli`) in helpers and imports submodules so their
decorators register commands. Keep this file minimal to avoid circular
imports and duplication.
"""
from .helpers import cli  # root group
from . import core  # noqa: F401
from . import playlists  # noqa: F401
from . import playlist_cmds  # noqa: F401

__all__ = ["cli"]
