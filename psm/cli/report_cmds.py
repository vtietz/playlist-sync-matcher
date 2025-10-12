"""Report generation commands."""

from __future__ import annotations
import click
import logging
from pathlib import Path

from .helpers import cli, get_db
from ..reporting.generator import write_analysis_quality_reports, write_match_reports, write_index_page

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
        section_header, success, error, warning, clickable_path,
        report_files, count_badge
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


__all__ = ['report']
