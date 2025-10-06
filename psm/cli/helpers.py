from __future__ import annotations
import click
from pathlib import Path
import copy
from ..config import load_typed_config
from ..version import __version__
from ..db import Database
from ..auth.spotify_oauth import SpotifyAuth


def _redact_spotify_config(cfg: dict) -> dict:
    result = copy.deepcopy(cfg)
    if 'spotify' in result and isinstance(result['spotify'], dict):
        if result['spotify'].get('client_id'):
            result['spotify']['client_id'] = '*** redacted ***'
    return result


@click.group()
@click.version_option(version=__version__, prog_name="playlist-sync-matcher")
@click.option('--config-file', type=click.Path(exists=False), default=None, help='Deprecated: config file parameter (ignored; use .env)')
@click.pass_context
def cli(ctx: click.Context, config_file: str | None):
    if hasattr(ctx, 'obj') and isinstance(ctx.obj, dict):
        ctx.obj = ctx.obj
    else:
        ctx.obj = load_typed_config(config_file).to_dict()


def get_db(cfg):
    return Database(Path(cfg['database']['path']))


def build_auth(cfg):
    sp = cfg['spotify']
    return SpotifyAuth(
        client_id=sp['client_id'],
        redirect_port=sp['redirect_port'],
        redirect_path=sp.get('redirect_path', '/callback'),
        scope=sp['scope'],
        cache_file=sp['cache_file'],
        redirect_scheme=sp.get('redirect_scheme', 'http'),
        redirect_host=sp.get('redirect_host', '127.0.0.1'),
        cert_file=sp.get('cert_file'),
        key_file=sp.get('key_file'),
    )


def get_token(cfg):
    auth = build_auth(cfg)
    tok = auth.get_token()
    return tok['access_token']

__all__ = ["cli", "get_db", "get_token", "build_auth", "_redact_spotify_config"]
