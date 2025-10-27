"""Unmatched albums report generator."""

import csv
from pathlib import Path

from ...db import Database
from ...providers.links import get_link_generator
from ..html_templates import get_html_template


def write_unmatched_albums_report(db: Database, out_dir: Path, provider: str = "spotify") -> tuple[Path, Path]:
    """Write unmatched albums report to CSV and HTML.

    Args:
        db: Database instance
        out_dir: Output directory for reports
        provider: Provider name (default: spotify)

    Returns:
        Tuple of (csv_path, html_path)
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # Fetch unmatched albums data with IDs for linking
    # Use CTEs to compute counts first, then get distinct track names
    unmatched_album_rows = db.conn.execute(
        """
        WITH album_stats AS (
            -- Compute track and playlist counts per album
            SELECT
                t.artist,
                t.album,
                t.artist_id,
                t.album_id,
                COUNT(DISTINCT t.id) as track_count,
                COUNT(DISTINCT pt.playlist_id) as playlist_count
            FROM tracks t
            LEFT JOIN playlist_tracks pt ON t.id = pt.track_id AND t.provider = pt.provider
            WHERE t.id NOT IN (SELECT track_id FROM matches)
              AND t.album IS NOT NULL
              AND t.artist IS NOT NULL
            GROUP BY t.artist, t.album, t.artist_id, t.album_id
        ),
        distinct_tracks AS (
            -- Get distinct track names and IDs per album (no duplicates from playlist joins)
            SELECT DISTINCT
                t.artist,
                t.album,
                t.id as track_id,
                t.name as track_name
            FROM tracks t
            WHERE t.id NOT IN (SELECT track_id FROM matches)
              AND t.album IS NOT NULL
              AND t.artist IS NOT NULL
        )
        SELECT
            s.artist,
            s.album,
            s.artist_id,
            s.album_id,
            s.track_count,
            s.playlist_count,
            GROUP_CONCAT(d.track_name, '; ') as tracks,
            GROUP_CONCAT(d.track_id, '|') as track_ids
        FROM album_stats s
        JOIN distinct_tracks d ON s.artist = d.artist AND s.album = d.album
        GROUP BY s.artist, s.album, s.artist_id, s.album_id
        ORDER BY s.playlist_count DESC, s.track_count DESC, s.artist, s.album
    """
    ).fetchall()

    # Write CSV
    csv_path = out_dir / "unmatched_albums.csv"
    _write_csv(csv_path, unmatched_album_rows)

    # Write HTML
    html_path = out_dir / "unmatched_albums.html"
    _write_html(html_path, unmatched_album_rows, provider)

    return (csv_path, html_path)


def _write_csv(csv_path: Path, unmatched_album_rows: list) -> None:
    """Write unmatched albums CSV report."""
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["artist", "album", "track_count", "playlist_count", "tracks"])
        for row in unmatched_album_rows:
            w.writerow([row["artist"], row["album"], row["track_count"], row["playlist_count"], row["tracks"]])


def _write_html(html_path: Path, unmatched_album_rows: list, provider: str) -> None:
    """Write unmatched albums HTML report."""
    links = get_link_generator(provider)
    html_rows = []

    for row in unmatched_album_rows:
        # Create artist link if artist_id is available
        artist_text = row["artist"] or ""
        if artist_text and row["artist_id"]:
            artist_url = links.artist_url(row["artist_id"])
            artist_link = f'<a href="{artist_url}" target="_blank" title="Open in {provider.title()}">{artist_text}</a>'
        else:
            artist_link = artist_text

        # Create album link if album_id is available
        album_text = row["album"] or ""
        if album_text and row["album_id"]:
            album_url = links.album_url(row["album_id"])
            album_link = f'<a href="{album_url}" target="_blank" title="Open in {provider.title()}">{album_text}</a>'
        else:
            album_link = album_text

        # Create track links for the track list
        tracks_text = row["tracks"] or ""
        track_ids = (row["track_ids"] or "").split("|") if row["track_ids"] else []
        track_names = tracks_text.split("; ") if tracks_text else []

        # Create clickable track list if we have IDs
        if track_ids and len(track_ids) == len(track_names):
            track_links = []
            for track_id, track_name in zip(track_ids, track_names):
                if track_id and track_name:
                    track_url = links.track_url(track_id)
                    track_links.append(
                        f'<a href="{track_url}" target="_blank" title="Open in {provider.title()}">{track_name}</a>'
                    )
                else:
                    track_links.append(track_name)
            tracks_display = "; ".join(track_links)
        else:
            tracks_display = tracks_text

        html_rows.append([artist_link, album_link, row["track_count"], row["playlist_count"], tracks_display])

    html_content = get_html_template(
        title="Unmatched Albums",
        columns=["Artist", "Album", "Track Count", "Playlists", "Tracks"],
        rows=html_rows,
        description=f"Total unmatched albums: {len(unmatched_album_rows):,}",
        default_order=[[3, "desc"], [2, "desc"], [0, "asc"]],  # Sort by Playlists, Tracks, Artist
        csv_filename="unmatched_albums.csv",
        active_page="unmatched_albums",
    )

    html_path.write_text(html_content, encoding="utf-8")
