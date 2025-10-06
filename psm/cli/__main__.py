from __future__ import annotations
"""Module entry point for `python -m psm.cli`.

Ensures the Click command group runs when the package is executed as a module.
Previously the package lacked a __main__ so `python -m psm.cli` failed in CI.
"""
from . import cli

if __name__ == "__main__":  # pragma: no cover (invocation driven)
    cli()
