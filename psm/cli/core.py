from __future__ import annotations
import click
import logging
from pathlib import Path
import json as _json
import time
from .helpers import cli, get_db, _redact_spotify_config, build_auth, get_provider_config
from ..reporting.generator import write_missing_tracks, write_album_completeness, write_analysis_quality_reports, write_match_reports, write_index_page
from ..services.pull_service import pull_data
from ..ingest.library import scan_library
from ..services.match_service import run_matching
from ..services.analysis_service import analyze_library_quality, print_quality_report
from ..services.export_service import export_playlists
from ..providers.base import available_provider_instances, get_provider_instance
from ..config import validate_single_provider

logger = logging.getLogger(__name__)


@cli.command()
@click.option('--match-reports/--no-match-reports', default=True, help='Generate match reports (matched/unmatched tracks/albums, playlist coverage)')
@click.option('--analysis-reports/--no-analysis-reports', default=True, help='Generate analysis reports (metadata quality)')
@click.option('--min-bitrate', type=int, help='Minimum acceptable bitrate in kbps for analysis report')
@click.pass_context
def report(ctx: click.Context, match_reports: bool, analysis_reports: bool, min_bitrate: int | None):
    """Generate all available reports from existing database.
    
    This command regenerates reports without re-running matching or analysis phases.
    Useful for:
    - Updating report formats after code changes
    - Generating reports with different settings
    - Creating reports after manual database changes
    
    Reports generated:
    - Match Reports: matched_tracks, unmatched_tracks, unmatched_albums, playlist_coverage
    - Analysis Reports: metadata_quality (if library has been scanned)
    - index.html: Navigation dashboard for all reports
    """
    from ..utils.output import (
        section_header, success, error, warning, info, 
        clickable_path, report_files, count_badge
    )
    
    cfg = ctx.obj
    out_dir = Path(cfg['reports']['directory'])
    
    with get_db(cfg) as db:
        reports_generated = []
        
        # Generate match reports
        if match_reports:
            click.echo(section_header("Generating match reports"))
            try:
                write_match_reports(db, out_dir)
                reports_generated.extend(['matched_tracks', 'unmatched_tracks', 'unmatched_albums', 'playlist_coverage'])
                
                # Show generated files
                click.echo(report_files(out_dir / 'matched_tracks.csv', out_dir / 'matched_tracks.html', 'Matched tracks'))
                click.echo(report_files(out_dir / 'unmatched_tracks.csv', out_dir / 'unmatched_tracks.html', 'Unmatched tracks'))
                click.echo(report_files(out_dir / 'unmatched_albums.csv', out_dir / 'unmatched_albums.html', 'Unmatched albums'))
                click.echo(report_files(out_dir / 'playlist_coverage.csv', out_dir / 'playlist_coverage.html', 'Playlist coverage'))
                click.echo(success("Match reports generated"))
            except Exception as e:
                logger.error(f"Failed to generate match reports: {e}")
                click.echo(error(f"Match reports failed: {e}"), err=True)
        
        # Generate analysis reports
        if analysis_reports:
            click.echo("")
            click.echo(section_header("Generating analysis reports"))
            try:
                # Check if library has been scanned
                file_count = db.conn.execute("SELECT COUNT(*) FROM library_files").fetchone()[0]
                if file_count == 0:
                    click.echo(warning("No library files found. Run 'scan' first to enable analysis reports."))
                else:
                    from ..services.analysis_service import analyze_library_quality
                    
                    if min_bitrate is None:
                        min_bitrate = cfg.get('library', {}).get('min_bitrate_kbps', 320)
                    min_bitrate = int(min_bitrate) if min_bitrate is not None else 320
                    
                    # Use large number for max_issues to get all issues for report
                    report_obj = analyze_library_quality(db, min_bitrate_kbps=min_bitrate, max_issues=999999, silent=True)
                    
                    if report_obj.issues:
                        write_analysis_quality_reports(report_obj, out_dir, min_bitrate_kbps=min_bitrate)
                        reports_generated.append('metadata_quality')
                        
                        # Show generated files
                        click.echo(report_files(out_dir / 'metadata_quality.csv', out_dir / 'metadata_quality.html', 'Metadata quality'))
                        click.echo(success(f"Analysis reports generated ({count_badge(len(report_obj.issues), 'issues', 'yellow')})"))
                    else:
                        click.echo(success("No quality issues found - no report needed"))
            except Exception as e:
                logger.error(f"Failed to generate analysis reports: {e}")
                click.echo(error(f"Analysis reports failed: {e}"), err=True)
        
        # Always generate index page if any reports were created
        if reports_generated:
            click.echo("")
            click.echo(section_header("Generating navigation dashboard"))
            write_index_page(out_dir, db)
            index_path = out_dir / 'index.html'
            click.echo(clickable_path(index_path, 'Index page'))
            click.echo(success("Navigation dashboard generated"))
        
        # Summary
        click.echo("")
        click.echo(success(f"Generated {count_badge(len(reports_generated), 'reports')} in {click.style(str(out_dir.resolve()), fg='cyan', underline=True)}"))
        if not reports_generated:
            click.echo(warning("No reports generated. Ensure database has data (run 'pull', 'scan', 'match' first)"))


@cli.command(name='report-albums')
@click.pass_context
def report_albums(ctx: click.Context):
    """[DEPRECATED] Generate album completeness report showing partially matched albums.
    
    This command is deprecated. Use 'report' command instead to regenerate all reports.
    """
    logger.warning("⚠️  'report-albums' command is deprecated - use 'report' instead")
    cfg = ctx.obj
    with get_db(cfg) as db:
        out_dir = Path(cfg['reports']['directory'])
        path = write_album_completeness(db, out_dir)
        click.echo(f"Album completeness report: {path}")




@cli.command(name='config')
@click.option('--section', '-s', help='Only show a specific top-level section (e.g. providers, export, database).')
@click.option('--redact', is_flag=True, help='Redact sensitive values like client_id.')
@click.pass_context
def show_config(ctx: click.Context, section: str | None, redact: bool):
    """Show current configuration settings."""
    cfg = ctx.obj
    data = cfg
    if section:
        section = section.lower()
        if section not in data:
            raise click.UsageError(f"Unknown section '{section}'. Available: {', '.join(sorted(data.keys()))}")
        data = {section: data[section]}
    out = data
    if redact:
        out = _redact_spotify_config(out)
    click.echo(_json.dumps(out, indent=2, sort_keys=True))


@cli.command(name='redirect-uri')
@click.pass_context
def redirect_uri(ctx: click.Context):
    """Show OAuth redirect URI for Spotify app configuration."""
    cfg = ctx.obj
    auth = build_auth(cfg)
    uri = auth.build_redirect_uri()
    click.echo(uri)
    provider_cfg = get_provider_config(cfg)
    click.echo("\nValidation checklist:")
    for line in [
        f"1. Spotify Dashboard has EXACT entry: {uri}",
        f"2. Scheme matches (expected {provider_cfg.get('redirect_scheme')})",
        f"3. Port matches (expected {provider_cfg.get('redirect_port')})",
        f"4. Path matches (expected {provider_cfg.get('redirect_path')})",
        "5. No trailing slash difference (unless you registered with one)",
        "6. Browser not caching old redirect (try private window)",
        "7. Client ID corresponds to the app whose dashboard you edited",
    ]:
        click.echo(f" - {line}")


@cli.command(name='token-info')
@click.pass_context
def token_info(ctx: click.Context):
    """Show OAuth token cache status and expiration info."""
    cfg = ctx.obj
    provider_cfg = get_provider_config(cfg)
    path = Path(provider_cfg['cache_file']).resolve()
    if not path.exists():
        click.echo(f"Token cache not found: {path}")
        return
    try:
        import json
        data = json.loads(path.read_text(encoding='utf-8'))
        exp = data.get('expires_at')
        if exp:
            remaining = int(exp - time.time())
            click.echo(f"Token cache: {path}\nExpires at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(exp))} (in {remaining}s)")
        else:
            click.echo(f"Token cache: {path}\n(No expires_at field)")
    except Exception as e:  # pragma: no cover
        click.echo(f"Failed to parse token cache {path}: {e}")


@cli.command()
@click.option('--force-auth', is_flag=True, help='Force full auth flow ignoring cached token')
@click.option('--force-refresh', is_flag=True, help='Force refresh all tracks even if playlists unchanged (populates new fields)')
@click.pass_context
def pull(ctx: click.Context, force_auth: bool, force_refresh: bool):
    """Pull playlists and liked tracks from streaming provider.
    
    Note: Currently only one provider can be configured at a time.
    Multi-provider support is planned for a future release.
    """
    cfg = ctx.obj
    
    # Validate single provider configuration
    try:
        provider = validate_single_provider(cfg)
    except ValueError as e:
        raise click.UsageError(str(e))
    
    provider_cfg = get_provider_config(cfg, provider)
    
    if provider == 'spotify':
        if not provider_cfg.get('client_id'):
            raise click.UsageError('providers.spotify.client_id not configured')
    else:
        raise click.UsageError(f"Provider '{provider}' not supported yet")
    
    with get_db(cfg) as db:
        result = pull_data(db=db, provider=provider, provider_config=provider_cfg, matching_config=cfg['matching'], force_auth=force_auth, force_refresh=force_refresh)
    click.echo(f"\n[summary] Provider={provider} | Playlists: {result.playlist_count} | Unique playlist tracks: {result.unique_playlist_tracks} | Liked tracks: {result.liked_tracks} | Total tracks: {result.total_tracks}")
    logger.debug(f"Completed in {result.duration_seconds:.2f}s")
    click.echo('Pull complete')


@cli.command()
@click.option('--force', is_flag=True, help='Force full auth ignoring cache')
@click.pass_context
def login(ctx: click.Context, force: bool):
    """Authenticate with streaming provider (Spotify OAuth).
    
    Note: Currently only one provider can be configured at a time.
    Multi-provider support is planned for a future release.
    """
    cfg = ctx.obj
    
    # Validate single provider configuration
    try:
        provider = validate_single_provider(cfg)
    except ValueError as e:
        raise click.UsageError(str(e))
    
    provider_cfg = get_provider_config(cfg)
    if not provider_cfg.get('client_id'):
        raise click.UsageError(f'providers.{provider}.client_id not configured')
    auth = build_auth(cfg)
    tok = auth.get_token(force=force)
    exp = tok.get('expires_at') if isinstance(tok, dict) else None
    if exp:
        click.echo(f"Token acquired; expires at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(exp))}")
    else:
        click.echo('Token acquired.')


@cli.command()
@click.option('--since', type=str, help='Only scan files modified since this time (e.g., "2 hours ago", "2025-10-08 10:00")')
@click.option('--quick', is_flag=True, help='Smart mode: only scan new/modified files (inferred from DB)')
@click.option('--paths', multiple=True, help='Override config: scan only these specific paths')
@click.option('--watch', is_flag=True, help='Watch library paths and continuously update DB on changes')
@click.option('--debounce', type=float, default=2.0, help='Seconds to wait after last change before processing (watch mode only)')
@click.pass_context
def scan(ctx: click.Context, since: str | None, quick: bool, paths: tuple, watch: bool, debounce: float):
    """Scan local music library and index track metadata.
    
    Modes:
    - Normal: Full scan of all library paths (default)
    - --since "TIME": Only files modified after specified time
    - --quick: Automatically detect and scan only changed files
    - --paths PATH...: Scan only specific directories or files
    - --watch: Monitor filesystem and update DB automatically
    
    Examples:
      psm scan                              # Full scan
      psm scan --since "2 hours ago"        # Only recently modified
      psm scan --quick                      # Smart incremental scan
      psm scan --paths ./newalbum/          # Scan specific directory
      psm scan --watch                      # Monitor and auto-update
      psm scan --watch --debounce 5         # Watch with 5s debounce
    """
    from ..ingest.library import scan_library_incremental, parse_time_string, scan_specific_files
    
    cfg = ctx.obj
    
    # Watch mode - continuous monitoring
    if watch:
        if since or quick or paths:
            raise click.UsageError("--watch cannot be combined with --since, --quick, or --paths")
        
        from ..services.watch_service import LibraryWatcher
        from ..utils.output import success, info, warning
        
        def handle_changes(changed_files: list):
            """Callback for filesystem changes."""
            click.echo(info(f"Detected {len(changed_files)} changed file(s)"))
            
            try:
                with get_db(cfg) as db:
                    result = scan_specific_files(db, cfg, changed_files)
                    import time
                    db.set_meta('last_scan_time', str(time.time()))
                    db.set_meta('library_last_modified', str(time.time()))
                
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
    
    if since and quick:
        raise click.UsageError("Cannot use both --since and --quick together")
    
    if since:
        try:
            changed_since = parse_time_string(since)
            from datetime import datetime
            click.echo(f"Scanning files modified since {datetime.fromtimestamp(changed_since).strftime('%Y-%m-%d %H:%M:%S')}")
        except ValueError as e:
            raise click.UsageError(str(e))
    
    if quick:
        # Get last scan time from database
        with get_db(cfg) as db:
            last_scan = db.get_meta('last_scan_time')
        if last_scan:
            changed_since = float(last_scan)
            from datetime import datetime
            click.echo(f"Quick mode: scanning files modified since last scan ({datetime.fromtimestamp(changed_since).strftime('%Y-%m-%d %H:%M:%S')})")
        else:
            click.echo("Quick mode: no previous scan found, performing full scan")
    
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
            db.set_meta('last_scan_time', str(time.time()))
            db.set_meta('library_last_modified', str(time.time()))
        
        # Print summary
        from ..utils.logging_helpers import format_summary
        summary = format_summary(
            new=result.inserted,
            updated=result.updated,
            unchanged=result.skipped,
            deleted=result.deleted,
            duration_seconds=result.duration_seconds,
            item_name="Library"
        )
        logger.info(summary)
        if result.errors:
            logger.debug(f"Errors: {result.errors}")
    else:
        # Full scan (existing behavior)
        with get_db(cfg) as db:
            scan_library(db, cfg)
            # Update last scan time
            import time
            db.set_meta('last_scan_time', str(time.time()))
            db.set_meta('library_last_modified', str(time.time()))
    
    click.echo('Scan complete')


@cli.command()
@click.option('--top-tracks', type=int, default=20, help='Number of top unmatched tracks to show')
@click.option('--top-albums', type=int, default=10, help='Number of top unmatched albums to show')
@click.pass_context
def match(ctx: click.Context, top_tracks: int, top_albums: int):
    """Match streaming tracks to local library files (scoring engine).
    
    Automatically generates detailed reports:
    - matched_tracks.csv / .html: All matched tracks with confidence scores
    - unmatched_tracks.csv / .html: All unmatched tracks
    - unmatched_albums.csv / .html: Unmatched albums grouped by popularity
    """
    cfg = ctx.obj
    # Use short-lived connection; avoid holding DB beyond required scope
    result = None
    with get_db(cfg) as db:
        result = run_matching(db, config=cfg, verbose=False, top_unmatched_tracks=top_tracks, top_unmatched_albums=top_albums)
        
        # Auto-generate match reports
        if result.matched > 0 or result.unmatched > 0:
            out_dir = Path(cfg['reports']['directory'])
            reports = write_match_reports(db, out_dir)
            write_index_page(out_dir, db)
            logger.info("")
            logger.info(f"✓ Generated match reports in: {out_dir}")
            logger.info(f"  Open index.html to navigate all reports")
    
    # At this point context manager closed the DB ensuring lock release
    if result is not None:
        click.echo(f'Matched {result.matched} tracks')


@cli.command()
@click.option('--min-bitrate', type=int, help='Minimum acceptable bitrate in kbps (overrides config)')
@click.option('--max-issues', type=int, default=50, help='Max number of detailed issues to show')
@click.option('--top-offenders', type=int, default=10, help='Number of top offenders to show per category')
@click.pass_context
def analyze(ctx: click.Context, min_bitrate: int | None, max_issues: int, top_offenders: int):
    """Analyze local library quality (missing tags, low bitrate).
    
    Automatically generates detailed reports:
    - metadata_quality.csv: All files with quality issues
    - metadata_quality.html: Sortable HTML table
    """
    cfg = ctx.obj
    if min_bitrate is None:
        min_bitrate = cfg.get('library', {}).get('min_bitrate_kbps', 320)
    min_bitrate = int(min_bitrate) if min_bitrate is not None else 320
    
    with get_db(cfg) as db:
        report = analyze_library_quality(db, min_bitrate_kbps=min_bitrate, max_issues=max_issues)
        print_quality_report(report, min_bitrate_kbps=min_bitrate, db=db, top_n=top_offenders)
        
        # Auto-generate CSV and HTML reports
        if report.issues:
            out_dir = Path(cfg['reports']['directory'])
            csv_path, html_path = write_analysis_quality_reports(report, out_dir, min_bitrate_kbps=min_bitrate)
            write_index_page(out_dir, db)
            logger.info("")
            logger.info(f"✓ Generated reports: {csv_path.name} | {html_path.name}")
            logger.info(f"  Location: {out_dir}")
            logger.info(f"  Open index.html to navigate all reports")
        else:
            logger.info("")
            logger.info("✓ No quality issues found - library metadata is excellent!")


@cli.command(name='match-diagnose')
@click.argument('query')
@click.option('--limit', type=int, default=10, help='Limit number of candidate files shown')
@click.pass_context
def match_diagnose(ctx: click.Context, query: str, limit: int):
    """Diagnose matching issues for a specific track."""
    from rapidfuzz import fuzz
    cfg = ctx.obj
    track_row = None
    rows = []
    with get_db(cfg) as db:
        cur = db.conn.execute("SELECT id,name,artist,album,normalized,year FROM tracks WHERE id=?", (query,))
        track_row = cur.fetchone()
        if not track_row:
            like = f"%{query}%"
            cur = db.conn.execute("SELECT id,name,artist,album,normalized,year FROM tracks WHERE name LIKE ? ORDER BY name LIMIT 1", (like,))
            track_row = cur.fetchone()
        if track_row:
            rows = db.conn.execute("SELECT id,path,title,artist,album,normalized,year FROM library_files").fetchall()
            match_row = db.conn.execute("SELECT file_id, score, method FROM matches WHERE track_id=?", (track_row['id'],)).fetchone()
        else:
            match_row = None
    if not track_row:
        click.echo(f"No track found matching '{query}'")
        return
    t_norm = track_row['normalized'] or ''
    click.echo(f"Track: {track_row['id']} | {track_row['artist']} - {track_row['name']} | album={track_row['album']} year={track_row['year']}\nNormalized: '{t_norm}'")
    scored = []
    for r in rows:
        f_norm = r['normalized'] or ''
        exact = 1.0 if f_norm == t_norm and t_norm else 0.0
        fuzzy_val = fuzz.token_set_ratio(t_norm, f_norm)/100.0 if t_norm else 0.0
        scored.append((exact, fuzzy_val, r))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    click.echo(f"Top candidates (limit={limit}):")
    for exact, fuzzy_val, r in scored[:limit]:
        click.echo(f"  file_id={r['id']} score_exact={exact:.3f} score_fuzzy={fuzzy_val:.3f} | title='{r['title']}' artist='{r['artist']}' album='{r['album']}' year={r['year']} path={r['path']} norm='{r['normalized']}'")
    if match_row:
        click.echo(f"Existing match: file_id={match_row['file_id']} score={match_row['score']:.3f} method={match_row['method']}")
    else:
        click.echo("Existing match: (none)")


@cli.command()
@click.pass_context
def export(ctx: click.Context):
    """Export matched playlists to M3U files."""
    cfg = ctx.obj
    organize_by_owner = cfg['export'].get('organize_by_owner', False)
    with get_db(cfg) as db:
        current_user_id = db.get_meta('current_user_id') if organize_by_owner else None
        result = export_playlists(db=db, export_config=cfg['export'], organize_by_owner=organize_by_owner, current_user_id=current_user_id)
    click.echo(f'Exported {result.playlist_count} playlists')
    click.echo('Export complete')


@cli.command(name='build')
@click.option('--no-report', is_flag=True, help='Skip report generation step')
@click.option('--no-export', is_flag=True, help='Skip playlist export step')
@click.option('--watch', is_flag=True, help='Watch library for changes and auto-rebuild')
@click.option('--debounce', type=float, default=2.0, help='Debounce time in seconds for watch mode')
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
        import time
        import os
        from ..services.watch_service import LibraryWatcher
        from ..ingest.library import scan_specific_files
        from ..services.match_service import match_changed_files, run_matching
        
        logger.info("")
        logger.info(click.style("=== Entering watch mode ===", fg='cyan', bold=True))
        logger.info("Monitoring library files AND database for changes.")
        logger.info("• Library changes → incremental scan + match")
        logger.info("• Database changes (e.g. after 'pull') → full re-match")
        logger.info(f"Debounce time: {debounce}s")
        logger.info("Press Ctrl+C to stop.")
        logger.info("")
        logger.info("Watching for changes...")
        
        # Track database modification time
        db_path = Path(cfg['database']['path'])
        last_db_mtime = db_path.stat().st_mtime if db_path.exists() else 0
        
        watcher = None
        try:
            def handle_library_changes(changed_file_paths: list):
                """Callback when library files change - incremental rebuild."""
                logger.info("")
                logger.info(click.style(f"▶ Library changed ({len(changed_file_paths)} files)", fg='yellow', bold=True))
                
                try:
                    with get_db(cfg) as db:
                        # 1. Scan changed files
                        logger.info("  [1/4] Scanning changed files...")
                        scan_result = scan_specific_files(db, cfg, changed_file_paths)
                        
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
                            new_matches = match_changed_files(db, cfg, file_ids=file_ids_to_match)
                            logger.info(f"    ✓ {new_matches} new match(es)")
                        else:
                            logger.info("  [2/4] No files to match (all deleted)")
                        
                        # 3. Export (only if matches changed)
                        if not no_export and file_ids_to_match:
                            logger.info("  [3/4] Exporting playlists...")
                            organize_by_owner = cfg['export'].get('organize_by_owner', False)
                            current_user_id = db.get_meta('current_user_id') if organize_by_owner else None
                            result = export_playlists(
                                db=db,
                                export_config=cfg['export'],
                                organize_by_owner=organize_by_owner,
                                current_user_id=current_user_id
                            )
                            logger.info(f"    ✓ Exported {result.playlist_count} playlists")
                        else:
                            logger.info("  [3/4] Export skipped")
                        
                        # 4. Regenerate reports (only if matches changed)
                        if not no_report and file_ids_to_match:
                            logger.info("  [4/4] Regenerating reports...")
                            out_dir = Path(cfg['reports']['directory'])
                            write_match_reports(db, out_dir)
                            write_index_page(out_dir, db)
                            logger.info(f"    ✓ Reports updated in {out_dir}")
                        else:
                            logger.info("  [4/4] Reports skipped")
                    
                    logger.info(click.style("✓ Incremental rebuild complete", fg='green'))
                except Exception as e:
                    logger.error(click.style(f"✗ Rebuild failed: {e}", fg='red'))
                    logger.exception("Watch mode error details:")
                
                logger.info("")
                logger.info("Watching for changes...")
            
            # Create and start library file watcher
            watcher = LibraryWatcher(
                config=cfg,
                on_change_callback=handle_library_changes,
                debounce_seconds=debounce
            )
            
            watcher.start()
            
            # Monitor loop: check for both library changes and database changes
            db_check_interval = 2  # Check database every 2 seconds
            last_check = time.time()
            
            while True:
                time.sleep(1)
                
                # Periodically check if database was modified (e.g., by 'pull' command)
                current_time = time.time()
                if current_time - last_check >= db_check_interval:
                    last_check = current_time
                    
                    if db_path.exists():
                        current_db_mtime = db_path.stat().st_mtime
                        
                        if current_db_mtime > last_db_mtime:
                            # Database changed! Someone ran 'pull' or modified tracks
                            last_db_mtime = current_db_mtime
                            
                            logger.info("")
                            logger.info(click.style("▶ Database changed (tracks/playlists updated)", fg='cyan', bold=True))
                            logger.info("  Detected external database modification (e.g., 'pull' command)")
                            
                            try:
                                with get_db(cfg) as db:
                                    # Full re-match since tracks may have changed
                                    logger.info("  [1/3] Re-matching all tracks...")
                                    result = run_matching(db, config=cfg, verbose=False, top_unmatched_tracks=0, top_unmatched_albums=0)
                                    logger.info(f"    ✓ Matched {result.matched} tracks")
                                    
                                    # Export
                                    if not no_export:
                                        logger.info("  [2/3] Exporting playlists...")
                                        organize_by_owner = cfg['export'].get('organize_by_owner', False)
                                        current_user_id = db.get_meta('current_user_id') if organize_by_owner else None
                                        export_result = export_playlists(
                                            db=db,
                                            export_config=cfg['export'],
                                            organize_by_owner=organize_by_owner,
                                            current_user_id=current_user_id
                                        )
                                        logger.info(f"    ✓ Exported {export_result.playlist_count} playlists")
                                    else:
                                        logger.info("  [2/3] Export skipped")
                                    
                                    # Reports
                                    if not no_report:
                                        logger.info("  [3/3] Regenerating reports...")
                                        out_dir = Path(cfg['reports']['directory'])
                                        write_match_reports(db, out_dir)
                                        write_index_page(out_dir, db)
                                        logger.info(f"    ✓ Reports updated in {out_dir}")
                                    else:
                                        logger.info("  [3/3] Reports skipped")
                                
                                logger.info(click.style("✓ Database sync complete", fg='green'))
                            except Exception as e:
                                logger.error(click.style(f"✗ Database sync failed: {e}", fg='red'))
                                logger.exception("Database sync error details:")
                            
                            logger.info("")
                            logger.info("Watching for changes...")
                
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
        
        # Exit after watch mode (don't run normal build)
        return
    
    # Normal build mode (non-watch): Run full pipeline
    ctx.invoke(pull)
    ctx.invoke(scan, since=None, quick=False, paths=(), watch=False, debounce=2.0)
    ctx.invoke(match)
    if not no_export:
        ctx.invoke(export)
    if not no_report:
        ctx.invoke(report)
    click.echo('Build complete')

__all__ = []

# Providers related commands
@cli.group(name='providers')
@click.pass_context
def providers_group(ctx: click.Context):  # pragma: no cover simple group
    """Provider related utilities."""
    pass


@providers_group.command(name='capabilities')
@click.pass_context
def providers_capabilities(ctx: click.Context):
    """List registered providers and their capabilities."""
    rows = []
    for p in available_provider_instances():
        provider = get_provider_instance(p)
        # Provider instances don't expose capabilities directly yet,
        # but we can create a client to check
        # For now, just show the provider name
        rows.append((p, "Registered"))
    
    if not rows:
        click.echo("No providers registered.")
        return
        
    width = max(len(r[0]) for r in rows)
    click.echo("Providers:")
    for name, desc in rows:
        click.echo(f"  {name.ljust(width)}  {desc}")


@cli.command()
@click.argument('track_id')
@click.option('--provider', default='spotify', help='Provider name (default: spotify)')
@click.option('--top-n', default=5, type=int, help='Number of closest files to show (default: 5)')
@click.pass_context
def diagnose(ctx: click.Context, track_id: str, provider: str, top_n: int):
    """Diagnose why a specific track isn't matching.
    
    This command helps troubleshoot unmatched tracks by showing:
    - Track metadata from the provider
    - Normalized search string used for matching
    - Closest matching files in your library with scores
    - Recommendations for fixing the issue
    
    To find the track ID, check the unmatched_tracks report (CSV or HTML).
    The track ID is shown in the first column.
    
    Example:
        psm diagnose 3n3Ppam7vgaVa1iaRUc9Lp
        psm diagnose --provider spotify --top-n 10 3n3Ppam7vgaVa1iaRUc9Lp
    """
    from ..services.diagnostic_service import diagnose_track, format_diagnostic_output
    from ..utils.output import section_header
    
    cfg = ctx.obj
    
    click.echo(section_header(f"Diagnosing Track: {track_id}"))
    click.echo("")
    
    with get_db(cfg) as db:
        result = diagnose_track(db, track_id, provider=provider, top_n=top_n)
        output = format_diagnostic_output(result)
        click.echo(output)
