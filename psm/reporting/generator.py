from __future__ import annotations
from pathlib import Path
from typing import Iterable, Any, TYPE_CHECKING
import csv
import logging

from .html_templates import get_html_template, get_index_template
from .formatting import (
    format_duration, shorten_path, get_confidence_badge_class, 
    format_badge, get_quality_badge_class, get_quality_status_text,
    get_coverage_badge_class, get_coverage_status_text, format_playlist_count_badge
)
from ..providers.links import get_link_generator

if TYPE_CHECKING:
    from ..services.analysis_service import QualityReport
    from ..db import Database

logger = logging.getLogger(__name__)


def write_missing_tracks(rows: Iterable, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "missing_tracks.csv"
    with path.open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(["track_id", "name", "artist", "album"])
        for r in rows:
            w.writerow([r['id'], r['name'], r['artist'], r['album']])
    return path


def compute_album_completeness(db) -> Iterable[dict[str, Any]]:
    """Return iterable of album completeness stats.

    Stats per (artist, album): total_spotify_tracks, matched_local, missing_count, percent_complete, status.
    """
    # Gather all Spotify tracks that have album & artist
    album_rows = db.conn.execute(
        """
        SELECT artist, album, COUNT(*) as total
        FROM tracks
        WHERE album IS NOT NULL AND artist IS NOT NULL
        GROUP BY artist, album
        """
    ).fetchall()
    # Pre-compute matched track_ids
    matched_rows = db.conn.execute("SELECT DISTINCT track_id FROM matches").fetchall()
    matched_set = {r['track_id'] for r in matched_rows}
    for row in album_rows:
        artist = row['artist']
        album = row['album']
        total = row['total']
        # Count matched in this album
        matched_in_album = db.conn.execute(
            "SELECT COUNT(*) FROM tracks WHERE artist=? AND album=? AND id IN (SELECT track_id FROM matches)",
            (artist, album),
        ).fetchone()[0]
        missing = total - matched_in_album
        percent = (matched_in_album / total) * 100.0 if total else 0.0
        if matched_in_album == 0:
            status = 'MISSING'
        elif missing == 0:
            status = 'COMPLETE'
        else:
            status = 'PARTIAL'
        yield {
            'artist': artist,
            'album': album,
            'total': total,
            'matched': matched_in_album,
            'missing': missing,
            'percent_complete': round(percent, 2),
            'status': status,
        }


def write_album_completeness(db, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "album_completeness.csv"
    rows = list(compute_album_completeness(db))
    # Sort: status priority (MISSING, PARTIAL, COMPLETE) then artist/album
    status_order = {'MISSING': 0, 'PARTIAL': 1, 'COMPLETE': 2}
    rows.sort(key=lambda r: (status_order.get(r['status'], 99), r['artist'] or '', r['album'] or ''))
    with path.open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(["artist", "album", "total", "matched", "missing", "percent_complete", "status"])
        for r in rows:
            w.writerow([r['artist'], r['album'], r['total'], r['matched'], r['missing'], r['percent_complete'], r['status']])
    return path


# ============================================================================
# Enhanced Analysis Reports (CSV + HTML)
# ============================================================================

def write_analysis_quality_reports(report: QualityReport, out_dir: Path, min_bitrate_kbps: int = 320) -> tuple[Path, Path]:
    """Write metadata quality analysis to CSV and HTML.
    
    Args:
        report: QualityReport from analysis_service
        out_dir: Output directory for reports
        min_bitrate_kbps: Bitrate threshold used
    
    Returns:
        Tuple of (csv_path, html_path)
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Prepare data rows with individual columns for each metadata field
    rows = []
    for issue in report.issues:
        # Check individual metadata fields
        has_artist = "artist" not in issue.missing_fields
        has_title = "title" not in issue.missing_fields
        has_album = "album" not in issue.missing_fields
        has_year = "year" not in issue.missing_fields
        
        # Count missing fields
        missing_count = len(issue.missing_fields)
        
        # Bitrate handling
        bitrate_num = issue.bitrate_kbps if issue.bitrate_kbps else 0
        
        rows.append({
            'path': issue.path,
            'has_artist': has_artist,
            'has_title': has_title,
            'has_album': has_album,
            'has_year': has_year,
            'missing_count': missing_count,
            'bitrate': bitrate_num,
        })
    
    # Write CSV - Standardized column order
    csv_path = out_dir / "metadata_quality.csv" 
    with csv_path.open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(["file_path", "title", "artist", "album", "year", "bitrate_kbps", "quality_status"])
        for row in rows:
            quality_status = get_quality_status_text(row['missing_count'])
            w.writerow([
                row['path'],
                "✓" if row['has_title'] else "✗",
                "✓" if row['has_artist'] else "✗", 
                "✓" if row['has_album'] else "✗",
                "✓" if row['has_year'] else "✗",
                row['bitrate'],
                quality_status
            ])
    
    # HTML - Standardized structure with shortened paths and quality badges
    html_rows = []
    for row in rows:
        # Shorten file path for display
        short_path = shorten_path(row['path'], max_length=60)
        path_display = f'<span class="path-short" title="{row["path"]}">{short_path}</span>'
        
        # Create quality status badge
        quality_status = get_quality_status_text(row['missing_count'])
        quality_badge_class = get_quality_badge_class(row['missing_count'])
        quality_badge = format_badge(quality_status, quality_badge_class)
        
        html_rows.append([
            path_display,                         # File (shortened)
            '<span class="check-yes">✓</span>' if row['has_title'] else '<span class="check-no">✗</span>',   # Title
            '<span class="check-yes">✓</span>' if row['has_artist'] else '<span class="check-no">✗</span>',  # Artist
            '<span class="check-yes">✓</span>' if row['has_album'] else '<span class="check-no">✗</span>',   # Album
            '<span class="check-yes">✓</span>' if row['has_year'] else '<span class="check-no">✗</span>',    # Year
            f"{row['bitrate']} kbps" if row['bitrate'] > 0 else "N/A",  # Bitrate
            quality_badge                         # Status (quality badge)
        ])
    
    stats = report.get_summary_stats()
    description = (
        f"Total files: {stats['total_files']:,} | "
        f"Missing artist: {stats['missing_artist']} ({stats['missing_artist_pct']}%) | "
        f"Missing title: {stats['missing_title']} ({stats['missing_title_pct']}%) | "
        f"Missing album: {stats['missing_album']} ({stats['missing_album_pct']}%) | "
        f"Missing year: {stats['missing_year']} ({stats['missing_year_pct']}%) | "
        f"Low bitrate (<{min_bitrate_kbps}kbps): {stats['low_bitrate_count']} ({stats['low_bitrate_pct']}%)"
    )
    
    # Default sort: Status (quality), then bitrate
    html_content = get_html_template(
        title="Metadata Quality Analysis",
        columns=["File", "Title", "Artist", "Album", "Year", "Bitrate", "Status"],
        rows=html_rows,
        description=description,
        default_order=[[6, "desc"], [5, "asc"]]  # Sort by Status (quality), then Bitrate ASC
    )
    
    html_path = out_dir / "metadata_quality.html"
    html_path.write_text(html_content, encoding='utf-8')
    
    return (csv_path, html_path)


# ============================================================================
# Enhanced Match Reports (CSV + HTML)
# ============================================================================

def write_match_reports(db: Database, out_dir: Path) -> dict[str, tuple[Path, Path]]:
    """Write comprehensive match reports (matched, unmatched tracks, unmatched albums).
    
    Args:
        db: Database instance
        out_dir: Output directory for reports
    
    Returns:
        Dict with keys 'matched', 'unmatched_tracks', 'unmatched_albums' pointing to (csv_path, html_path) tuples
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    reports = {}
    
    # Get provider from database (default to spotify)
    provider_row = db.conn.execute("SELECT DISTINCT provider FROM tracks LIMIT 1").fetchone()
    provider = provider_row['provider'] if provider_row else 'spotify'
    links = get_link_generator(provider)
    
    # ---------------------------------------------------------------
    # 1. Matched Tracks Report (with confidence and match details)
    # ---------------------------------------------------------------
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
            l.year as file_year
        FROM matches m
        JOIN tracks t ON m.track_id = t.id
        JOIN library_files l ON m.file_id = l.id
        ORDER BY m.score DESC
    """).fetchall()
    
    # Extract confidence from method field (e.g., "MatchConfidence.CERTAIN" -> "CERTAIN" or "score:HIGH:89.50" -> "HIGH")
    def extract_confidence(method_str):
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
    
    # CSV - Standardized column order
    csv_path = out_dir / "matched_tracks.csv"
    with csv_path.open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow([
            "track_name", "track_artist", "track_album", "track_duration", "track_year",
            "file_path", "file_title", "file_artist", "file_album", "file_duration",
            "score", "confidence"
        ])
        for row in matched_rows:
            confidence = extract_confidence(row['method'])
            track_duration = format_duration(duration_ms=row['track_duration_ms'])
            file_duration = format_duration(duration_sec=row['file_duration_sec'])
            w.writerow([
                row['track_name'], row['track_artist'], row['track_album'], 
                track_duration, row['track_year'] or "",
                row['file_path'], row['file_title'], row['file_artist'], 
                row['file_album'], file_duration,
                f"{row['score']:.2f}", confidence
            ])
    
    # HTML - Standardized structure with entity linking and shortened paths
    html_rows = []
    for row in matched_rows:
        confidence = extract_confidence(row['method'])
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
        
        # Shorten file path (could be enhanced with base_dir detection)
        short_path = shorten_path(row['file_path'], max_length=60)
        path_display = f'<span class="path-short" title="{row["file_path"]}">{short_path}</span>'
        
        html_rows.append([
            track_link,                                    # Track (linked)
            artist_link,                                   # Artist (linked if ID available)
            album_link,                                    # Album (linked if ID available)
            track_duration,                               # Duration
            row['track_year'] or "",                      # Year
            path_display,                                 # File (shortened)
            row['file_title'] or "",                      # Local Title
            row['file_artist'] or "",                     # Local Artist
            row['file_album'] or "",                      # Local Album
            file_duration,                                # Local Duration
            f"{row['score']:.2f}",                        # Score
            confidence_badge                              # Status (last column)
        ])
    
    html_content = get_html_template(
        title="Matched Tracks",
        columns=[
            "Track", "Artist", "Album", "Duration", "Year",
            "File", "Local Title", "Local Artist", "Local Album", "Local Duration",
            "Score", "Status"
        ],
        rows=html_rows,
        description=f"Total matched tracks: {len(matched_rows):,}",
        default_order=[[11, "asc"], [10, "desc"]]  # Sort by Status (confidence), then Score DESC
    )
    
    html_path = out_dir / "matched_tracks.html"
    html_path.write_text(html_content, encoding='utf-8')
    
    reports['matched'] = (csv_path, html_path)
    
    # ---------------------------------------------------------------
    # 2. Unmatched Tracks Report (with playlist popularity)
    # ---------------------------------------------------------------
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
            COUNT(DISTINCT pt.playlist_id) as playlist_count
        FROM tracks t
        LEFT JOIN playlist_tracks pt ON t.id = pt.track_id
        WHERE t.id NOT IN (SELECT track_id FROM matches)
        GROUP BY t.id, t.name, t.artist, t.album, t.artist_id, t.album_id, t.year
        ORDER BY playlist_count DESC, t.artist, t.album, t.name
    """).fetchall()
    
    # CSV - Standardized column order  
    csv_path = out_dir / "unmatched_tracks.csv"
    with csv_path.open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(["track_name", "artist", "album", "duration", "year", "playlists", "priority"])
        for row in unmatched_rows:
            duration = format_duration(duration_ms=row['duration_ms'])
            playlist_count = row['playlist_count']
            # Priority based on playlist count
            if playlist_count >= 5:
                priority = "HIGH"
            elif playlist_count >= 2:
                priority = "MEDIUM"
            elif playlist_count == 1:
                priority = "LOW"
            else:
                priority = "NONE"
            
            w.writerow([
                row['name'], row['artist'], row['album'], 
                duration, row['year'] or "", playlist_count, priority
            ])
    
    # HTML - Standardized structure with entity linking
    html_rows = []
    for row in unmatched_rows:
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
        
        # Create priority badge based on playlist count
        priority_badge = format_playlist_count_badge(row['playlist_count'])
        
        html_rows.append([
            track_link,                           # Track (linked)
            artist_link,                          # Artist (linked if ID available)
            album_link,                           # Album (linked if ID available)
            duration,                             # Duration
            row['year'] or "",                    # Year
            row['playlist_count'],                # Playlists count
            priority_badge                        # Status (priority based on playlists)
        ])
    
    html_content = get_html_template(
        title="Unmatched Tracks",
        columns=["Track", "Artist", "Album", "Duration", "Year", "Playlists", "Status"],
        rows=html_rows,
        description=f"Total unmatched tracks: {len(unmatched_rows):,}",
        default_order=[[6, "desc"], [5, "desc"]]  # Sort by Status (priority), then Playlists DESC
    )
    
    html_path = out_dir / "unmatched_tracks.html"
    html_path.write_text(html_content, encoding='utf-8')
    
    reports['unmatched_tracks'] = (csv_path, html_path)
    
    # ---------------------------------------------------------------
    # 3. Unmatched Albums Report (grouped by album with track counts and playlist popularity)
    # ---------------------------------------------------------------
    unmatched_album_rows = db.conn.execute("""
        SELECT 
            t.artist,
            t.album,
            COUNT(DISTINCT t.id) as track_count,
            COUNT(DISTINCT pt.playlist_id) as playlist_count,
            GROUP_CONCAT(t.name, '; ') as tracks
        FROM tracks t
        LEFT JOIN playlist_tracks pt ON t.id = pt.track_id
        WHERE t.id NOT IN (SELECT track_id FROM matches)
          AND t.album IS NOT NULL
          AND t.artist IS NOT NULL
        GROUP BY t.artist, t.album
        ORDER BY playlist_count DESC, track_count DESC, t.artist, t.album
    """).fetchall()
    
    # CSV
    csv_path = out_dir / "unmatched_albums.csv"
    with csv_path.open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(["artist", "album", "track_count", "playlist_count", "tracks"])
        for row in unmatched_album_rows:
            w.writerow([row['artist'], row['album'], row['track_count'], row['playlist_count'], row['tracks']])
    
    # HTML
    html_rows = [[
        row['artist'], 
        row['album'], 
        row['track_count'], 
        row['playlist_count'],
        row['tracks']
    ] for row in unmatched_album_rows]
    
    html_content = get_html_template(
        title="Unmatched Albums",
        columns=["Artist", "Album", "Track Count", "Playlists", "Tracks"],
        rows=html_rows,
        description=f"Total unmatched albums: {len(unmatched_album_rows):,}",
        default_order=[[3, "desc"], [2, "desc"], [0, "asc"]]  # Sort by Playlist Count DESC, Track Count DESC, then Artist ASC
    )
    
    html_path = out_dir / "unmatched_albums.html"
    html_path.write_text(html_content, encoding='utf-8')
    
    reports['unmatched_albums'] = (csv_path, html_path)
    
    # ---------------------------------------------------------------
    # 4. Playlist Coverage Report (shows match % for each playlist)
    # ---------------------------------------------------------------
    playlist_coverage_rows = db.conn.execute("""
        SELECT 
            p.id as playlist_id,
            p.name as playlist_name,
            p.owner_name,
            COUNT(DISTINCT pt.track_id) as total_tracks,
            COUNT(DISTINCT m.track_id) as matched_tracks,
            ROUND(CAST(COUNT(DISTINCT m.track_id) AS FLOAT) / COUNT(DISTINCT pt.track_id) * 100, 2) as coverage_percent
        FROM playlists p
        JOIN playlist_tracks pt ON p.id = pt.playlist_id
        LEFT JOIN matches m ON pt.track_id = m.track_id
        GROUP BY p.id, p.name, p.owner_name
        ORDER BY coverage_percent ASC, total_tracks DESC
    """).fetchall()
    
    # CSV
    csv_path = out_dir / "playlist_coverage.csv"
    with csv_path.open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(["playlist_id", "playlist_name", "owner", "total_tracks", "matched_tracks", "missing_tracks", "coverage_percent"])
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
    
    # HTML - add visual coverage bars and playlist links
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
        
        # Add clickable playlist link
        playlist_url = links.playlist_url(row['playlist_id'])
        playlist_link = f'<a href="{playlist_url}" target="_blank" title="Open in {provider.title()}">{row["playlist_name"]}</a>'
        
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
        default_order=[[5, "asc"], [2, "desc"]]  # Sort by Coverage ASC (worst first), then Total Tracks DESC
    )
    
    html_path = out_dir / "playlist_coverage.html"
    html_path.write_text(html_content, encoding='utf-8')
    
    reports['playlist_coverage'] = (csv_path, html_path)
    
    return reports


__all__ = [
    "write_missing_tracks", 
    "write_album_completeness", 
    "compute_album_completeness",
    "write_analysis_quality_reports",
    "write_match_reports",
    "write_index_page",
]


def write_index_page(out_dir: Path, db: "Database | None" = None) -> Path:
    """Generate an index.html page with links to all available reports.
    
    Args:
        out_dir: Output directory containing report files
        db: Optional database instance to get live counts
    
    Returns:
        Path to generated index.html file
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Collect available reports
    reports = {
        'Match Reports': {},
        'Analysis Reports': {},
    }
    
    # Check which match reports exist
    if (out_dir / "matched_tracks.html").exists():
        count = None
        if db:
            count = db.conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
        reports['Match Reports']['matched_tracks'] = (
            "Successfully matched Spotify tracks to local files",
            "matched_tracks.html",
            count
        )
    
    if (out_dir / "unmatched_tracks.html").exists():
        count = None
        if db:
            count = db.conn.execute(
                "SELECT COUNT(*) FROM tracks WHERE id NOT IN (SELECT track_id FROM matches)"
            ).fetchone()[0]
        reports['Match Reports']['unmatched_tracks'] = (
            "Spotify tracks not found in local library",
            "unmatched_tracks.html",
            count
        )
    
    if (out_dir / "unmatched_albums.html").exists():
        count = None
        if db:
            count = db.conn.execute(
                """SELECT COUNT(DISTINCT album) FROM tracks 
                   WHERE id NOT IN (SELECT track_id FROM matches) 
                   AND album IS NOT NULL"""
            ).fetchone()[0]
        reports['Match Reports']['unmatched_albums'] = (
            "Albums with missing tracks grouped by artist",
            "unmatched_albums.html",
            count
        )
    
    if (out_dir / "playlist_coverage.html").exists():
        count = None
        if db:
            count = db.conn.execute("SELECT COUNT(*) FROM playlists").fetchone()[0]
        reports['Match Reports']['playlist_coverage'] = (
            "Coverage statistics for each playlist",
            "playlist_coverage.html",
            count
        )
    
    # Check which analysis reports exist
    if (out_dir / "metadata_quality.html").exists():
        count = None
        # Count is from the report itself (files with missing metadata)
        reports['Analysis Reports']['metadata_quality'] = (
            "Local files with missing or low-quality metadata",
            "metadata_quality.html",
            count
        )
    
    # Generate index page
    html_content = get_index_template(reports)
    index_path = out_dir / "index.html"
    index_path.write_text(html_content, encoding='utf-8')
    
    return index_path
