"""Core CLI module - main entry point with build and GUI commands.

Command modules are organized by functionality:
- report_cmds: Report generation
- config_cmds: Configuration display
- oauth_cmds: OAuth helpers (redirect-uri, token-info)
- provider_cmds: Provider authentication (pull, login, providers group)
- scan_cmds: Library scanning
- match_cmds: Matching engine
- analyze_cmds: Library analysis
- export_cmds: Playlist export
- diagnose_cmds: Track matching diagnostics
"""

from __future__ import annotations
import click
import logging

from .helpers import cli, get_db

# Import command modules to register commands with cli group
from . import report_cmds
from . import provider_cmds
from . import scan_cmds
from . import match_cmds
from . import export_cmds

logger = logging.getLogger(__name__)


@cli.command(name="build")
@click.option("--no-report", is_flag=True, help="Skip report generation step")
@click.option("--no-export", is_flag=True, help="Skip playlist export step")
@click.option("--watch", is_flag=True, help="Watch library for changes and auto-rebuild")
@click.option("--debounce", type=float, default=2.0, help="Debounce time in seconds for watch mode")
@click.pass_context
def build(ctx: click.Context, no_report: bool, no_export: bool, watch: bool, debounce: float):
    """Run the full one-way pipeline (pull -> scan -> match -> export -> report).

    Builds local artifacts from remote + local state without mutating the
    provider. Use --no-export or --no-report to skip phases for faster iteration.

    With --watch, ONLY monitors library for changes and incrementally processes them.
    Does NOT run initial full build - run 'psm build' first without --watch to do
    initial setup. In watch mode: only changed files are scanned, matched, exported,
    and reported. This is much more efficient than re-running the entire pipeline.
    """
    cfg = ctx.obj

    # Watch mode: skip initial build, only process changes
    if watch:
        from ..services.watch_build_service import run_watch_build, WatchBuildConfig

        # Print styled header for watch mode
        click.echo(click.style("=== Entering watch mode ===", fg="cyan", bold=True))

        watch_config = WatchBuildConfig(
            config=cfg, get_db_func=get_db, skip_export=no_export, skip_report=no_report, debounce_seconds=debounce
        )

        run_watch_build(watch_config)
        return

    # Normal build mode (non-watch): Run full pipeline
    ctx.invoke(provider_cmds.pull)
    ctx.invoke(
        scan_cmds.scan, since=None, deep=True, paths=(), watch=False, debounce=2.0
    )  # Use --deep for initial full scan
    ctx.invoke(match_cmds.match, full=True)  # Use --full for initial complete match
    if not no_export:
        ctx.invoke(export_cmds.export)
    if not no_report:
        ctx.invoke(report_cmds.report, match_reports=True, analysis_reports=True, min_bitrate=None)
    click.echo("Build complete")


@cli.command()
@click.pass_context
def gui(ctx):
    """Launch the desktop GUI application.

    Opens a graphical interface for managing playlists, viewing reports,
    and running sync operations with visual progress tracking.

    Requires PySide6 to be installed (included in requirements.txt).

    \b
    Features:
    - Browse playlists and tracks
    - View unmatched tracks and coverage statistics
    - Run Pull, Scan, Match, Export, Report operations
    - Watch mode with live progress updates
    - Real-time log streaming

    \b
    Example:
        psm gui
    """
    import sys

    try:
        from psm.gui.app import main as gui_main

        sys.exit(gui_main())
    except ImportError as e:
        if "PySide6" in str(e):
            click.echo(click.style("✗ Error: PySide6 not installed", fg="red", bold=True))
            click.echo("")
            click.echo("The GUI requires PySide6. Install it with:")
            click.echo(click.style("  pip install PySide6>=6.6.0", fg="cyan"))
            click.echo("")
            click.echo("Or install all dependencies:")
            click.echo(click.style("  pip install -r requirements.txt", fg="cyan"))
            sys.exit(1)
        else:
            raise
