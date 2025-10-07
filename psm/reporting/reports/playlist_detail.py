"""Playlist detail report generator - shows all tracks in a playlist with match status."""

import csv
from pathlib import Path

from ...db import Database
from ...providers.links import get_link_generator
from ..html_templates import get_html_template
from ..formatting import format_duration, shorten_path


def write_playlist_detail_report(
    db: Database,
    out_dir: Path,
    playlist_id: str,
    provider: str = 'spotify'
) -> tuple[Path, Path]:
    """Write playlist detail report to CSV and HTML.
    
    Args:
        db: Database instance
        out_dir: Output directory for reports (will create playlists/ subdirectory)
        playlist_id: Playlist ID to generate report for
        provider: Provider name (default: spotify)
    
    Returns:
        Tuple of (csv_path, html_path)
    """
    # Create playlists subdirectory
    playlist_dir = out_dir / "playlists"
    playlist_dir.mkdir(parents=True, exist_ok=True)
    
    # Get playlist info
    playlist_info = db.conn.execute("""
        SELECT name, owner_name, id
        FROM playlists
        WHERE id = ?
    """, (playlist_id,)).fetchone()
    
    if not playlist_info:
        raise ValueError(f"Playlist {playlist_id} not found in database")
    
    # Fetch all tracks in playlist with match status
    tracks = db.conn.execute("""
        SELECT 
            t.name as track_name,
            t.artist,
            t.album,
            t.artist_id,
            t.album_id,
            t.duration_ms,
            t.year,
            t.id as track_id,
            m.file_id,
            l.path as file_path,
            CASE WHEN m.file_id IS NOT NULL THEN 1 ELSE 0 END as is_matched
        FROM playlist_tracks pt
        JOIN tracks t ON pt.track_id = t.id AND pt.provider = t.provider
        LEFT JOIN matches m ON t.id = m.track_id AND t.provider = m.provider
        LEFT JOIN library_files l ON m.file_id = l.id
        WHERE pt.playlist_id = ? AND pt.provider = ?
        ORDER BY pt.position
    """, (playlist_id, provider)).fetchall()
    
    # Write CSV
    csv_path = playlist_dir / f"{playlist_id}.csv"
    _write_csv(csv_path, tracks, playlist_info)
    
    # Write HTML
    html_path = playlist_dir / f"{playlist_id}.html"
    _write_html(html_path, tracks, playlist_info, provider, playlist_id)
    
    return (csv_path, html_path)


def _write_csv(csv_path: Path, tracks: list, playlist_info: dict) -> None:
    """Write playlist detail CSV report."""
    with csv_path.open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow([
            "#", "track_name", "artist", "album", "duration", "year",
            "status", "local_file"
        ])
        for idx, row in enumerate(tracks, 1):
            duration = format_duration(row['duration_ms'])
            status = "MATCHED" if row['is_matched'] else "UNMATCHED"
            local_file = row['file_path'] if row['file_path'] else ""
            
            w.writerow([
                idx,
                row['track_name'],
                row['artist'] or "",
                row['album'] or "",
                duration,
                row['year'] or "",
                status,
                local_file
            ])


def _write_html(
    html_path: Path,
    tracks: list,
    playlist_info: dict,
    provider: str,
    playlist_id: str
) -> None:
    """Write playlist detail HTML report."""
    links = get_link_generator(provider)
    html_rows = []
    
    matched_count = sum(1 for t in tracks if t['is_matched'])
    total_count = len(tracks)
    unmatched_count = total_count - matched_count
    coverage_pct = (matched_count / total_count * 100) if total_count > 0 else 0
    
    for idx, row in enumerate(tracks, 1):
        # Status badge
        if row['is_matched']:
            status_badge = '<span class="badge badge-success">MATCHED</span>'
        else:
            status_badge = '<span class="badge badge-danger">UNMATCHED</span>'
        
        # Track link
        track_url = links.track_url(row['track_id'])
        track_link = f'<a href="{track_url}" target="_blank" title="Open in {provider.title()}">{row["track_name"]}</a>'
        
        # Artist link (if artist_id available)
        artist_text = row['artist'] or ""
        if artist_text and row['artist_id']:
            artist_url = links.artist_url(row['artist_id'])
            artist_link = f'<a href="{artist_url}" target="_blank" title="Open artist in {provider.title()}">{artist_text}</a>'
        else:
            artist_link = artist_text
        
        # Album link (if album_id available)
        album_text = row['album'] or ""
        if album_text and row['album_id']:
            album_url = links.album_url(row['album_id'])
            album_link = f'<a href="{album_url}" target="_blank" title="Open album in {provider.title()}">{album_text}</a>'
        else:
            album_link = album_text
        
        # Duration
        duration = format_duration(row['duration_ms'])
        
        # Local file path (shortened for display)
        local_file = ""
        if row['file_path']:
            short_path = shorten_path(row['file_path'], max_length=60)
            local_file = f'<span class="path-short" title="{row["file_path"]}">{short_path}</span>'
        
        html_rows.append([
            idx,
            track_link,
            artist_link,
            album_link,
            duration,
            row['year'] or "",
            status_badge,
            local_file
        ])
    
    # Create playlist header with Spotify link
    playlist_url = links.playlist_url(playlist_id)
    playlist_link = f'<a href="{playlist_url}" target="_blank" class="download-btn" style="margin-left: 10px;">🎵 Open in {provider.title()}</a>'
    
    description = (
        f'<div style="margin-bottom: 20px;">'
        f'<strong>Owner:</strong> {playlist_info["owner_name"] or "Unknown"} | '
        f'<strong>Total Tracks:</strong> {total_count} | '
        f'<strong>Matched:</strong> {matched_count} | '
        f'<strong>Unmatched:</strong> {unmatched_count} | '
        f'<strong>Coverage:</strong> {coverage_pct:.1f}%'
        f'{playlist_link}'
        f'</div>'
    )
    
    html_content = get_html_template(
        title=f"Playlist: {playlist_info['name']}",
        columns=["#", "Track", "Artist", "Album", "Duration", "Year", "Status", "Local File"],
        rows=html_rows,
        description=description,
        default_order=[[0, "asc"]],  # Sort by track number
        csv_filename=f"{playlist_id}.csv"
    )
    
    html_path.write_text(html_content, encoding='utf-8')
