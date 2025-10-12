"""Unmatched tracks report generator."""

import csv
from pathlib import Path

from ...db import Database
from ...providers.links import get_link_generator
from ..formatting import (
    format_duration,
    format_playlist_count_simple
)
from ..html_templates import get_html_template
from .base import format_liked


def write_unmatched_tracks_report(
    db: Database,
    out_dir: Path,
    provider: str = 'spotify'
) -> tuple[Path, Path]:
    """Write unmatched tracks report to CSV and HTML.

    Args:
        db: Database instance
        out_dir: Output directory for reports
        provider: Provider name (default: spotify)

    Returns:
        Tuple of (csv_path, html_path)
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # Fetch unmatched tracks data
    unmatched_rows = db.conn.execute("""
        SELECT
            t.id as track_id,
            t.name,
            t.artist,
            t.album,
            t.artist_id,
            t.album_id,
            t.duration_ms,
            t.year,
            COUNT(DISTINCT pt.playlist_id) as playlist_count,
            EXISTS(
                SELECT 1 FROM liked_tracks lt
                WHERE lt.track_id = t.id AND lt.provider = t.provider
            ) as is_liked
        FROM tracks t
        LEFT JOIN playlist_tracks pt ON t.id = pt.track_id AND t.provider = pt.provider
        WHERE t.id NOT IN (SELECT track_id FROM matches WHERE provider = t.provider)
        GROUP BY t.id, t.name, t.artist, t.album, t.artist_id, t.album_id, t.year, t.provider
        ORDER BY playlist_count DESC, t.artist, t.album, t.name
    """).fetchall()

    # Write CSV
    csv_path = out_dir / "unmatched_tracks.csv"
    _write_csv(csv_path, unmatched_rows)

    # Write HTML
    html_path = out_dir / "unmatched_tracks.html"
    _write_html(html_path, unmatched_rows, provider)

    return (csv_path, html_path)


def _write_csv(csv_path: Path, unmatched_rows: list) -> None:
    """Write unmatched tracks CSV report."""
    with csv_path.open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(["track_id", "track_name", "artist", "album", "duration", "year", "playlists", "liked"])
        for row in unmatched_rows:
            duration = format_duration(duration_ms=row['duration_ms'])

            w.writerow([
                row['track_id'],
                row['name'], row['artist'], row['album'],
                duration, row['year'] or "", row['playlist_count'],
                format_liked(row['is_liked'])
            ])


def _write_html(html_path: Path, unmatched_rows: list, provider: str) -> None:
    """Write unmatched tracks HTML report."""
    links = get_link_generator(provider)
    html_rows = []

    for row in unmatched_rows:
        # Track ID (monospaced for easy copying)
        track_id_display = f'<code style="font-size: 0.85em">{row["track_id"]}</code>'

        # Create provider links for track, artist, and album
        track_url = links.track_url(row['track_id'])
        track_link = f'<a href="{track_url}" target="_blank" title="Open in {provider.title()}">{row["name"] or "Unknown"}</a>'

        # Artist link (if artist_id available)
        if row['artist_id']:
            artist_url = links.artist_url(row['artist_id'])
            artist_link = f'<a href="{artist_url}" target="_blank" title="Open in {provider.title()}">{row["artist"] or "Unknown"}</a>'
        else:
            artist_link = row['artist'] or ""

        # Album link (if album_id available)
        if row['album_id']:
            album_url = links.album_url(row['album_id'])
            album_link = f'<a href="{album_url}" target="_blank" title="Open in {provider.title()}">{row["album"] or "Unknown"}</a>'
        else:
            album_link = row['album'] or ""

        # Format duration
        duration = format_duration(duration_ms=row['duration_ms'])

        # Simple colored badge with just the number
        playlist_badge = format_playlist_count_simple(row['playlist_count'])

        # Liked status
        liked_display = format_liked(row['is_liked'])

        html_rows.append([
            track_id_display,
            track_link,
            artist_link,
            album_link,
            duration,
            row['year'] or "",
            playlist_badge,
            liked_display
        ])

    html_content = get_html_template(
        title="Unmatched Tracks",
        columns=["Track ID", "Track", "Artist", "Album", "Duration", "Year", "Playlists", "Liked"],
        rows=html_rows,
        description=f"Total unmatched tracks: {len(unmatched_rows):,}",
        default_order=[[6, "desc"]],  # Sort by Playlists DESC (column index shifted by 1)
        csv_filename="unmatched_tracks.csv",
        active_page="unmatched_tracks"
    )

    html_path.write_text(html_content, encoding='utf-8')
