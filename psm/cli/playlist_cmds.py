from __future__ import annotations
import click
import logging
from pathlib import Path
from .helpers import get_db, cli, get_token, get_provider_config
from ..services.playlist_service import (
    pull_single_playlist,
    match_single_playlist,
    export_single_playlist,
    build_single_playlist,
)
from ..services.push_service import push_playlist

logger = logging.getLogger(__name__)


@cli.group(name='playlist')
@click.pass_context
def playlist_group(ctx: click.Context):  # pragma: no cover - simple container
    """Single playlist operations (pull, match, export, build, push)."""
    pass


@playlist_group.command(name='pull')
@click.argument('playlist_id')
@click.option('--force-auth', is_flag=True)
@click.pass_context
def playlist_pull(ctx: click.Context, playlist_id: str, force_auth: bool):
    """Pull and ingest a single playlist by ID."""
    cfg = ctx.obj
    provider_cfg = get_provider_config(cfg)
    if not provider_cfg.get('client_id'):
        raise click.UsageError('providers.spotify.client_id not configured')
    with get_db(cfg) as db:
        result = pull_single_playlist(db=db, playlist_id=playlist_id, spotify_config=provider_cfg, matching_config=cfg['matching'], force_auth=force_auth)
        click.echo(f"Pulled playlist '{result.playlist_name}' ({result.playlist_id})")
        click.echo(f"Tracks: {result.tracks_processed}")
        logger.debug(f"Duration: {result.duration_seconds:.2f}s")


@playlist_group.command(name='match')
@click.argument('playlist_id')
@click.pass_context
def playlist_match(ctx: click.Context, playlist_id: str):
    """Match tracks from a single playlist to local files."""
    cfg = ctx.obj
    with get_db(cfg) as db:
        result = match_single_playlist(db=db, playlist_id=playlist_id, config=cfg)
        click.echo(f"Matched playlist '{result.playlist_name}' ({result.playlist_id})")
        click.echo(f"Matched: {result.tracks_matched}/{result.tracks_processed} tracks")
        logger.debug(f"Duration: {result.duration_seconds:.2f}s")


@playlist_group.command(name='export')
@click.argument('playlist_id')
@click.pass_context
def playlist_export(ctx: click.Context, playlist_id: str):
    """Export a single playlist to M3U file."""
    cfg = ctx.obj
    provider = cfg.get('provider', 'spotify')
    organize_by_owner = cfg['export'].get('organize_by_owner', False)
    library_paths = cfg.get('library', {}).get('paths', [])
    with get_db(cfg) as db:
        current_user_id = db.get_meta('current_user_id') if organize_by_owner else None
        result = export_single_playlist(
            db=db, 
            playlist_id=playlist_id, 
            export_config=cfg['export'], 
            organize_by_owner=organize_by_owner, 
            current_user_id=current_user_id, 
            library_paths=library_paths,
            provider=provider
        )
    click.echo(f"Exported playlist '{result.playlist_name}' ({result.playlist_id})")
    click.echo(f"File: {result.exported_file}")
    logger.debug(f"Duration: {result.duration_seconds:.2f}s")


@playlist_group.command(name='build')
@click.argument('playlist_id')
@click.option('--force-auth', is_flag=True)
@click.pass_context
def playlist_build(ctx: click.Context, playlist_id: str, force_auth: bool):
    """Pull, match, and export a single playlist (complete pipeline)."""
    cfg = ctx.obj
    provider_cfg = get_provider_config(cfg)
    if not provider_cfg.get('client_id'):
        raise click.UsageError('providers.spotify.client_id not configured')
    with get_db(cfg) as db:
        result = build_single_playlist(db=db, playlist_id=playlist_id, spotify_config=provider_cfg, config=cfg, force_auth=force_auth)
    click.echo(f"Built playlist '{result.playlist_name}' ({result.playlist_id})")
    click.echo(f"Tracks processed: {result.tracks_processed}")
    click.echo(f"Tracks matched: {result.tracks_matched}")
    click.echo(f"Exported to: {result.exported_file}")
    logger.debug(f"Total duration: {result.duration_seconds:.2f}s")


@playlist_group.command(name='push')
@click.argument('playlist_id')
@click.option('--file', 'file_path', type=click.Path(exists=True, dir_okay=False, path_type=Path), required=False, help='Exported M3U file (file mode). Omit for DB mode.')
@click.option('--apply', is_flag=True, help='Apply changes (otherwise preview only)')
@click.pass_context
def playlist_push(ctx: click.Context, playlist_id: str, file_path: Path | None, apply: bool):
    """Push local changes to update a remote playlist (Spotify only)."""
    cfg = ctx.obj
    provider = cfg.get('provider', 'spotify')
    
    # For now, only Spotify is supported for push
    if provider != 'spotify':
        raise click.UsageError(f"Push is currently only supported for Spotify, not '{provider}'")

    provider_cfg = get_provider_config(cfg, provider)
    if not provider_cfg.get('client_id'):
        raise click.UsageError('providers.spotify.client_id not configured')
    
    token = get_token(cfg)
    
    # Use SpotifyAPIClient directly
    from ..providers.spotify import SpotifyAPIClient
    client = SpotifyAPIClient(token)

    with get_db(cfg) as db:
        preview = push_playlist(
            db=db,
            playlist_id=playlist_id,
            client=client,
            m3u_path=file_path,
            apply=apply,
        )
    click.echo(f"Playlist: {preview.playlist_name or playlist_id}")
    click.echo(f"Current tracks: {preview.current_count} | New tracks: {preview.new_count}")
    click.echo(f"Changes -> positional:{preview.positional_changes} added:{preview.added} removed:{preview.removed}")
    if preview.unmatched_file_paths:
        click.echo(f"Unresolved file paths (skipped): {preview.unmatched_file_paths}")
    click.echo(f"Changed: {'yes' if preview.changed else 'no'} | Applied: {'yes' if preview.applied else 'no'}")

__all__ = ["playlist_group"]
