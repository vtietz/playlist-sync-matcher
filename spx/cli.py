from __future__ import annotations
import click
from pathlib import Path
from .config import load_config
from .db import Database
from .reporting.generator import write_missing_tracks, write_album_completeness
from .auth.spotify_oauth import SpotifyAuth
from .ingest.spotify import SpotifyClient, ingest_playlists, ingest_liked
from .ingest.library import scan_library
from .match.engine import match_and_store
from .export.playlists import export_strict, export_mirrored, export_placeholders

@click.group()
@click.option('--config-file', type=click.Path(exists=False), default=None)
@click.pass_context
def cli(ctx: click.Context, config_file: str | None):
    cfg = load_config(config_file)
    ctx.obj = cfg

@cli.command()
@click.pass_context
def report(ctx: click.Context):
    cfg = ctx.obj
    db_path = Path(cfg['database']['path'])
    db = Database(db_path)
    rows = db.get_missing_tracks()
    out_dir = Path(cfg['reports']['directory'])
    path = write_missing_tracks(rows, out_dir)
    click.echo(f"Missing tracks report: {path}")

@cli.command(name='report-albums')
@click.pass_context
def report_albums(ctx: click.Context):
    """Generate album completeness report."""
    cfg = ctx.obj
    db_path = Path(cfg['database']['path'])
    db = Database(db_path)
    out_dir = Path(cfg['reports']['directory'])
    path = write_album_completeness(db, out_dir)
    click.echo(f"Album completeness report: {path}")

@cli.command()
@click.pass_context
def version(ctx: click.Context):
    click.echo("spotify-m3u-sync prototype")


def _get_db(cfg):
    return Database(Path(cfg['database']['path']))


def _get_token(cfg):
    auth = SpotifyAuth(
        client_id=cfg['spotify']['client_id'],
        redirect_port=cfg['spotify']['redirect_port'],
        redirect_path=cfg['spotify'].get('redirect_path', '/callback'),
        scope=cfg['spotify']['scope'],
        cache_file=cfg['spotify']['cache_file'],
    )
    tok = auth.get_token()
    return tok['access_token']


@cli.command()
@click.option('--force-auth', is_flag=True, help='Force full auth flow ignoring cached token')
@click.pass_context
def pull(ctx: click.Context, force_auth: bool):
    """Ingest playlists & liked tracks incrementally."""
    cfg = ctx.obj
    if not cfg['spotify']['client_id']:
        raise click.UsageError('spotify.client_id not configured')
    auth = SpotifyAuth(
        client_id=cfg['spotify']['client_id'],
        redirect_port=cfg['spotify']['redirect_port'],
        redirect_path=cfg['spotify'].get('redirect_path', '/callback'),
        scope=cfg['spotify']['scope'],
        cache_file=cfg['spotify']['cache_file'],
    )
    tok = auth.get_token(force=force_auth)
    client = SpotifyClient(tok['access_token']) if 'access_token' in tok else SpotifyClient(tok)
    db = _get_db(cfg)
    ingest_playlists(db, client)
    ingest_liked(db, client)
    click.echo('Pull complete')


@cli.command()
@click.pass_context
def scan(ctx: click.Context):
    """Scan local library into database."""
    cfg = ctx.obj
    db = _get_db(cfg)
    scan_library(db, cfg)
    click.echo('Scan complete')


@cli.command()
@click.pass_context
def match(ctx: click.Context):
    """Run matching engine and persist matches."""
    cfg = ctx.obj
    db = _get_db(cfg)
    fuzzy_threshold = cfg['matching']['fuzzy_threshold']
    count = match_and_store(db, fuzzy_threshold=fuzzy_threshold)
    click.echo(f'Matched {count} tracks')


@cli.command()
@click.pass_context
def export(ctx: click.Context):
    """Export playlists in configured mode (strict|mirrored|placeholders)."""
    cfg = ctx.obj
    mode = cfg['export']['mode']
    db = _get_db(cfg)
    export_dir = Path(cfg['export']['directory'])
    placeholder_ext = cfg['export'].get('placeholder_extension', '.missing')
    cur = db.conn.execute("SELECT id,name FROM playlists")
    playlists = cur.fetchall()
    for pl in playlists:
        pl_id = pl['id']
        # Gather richer track context for mirrored/placeholders modes
        track_rows = db.conn.execute(
            """
            SELECT pt.position, t.id as track_id, t.name, t.artist, t.album, t.duration_ms, lf.path AS local_path
            FROM playlist_tracks pt
            LEFT JOIN tracks t ON t.id = pt.track_id
            LEFT JOIN matches m ON m.track_id = pt.track_id
            LEFT JOIN library_files lf ON lf.id = m.file_id
            WHERE pt.playlist_id=?
            ORDER BY pt.position
            """,
            (pl_id,),
        ).fetchall()
        # Convert rows to dicts for export functions
        tracks = [dict(r) | {'position': r['position']} for r in track_rows]
        playlist_meta = {'name': pl['name'], 'id': pl_id}
        if mode == 'strict':
            export_strict(playlist_meta, tracks, export_dir)
        elif mode == 'mirrored':
            export_mirrored(playlist_meta, tracks, export_dir)
        elif mode == 'placeholders':
            export_placeholders(playlist_meta, tracks, export_dir, placeholder_extension=placeholder_ext)
        else:
            click.echo(f"Unknown export mode '{mode}', defaulting to strict")
            export_strict(playlist_meta, tracks, export_dir)
    click.echo('Export complete')


@cli.command()
@click.pass_context
def sync(ctx: click.Context):
    """Run pull -> scan -> match -> export -> report pipeline."""
    ctx.invoke(pull)
    ctx.invoke(scan)
    ctx.invoke(match)
    ctx.invoke(export)
    ctx.invoke(report)
    click.echo('Sync complete')

if __name__ == '__main__':  # pragma: no cover
    cli()
