"""Unmatched albums report generator."""

import csv
from pathlib import Path

from ...db import Database
from ..html_templates import get_html_template


def write_unmatched_albums_report(
    db: Database,
    out_dir: Path
) -> tuple[Path, Path]:
    """Write unmatched albums report to CSV and HTML.
    
    Args:
        db: Database instance
        out_dir: Output directory for reports
    
    Returns:
        Tuple of (csv_path, html_path)
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Fetch unmatched albums data
    # Use CTEs to compute counts first, then get distinct track names
    unmatched_album_rows = db.conn.execute("""
        WITH album_stats AS (
            -- Compute track and playlist counts per album
            SELECT 
                t.artist,
                t.album,
                COUNT(DISTINCT t.id) as track_count,
                COUNT(DISTINCT pt.playlist_id) as playlist_count
            FROM tracks t
            LEFT JOIN playlist_tracks pt ON t.id = pt.track_id AND t.provider = pt.provider
            WHERE t.id NOT IN (SELECT track_id FROM matches)
              AND t.album IS NOT NULL
              AND t.artist IS NOT NULL
            GROUP BY t.artist, t.album
        ),
        distinct_tracks AS (
            -- Get distinct track names per album (no duplicates from playlist joins)
            SELECT DISTINCT
                t.artist,
                t.album,
                t.name as track_name
            FROM tracks t
            WHERE t.id NOT IN (SELECT track_id FROM matches)
              AND t.album IS NOT NULL
              AND t.artist IS NOT NULL
        )
        SELECT 
            s.artist,
            s.album,
            s.track_count,
            s.playlist_count,
            GROUP_CONCAT(d.track_name, '; ') as tracks
        FROM album_stats s
        JOIN distinct_tracks d ON s.artist = d.artist AND s.album = d.album
        GROUP BY s.artist, s.album
        ORDER BY s.playlist_count DESC, s.track_count DESC, s.artist, s.album
    """).fetchall()
    
    # Write CSV
    csv_path = out_dir / "unmatched_albums.csv"
    _write_csv(csv_path, unmatched_album_rows)
    
    # Write HTML
    html_path = out_dir / "unmatched_albums.html"
    _write_html(html_path, unmatched_album_rows)
    
    return (csv_path, html_path)


def _write_csv(csv_path: Path, unmatched_album_rows: list) -> None:
    """Write unmatched albums CSV report."""
    with csv_path.open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(["artist", "album", "track_count", "playlist_count", "tracks"])
        for row in unmatched_album_rows:
            w.writerow([
                row['artist'],
                row['album'],
                row['track_count'],
                row['playlist_count'],
                row['tracks']
            ])


def _write_html(html_path: Path, unmatched_album_rows: list) -> None:
    """Write unmatched albums HTML report."""
    html_rows = []
    for row in unmatched_album_rows:
        html_rows.append([
            row['artist'],
            row['album'],
            row['track_count'],
            row['playlist_count'],
            row['tracks']
        ])
    
    html_content = get_html_template(
        title="Unmatched Albums",
        columns=["Artist", "Album", "Track Count", "Playlists", "Tracks"],
        rows=html_rows,
        description=f"Total unmatched albums: {len(unmatched_album_rows):,}",
        default_order=[[3, "desc"], [2, "desc"], [0, "asc"]],  # Sort by Playlists, Tracks, Artist
        csv_filename="unmatched_albums.csv",
        active_page="unmatched_albums"
    )
    
    html_path.write_text(html_content, encoding='utf-8')
