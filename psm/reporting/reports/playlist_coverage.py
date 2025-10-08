"""Playlist coverage report generator."""

import csv
from pathlib import Path

from ...db import Database
from ...providers.links import get_link_generator
from ..html_templates import get_html_template


def write_playlist_coverage_report(
    db: Database,
    out_dir: Path,
    provider: str = 'spotify'
) -> tuple[Path, Path]:
    """Write playlist coverage report to CSV and HTML.
    
    Args:
        db: Database instance
        out_dir: Output directory for reports
        provider: Provider name (default: spotify)
    
    Returns:
        Tuple of (csv_path, html_path)
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Get owner name for liked songs (fallback to 'Me' if not available)
    try:
        owner_name = db.get_meta('current_user_name') or 'Me'
    except Exception:
        owner_name = 'Me'
    
    # Fetch playlist coverage data including virtual "Liked Songs" playlist
    playlist_coverage_rows = db.conn.execute("""
        -- Regular playlists
        SELECT 
            p.id as playlist_id,
            p.name as playlist_name,
            p.owner_name,
            COUNT(DISTINCT pt.track_id) as total_tracks,
            COUNT(DISTINCT m.track_id) as matched_tracks,
            ROUND(CAST(COUNT(DISTINCT m.track_id) AS FLOAT) / COUNT(DISTINCT pt.track_id) * 100, 2) as coverage_percent,
            0 as is_liked_songs
        FROM playlists p
        JOIN playlist_tracks pt ON p.id = pt.playlist_id
        LEFT JOIN matches m ON pt.track_id = m.track_id
        GROUP BY p.id, p.name, p.owner_name
        
        UNION ALL
        
        -- Virtual "Liked Songs" playlist (only if liked_tracks exist)
        SELECT 
            '_liked_songs_virtual' as playlist_id,
            'Liked Songs' as playlist_name,
            ? as owner_name,
            COUNT(DISTINCT lt.track_id) as total_tracks,
            COUNT(DISTINCT m.track_id) as matched_tracks,
            ROUND(CAST(COUNT(DISTINCT m.track_id) AS FLOAT) / COUNT(DISTINCT lt.track_id) * 100, 2) as coverage_percent,
            1 as is_liked_songs
        FROM liked_tracks lt
        LEFT JOIN matches m ON lt.track_id = m.track_id
        HAVING total_tracks > 0
        
        ORDER BY coverage_percent ASC, total_tracks DESC
    """, (owner_name,)).fetchall()
    
    # Write CSV
    csv_path = out_dir / "playlist_coverage.csv"
    _write_csv(csv_path, playlist_coverage_rows)
    
    # Write HTML
    html_path = out_dir / "playlist_coverage.html"
    _write_html(html_path, playlist_coverage_rows, provider)
    
    return (csv_path, html_path)


def _write_csv(csv_path: Path, playlist_coverage_rows: list) -> None:
    """Write playlist coverage CSV report."""
    with csv_path.open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow([
            "playlist_id", "playlist_name", "owner", "total_tracks",
            "matched_tracks", "missing_tracks", "coverage_percent"
        ])
        for row in playlist_coverage_rows:
            missing = row['total_tracks'] - row['matched_tracks']
            w.writerow([
                row['playlist_id'],
                row['playlist_name'],
                row['owner_name'] or 'Unknown',
                row['total_tracks'],
                row['matched_tracks'],
                missing,
                row['coverage_percent']
            ])


def _write_html(html_path: Path, playlist_coverage_rows: list, provider: str) -> None:
    """Write playlist coverage HTML report."""
    html_rows = []
    
    for row in playlist_coverage_rows:
        missing = row['total_tracks'] - row['matched_tracks']
        coverage = row['coverage_percent'] or 0
        
        # Color-coded badge based on coverage
        if coverage >= 90:
            badge_class = "badge-success"   # COMPLETE
        elif coverage >= 70:
            badge_class = "badge-primary"   # HIGH
        elif coverage >= 50:
            badge_class = "badge-warning"   # PARTIAL
        else:
            badge_class = "badge-danger"    # LOW
        
        # Link to detail page
        detail_url = f"playlists/{row['playlist_id']}.html"
        playlist_link = f'<a href="{detail_url}">{row["playlist_name"]}</a>'
        
        html_rows.append([
            playlist_link,
            row['owner_name'] or 'Unknown',
            row['total_tracks'],
            row['matched_tracks'],
            missing,
            f'<span class="badge {badge_class}">{coverage:.1f}%</span>'
        ])
    
    html_content = get_html_template(
        title="Playlist Coverage",
        columns=["Playlist Name", "Owner", "Total Tracks", "Matched", "Missing", "Coverage"],
        rows=html_rows,
        description=f"Total playlists: {len(playlist_coverage_rows):,}",
        default_order=[[5, "asc"], [2, "desc"]],  # Sort by Coverage ASC, Total Tracks DESC
        csv_filename="playlist_coverage.csv",
        active_page="playlist_coverage"
    )
    
    html_path.write_text(html_content, encoding='utf-8')
