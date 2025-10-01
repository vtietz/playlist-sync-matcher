from __future__ import annotations
import click
from pathlib import Path
from .config import load_config
import os
from .db import Database
from .reporting.generator import write_missing_tracks, write_album_completeness
from .auth.spotify_oauth import SpotifyAuth
from .ingest.spotify import SpotifyClient, ingest_playlists, ingest_liked
from .ingest.library import scan_library
from .match.engine import match_and_store
from .export.playlists import export_strict, export_mirrored, export_placeholders
import time
import json as _json

@click.group()
@click.option('--config-file', type=click.Path(exists=False), default=None)
@click.pass_context
def cli(ctx: click.Context, config_file: str | None):
    cfg = load_config(config_file)
    ctx.obj = cfg
    # Ensure SPX_DEBUG is set if config debug flag used through SPX__DEBUG env/ .env
    if cfg.get('debug') and not os.environ.get('SPX_DEBUG'):
        os.environ['SPX_DEBUG'] = '1'

# type: ignore[arg-type, misc]  # Silence type checker complaints about dynamic decorators
@cli.command()
@click.pass_context
def report(ctx: click.Context):
    cfg = ctx.obj
    db_path = Path(cfg['database']['path'])
    with Database(db_path) as db:
        rows = db.get_missing_tracks()
        out_dir = Path(cfg['reports']['directory'])
        path = write_missing_tracks(rows, out_dir)
        click.echo(f"Missing tracks report: {path}")

# type: ignore[arg-type, misc]
@cli.command(name='report-albums')
@click.pass_context
def report_albums(ctx: click.Context):
    """Generate album completeness report."""
    cfg = ctx.obj
    db_path = Path(cfg['database']['path'])
    with Database(db_path) as db:
        out_dir = Path(cfg['reports']['directory'])
        path = write_album_completeness(db, out_dir)
        click.echo(f"Album completeness report: {path}")

# type: ignore[arg-type, misc]
@cli.command()
@click.pass_context
def version(ctx: click.Context):
    click.echo("spotify-m3u-sync prototype")


# type: ignore[arg-type, misc]
@cli.command(name='config')
@click.option('--section', '-s', help='Only show a specific top-level section (e.g. spotify, export, database).')
@click.option('--redact', is_flag=True, help='Redact sensitive values like client_id.')
@click.pass_context
def show_config(ctx: click.Context, section: str | None, redact: bool):
    """Print the effective merged configuration (after .env & env overrides)."""
    cfg = ctx.obj
    data = cfg
    if section:
        section = section.lower()
        if section not in data:
            raise click.UsageError(f"Unknown section '{section}'. Available: {', '.join(sorted(data.keys()))}")
        data = {section: data[section]}
    out = _json.loads(_json.dumps(data))  # shallow copy via serialization
    if redact and 'spotify' in out and isinstance(out['spotify'], dict):
        if out['spotify'].get('client_id'):
            out['spotify']['client_id'] = '*** redacted ***'
    click.echo(_json.dumps(out, indent=2, sort_keys=True))


# type: ignore[arg-type, misc]
@cli.command(name='redirect-uri')
@click.pass_context
def redirect_uri(ctx: click.Context):
    """Print the exact redirect URI that will be sent to Spotify plus a validation checklist."""
    cfg = ctx.obj
    auth = _build_auth(cfg)
    uri = auth.build_redirect_uri()
    click.echo(uri)
    click.echo("\nValidation checklist:")
    checklist = [
        f"1. Spotify Dashboard has EXACT entry: {uri}",
        f"2. Scheme matches (expected {cfg['spotify'].get('redirect_scheme')})",
        f"3. Port matches (expected {cfg['spotify'].get('redirect_port')})",
        f"4. Path matches (expected {cfg['spotify'].get('redirect_path')})",
        "5. No trailing slash difference (unless you registered with one)",
        "6. Browser not caching old redirect (try private window)",
        "7. Client ID corresponds to the app whose dashboard you edited",
    ]
    for line in checklist:
        click.echo(f" - {line}")


# type: ignore[arg-type, misc]
@cli.command(name='token-info')
@click.pass_context
def token_info(ctx: click.Context):
    """Show token cache file path and expiration (if present)."""
    cfg = ctx.obj
    auth = _build_auth(cfg)
    path = Path(cfg['spotify']['cache_file']).resolve()
    if not path.exists():
        click.echo(f"Token cache not found: {path}")
        return
    try:
        import json, time as _time
        data = json.loads(path.read_text(encoding='utf-8'))
        exp = data.get('expires_at')
        if exp:
            remaining = int(exp - _time.time())
            click.echo(f"Token cache: {path}\nExpires at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(exp))} (in {remaining}s)")
        else:
            click.echo(f"Token cache: {path}\n(No expires_at field)")
    except Exception as e:  # pragma: no cover
        click.echo(f"Failed to parse token cache {path}: {e}")


def _get_db(cfg):
    return Database(Path(cfg['database']['path']))


def _build_auth(cfg):
    return SpotifyAuth(
        client_id=cfg['spotify']['client_id'],
        redirect_port=cfg['spotify']['redirect_port'],
        redirect_path=cfg['spotify'].get('redirect_path', '/callback'),
        scope=cfg['spotify']['scope'],
        cache_file=cfg['spotify']['cache_file'],
        redirect_scheme=cfg['spotify'].get('redirect_scheme', 'https'),
        redirect_host=cfg['spotify'].get('redirect_host', '127.0.0.1'),
        cert_file=cfg['spotify'].get('cert_file'),
        key_file=cfg['spotify'].get('key_file'),
    )


def _get_token(cfg):
    auth = _build_auth(cfg)
    tok = auth.get_token()
    return tok['access_token']


# type: ignore[arg-type, misc]
@cli.command()
@click.option('--force-auth', is_flag=True, help='Force full auth flow ignoring cached token')
@click.option('--verbose', '-v', is_flag=True, help='Verbose pull logging (API pages, counts, incremental skips)')
@click.pass_context
def pull(ctx: click.Context, force_auth: bool, verbose: bool):
    """Ingest playlists & liked tracks incrementally.

    Verbose mode prints:
      - Token reuse vs fresh auth
      - Playlist pagination progress & snapshot skip reasons
      - Per-playlist track counts
      - Liked tracks incremental stop condition
      - Timing summary
    """
    cfg = ctx.obj
    if not cfg['spotify']['client_id']:
        raise click.UsageError('spotify.client_id not configured')
    auth = _build_auth(cfg)
    start = time.time()
    tok_dict = auth.get_token(force=force_auth)
    if not isinstance(tok_dict, dict) or 'access_token' not in tok_dict:
        raise click.ClickException('Failed to obtain access token')
    if verbose or os.environ.get('SPX_DEBUG'):
        from datetime import datetime
        exp = tok_dict.get('expires_at')
        if exp:
            rem = int(exp - time.time())
            click.echo(f"[pull] Using access token (expires {datetime.fromtimestamp(exp)}; +{rem}s)")
        else:
            click.echo("[pull] Using access token (no expires_at field)")
    client = SpotifyClient(tok_dict['access_token'])
    use_year = cfg['matching'].get('use_year', False)
    with _get_db(cfg) as db:
        ingest_playlists(db, client, verbose=verbose, use_year=use_year)
        ingest_liked(db, client, verbose=verbose, use_year=use_year)
    if verbose or os.environ.get('SPX_DEBUG'):
        dur = time.time() - start
        click.echo(f"[pull] Completed in {dur:.2f}s")
    click.echo('Pull complete')


# type: ignore[arg-type, misc]
@cli.command()
@click.option('--force', is_flag=True, help='Force full auth ignoring cache')
@click.pass_context
def login(ctx: click.Context, force: bool):
    """Perform (or refresh) Spotify OAuth without running ingestion."""
    cfg = ctx.obj
    if not cfg['spotify']['client_id']:
        raise click.UsageError('spotify.client_id not configured')
    auth = _build_auth(cfg)
    tok = auth.get_token(force=force)
    exp = tok.get('expires_at') if isinstance(tok, dict) else None
    if exp:
        click.echo(f"Token acquired; expires at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(exp))}")
    else:
        click.echo('Token acquired.')


# type: ignore[arg-type, misc]
@cli.command()
@click.pass_context
def scan(ctx: click.Context):
    """Scan local library into database."""
    cfg = ctx.obj
    with _get_db(cfg) as db:
        scan_library(db, cfg)
    click.echo('Scan complete')


# type: ignore[arg-type, misc]
@cli.command()
@click.pass_context
def match(ctx: click.Context):
    """Run matching engine and persist matches."""
    cfg = ctx.obj
    with _get_db(cfg) as db:
        count = match_and_store(db, config=cfg)
        click.echo(f'Matched {count} tracks')


@cli.command(name='match-diagnose')
@click.argument('query')
@click.option('--limit', type=int, default=10, help='Limit number of candidate files shown')
@click.pass_context
def match_diagnose(ctx: click.Context, query: str, limit: int):
    """Diagnose why a track may not be matched.

    QUERY can be a Spotify track id or a substring of the track name.
    Shows normalized forms and top fuzzy candidate scores.
    """
    from rapidfuzz import fuzz
    cfg = ctx.obj
    with _get_db(cfg) as db:
    # locate track
        track_row = None
        cur = None
        # exact id first
        cur = db.conn.execute("SELECT id,name,artist,album,normalized,year FROM tracks WHERE id=?", (query,))
        track_row = cur.fetchone()
        if not track_row:
            like = f"%{query}%"
            cur = db.conn.execute("SELECT id,name,artist,album,normalized,year FROM tracks WHERE name LIKE ? ORDER BY name LIMIT 1", (like,))
            track_row = cur.fetchone()
        if not track_row:
            click.echo(f"No track found matching '{query}'")
            return
        t_norm = track_row['normalized'] or ''
        click.echo(f"Track: {track_row['id']} | {track_row['artist']} - {track_row['name']} | album={track_row['album']} year={track_row['year']}\nNormalized: '{t_norm}'")
        # gather files
        rows = db.conn.execute("SELECT id,path,title,artist,album,normalized,year FROM library_files").fetchall()
        scored = []
        for r in rows:
            f_norm = r['normalized'] or ''
            exact = 1.0 if f_norm == t_norm and t_norm else 0.0
            fuzzy = fuzz.token_set_ratio(t_norm, f_norm)/100.0 if t_norm else 0.0
            scored.append((exact, fuzzy, r))
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        click.echo(f"Top candidates (limit={limit}):")
        for exact, fuzzy, r in scored[:limit]:
            click.echo(f"  file_id={r['id']} score_exact={exact:.3f} score_fuzzy={fuzzy:.3f} | title='{r['title']}' artist='{r['artist']}' album='{r['album']}' year={r['year']} path={r['path']} norm='{r['normalized']}'")
        # show if any existing match stored
        m = db.conn.execute("SELECT file_id, score, method FROM matches WHERE track_id=?", (track_row['id'],)).fetchone()
        if m:
            click.echo(f"Existing match: file_id={m['file_id']} score={m['score']:.3f} method={m['method']}")
        else:
            click.echo("Existing match: (none)")


@cli.command()
@click.pass_context
def export(ctx: click.Context):
    """Export playlists in configured mode (strict|mirrored|placeholders)."""
    cfg = ctx.obj
    mode = cfg['export']['mode']
    with _get_db(cfg) as db:
        export_dir = Path(cfg['export']['directory'])
        placeholder_ext = cfg['export'].get('placeholder_extension', '.missing')
        organize_by_owner = cfg['export'].get('organize_by_owner', False)
        
        # Get current user ID for comparison
        current_user_id = None
        if organize_by_owner:
            # Try to get current user ID from database metadata or config
            current_user_id = db.get_meta('current_user_id')
        
        cur = db.conn.execute("SELECT id, name, owner_id, owner_name FROM playlists")
        playlists = cur.fetchall()
        for pl in playlists:
            pl_id = pl['id']
            owner_id = pl.get('owner_id')
            owner_name = pl.get('owner_name')
            
            # Determine target directory
            if organize_by_owner:
                if owner_id and current_user_id and owner_id == current_user_id:
                    # User's own playlists
                    target_dir = export_dir / 'my_playlists'
                elif owner_name:
                    # Other user's playlists - use sanitized owner name
                    from .export.playlists import sanitize_filename
                    folder_name = sanitize_filename(owner_name)
                    target_dir = export_dir / folder_name
                else:
                    # Unknown owner - put in 'other' folder
                    target_dir = export_dir / 'other'
            else:
                # No organization - flat structure
                target_dir = export_dir
            
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
            tracks = [dict(r) | {'position': r['position']} for r in track_rows]
            playlist_meta = {'name': pl['name'], 'id': pl_id}
            if mode == 'strict':
                export_strict(playlist_meta, tracks, target_dir)
            elif mode == 'mirrored':
                export_mirrored(playlist_meta, tracks, target_dir)
            elif mode == 'placeholders':
                export_placeholders(playlist_meta, tracks, target_dir, placeholder_extension=placeholder_ext)
            else:
                click.echo(f"Unknown export mode '{mode}', defaulting to strict")
                export_strict(playlist_meta, tracks, target_dir)
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
