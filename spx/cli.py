from __future__ import annotations
import click
from pathlib import Path
from .config import load_typed_config
import copy
from .db import Database
from .reporting.generator import write_missing_tracks, write_album_completeness
from .auth.spotify_oauth import SpotifyAuth
from .ingest.library import scan_library
from .services.pull_service import pull_data
from .services.match_service import run_matching
from .services.export_service import export_playlists
from .services.playlist_service import (
    pull_single_playlist,
    match_single_playlist,
    export_single_playlist,
    sync_single_playlist,
)
import time
import json as _json
from datetime import datetime


def _redact_spotify_config(cfg: dict) -> dict:
    """Create a deep copy of config and redact sensitive Spotify values.
    
    Args:
        cfg: Configuration dictionary
        
    Returns:
        Deep copy with client_id redacted if present
    """
    result = copy.deepcopy(cfg)
    if 'spotify' in result and isinstance(result['spotify'], dict):
        if result['spotify'].get('client_id'):
            result['spotify']['client_id'] = '*** redacted ***'
    return result


@click.group()
@click.option('--config-file', type=click.Path(exists=False), default=None, help='Deprecated: config file parameter (ignored, use .env instead)')
@click.pass_context
def cli(ctx: click.Context, config_file: str | None):
    # Allow tests to inject config via context object
    if hasattr(ctx, 'obj') and isinstance(ctx.obj, dict):  # test injection path
        ctx.obj = ctx.obj  # keep as-is for tests that still inject raw dict
    else:
        ctx.obj = load_typed_config(config_file).to_dict()  # store dict form for backward compatibility in commands

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
    
    # Use deepcopy instead of JSON round-trip
    out = copy.deepcopy(data)
    if redact:
        out = _redact_spotify_config(out)
    
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


def _get_db(cfg):
    return Database(Path(cfg['database']['path']))


def _build_auth(cfg):
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
    provider = cfg.get('provider', 'spotify')
    if provider == 'spotify':
        if not cfg['spotify']['client_id']:
            raise click.UsageError('spotify.client_id not configured')
        provider_cfg = cfg['spotify']
    else:
        raise click.UsageError(f"Provider '{provider}' not supported yet")

    with _get_db(cfg) as db:
        result = pull_data(
            db=db,
            provider=provider,
            provider_config=provider_cfg,
            matching_config=cfg['matching'],
            force_auth=force_auth,
            verbose=verbose,
        )
        
        # Print summary
    click.echo(f"\n[summary] Provider={provider} | Playlists: {result.playlist_count} | Unique playlist tracks: {result.unique_playlist_tracks} | Liked tracks: {result.liked_tracks} | Total tracks: {result.total_tracks}")
    
    if verbose:
        click.echo(f"[pull] Completed in {result.duration_seconds:.2f}s")
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
        result = run_matching(db, config=cfg, verbose=False)
        click.echo(f'Matched {result.matched} tracks')


@cli.command()
@click.option('--min-bitrate', type=int, help='Minimum acceptable bitrate in kbps (overrides config)')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed list of problematic files')
@click.option('--max-issues', type=int, default=50, help='Maximum number of detailed issues to show')
@click.pass_context
def analyze(ctx: click.Context, min_bitrate: int | None, verbose: bool, max_issues: int):
    """Analyze library metadata quality.
    
    Reports files with missing metadata (artist, title, album, year)
    and bitrate issues. Helps identify tagging problems that hurt matching.
    """
    from .services.analysis_service import analyze_library_quality, print_quality_report
    
    cfg = ctx.obj
    # Get min_bitrate from config or use default
    if min_bitrate is None:
        min_bitrate = cfg.get('library', {}).get('min_bitrate_kbps', 320)
    
    # Ensure min_bitrate is an int
    min_bitrate = int(min_bitrate) if min_bitrate is not None else 320
    
    with _get_db(cfg) as db:
        report = analyze_library_quality(db, min_bitrate_kbps=min_bitrate, max_issues=max_issues)
        print_quality_report(report, min_bitrate_kbps=min_bitrate, verbose=verbose)


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
    organize_by_owner = cfg['export'].get('organize_by_owner', False)
    
    with _get_db(cfg) as db:
        # Get current user ID if needed
        current_user_id = None
        if organize_by_owner:
            current_user_id = db.get_meta('current_user_id')
        
        # Use service layer
        result = export_playlists(
            db=db,
            export_config=cfg['export'],
            organize_by_owner=organize_by_owner,
            current_user_id=current_user_id
        )
        
    click.echo(f'Exported {result.playlist_count} playlists')
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


# Playlist-specific commands
@cli.group(name='playlists')
@click.pass_context
def playlists_group(ctx: click.Context):
    """List and manage playlists."""
    pass


@playlists_group.command(name='list')
@click.option('--show-urls', is_flag=True, help='Show Spotify URLs for each playlist')
@click.pass_context
def playlists_list(ctx: click.Context, show_urls: bool):
    """List all playlists with their IDs, names, owners, and track counts."""
    cfg = ctx.obj
    with _get_db(cfg) as db:
        playlists = db.get_all_playlists()
        
        if not playlists:
            click.echo("No playlists found. Run 'spx pull' first.")
            return
        
        # Print header
        click.echo(f"{'ID':<24} {'Name':<40} {'Owner':<20} {'Tracks':>7}")
        click.echo("-" * 95)
        
        # Print each playlist
        for pl in playlists:
            pl_id = pl['id']
            name = pl['name'][:40]  # Truncate long names
            owner = (pl['owner_name'] or pl['owner_id'] or 'Unknown')[:20]
            track_count = pl['track_count']
            click.echo(f"{pl_id:<24} {name:<40} {owner:<20} {track_count:>7}")
            
            if show_urls:
                url = f"https://open.spotify.com/playlist/{pl_id}"
                click.echo(f"  → {url}")
        
        click.echo(f"\nTotal: {len(playlists)} playlists")


@cli.group(name='playlist')
@click.pass_context
def playlist_group(ctx: click.Context):
    """Operations on a single playlist."""
    pass


@playlist_group.command(name='pull')
@click.argument('playlist_id')
@click.option('--force-auth', is_flag=True, help='Force full auth flow ignoring cached token')
@click.option('--verbose', '-v', is_flag=True, help='Verbose logging')
@click.pass_context
def playlist_pull(ctx: click.Context, playlist_id: str, force_auth: bool, verbose: bool):
    """Pull a single playlist from Spotify.
    
    PLAYLIST_ID: Spotify playlist ID (get from 'spx playlists list')
    """
    cfg = ctx.obj
    if not cfg['spotify']['client_id']:
        raise click.UsageError('spotify.client_id not configured')
    
    with _get_db(cfg) as db:
        result = pull_single_playlist(
            db=db,
            playlist_id=playlist_id,
            spotify_config=cfg['spotify'],
            matching_config=cfg['matching'],
            force_auth=force_auth,
            verbose=verbose
        )
        
        click.echo(f"Pulled playlist '{result.playlist_name}' ({result.playlist_id})")
        click.echo(f"Tracks: {result.tracks_processed}")
        if verbose:
            click.echo(f"Duration: {result.duration_seconds:.2f}s")


@playlist_group.command(name='match')
@click.argument('playlist_id')
@click.option('--verbose', '-v', is_flag=True, help='Verbose logging')
@click.pass_context
def playlist_match(ctx: click.Context, playlist_id: str, verbose: bool):
    """Match tracks from a single playlist against local library.
    
    PLAYLIST_ID: Spotify playlist ID (get from 'spx playlists list')
    """
    cfg = ctx.obj
    
    with _get_db(cfg) as db:
        result = match_single_playlist(
            db=db,
            playlist_id=playlist_id,
            config=cfg,
            verbose=verbose
        )
        
        click.echo(f"Matched playlist '{result.playlist_name}' ({result.playlist_id})")
        click.echo(f"Matched: {result.tracks_matched}/{result.tracks_processed} tracks")
        if verbose:
            click.echo(f"Duration: {result.duration_seconds:.2f}s")


@playlist_group.command(name='export')
@click.argument('playlist_id')
@click.option('--verbose', '-v', is_flag=True, help='Verbose logging')
@click.pass_context
def playlist_export(ctx: click.Context, playlist_id: str, verbose: bool):
    """Export a single playlist to M3U file.
    
    PLAYLIST_ID: Spotify playlist ID (get from 'spx playlists list')
    """
    cfg = ctx.obj
    organize_by_owner = cfg['export'].get('organize_by_owner', False)
    
    with _get_db(cfg) as db:
        # Get current user ID if needed
        current_user_id = None
        if organize_by_owner:
            current_user_id = db.get_meta('current_user_id')
        
        result = export_single_playlist(
            db=db,
            playlist_id=playlist_id,
            export_config=cfg['export'],
            organize_by_owner=organize_by_owner,
            current_user_id=current_user_id,
            verbose=verbose
        )
        
        click.echo(f"Exported playlist '{result.playlist_name}' ({result.playlist_id})")
        click.echo(f"File: {result.exported_file}")
        if verbose:
            click.echo(f"Duration: {result.duration_seconds:.2f}s")


@playlist_group.command(name='sync')
@click.argument('playlist_id')
@click.option('--force-auth', is_flag=True, help='Force full auth flow ignoring cached token')
@click.option('--verbose', '-v', is_flag=True, help='Verbose logging')
@click.pass_context
def playlist_sync(ctx: click.Context, playlist_id: str, force_auth: bool, verbose: bool):
    """Sync a single playlist (pull + match + export).
    
    PLAYLIST_ID: Spotify playlist ID (get from 'spx playlists list')
    """
    cfg = ctx.obj
    if not cfg['spotify']['client_id']:
        raise click.UsageError('spotify.client_id not configured')
    
    with _get_db(cfg) as db:
        result = sync_single_playlist(
            db=db,
            playlist_id=playlist_id,
            spotify_config=cfg['spotify'],
            config=cfg,
            force_auth=force_auth,
            verbose=verbose
        )
        
        click.echo(f"Synced playlist '{result.playlist_name}' ({result.playlist_id})")
        click.echo(f"Tracks processed: {result.tracks_processed}")
        click.echo(f"Tracks matched: {result.tracks_matched}")
        click.echo(f"Exported to: {result.exported_file}")
        if verbose:
            click.echo(f"Total duration: {result.duration_seconds:.2f}s")


if __name__ == '__main__':  # pragma: no cover
    cli()
