"""Library scanning command."""

from __future__ import annotations
import click
import logging

from .helpers import cli, get_db
from ..ingest.library import scan_library, scan_library_incremental, parse_time_string, scan_specific_files

logger = logging.getLogger(__name__)


@cli.command()
@click.option(
    "--since", type=str, help='Only scan files modified since this time (e.g., "2 hours ago", "2025-10-08 10:00")'
)
@click.option("--deep", is_flag=True, help="Force full rescan of all library paths (default: smart incremental)")
@click.option("--paths", multiple=True, help="Override config: scan only these specific paths")
@click.option("--watch", is_flag=True, help="Watch library paths and continuously update DB on changes")
@click.option(
    "--debounce", type=float, default=2.0, help="Seconds to wait after last change before processing (watch mode only)"
)
@click.pass_context
def scan(ctx: click.Context, since: str | None, deep: bool, paths: tuple, watch: bool, debounce: float):
    """Scan local music library and index track metadata.

    Default mode: Smart incremental (only new/modified files)
    Use --deep to force complete rescan of all library paths

    Other modes:
    - --since "TIME": Only files modified after specified time
    - --paths PATH...: Scan only specific directories or files
    - --watch: Monitor filesystem and update DB automatically

    Examples:
      psm scan                              # Smart incremental (default)
      psm scan --deep                       # Force complete rescan
      psm scan --since "2 hours ago"        # Only recently modified
      psm scan --paths ./newalbum/          # Scan specific directory
      psm scan --watch                      # Monitor and auto-update
      psm scan --watch --debounce 5         # Watch with 5s debounce
    """
    cfg = ctx.obj

    # Watch mode - continuous monitoring
    if watch:
        if since or deep or paths:
            raise click.UsageError("--watch cannot be combined with --since, --deep, or --paths")

        from ..services.watch_service import LibraryWatcher
        from ..utils.output import success, info, warning

        def handle_changes(changed_files: list):
            """Callback for filesystem changes."""
            click.echo(info(f"Detected {len(changed_files)} changed file(s)"))

            try:
                with get_db(cfg) as db:
                    result = scan_specific_files(db, cfg, changed_files)
                    import time

                    db.set_meta("last_scan_time", str(time.time()))
                    db.set_meta("library_last_modified", str(time.time()))

                # Print summary
                changes = []
                if result.inserted > 0:
                    changes.append(f"{result.inserted} new")
                if result.updated > 0:
                    changes.append(f"{result.updated} updated")
                if result.deleted > 0:
                    changes.append(f"{result.deleted} deleted")

                if changes:
                    click.echo(success(f"✓ {', '.join(changes)}"))
                else:
                    click.echo(info("No changes"))

            except Exception as e:
                click.echo(warning(f"Error processing changes: {e}"), err=True)
                logger.error(f"Watch mode error: {e}", exc_info=True)

        click.echo(info(f"Starting watch mode (debounce={debounce}s)..."))
        click.echo(info("Press Ctrl+C to stop"))
        click.echo("")

        watcher = None
        try:
            watcher = LibraryWatcher(cfg, handle_changes, debounce_seconds=debounce)
            watcher.start()

            # Keep running until interrupted
            import time

            while True:
                time.sleep(1)

        except KeyboardInterrupt:
            click.echo("")
            click.echo(info("Stopping watch mode..."))
            if watcher:
                watcher.stop()
            click.echo(success("Watch mode stopped"))
            return
        except Exception as e:
            click.echo(warning(f"Watch mode error: {e}"), err=True)
            logger.error(f"Watch mode failed: {e}", exc_info=True)
            if watcher:
                watcher.stop()
            raise

    # Determine scan mode (non-watch)
    changed_since = None
    specific_paths = None

    if since and not deep:
        # --since flag takes precedence for time-based filtering
        try:
            changed_since = parse_time_string(since)
            from datetime import datetime

            click.echo(
                f"Scanning files modified since {datetime.fromtimestamp(changed_since).strftime('%Y-%m-%d %H:%M:%S')}"
            )
        except ValueError as e:
            raise click.UsageError(str(e))
    elif not deep and not since:
        # Default: Smart mode - use last scan time
        with get_db(cfg) as db:
            last_scan = db.get_meta("last_scan_time")
        if last_scan:
            changed_since = float(last_scan)
            from datetime import datetime

            click.echo(
                f"Smart mode: scanning files modified since last scan ({datetime.fromtimestamp(changed_since).strftime('%Y-%m-%d %H:%M:%S')})"
            )
            click.echo("  (Use --deep to force complete rescan)")
        else:
            click.echo("Smart mode: no previous scan found, performing full scan")
    else:
        # --deep flag: full rescan
        click.echo("Deep scan: rescanning all library paths")

    if paths:
        from pathlib import Path

        specific_paths = [Path(p) for p in paths]
        click.echo(f"Scanning {len(specific_paths)} specific path(s)")

    # Perform scan
    if changed_since is not None or specific_paths:
        # Incremental scan
        with get_db(cfg) as db:
            result = scan_library_incremental(db, cfg, changed_since=changed_since, specific_paths=specific_paths)
            # Update last scan time
            import time

            db.set_meta("last_scan_time", str(time.time()))
            db.set_meta("library_last_modified", str(time.time()))
            # Set write signal for GUI auto-refresh
            db.set_meta("last_write_epoch", str(time.time()))
            db.set_meta("last_write_source", "scan")

        # Print summary
        from ..utils.logging_helpers import format_summary

        summary = format_summary(
            new=result.inserted,
            updated=result.updated,
            unchanged=result.skipped,
            deleted=result.deleted,
            duration_seconds=result.duration_seconds,
            item_name="Library",
        )
        logger.info(summary)
        if result.errors:
            logger.debug(f"Errors: {result.errors}")
    else:
        # Full scan
        with get_db(cfg) as db:
            scan_library(db, cfg)
            # Update last scan time
            import time

            db.set_meta("last_scan_time", str(time.time()))
            db.set_meta("library_last_modified", str(time.time()))
            # Set write signal for GUI auto-refresh
            db.set_meta("last_write_epoch", str(time.time()))
            db.set_meta("last_write_source", "scan")

    click.echo("Scan complete")


__all__ = ["scan"]
