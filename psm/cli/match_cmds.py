"""Matching engine command."""

from __future__ import annotations
import click
import logging
from pathlib import Path

from .helpers import cli, get_db
from ..services.match_service import run_matching
from ..reporting.generator import write_match_reports, write_index_page

logger = logging.getLogger(__name__)


@cli.command()
@click.option('--top-tracks', type=int, default=20, help='Number of top unmatched tracks to show')
@click.option('--top-albums', type=int, default=10, help='Number of top unmatched albums to show')
@click.option('--full', is_flag=True, help='Force full re-match of all tracks (default: skip already-matched)')
@click.option('--track-id', type=str, help='Match only a specific track by ID')
@click.pass_context
def match(ctx: click.Context, top_tracks: int, top_albums: int, full: bool, track_id: str | None):
    """Match streaming tracks to local library files (scoring engine).
    
    Default mode: Smart incremental matching (skips already-matched tracks)
    Use --full to force complete re-match of all tracks
    Use --track-id <id> to match only a specific track
    
    Automatically generates detailed reports:
    - matched_tracks.csv / .html: All matched tracks with confidence scores
    - unmatched_tracks.csv / .html: All unmatched tracks
    - unmatched_albums.csv / .html: Unmatched albums grouped by popularity
    """
    cfg = ctx.obj
    
    # Handle single track matching
    if track_id:
        from ..services.match_service import match_changed_tracks
        
        with get_db(cfg) as db:
            # Get track info for logging
            track = db.get_track_by_id(track_id)
            
            if track:
                click.echo(click.style(
                    f"=== Matching single track: {track_id} ===",
                    fg='cyan', bold=True
                ))
                click.echo(f"Track: {track.name}")
                click.echo(f"Artist: {track.artist}")
            else:
                click.echo(click.style(
                    f"=== Matching single track: {track_id} ===",
                    fg='cyan', bold=True
                ))
                click.echo(click.style("⚠ Track not found in database", fg='yellow'))
                return
            
            matched_count = match_changed_tracks(db, cfg, track_ids=[track_id])
            
            if matched_count > 0:
                click.echo(f'✓ Matched track {track_id}')
            else:
                click.echo(f'⚠ No match found for track')
        
        return
    
    # Print styled header for user experience
    if full:
        click.echo(click.style("=== Matching tracks to library files (full re-match) ===", fg='cyan', bold=True))
    else:
        click.echo(click.style("=== Matching tracks to library files ===", fg='cyan', bold=True))
    
    # Use short-lived connection; avoid holding DB beyond required scope
    result = None
    with get_db(cfg) as db:
        result = run_matching(db, config=cfg, verbose=False, top_unmatched_tracks=top_tracks, top_unmatched_albums=top_albums, force_full=full)
        
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


__all__ = ['match']
