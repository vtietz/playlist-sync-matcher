from __future__ import annotations
import click
from pathlib import Path
from .helpers import get_db, cli, get_token
from ..services.playlist_service import (
    pull_single_playlist,
    match_single_playlist,
    export_single_playlist,
    sync_single_playlist,
)
from ..services.push_service import push_playlist
from ..providers.base import get as get_provider, available_providers


@cli.group(name='playlist')
@click.pass_context
def playlist_group(ctx: click.Context):  # pragma: no cover - simple container
    pass


@playlist_group.command(name='pull')
@click.argument('playlist_id')
@click.option('--force-auth', is_flag=True)
@click.option('--verbose', '-v', is_flag=True)
@click.pass_context
def playlist_pull(ctx: click.Context, playlist_id: str, force_auth: bool, verbose: bool):
    cfg = ctx.obj
    if not cfg['spotify']['client_id']:
        raise click.UsageError('spotify.client_id not configured')
    with get_db(cfg) as db:
        result = pull_single_playlist(db=db, playlist_id=playlist_id, spotify_config=cfg['spotify'], matching_config=cfg['matching'], force_auth=force_auth, verbose=verbose)
        click.echo(f"Pulled playlist '{result.playlist_name}' ({result.playlist_id})")
        click.echo(f"Tracks: {result.tracks_processed}")
        if verbose:
            click.echo(f"Duration: {result.duration_seconds:.2f}s")


@playlist_group.command(name='match')
@click.argument('playlist_id')
@click.option('--verbose', '-v', is_flag=True)
@click.pass_context
def playlist_match(ctx: click.Context, playlist_id: str, verbose: bool):
    cfg = ctx.obj
    with get_db(cfg) as db:
        result = match_single_playlist(db=db, playlist_id=playlist_id, config=cfg, verbose=verbose)
        click.echo(f"Matched playlist '{result.playlist_name}' ({result.playlist_id})")
        click.echo(f"Matched: {result.tracks_matched}/{result.tracks_processed} tracks")
        if verbose:
            click.echo(f"Duration: {result.duration_seconds:.2f}s")


@playlist_group.command(name='export')
@click.argument('playlist_id')
@click.option('--verbose', '-v', is_flag=True)
@click.pass_context
def playlist_export(ctx: click.Context, playlist_id: str, verbose: bool):
    cfg = ctx.obj
    organize_by_owner = cfg['export'].get('organize_by_owner', False)
    with get_db(cfg) as db:
        current_user_id = db.get_meta('current_user_id') if organize_by_owner else None
        result = export_single_playlist(db=db, playlist_id=playlist_id, export_config=cfg['export'], organize_by_owner=organize_by_owner, current_user_id=current_user_id, verbose=verbose)
    click.echo(f"Exported playlist '{result.playlist_name}' ({result.playlist_id})")
    click.echo(f"File: {result.exported_file}")
    if verbose:
        click.echo(f"Duration: {result.duration_seconds:.2f}s")


@playlist_group.command(name='sync')
@click.argument('playlist_id')
@click.option('--force-auth', is_flag=True)
@click.option('--verbose', '-v', is_flag=True)
@click.pass_context
def playlist_sync(ctx: click.Context, playlist_id: str, force_auth: bool, verbose: bool):
    cfg = ctx.obj
    if not cfg['spotify']['client_id']:
        raise click.UsageError('spotify.client_id not configured')
    with get_db(cfg) as db:
        result = sync_single_playlist(db=db, playlist_id=playlist_id, spotify_config=cfg['spotify'], config=cfg, force_auth=force_auth, verbose=verbose)
    click.echo(f"Synced playlist '{result.playlist_name}' ({result.playlist_id})")
    click.echo(f"Tracks processed: {result.tracks_processed}")
    click.echo(f"Tracks matched: {result.tracks_matched}")
    click.echo(f"Exported to: {result.exported_file}")
    if verbose:
        click.echo(f"Total duration: {result.duration_seconds:.2f}s")


@playlist_group.command(name='push')
@click.argument('playlist_id')
@click.option('--file', 'file_path', type=click.Path(exists=True, dir_okay=False, path_type=Path), required=False, help='Exported M3U file (file mode). Omit for DB mode.')
@click.option('--apply', is_flag=True, help='Apply changes (otherwise preview only)')
@click.option('--verbose', '-v', is_flag=True, help='Verbose logging (adds debug details)')
@click.pass_context
def playlist_push(ctx: click.Context, playlist_id: str, file_path: Path | None, apply: bool, verbose: bool):
    """Preview (and optionally apply) a remote playlist full replace."""
    cfg = ctx.obj
    provider = cfg.get('provider', 'spotify')
    try:
        provider_cls = get_provider(provider)
    except KeyError:
        raise click.UsageError(f"Unknown provider '{provider}'. Available: {', '.join(available_providers())}")
    caps = getattr(provider_cls, 'capabilities', None)
    if not caps or not getattr(caps, 'replace_playlist', False):
        raise click.UsageError(f"Provider '{provider}' does not support push (replace_playlist capability missing)")

    if provider == 'spotify':
        if not cfg['spotify']['client_id']:
            raise click.UsageError('spotify.client_id not configured')
        token = get_token(cfg)
        try:
            client = provider_cls(token)  # type: ignore[call-arg]
        except TypeError:
            client = provider_cls()  # type: ignore[call-arg]
    else:
        try:
            client = provider_cls()  # type: ignore[call-arg]
        except TypeError as e:
            raise click.UsageError(f"Provider '{provider}' requires auth not yet implemented: {e}")

    with get_db(cfg) as db:
        preview = push_playlist(
            db=db,
            playlist_id=playlist_id,
            client=client,
            m3u_path=file_path,
            apply=apply,
            verbose=verbose,
        )
    click.echo(f"Playlist: {preview.playlist_name or playlist_id}")
    click.echo(f"Current tracks: {preview.current_count} | New tracks: {preview.new_count}")
    click.echo(f"Changes -> positional:{preview.positional_changes} added:{preview.added} removed:{preview.removed}")
    if preview.unmatched_file_paths:
        click.echo(f"Unresolved file paths (skipped): {preview.unmatched_file_paths}")
    click.echo(f"Changed: {'yes' if preview.changed else 'no'} | Applied: {'yes' if preview.applied else 'no'}")

__all__ = ["playlist_group"]
