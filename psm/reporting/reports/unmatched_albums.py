"""Unmatched albums report generator."""

import csv
from pathlib import Path

from ...db import Database
from ..html_templates import get_html_template
from .base import format_liked


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
    unmatched_album_rows = db.conn.execute("""
        SELECT 
            t.artist,
            t.album,
            COUNT(DISTINCT t.id) as track_count,
            COUNT(DISTINCT pt.playlist_id) as playlist_count,
            MAX(
                CASE WHEN EXISTS(
                    SELECT 1 FROM liked_tracks lt 
                    WHERE lt.track_id = t.id AND lt.provider = t.provider
                ) THEN 1 ELSE 0 END
            ) as is_liked,
            GROUP_CONCAT(t.name, '; ') as tracks
        FROM tracks t
        LEFT JOIN playlist_tracks pt ON t.id = pt.track_id AND t.provider = pt.provider
        WHERE t.id NOT IN (SELECT track_id FROM matches)
          AND t.album IS NOT NULL
          AND t.artist IS NOT NULL
        GROUP BY t.artist, t.album
        ORDER BY playlist_count DESC, track_count DESC, t.artist, t.album
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
        w.writerow(["artist", "album", "track_count", "playlist_count", "liked", "tracks"])
        for row in unmatched_album_rows:
            w.writerow([
                row['artist'],
                row['album'],
                row['track_count'],
                row['playlist_count'],
                format_liked(row['is_liked']),
                row['tracks']
            ])


def _write_html(html_path: Path, unmatched_album_rows: list) -> None:
    """Write unmatched albums HTML report."""
    html_rows = []
    for row in unmatched_album_rows:
        liked_display = format_liked(row['is_liked'])
        html_rows.append([
            row['artist'],
            row['album'],
            row['track_count'],
            row['playlist_count'],
            liked_display,
            row['tracks']
        ])
    
    html_content = get_html_template(
        title="Unmatched Albums",
        columns=["Artist", "Album", "Track Count", "Playlists", "Liked", "Tracks"],
        rows=html_rows,
        description=f"Total unmatched albums: {len(unmatched_album_rows):,}",
        default_order=[[3, "desc"], [2, "desc"], [0, "asc"]]  # Sort by Playlists, Tracks, Artist
    )
    
    html_path.write_text(html_content, encoding='utf-8')
