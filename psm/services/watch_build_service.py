"""Watch build service: Orchestrate incremental rebuild on changes.

This service handles watch mode for the build command, monitoring both
library file changes and database changes, then triggering appropriate
incremental rebuilds.
"""

from __future__ import annotations
import time
import logging
import click
from pathlib import Path
from typing import Dict, Any, Callable, List

from ..db import Database
from ..ingest.library import scan_specific_files
from ..services.match_service import match_changed_files, run_matching
from ..services.export_service import export_playlists
from ..reporting.generator import write_match_reports, write_index_page
from ..services.watch_service import LibraryWatcher
from ..utils import progress
from ..utils.fs import normalize_library_path

logger = logging.getLogger(__name__)


class WatchBuildConfig:
    """Configuration for watch build mode."""

    def __init__(
        self,
        config: Dict[str, Any],
        get_db_func: Callable,
        skip_export: bool = False,
        skip_report: bool = False,
        debounce_seconds: float = 2.0,
        db_check_interval: float = 2.0,
    ):
        self.config = config
        self.get_db = get_db_func
        self.skip_export = skip_export
        self.skip_report = skip_report
        self.debounce_seconds = debounce_seconds
        self.db_check_interval = db_check_interval
        self.db_path = Path(config["database"]["path"])


def _handle_library_changes(changed_file_paths: list, watch_config: WatchBuildConfig) -> float:
    """Handle library file changes with incremental scan and match.

    Returns:
        Updated database mtime after all operations complete
    """
    logger.info("")
    logger.info(f"▶ Library changed ({len(changed_file_paths)} files)")

    try:
        with watch_config.get_db(watch_config.config) as db:
            # 1. Scan changed files
            progress.step(1, 4, "Scanning changed files")
            scan_result = scan_specific_files(db, watch_config.config, changed_file_paths)

            # Track which file IDs were affected
            file_ids_to_match = []

            # Get file IDs for paths that were scanned (use normalized paths to match DB storage)
            for path in changed_file_paths:
                # Normalize path to match database storage format
                if not isinstance(path, Path):
                    path = Path(path)
                normalized_path = normalize_library_path(path)

                file_row = db.conn.execute("SELECT id FROM library_files WHERE path = ?", (normalized_path,)).fetchone()
                if file_row:
                    file_ids_to_match.append(file_row["id"])

            progress.status(
                f"✓ {scan_result.inserted} new, {scan_result.updated} updated, {scan_result.deleted} deleted"
            )

            # 2. Incrementally match only changed files
            matched_track_ids = []
            if file_ids_to_match:
                progress.step(2, 4, f"Matching {len(file_ids_to_match)} changed file(s)")
                new_matches, matched_track_ids = match_changed_files(
                    db, watch_config.config, file_ids=file_ids_to_match
                )
                progress.status(f"✓ {new_matches} new match(es)")
            else:
                progress.step(2, 4, "No files to match (all deleted)")

            # 3. Determine affected playlists and export
            affected_playlist_ids = []
            has_liked_tracks = False
            if matched_track_ids:
                provider = watch_config.config.get("provider", "spotify")
                affected_playlist_ids = db.get_playlists_containing_tracks(matched_track_ids, provider=provider)
                logger.debug(
                    f"Affected playlists: {len(affected_playlist_ids)} - {affected_playlist_ids[:5] if len(affected_playlist_ids) > 5 else affected_playlist_ids}"
                )

                # Check if any matched tracks are in Liked Songs
                liked_track_ids = db.get_liked_track_ids(matched_track_ids, provider=provider)
                has_liked_tracks = len(liked_track_ids) > 0
                if has_liked_tracks:
                    logger.debug(f"Matched tracks in Liked Songs: {len(liked_track_ids)}")

            if not watch_config.skip_export:
                if affected_playlist_ids or has_liked_tracks:
                    if affected_playlist_ids:
                        progress.step(
                            3,
                            4,
                            f"Exporting {len(affected_playlist_ids)} affected playlist(s){' + Liked Songs' if has_liked_tracks else ''}",
                        )
                        _export_playlists(db, watch_config.config, playlist_ids=affected_playlist_ids)
                    else:
                        # Only Liked Songs affected (no playlists)
                        progress.step(3, 4, "Exporting Liked Songs")
                        _export_playlists(db, watch_config.config)  # Full export to include Liked Songs
                elif matched_track_ids:
                    progress.step(3, 4, "Export skipped (no affected playlists or liked tracks)")
                    logger.info("No playlists or liked songs contain the matched tracks; skipping export")
                else:
                    progress.step(3, 4, "Export skipped (no matches)")
            else:
                progress.step(3, 4, "Export skipped (disabled)")

            # 4. Regenerate reports (incrementally for affected playlists, or full if only Liked Songs)
            if not watch_config.skip_report:
                if affected_playlist_ids or has_liked_tracks:
                    if affected_playlist_ids:
                        progress.step(4, 4, "Updating reports (incremental)")
                        _generate_reports(db, watch_config.config, affected_playlist_ids=affected_playlist_ids)
                    else:
                        # Only Liked Songs affected - need full report to update Liked Songs section
                        progress.step(4, 4, "Updating reports (Liked Songs)")
                        _generate_reports(db, watch_config.config)  # Full report generation
                elif matched_track_ids:
                    progress.step(4, 4, "Reports skipped (no affected playlists or liked tracks)")
                    logger.info("No playlists or liked songs contain the matched tracks; skipping report update")
                else:
                    progress.step(4, 4, "Reports skipped (no matches)")
            else:
                progress.step(4, 4, "Reports skipped (disabled)")

            # Set write signal for GUI auto-refresh
            import time

            db.set_meta("last_write_epoch", str(time.time()))
            db.set_meta("last_write_source", "watch:library")

        progress.complete("Incremental rebuild")
    except Exception as e:
        progress.error(f"Rebuild failed: {e}")
        logger.exception("Watch mode error details:")

    click.echo("")
    progress.status("Watching for changes...")

    # Return updated DB mtime to prevent false-positive database change detection
    return watch_config.db_path.stat().st_mtime if watch_config.db_path.exists() else 0.0


def _handle_database_changes(watch_config: WatchBuildConfig) -> float:
    """Handle database changes (e.g., after external 'pull' command).

    Performs incremental matching if we can determine which tracks changed,
    otherwise falls back to full re-match.

    Returns:
        Updated database mtime after all operations complete
    """
    click.echo("")
    progress.status("▶ Database changed (tracks/playlists updated)")

    try:
        with watch_config.get_db(watch_config.config) as db:
            # Check if we have metadata about which tracks changed
            changed_track_ids_str = db.get_meta("last_pull_changed_tracks")

            if changed_track_ids_str:
                # Parse comma-separated track IDs
                changed_track_ids = [tid.strip() for tid in changed_track_ids_str.split(",") if tid.strip()]

                if changed_track_ids:
                    from .match_service import match_changed_tracks

                    progress.step(1, 3, f"Incrementally matching {len(changed_track_ids)} changed track(s)")
                    new_matches = match_changed_tracks(db, watch_config.config, track_ids=changed_track_ids)
                    progress.status(f"✓ {new_matches} new match(es)")

                    # Clear the metadata after processing
                    db.set_meta("last_pull_changed_tracks", None)
                    db.commit()

                    # Store matched track IDs for incremental report generation
                    matched_track_ids = changed_track_ids if new_matches > 0 else []
                else:
                    progress.step(1, 3, "No track changes detected, skipping match")
                    matched_track_ids = []
            else:
                # Fallback: Full re-match since we don't know what changed
                progress.step(1, 3, "Re-matching all tracks (no change tracking available)")
                result = run_matching(
                    db, config=watch_config.config, verbose=False, top_unmatched_tracks=0, top_unmatched_albums=0
                )
                progress.status(f"✓ Matched {result.matched} tracks")
                matched_track_ids = []  # Full rebuild, so regenerate all reports

            # Determine affected playlists
            affected_playlist_ids = []
            has_liked_tracks = False
            if matched_track_ids:
                provider = watch_config.config.get("provider", "spotify")
                affected_playlist_ids = db.get_playlists_containing_tracks(matched_track_ids, provider=provider)
                logger.debug(
                    f"Affected playlists: {len(affected_playlist_ids)} - {affected_playlist_ids[:5] if len(affected_playlist_ids) > 5 else affected_playlist_ids}"
                )

                # Check if any matched tracks are in Liked Songs
                liked_track_ids = db.get_liked_track_ids(matched_track_ids, provider=provider)
                has_liked_tracks = len(liked_track_ids) > 0
                if has_liked_tracks:
                    logger.debug(f"Matched tracks in Liked Songs: {len(liked_track_ids)}")

            # Export
            if not watch_config.skip_export:
                if affected_playlist_ids or has_liked_tracks:
                    if affected_playlist_ids:
                        progress.step(
                            2,
                            3,
                            f"Exporting {len(affected_playlist_ids)} affected playlist(s){' + Liked Songs' if has_liked_tracks else ''}",
                        )
                        _export_playlists(db, watch_config.config, playlist_ids=affected_playlist_ids)
                    else:
                        # Only Liked Songs affected (no playlists)
                        progress.step(2, 3, "Exporting Liked Songs")
                        _export_playlists(db, watch_config.config)  # Full export to include Liked Songs
                elif matched_track_ids:
                    # Full rebuild case
                    progress.step(2, 3, "Exporting all playlists")
                    _export_playlists(db, watch_config.config)
                else:
                    progress.step(2, 3, "Export skipped (no changes)")
            else:
                progress.step(2, 3, "Export skipped (disabled)")

            # Reports (incremental if we know which tracks changed)
            if not watch_config.skip_report:
                if affected_playlist_ids or has_liked_tracks:
                    if affected_playlist_ids:
                        progress.step(3, 3, "Updating reports (incremental)")
                        _generate_reports(db, watch_config.config, affected_playlist_ids=affected_playlist_ids)
                    else:
                        # Only Liked Songs affected - need full report to update Liked Songs section
                        progress.step(3, 3, "Updating reports (Liked Songs)")
                        _generate_reports(db, watch_config.config)  # Full report generation
                elif matched_track_ids:
                    # Full rebuild case
                    progress.step(3, 3, "Regenerating all reports")
                    _generate_reports(db, watch_config.config)
                else:
                    progress.step(3, 3, "Reports skipped (no changes)")
            else:
                progress.step(3, 3, "Reports skipped (disabled)")

            # Set write signal for GUI auto-refresh
            import time

            db.set_meta("last_write_epoch", str(time.time()))
            db.set_meta("last_write_source", "watch:database")

        progress.complete("Database sync")
    except Exception as e:
        progress.error(f"Database sync failed: {e}")
        logger.exception("Database sync error details:")
        # Return current mtime even on error to prevent infinite re-trigger loops
        return watch_config.db_path.stat().st_mtime if watch_config.db_path.exists() else 0.0

    click.echo("")
    progress.status("Watching for changes...")

    # Return updated DB mtime to prevent false-positive database change detection
    return watch_config.db_path.stat().st_mtime if watch_config.db_path.exists() else 0.0


def _export_playlists(db: Database, config: Dict[str, Any], playlist_ids: List[str] | None = None) -> None:
    """Export playlists helper.

    Args:
        db: Database instance
        config: Full configuration dict
        playlist_ids: Optional list of specific playlist IDs to export (None = export all)
    """
    if playlist_ids is not None and len(playlist_ids) == 0:
        # Empty list means no playlists to export
        logger.info("Export skipped: no playlists affected")
        click.echo(click.style("  ✓ Export skipped (no affected playlists)", fg="yellow"))
        return

    organize_by_owner = config["export"].get("organize_by_owner", False)
    current_user_id = db.get_meta("current_user_id") if organize_by_owner else None
    result = export_playlists(
        db=db,
        export_config=config["export"],
        organize_by_owner=organize_by_owner,
        current_user_id=current_user_id,
        playlist_ids=playlist_ids,
    )

    if playlist_ids:
        click.echo(click.style(f"  ✓ Exported {result.playlist_count} affected playlist(s)", fg="green"))
    else:
        click.echo(click.style(f"  ✓ Exported {result.playlist_count} playlists", fg="green"))


def _generate_reports(db: Database, config: Dict[str, Any], affected_playlist_ids: List[str] | None = None) -> None:
    """Generate reports helper.

    Args:
        db: Database instance
        config: Full configuration dict
        affected_playlist_ids: Optional list of playlist IDs that changed.
            If provided, only regenerates detail pages for these playlists.
            If None, regenerates all reports.
    """
    if affected_playlist_ids is not None and len(affected_playlist_ids) == 0:
        # Empty list means no playlists to update
        logger.info("Report update skipped: no playlists affected")
        click.echo(click.style("  ✓ Reports skipped (no affected playlists)", fg="yellow"))
        return

    out_dir = Path(config["reports"]["directory"])
    write_match_reports(db, out_dir, affected_playlist_ids=affected_playlist_ids)
    write_index_page(out_dir, db)

    if affected_playlist_ids:
        click.echo(
            click.style(f"  ✓ Reports updated ({len(affected_playlist_ids)} playlist details) in {out_dir}", fg="green")
        )
    else:
        click.echo(click.style(f"  ✓ Reports updated in {out_dir}", fg="green"))


def run_watch_build(watch_config: WatchBuildConfig) -> None:
    """Run watch mode: monitor library files and database for changes.

    Args:
        watch_config: Watch build configuration
    """
    logger.info("")
    logger.info("Monitoring library files AND database for changes.")
    logger.info("• Library changes → incremental scan + match")
    logger.info("• Database changes (e.g. after 'pull') → incremental track match")
    logger.info(f"Debounce time: {watch_config.debounce_seconds}s")
    logger.info("Press Ctrl+C to stop.")
    logger.info("")
    logger.info("Watching for changes...")

    # Track database modification time
    last_db_mtime = watch_config.db_path.stat().st_mtime if watch_config.db_path.exists() else 0

    watcher = None
    try:
        # Create library file change handler
        def library_change_handler(changed_file_paths: list):
            nonlocal last_db_mtime  # Allow updating parent scope variable
            # Update mtime BEFORE operations to prevent race condition with DB monitoring loop
            # The monitoring loop runs every 2s and might detect changes mid-operation
            last_db_mtime = time.time() + 3600  # Temporarily set to future to prevent false triggers
            updated_mtime = _handle_library_changes(changed_file_paths, watch_config)
            last_db_mtime = updated_mtime  # Update to actual final mtime

        # Create and start library file watcher
        watcher = LibraryWatcher(
            config=watch_config.config,
            on_change_callback=library_change_handler,
            debounce_seconds=watch_config.debounce_seconds,
        )

        watcher.start()

        # Monitor loop: check for both library changes and database changes
        last_check = time.time()

        while True:
            time.sleep(1)

            # Periodically check if database was modified (e.g., by 'pull' command)
            current_time = time.time()
            if current_time - last_check >= watch_config.db_check_interval:
                last_check = current_time

                if watch_config.db_path.exists():
                    current_db_mtime = watch_config.db_path.stat().st_mtime

                    if current_db_mtime > last_db_mtime:
                        # Database changed! Someone ran 'pull' or modified tracks
                        # Update mtime BEFORE operations to prevent race condition
                        last_db_mtime = time.time() + 3600  # Temporarily set to future
                        updated_mtime = _handle_database_changes(watch_config)
                        last_db_mtime = updated_mtime  # Update to actual final mtime

    except KeyboardInterrupt:
        logger.info("")
        logger.info("⏹ Stopping watch mode...")
        if watcher:
            watcher.stop()
        logger.info("✓ Watch mode stopped")
    except Exception as e:
        logger.error(f"Watch mode error: {e}")
        if watcher:
            watcher.stop()
        raise
