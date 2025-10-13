from __future__ import annotations
import sys
import os
import click
from pathlib import Path
import copy
from ..config import load_typed_config
from ..version import __version__
from ..db import Database
from ..providers import get_provider_instance

# Import shared utilities (also used by GUI)
from .shared import get_db


def check_first_run() -> bool:
    """Check for first run and handle .env creation.
    
    Returns:
        True if app should continue, False if should exit
    """
    # Skip check if running from GUI (GUI handles its own first-run experience)
    if os.environ.get('PSM_SKIP_FIRST_RUN_CHECK'):
        return True
    
    try:
        from ..utils.first_run import check_first_run_cli
        return check_first_run_cli()
    except Exception as e:
        # If first-run check fails, log warning and continue
        # (don't block users with working env vars)
        import logging
        logging.warning(f"First-run check failed: {e}")
        return True


def get_provider_config(cfg: dict, provider_name: str | None = None) -> dict:
    """Get provider configuration from config dict.

    Args:
        cfg: Full configuration dict
        provider_name: Provider name (defaults to cfg['provider'])

    Returns:
        Provider configuration dict
    """
    if provider_name is None:
        provider_name = cfg.get('provider', 'spotify')

    providers = cfg.get('providers', {})
    return providers.get(provider_name, {})


def _redact_spotify_config(cfg: dict) -> dict:
    result = copy.deepcopy(cfg)
    providers = result.get('providers', {})
    if 'spotify' in providers and isinstance(providers['spotify'], dict):
        if providers['spotify'].get('client_id'):
            providers['spotify']['client_id'] = '*** redacted ***'
    return result


@click.group()
@click.version_option(version=__version__, prog_name="playlist-sync-matcher")
@click.option('--config-file', type=click.Path(exists=False), default=None, help='Deprecated: config file parameter (ignored; use .env)')
@click.option('--progress/--no-progress', default=None, help='Enable/disable progress logging (overrides config)')
@click.option('--progress-interval', type=int, default=None, help='Log progress every N items (overrides config)')
@click.pass_context
def cli(ctx: click.Context, config_file: str | None, progress: bool | None, progress_interval: int | None):
    """Spotify-to-local music library synchronization tool.

    \b
    TYPICAL WORKFLOWS:

    \b
    Initial Setup:
      psm login        # Authenticate with Spotify
      psm scan         # Index your local music library

    \b
    Full Sync (all playlists):
      psm pull         # Download playlists from Spotify
      psm match        # Match tracks to local files
      psm export       # Generate M3U playlist files

    \b
    Single Playlist Workflow:
      psm playlist pull PLAYLIST_ID      # Pull one playlist
      psm playlist match PLAYLIST_ID     # Match its tracks
      psm playlist export PLAYLIST_ID    # Export to M3U
      # OR: psm playlist build PLAYLIST_ID  (does all three)

    \b
    Quality Analysis:
      psm analyze         # Check library quality issues
      psm report          # Show unmatched tracks
      psm report-albums   # Show incomplete albums

    \b
    Maintenance:
      psm scan --full             # Refresh library index
      psm scan --watch            # Continuously import changed files
      psm match-diagnose TRACK    # Debug matching issues

    \b
    Note: SQLite WAL mode enables safe concurrent operations.
    You can run pull, scan, and match simultaneously in different terminals.
    """
    # Check for first run and offer to create .env
    # Only check if not running --version (which doesn't need config)
    if ctx.invoked_subcommand is not None:
        if not check_first_run():
            ctx.exit(1)
    
    if hasattr(ctx, 'obj') and isinstance(ctx.obj, dict):
        ctx.obj = ctx.obj
    else:
        ctx.obj = load_typed_config(config_file).to_dict()

    # Override logging config from CLI flags
    if progress is not None:
        ctx.obj.setdefault('logging', {})['progress_enabled'] = progress
    if progress_interval is not None:
        ctx.obj.setdefault('logging', {})['progress_interval'] = progress_interval


def build_auth(cfg):
    """Build authentication provider from config.

    Args:
        cfg: Full configuration dict with providers configuration

    Returns:
        AuthProvider instance
    """
    provider_config = get_provider_config(cfg)
    provider = get_provider_instance('spotify')
    provider.validate_config(provider_config)
    return provider.create_auth(provider_config)


def get_token(cfg):
    """Get access token using authentication provider.

    Args:
        cfg: Full configuration dict with providers configuration

    Returns:
        Access token string
    """
    auth = build_auth(cfg)
    tok = auth.get_token()
    return tok['access_token']

__all__ = ["cli", "get_db", "get_token", "build_auth", "get_provider_config", "_redact_spotify_config"]
