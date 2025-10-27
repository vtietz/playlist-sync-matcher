"""OAuth helper commands."""

from __future__ import annotations
import click
import time
from pathlib import Path

from .helpers import cli, build_auth, get_provider_config


@cli.command(name="redirect-uri")
@click.pass_context
def redirect_uri(ctx: click.Context):
    """Show OAuth redirect URI for Spotify app configuration."""
    cfg = ctx.obj
    auth = build_auth(cfg)
    uri = auth.build_redirect_uri()
    click.echo(uri)
    provider_cfg = get_provider_config(cfg)
    click.echo("\nValidation checklist:")
    for line in [
        f"1. Spotify Dashboard has EXACT entry: {uri}",
        f"2. Scheme matches (expected {provider_cfg.get('redirect_scheme')})",
        f"3. Port matches (expected {provider_cfg.get('redirect_port')})",
        f"4. Path matches (expected {provider_cfg.get('redirect_path')})",
        "5. No trailing slash difference (unless you registered with one)",
        "6. Browser not caching old redirect (try private window)",
        "7. Client ID corresponds to the app whose dashboard you edited",
    ]:
        click.echo(f" - {line}")


@cli.command(name="token-info")
@click.pass_context
def token_info(ctx: click.Context):
    """Show OAuth token cache status and expiration info."""
    cfg = ctx.obj
    provider_cfg = get_provider_config(cfg)
    path = Path(provider_cfg["cache_file"]).resolve()
    if not path.exists():
        click.echo(f"Token cache not found: {path}")
        return
    try:
        import json

        data = json.loads(path.read_text(encoding="utf-8"))
        exp = data.get("expires_at")
        if exp:
            remaining = int(exp - time.time())
            click.echo(
                f"Token cache: {path}\nExpires at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(exp))} (in {remaining}s)"
            )
        else:
            click.echo(f"Token cache: {path}\n(No expires_at field)")
    except Exception as e:  # pragma: no cover
        click.echo(f"Failed to parse token cache {path}: {e}")


__all__ = ["redirect_uri", "token_info"]
