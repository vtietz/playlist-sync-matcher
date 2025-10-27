"""Track matching diagnostic command."""

from __future__ import annotations
import click
import logging

from .helpers import cli, get_db
from ..services.diagnostic_service import diagnose_track, format_diagnostic_output
from ..utils.output import section_header

logger = logging.getLogger(__name__)


@cli.command()
@click.argument("track_id")
@click.option("--provider", default="spotify", help="Provider name (default: spotify)")
@click.option("--top-n", default=5, type=int, help="Number of closest files to show (default: 5)")
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
    cfg = ctx.obj

    click.echo(section_header(f"Diagnosing Track: {track_id}"))
    click.echo("")

    with get_db(cfg) as db:
        result = diagnose_track(db, track_id, provider=provider, top_n=top_n)
        output = format_diagnostic_output(result)
        click.echo(output)


__all__ = ["diagnose"]
