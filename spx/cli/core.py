from __future__ import annotations
import click
from pathlib import Path
import json as _json
import time
from .helpers import cli, get_db, _redact_spotify_config, build_auth
from ..reporting.generator import write_missing_tracks, write_album_completeness
from ..services.pull_service import pull_data
from ..ingest.library import scan_library
from ..services.match_service import run_matching
from ..services.analysis_service import analyze_library_quality, print_quality_report
from ..services.export_service import export_playlists
from ..providers.base import available_providers, get as get_provider


@cli.command()
@click.pass_context
def report(ctx: click.Context):
    cfg = ctx.obj
    with get_db(cfg) as db:
        rows = db.get_missing_tracks()
        out_dir = Path(cfg['reports']['directory'])
        path = write_missing_tracks(rows, out_dir)
        click.echo(f"Missing tracks report: {path}")


@cli.command(name='report-albums')
@click.pass_context
def report_albums(ctx: click.Context):
    cfg = ctx.obj
    with get_db(cfg) as db:
        out_dir = Path(cfg['reports']['directory'])
        path = write_album_completeness(db, out_dir)
        click.echo(f"Album completeness report: {path}")


@cli.command()
@click.pass_context
def version(ctx: click.Context):  # pragma: no cover
    click.echo("spotify-m3u-sync prototype")


@cli.command(name='config')
@click.option('--section', '-s', help='Only show a specific top-level section (e.g. spotify, export, database).')
@click.option('--redact', is_flag=True, help='Redact sensitive values like client_id.')
@click.pass_context
def show_config(ctx: click.Context, section: str | None, redact: bool):
    cfg = ctx.obj
    data = cfg
    if section:
        section = section.lower()
        if section not in data:
            raise click.UsageError(f"Unknown section '{section}'. Available: {', '.join(sorted(data.keys()))}")
        data = {section: data[section]}
    out = data
    if redact:
        out = _redact_spotify_config(out)
    click.echo(_json.dumps(out, indent=2, sort_keys=True))


@cli.command(name='redirect-uri')
@click.pass_context
def redirect_uri(ctx: click.Context):
    cfg = ctx.obj
    auth = build_auth(cfg)
    uri = auth.build_redirect_uri()
    click.echo(uri)
    click.echo("\nValidation checklist:")
    for line in [
        f"1. Spotify Dashboard has EXACT entry: {uri}",
        f"2. Scheme matches (expected {cfg['spotify'].get('redirect_scheme')})",
        f"3. Port matches (expected {cfg['spotify'].get('redirect_port')})",
        f"4. Path matches (expected {cfg['spotify'].get('redirect_path')})",
        "5. No trailing slash difference (unless you registered with one)",
        "6. Browser not caching old redirect (try private window)",
        "7. Client ID corresponds to the app whose dashboard you edited",
    ]:
        click.echo(f" - {line}")


@cli.command(name='token-info')
@click.pass_context
def token_info(ctx: click.Context):
    cfg = ctx.obj
    path = Path(cfg['spotify']['cache_file']).resolve()
    if not path.exists():
        click.echo(f"Token cache not found: {path}")
        return
    try:
        import json
        data = json.loads(path.read_text(encoding='utf-8'))
        exp = data.get('expires_at')
        if exp:
            remaining = int(exp - time.time())
            click.echo(f"Token cache: {path}\nExpires at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(exp))} (in {remaining}s)")
        else:
            click.echo(f"Token cache: {path}\n(No expires_at field)")
    except Exception as e:  # pragma: no cover
        click.echo(f"Failed to parse token cache {path}: {e}")


@cli.command()
@click.option('--force-auth', is_flag=True, help='Force full auth flow ignoring cached token')
@click.option('--verbose', '-v', is_flag=True, help='Verbose pull logging')
@click.pass_context
def pull(ctx: click.Context, force_auth: bool, verbose: bool):
    cfg = ctx.obj
    provider = cfg.get('provider', 'spotify')
    if provider == 'spotify':
        if not cfg['spotify']['client_id']:
            raise click.UsageError('spotify.client_id not configured')
        provider_cfg = cfg['spotify']
    else:
        raise click.UsageError(f"Provider '{provider}' not supported yet")
    with get_db(cfg) as db:
        result = pull_data(db=db, provider=provider, provider_config=provider_cfg, matching_config=cfg['matching'], force_auth=force_auth, verbose=verbose)
    click.echo(f"\n[summary] Provider={provider} | Playlists: {result.playlist_count} | Unique playlist tracks: {result.unique_playlist_tracks} | Liked tracks: {result.liked_tracks} | Total tracks: {result.total_tracks}")
    if verbose:
        click.echo(f"[pull] Completed in {result.duration_seconds:.2f}s")
    click.echo('Pull complete')


@cli.command()
@click.option('--force', is_flag=True, help='Force full auth ignoring cache')
@click.pass_context
def login(ctx: click.Context, force: bool):
    cfg = ctx.obj
    if not cfg['spotify']['client_id']:
        raise click.UsageError('spotify.client_id not configured')
    auth = build_auth(cfg)
    tok = auth.get_token(force=force)
    exp = tok.get('expires_at') if isinstance(tok, dict) else None
    if exp:
        click.echo(f"Token acquired; expires at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(exp))}")
    else:
        click.echo('Token acquired.')


@cli.command()
@click.pass_context
def scan(ctx: click.Context):
    cfg = ctx.obj
    with get_db(cfg) as db:
        scan_library(db, cfg)
    click.echo('Scan complete')


@cli.command()
@click.pass_context
def match(ctx: click.Context):
    cfg = ctx.obj
    with get_db(cfg) as db:
        result = run_matching(db, config=cfg, verbose=False)
        click.echo(f'Matched {result.matched} tracks')


@cli.command()
@click.option('--min-bitrate', type=int, help='Minimum acceptable bitrate in kbps (overrides config)')
@click.option('--verbose', '-v', is_flag=True, help='Verbose file issue list')
@click.option('--max-issues', type=int, default=50, help='Max number of detailed issues to show')
@click.pass_context
def analyze(ctx: click.Context, min_bitrate: int | None, verbose: bool, max_issues: int):
    cfg = ctx.obj
    if min_bitrate is None:
        min_bitrate = cfg.get('library', {}).get('min_bitrate_kbps', 320)
    min_bitrate = int(min_bitrate) if min_bitrate is not None else 320
    with get_db(cfg) as db:
        report = analyze_library_quality(db, min_bitrate_kbps=min_bitrate, max_issues=max_issues)
        print_quality_report(report, min_bitrate_kbps=min_bitrate, verbose=verbose)


@cli.command(name='match-diagnose')
@click.argument('query')
@click.option('--limit', type=int, default=10, help='Limit number of candidate files shown')
@click.pass_context
def match_diagnose(ctx: click.Context, query: str, limit: int):
    from rapidfuzz import fuzz
    cfg = ctx.obj
    with get_db(cfg) as db:
        track_row = None
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
        m = db.conn.execute("SELECT file_id, score, method FROM matches WHERE track_id=?", (track_row['id'],)).fetchone()
        if m:
            click.echo(f"Existing match: file_id={m['file_id']} score={m['score']:.3f} method={m['method']}")
        else:
            click.echo("Existing match: (none)")


@cli.command()
@click.pass_context
def export(ctx: click.Context):
    cfg = ctx.obj
    organize_by_owner = cfg['export'].get('organize_by_owner', False)
    with get_db(cfg) as db:
        current_user_id = db.get_meta('current_user_id') if organize_by_owner else None
        result = export_playlists(db=db, export_config=cfg['export'], organize_by_owner=organize_by_owner, current_user_id=current_user_id)
    click.echo(f'Exported {result.playlist_count} playlists')
    click.echo('Export complete')


@cli.command(name='build')
@click.option('--no-report', is_flag=True, help='Skip report generation step')
@click.option('--no-export', is_flag=True, help='Skip playlist export step')
@click.pass_context
def build(ctx: click.Context, no_report: bool, no_export: bool):
    """Run the full one-way pipeline (pull -> scan -> match -> export -> report).

    This replaces the old 'sync' command (removed, no alias) to better reflect
    that the operation builds local artifacts from remote + local state without
    mutating the remote provider (push is a separate explicit command).
    Use --no-export or --no-report to skip those phases for faster iterations.
    """
    ctx.invoke(pull)
    ctx.invoke(scan)
    ctx.invoke(match)
    if not no_export:
        ctx.invoke(export)
    if not no_report:
        ctx.invoke(report)
    click.echo('Build complete')

__all__ = []

# Providers related commands
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
    for p in available_providers():
        cls = get_provider(p)
        caps = getattr(cls, 'capabilities', None)
        if not caps:
            rows.append((p, 'NO CAPABILITY OBJECT'))
            continue
        rows.append((p, f"replace_playlist={caps.replace_playlist} supports_isrc={caps.supports_isrc} create_playlist={caps.create_playlist}"))
    width = max(len(r[0]) for r in rows) if rows else 8
    click.echo("Providers:")
    for name, desc in rows:
        click.echo(f"  {name.ljust(width)}  {desc}")
