from __future__ import annotations

"""Module entry point for `python -m psm.cli`.

Ensures the Click command group runs when the package is executed as a module.
Previously the package lacked a __main__ so `python -m psm.cli` failed in CI.
"""
import sys
import os

if __name__ == "__main__":  # pragma: no cover (invocation driven)
    # Force UTF-8 encoding for console output (fixes emoji display in PyInstaller builds on Windows)
    if sys.platform == "win32":
        # Set UTF-8 mode for stdin/stdout/stderr
        os.environ["PYTHONIOENCODING"] = "utf-8"
        # Reconfigure stdout/stderr to use UTF-8 with error handling
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    # Use absolute import for PyInstaller compatibility
    from psm.cli import cli

    cli()
