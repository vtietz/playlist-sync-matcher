"""Matched tracks report generator."""

import csv
from pathlib import Path

from ...db import Database
from ...providers.links import get_link_generator
from ..formatting import (
    format_badge,
    format_duration,
    get_confidence_badge_class,
    shorten_path
)
from ..html_templates import get_html_template
from .base import format_liked, format_playlist_count


def write_matched_tracks_report(
    db: Database,
    out_dir: Path,
    provider: str = 'spotify'
) -> tuple[Path, Path]:
    """Write matched tracks report to CSV and HTML.
    
    Args:
        db: Database instance
        out_dir: Output directory for reports
        provider: Provider name (default: spotify)
    
    Returns:
        Tuple of (csv_path, html_path)
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Fetch matched tracks data
    matched_rows = db.conn.execute("""
        SELECT 
            m.track_id,
            m.file_id,
            m.method,
            m.score,
            t.name as track_name,
            t.artist as track_artist,
            t.album as track_album,
            t.artist_id as track_artist_id,
            t.album_id as track_album_id,
            t.duration_ms as track_duration_ms,
            t.year as track_year,
            l.path as file_path,
            l.artist as file_artist,
            l.title as file_title,
            l.album as file_album,
            l.duration as file_duration_sec,
            l.year as file_year,
            COUNT(DISTINCT pt.playlist_id) as playlist_count,
            EXISTS(
                SELECT 1 FROM liked_tracks lt
                WHERE lt.track_id = m.track_id AND lt.provider = m.provider
            ) as is_liked
        FROM matches m
        JOIN tracks t ON m.track_id = t.id AND m.provider = t.provider
        JOIN library_files l ON m.file_id = l.id
        LEFT JOIN playlist_tracks pt ON m.track_id = pt.track_id AND m.provider = pt.provider
        GROUP BY m.track_id, m.file_id, m.provider
        ORDER BY m.score DESC
    """).fetchall()
    
    # Write CSV
    csv_path = out_dir / "matched_tracks.csv"
    _write_csv(csv_path, matched_rows)
    
    # Write HTML
    html_path = out_dir / "matched_tracks.html"
    _write_html(html_path, matched_rows, provider)
    
    return (csv_path, html_path)


def _extract_confidence(method_str: str) -> str:
    """Extract confidence from method string like 'MatchConfidence.CERTAIN' or 'score:HIGH:89.50'."""
    if not method_str:
        return "UNKNOWN"
    
    # Handle enum format: "MatchConfidence.CERTAIN" -> "CERTAIN"
    if "MatchConfidence." in method_str:
        return method_str.split(".")[-1]
    
    # Handle old score format: "score:HIGH:89.50" -> "HIGH"
    if ':' in method_str:
        parts = method_str.split(':')
        if len(parts) >= 2:
            return parts[1]
    
    return "UNKNOWN"


def _write_csv(csv_path: Path, matched_rows: list) -> None:
    """Write matched tracks CSV report."""
    with csv_path.open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow([
            "track_name", "track_artist", "track_album", "track_duration", "track_year",
            "file_path", "file_title", "file_artist", "file_album", "file_duration",
            "score", "confidence", "playlists", "liked"
        ])
        for row in matched_rows:
            confidence = _extract_confidence(row['method'])
            track_duration = format_duration(duration_ms=row['track_duration_ms'])
            file_duration = format_duration(duration_sec=row['file_duration_sec'])
            w.writerow([
                row['track_name'], row['track_artist'], row['track_album'],
                track_duration, row['track_year'] or "",
                row['file_path'], row['file_title'], row['file_artist'],
                row['file_album'], file_duration,
                f"{row['score']:.2f}", confidence,
                format_playlist_count(row['playlist_count']),
                format_liked(row['is_liked'])
            ])


def _write_html(html_path: Path, matched_rows: list, provider: str) -> None:
    """Write matched tracks HTML report."""
    links = get_link_generator(provider)
    html_rows = []
    
    for row in matched_rows:
        confidence = _extract_confidence(row['method'])
        confidence_badge_class = get_confidence_badge_class(confidence)
        confidence_badge = format_badge(confidence, confidence_badge_class)
        
        # Create provider links for track, artist, and album
        track_url = links.track_url(row['track_id'])
        track_link = f'<a href="{track_url}" target="_blank" title="Open in {provider.title()}">{row["track_name"] or "Unknown"}</a>'
        
        # Artist link (if artist_id available)
        if row['track_artist_id']:
            artist_url = links.artist_url(row['track_artist_id'])
            artist_link = f'<a href="{artist_url}" target="_blank" title="Open in {provider.title()}">{row["track_artist"] or "Unknown"}</a>'
        else:
            artist_link = row['track_artist'] or ""
        
        # Album link (if album_id available)
        if row['track_album_id']:
            album_url = links.album_url(row['track_album_id'])
            album_link = f'<a href="{album_url}" target="_blank" title="Open in {provider.title()}">{row["track_album"] or "Unknown"}</a>'
        else:
            album_link = row['track_album'] or ""
        
        # Format durations
        track_duration = format_duration(duration_ms=row['track_duration_ms'])
        file_duration = format_duration(duration_sec=row['file_duration_sec'])
        
        # Shorten file path
        short_path = shorten_path(row['file_path'], max_length=60)
        path_display = f'<span class="path-short" title="{row["file_path"]}">{short_path}</span>'
        
        # Playlist count and liked status
        playlist_display = format_playlist_count(row['playlist_count'])
        liked_display = format_liked(row['is_liked'])
        
        html_rows.append([
            track_link,
            artist_link,
            album_link,
            track_duration,
            row['track_year'] or "",
            path_display,
            row['file_title'] or "",
            row['file_artist'] or "",
            row['file_album'] or "",
            file_duration,
            f"{row['score']:.2f}",
            playlist_display,
            liked_display,
            confidence_badge
        ])
    
    html_content = get_html_template(
        title="Matched Tracks",
        columns=[
            "Track", "Artist", "Album", "Duration", "Year",
            "File", "Local Title", "Local Artist", "Local Album", "Local Duration",
            "Score", "Playlists", "Liked", "Status"
        ],
        rows=html_rows,
        description=f"Total matched tracks: {len(matched_rows):,}",
        default_order=[[11, "asc"], [10, "desc"]],  # Sort by Status, then Score DESC
        csv_filename="matched_tracks.csv",
        active_page="matched_tracks"
    )
    
    html_path.write_text(html_content, encoding='utf-8')
