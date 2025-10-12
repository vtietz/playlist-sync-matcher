"""Playlist export command."""

from __future__ import annotations
import click
import logging
from pathlib import Path

from .helpers import cli, get_db
from ..services.export_service import export_playlists

logger = logging.getLogger(__name__)


@cli.command()
@click.pass_context
def export(ctx: click.Context):
    """Export matched playlists to M3U files."""
    from ..utils.output import section_header, success, warning, info

    cfg = ctx.obj

    # Print styled header for user experience
    click.echo(section_header("Exporting playlists to M3U"))

    organize_by_owner = cfg['export'].get('organize_by_owner', False)
    library_paths = cfg.get('library', {}).get('paths', [])
    with get_db(cfg) as db:
        current_user_id = db.get_meta('current_user_id') if organize_by_owner else None
        result = export_playlists(
            db=db,
            export_config=cfg['export'],
            organize_by_owner=organize_by_owner,
            current_user_id=current_user_id,
            library_paths=library_paths
        )

    # Handle obsolete files (if detected)
    if result.obsolete_files:
        click.echo()
        click.echo(warning(f"Found {len(result.obsolete_files)} obsolete playlist(s):"))
        for obsolete_file in result.obsolete_files:
            click.echo(info(f"{Path(obsolete_file).name}"))

        click.echo()
        if click.confirm("Delete obsolete playlists?", default=False):
            deleted_count = 0
            for obsolete_file in result.obsolete_files:
                try:
                    Path(obsolete_file).unlink()
                    deleted_count += 1
                    logger.debug(f"Deleted obsolete: {obsolete_file}")
                except Exception as e:
                    logger.warning(f"Failed to delete {obsolete_file}: {e}")
            click.echo(success(f"Deleted {deleted_count} obsolete playlist(s)"))
        else:
            click.echo(info("Kept obsolete playlists"))

    # Service already logs the summary, no need to repeat here
    click.echo(success("Export complete"))


__all__ = ['export']
