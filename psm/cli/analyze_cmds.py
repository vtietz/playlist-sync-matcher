"""Library analysis command."""

from __future__ import annotations
import click
import logging
from pathlib import Path

from .helpers import cli, get_db
from ..services.analysis_service import analyze_library_quality, print_quality_report
from ..reporting.generator import write_analysis_quality_reports, write_index_page

logger = logging.getLogger(__name__)


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


__all__ = ['analyze']
