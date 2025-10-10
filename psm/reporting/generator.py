from __future__ import annotations
from pathlib import Path
from typing import Iterable, Any, TYPE_CHECKING, List
import csv
import logging
import shutil

from .html_templates import get_html_template, get_index_template
from .formatting import (
    format_duration, shorten_path, get_confidence_badge_class, 
    format_badge, get_quality_badge_class, get_quality_status_text,
    get_coverage_badge_class, get_coverage_status_text, format_playlist_count_badge
)
from ..providers.links import get_link_generator
from .reports import (
    write_matched_tracks_report,
    write_unmatched_tracks_report,
    write_unmatched_albums_report,
    write_playlist_coverage_report,
    write_playlist_detail_report,
    write_metadata_quality_report,
    write_album_completeness_report,
)

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
    """Write album completeness report (wrapper for backward compatibility)."""
    return write_album_completeness_report(db, out_dir)


# ============================================================================
# Enhanced Analysis Reports (CSV + HTML)
# ============================================================================

def write_analysis_quality_reports(report: QualityReport, out_dir: Path, min_bitrate_kbps: int = 320) -> tuple[Path, Path]:
    """Write metadata quality analysis (wrapper for backward compatibility)."""
    return write_metadata_quality_report(report, out_dir, min_bitrate_kbps)


# ============================================================================
# Enhanced Match Reports (CSV + HTML)
# ============================================================================

def write_match_reports(
    db: Database, 
    out_dir: Path, 
    affected_playlist_ids: List[str] | None = None
) -> dict[str, tuple[Path, Path]]:
    """Write comprehensive match reports.
    
    Args:
        db: Database instance
        out_dir: Output directory for reports
        affected_playlist_ids: Optional list of playlist IDs that changed.
            If provided, only regenerates detail pages for these playlists
            (but always regenerates overview/index pages).
            If None, regenerates all reports (full rebuild).
    
    Returns:
        Dict with keys 'matched', 'unmatched_tracks', 'unmatched_albums', 'playlist_coverage'
        pointing to (csv_path, html_path) tuples
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine if this is an incremental update
    is_incremental = affected_playlist_ids is not None
    
    if is_incremental:
        logger.info(f"Incremental report update for {len(affected_playlist_ids)} playlist(s)")
        # In incremental mode, don't delete everything
        # Just ensure the playlists directory exists
        playlists_dir = out_dir / "playlists"
        playlists_dir.mkdir(exist_ok=True)
    else:
        logger.info("Full report generation - cleaning up old reports")
        # Full rebuild: clean up old reports to avoid stale data
        _cleanup_reports_directory(out_dir)
    
    # Get provider from database (default to spotify)
    provider_row = db.conn.execute("SELECT DISTINCT provider FROM tracks LIMIT 1").fetchone()
    provider = provider_row['provider'] if provider_row else 'spotify'
    
    # Always regenerate overview reports (they're fast and must be current)
    reports = {}
    reports['matched'] = write_matched_tracks_report(db, out_dir, provider)
    reports['unmatched_tracks'] = write_unmatched_tracks_report(db, out_dir, provider)
    reports['unmatched_albums'] = write_unmatched_albums_report(db, out_dir)
    reports['playlist_coverage'] = write_playlist_coverage_report(db, out_dir, provider)
    
    # Generate playlist detail pages (incremental or full)
    _generate_playlist_details(db, out_dir, provider, affected_playlist_ids)
    
    return reports


def _cleanup_reports_directory(out_dir: Path) -> None:
    """Clean up old report files to avoid stale data.
    
    Args:
        out_dir: Reports directory to clean
    """
    if not out_dir.exists():
        return
    
    logger.info(f"Cleaning up old reports in {out_dir}")
    
    # Remove all HTML and CSV files
    for pattern in ['*.html', '*.csv']:
        for file in out_dir.glob(pattern):
            try:
                file.unlink()
                logger.debug(f"Removed old report: {file.name}")
            except Exception as e:
                logger.warning(f"Failed to remove {file}: {e}")
    
    # Remove playlists subdirectory
    playlists_dir = out_dir / "playlists"
    if playlists_dir.exists():
        try:
            shutil.rmtree(playlists_dir)
            logger.debug(f"Removed old playlists directory")
        except Exception as e:
            logger.warning(f"Failed to remove playlists directory: {e}")


def _generate_playlist_details(
    db: Database, 
    out_dir: Path, 
    provider: str,
    affected_playlist_ids: List[str] | None = None
) -> None:
    """Generate detail page for each playlist.
    
    Args:
        db: Database instance
        out_dir: Reports directory
        provider: Provider name
        affected_playlist_ids: Optional list of playlist IDs to regenerate.
            If None, regenerates all playlists.
    """
    # Determine which playlists to regenerate
    if affected_playlist_ids is not None:
        # Incremental: only regenerate specific playlists
        playlists = []
        for playlist_id in affected_playlist_ids:
            playlist = db.conn.execute(
                "SELECT id, name FROM playlists WHERE id = ?", 
                (playlist_id,)
            ).fetchone()
            if playlist:
                playlists.append(playlist)
        
        logger.info(f"Regenerating detail pages for {len(playlists)} affected playlist(s)")
    else:
        # Full rebuild: regenerate all playlists
        playlists = db.conn.execute("SELECT id, name FROM playlists").fetchall()
        logger.info(f"Generating detail pages for {len(playlists)} playlists")
    
    for playlist in playlists:
        try:
            write_playlist_detail_report(db, out_dir, playlist['id'], provider)
            logger.debug(f"Generated detail page for playlist: {playlist['name']}")
        except Exception as e:
            logger.warning(f"Failed to generate detail page for playlist {playlist['name']}: {e}")


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
        # Count files with metadata issues from CSV
        csv_file = out_dir / "metadata_quality.csv"
        if csv_file.exists():
            try:
                import csv as csv_module
                with csv_file.open('r', encoding='utf-8') as f:
                    reader = csv_module.reader(f)
                    next(reader)  # Skip header
                    count = sum(1 for _ in reader)
            except Exception:
                pass  # Keep count as None if reading fails
        
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
