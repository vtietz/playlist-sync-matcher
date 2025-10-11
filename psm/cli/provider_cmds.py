"""Provider authentication and management commands."""

from __future__ import annotations
import click
import time
import logging

from .helpers import cli, get_db, build_auth, get_provider_config
from ..services.pull_service import pull_data
from ..providers import available_provider_instances, get_provider_instance

logger = logging.getLogger(__name__)


def validate_single_provider(cfg: dict) -> str:
    """Validate that exactly one provider is configured and return its name.
    
    Raises:
        ValueError: If no providers or multiple providers are configured
    """
    enabled = []
    provider_section = cfg.get('providers', {})
    for name in ['spotify']:  # Future: add more providers
        if provider_section.get(name, {}).get('client_id'):
            enabled.append(name)
    
    if len(enabled) == 0:
        raise ValueError("No providers configured. Set providers.<name>.client_id in config.")
    if len(enabled) > 1:
        raise ValueError(f"Multiple providers configured: {', '.join(enabled)}. Only one provider supported per run.")
    
    return enabled[0]


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
        
        # Store changed track IDs in metadata for incremental matching in watch mode
        if result.changed_track_ids:
            changed_ids_str = ','.join(result.changed_track_ids)
            db.set_meta('last_pull_changed_tracks', changed_ids_str)
            db.commit()
            click.echo(f"  → {len(result.changed_track_ids)} track(s) added/updated")
        
        # Set write signal for GUI auto-refresh
        import time
        db.set_meta('last_write_epoch', str(time.time()))
        db.set_meta('last_write_source', 'pull')
    
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


__all__ = ['pull', 'login', 'providers_group', 'providers_capabilities']
