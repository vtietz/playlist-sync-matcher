"""Watch build service: Orchestrate incremental rebuild on changes.

This service handles watch mode for the build command, monitoring both
library file changes and database changes, then triggering appropriate
incremental rebuilds.
"""

from __future__ import annotations
import time
import logging
from pathlib import Path
from typing import Dict, Any, Callable

import click

from ..db import Database
from ..ingest.library import scan_specific_files
from ..services.match_service import match_changed_files, run_matching
from ..services.export_service import export_playlists
from ..reporting.generator import write_match_reports, write_index_page
from ..services.watch_service import LibraryWatcher

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
        db_check_interval: float = 2.0
    ):
        self.config = config
        self.get_db = get_db_func
        self.skip_export = skip_export
        self.skip_report = skip_report
        self.debounce_seconds = debounce_seconds
        self.db_check_interval = db_check_interval
        self.db_path = Path(config['database']['path'])


def _handle_library_changes(
    changed_file_paths: list,
    watch_config: WatchBuildConfig
) -> None:
    """Handle library file changes with incremental scan and match."""
    logger.info("")
    logger.info(click.style(f"▶ Library changed ({len(changed_file_paths)} files)", fg='yellow', bold=True))
    
    try:
        with watch_config.get_db(watch_config.config) as db:
            # 1. Scan changed files
            logger.info("  [1/4] Scanning changed files...")
            scan_result = scan_specific_files(db, watch_config.config, changed_file_paths)
            
            # Track which file IDs were affected
            file_ids_to_match = []
            
            # Get file IDs for paths that were scanned
            for path in changed_file_paths:
                file_row = db.conn.execute(
                    "SELECT id FROM library_files WHERE path = ?",
                    (str(path),)
                ).fetchone()
                if file_row:
                    file_ids_to_match.append(file_row['id'])
            
            logger.info(f"    ✓ {scan_result.inserted} new, {scan_result.updated} updated, {scan_result.deleted} deleted")
            
            # 2. Incrementally match only changed files
            if file_ids_to_match:
                logger.info(f"  [2/4] Matching {len(file_ids_to_match)} changed file(s)...")
                new_matches = match_changed_files(db, watch_config.config, file_ids=file_ids_to_match)
                logger.info(f"    ✓ {new_matches} new match(es)")
            else:
                logger.info("  [2/4] No files to match (all deleted)")
            
            # 3. Export (only if matches changed)
            if not watch_config.skip_export and file_ids_to_match:
                logger.info("  [3/4] Exporting playlists...")
                _export_playlists(db, watch_config.config)
            else:
                logger.info("  [3/4] Export skipped")
            
            # 4. Regenerate reports (only if matches changed)
            if not watch_config.skip_report and file_ids_to_match:
                logger.info("  [4/4] Regenerating reports...")
                _generate_reports(db, watch_config.config)
            else:
                logger.info("  [4/4] Reports skipped")
        
        logger.info(click.style("✓ Incremental rebuild complete", fg='green'))
    except Exception as e:
        logger.error(click.style(f"✗ Rebuild failed: {e}", fg='red'))
        logger.exception("Watch mode error details:")
    
    logger.info("")
    logger.info("Watching for changes...")


def _handle_database_changes(watch_config: WatchBuildConfig) -> None:
    """Handle database changes (e.g., after external 'pull' command).
    
    Performs incremental matching if we can determine which tracks changed,
    otherwise falls back to full re-match.
    """
    logger.info("")
    logger.info(click.style("▶ Database changed (tracks/playlists updated)", fg='cyan', bold=True))
    logger.info("  Detected external database modification (e.g., 'pull' command)")
    
    try:
        with watch_config.get_db(watch_config.config) as db:
            # Check if we have metadata about which tracks changed
            changed_track_ids_str = db.get_meta('last_pull_changed_tracks')
            
            if changed_track_ids_str:
                # Parse comma-separated track IDs
                changed_track_ids = [tid.strip() for tid in changed_track_ids_str.split(',') if tid.strip()]
                
                if changed_track_ids:
                    from .match_service import match_changed_tracks
                    
                    logger.info(f"  [1/3] Incrementally matching {len(changed_track_ids)} changed track(s)...")
                    new_matches = match_changed_tracks(db, watch_config.config, track_ids=changed_track_ids)
                    logger.info(f"    ✓ {new_matches} new match(es)")
                    
                    # Clear the metadata after processing
                    db.set_meta('last_pull_changed_tracks', None)
                    db.commit()
                else:
                    logger.info("  [1/3] No track changes detected, skipping match")
            else:
                # Fallback: Full re-match since we don't know what changed
                logger.info("  [1/3] Re-matching all tracks (no change tracking available)...")
                result = run_matching(db, config=watch_config.config, verbose=False, top_unmatched_tracks=0, top_unmatched_albums=0)
                logger.info(f"    ✓ Matched {result.matched} tracks")
            
            # Export
            if not watch_config.skip_export:
                logger.info("  [2/3] Exporting playlists...")
                _export_playlists(db, watch_config.config)
            else:
                logger.info("  [2/3] Export skipped")
            
            # Reports
            if not watch_config.skip_report:
                logger.info("  [3/3] Regenerating reports...")
                _generate_reports(db, watch_config.config)
            else:
                logger.info("  [3/3] Reports skipped")
        
        logger.info(click.style("✓ Database sync complete", fg='green'))
    except Exception as e:
        logger.error(click.style(f"✗ Database sync failed: {e}", fg='red'))
        logger.exception("Database sync error details:")
    
    logger.info("")
    logger.info("Watching for changes...")


def _export_playlists(db: Database, config: Dict[str, Any]) -> None:
    """Export playlists helper."""
    organize_by_owner = config['export'].get('organize_by_owner', False)
    current_user_id = db.get_meta('current_user_id') if organize_by_owner else None
    result = export_playlists(
        db=db,
        export_config=config['export'],
        organize_by_owner=organize_by_owner,
        current_user_id=current_user_id
    )
    logger.info(f"    ✓ Exported {result.playlist_count} playlists")


def _generate_reports(db: Database, config: Dict[str, Any]) -> None:
    """Generate reports helper."""
    out_dir = Path(config['reports']['directory'])
    write_match_reports(db, out_dir)
    write_index_page(out_dir, db)
    logger.info(f"    ✓ Reports updated in {out_dir}")


def run_watch_build(watch_config: WatchBuildConfig) -> None:
    """Run watch mode: monitor library files and database for changes.
    
    Args:
        watch_config: Watch build configuration
    """
    logger.info("")
    logger.info(click.style("=== Entering watch mode ===", fg='cyan', bold=True))
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
            _handle_library_changes(changed_file_paths, watch_config)
        
        # Create and start library file watcher
        watcher = LibraryWatcher(
            config=watch_config.config,
            on_change_callback=library_change_handler,
            debounce_seconds=watch_config.debounce_seconds
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
                        last_db_mtime = current_db_mtime
                        _handle_database_changes(watch_config)
        
    except KeyboardInterrupt:
        logger.info("")
        logger.info(click.style("⏹ Stopping watch mode...", fg='yellow'))
        if watcher:
            watcher.stop()
        logger.info(click.style("✓ Watch mode stopped", fg='green'))
    except Exception as e:
        logger.error(f"Watch mode error: {e}")
        if watcher:
            watcher.stop()
        raise
