from __future__ import annotations
import click
from .helpers import cli, get_db


@cli.group(name='playlists')
@click.pass_context
def playlists_group(ctx: click.Context):
    """List and manage playlists."""


@playlists_group.command(name='list')
@click.option('--show-urls', is_flag=True, help='Show provider URLs for each playlist')
@click.pass_context
def playlists_list(ctx: click.Context, show_urls: bool):
    cfg = ctx.obj
    with get_db(cfg) as db:
        playlists = db.get_all_playlists()
        if not playlists:
            click.echo("No playlists found. Run 'spx pull' first.")
            return
        click.echo(f"{'ID':<24} {'Name':<40} {'Owner':<20} {'Tracks':>7}")
        click.echo("-" * 95)
        for pl in playlists:
            pl_id = pl['id']
            name = pl['name'][:40]
            owner = (pl['owner_name'] or pl['owner_id'] or 'Unknown')[:20]
            track_count = pl['track_count']
            click.echo(f"{pl_id:<24} {name:<40} {owner:<20} {track_count:>7}")
            if show_urls:
                click.echo(f"  → https://open.spotify.com/playlist/{pl_id}")
        click.echo(f"\nTotal: {len(playlists)} playlists")

__all__ = ["playlists_group"]
