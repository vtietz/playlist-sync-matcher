"""Library metadata quality analysis service.

This module provides comprehensive analysis of library metadata quality,
including missing tags and bitrate issues. The service is designed to help
users identify and fix tagging problems that negatively impact matching.

Reports are automatically generated in both CSV and HTML formats.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any
import logging

import click
from ..db import DatabaseInterface  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class QualityIssue:
    """Represents a metadata quality issue for a file."""
    path: str
    missing_fields: List[str] = field(default_factory=list)
    low_bitrate: bool = False
    bitrate_kbps: int | None = None
    playlist_count: int = 0
    is_liked: bool = False


@dataclass
class QualityReport:
    """Structured quality analysis results."""
    total_files: int = 0
    missing_artist: int = 0
    missing_title: int = 0
    missing_album: int = 0
    missing_year: int = 0
    missing_multiple: int = 0
    low_bitrate_count: int = 0
    files_without_bitrate: int = 0
    issues: List[QualityIssue] = field(default_factory=list)

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics as a dict."""
        return {
            'total_files': self.total_files,
            'missing_artist': self.missing_artist,
            'missing_artist_pct': round(self.missing_artist / self.total_files * 100, 1) if self.total_files else 0,
            'missing_title': self.missing_title,
            'missing_title_pct': round(self.missing_title / self.total_files * 100, 1) if self.total_files else 0,
            'missing_album': self.missing_album,
            'missing_album_pct': round(self.missing_album / self.total_files * 100, 1) if self.total_files else 0,
            'missing_year': self.missing_year,
            'missing_year_pct': round(self.missing_year / self.total_files * 100, 1) if self.total_files else 0,
            'missing_multiple': self.missing_multiple,
            'low_bitrate_count': self.low_bitrate_count,
            'low_bitrate_pct': round(self.low_bitrate_count / self.total_files * 100, 1) if self.total_files else 0,
            'files_without_bitrate': self.files_without_bitrate,
        }


def analyze_library_quality(db: DatabaseInterface, min_bitrate_kbps: int = 320, max_issues: int = 50, silent: bool = False) -> QualityReport:
    """
    Analyze library metadata quality.

    Args:
        db: Database instance
        min_bitrate_kbps: Minimum acceptable bitrate in kbps (default: 320)
        max_issues: Maximum number of detailed issues to collect (default: 50)
        silent: If True, suppress progress logging (default: False)

    Returns:
        QualityReport with detailed issue breakdown
    """
    if not silent:
        logger.info("[analyze] Analyzing library metadata quality...")

    report = QualityReport()
    issues_collected = 0

    # Query all files with their metadata, playlist count, and liked status
    rows = db.conn.execute("""
        SELECT
            lf.path,
            lf.artist,
            lf.title,
            lf.album,
            lf.year,
            lf.bitrate_kbps,
            COUNT(DISTINCT pt.playlist_id) as playlist_count,
            EXISTS(
                SELECT 1 FROM liked_tracks lt
                JOIN matches m2 ON lt.track_id = m2.track_id AND lt.provider = m2.provider
                WHERE m2.file_id = lf.id
            ) as is_liked
        FROM library_files lf
        LEFT JOIN matches m ON lf.id = m.file_id
        LEFT JOIN playlist_tracks pt ON m.track_id = pt.track_id AND m.provider = pt.provider
        GROUP BY lf.id
        ORDER BY lf.path
    """).fetchall()

    report.total_files = len(rows)
    if not silent:
        logger.info(f"[analyze] Analyzing {report.total_files} files...")

    for row in rows:
        path = row['path']
        missing = []
        has_issue = False

        # Check for missing metadata fields
        if not row['artist']:
            missing.append('artist')
            report.missing_artist += 1
            has_issue = True

        if not row['title']:
            missing.append('title')
            report.missing_title += 1
            has_issue = True

        if not row['album']:
            missing.append('album')
            report.missing_album += 1
            has_issue = True

        if not row['year']:
            missing.append('year')
            report.missing_year += 1
            has_issue = True

        if len(missing) > 1:
            report.missing_multiple += 1

        # Check bitrate
        bitrate = row['bitrate_kbps']
        low_bitrate = False

        if bitrate is None:
            report.files_without_bitrate += 1
        elif bitrate < min_bitrate_kbps:
            low_bitrate = True
            report.low_bitrate_count += 1
            has_issue = True

        # Collect detailed issues (up to max_issues)
        if has_issue and issues_collected < max_issues:
            report.issues.append(QualityIssue(
                path=path,
                missing_fields=missing,
                low_bitrate=low_bitrate,
                bitrate_kbps=bitrate,
                playlist_count=row['playlist_count'],
                is_liked=bool(row['is_liked'])
            ))
            issues_collected += 1

    if not silent:
        logger.info(f"[analyze] Analysis complete. Found issues in {len(report.issues)} files (showing first {max_issues})")

    return report


def _get_top_offenders_by_field_grouped(db, field_name: str, top_n: int = 10) -> List[Dict[str, Any]]:
    """Get top offenders with missing field, intelligently grouped by album.

    Groups files by album to maximize impact - fixing one album fixes multiple files.
    Returns albums sorted by: file count (desc), then album name.

    Args:
        db: Database instance
        field_name: Field to check ('artist', 'title', 'album', 'year')
        top_n: Number of album groups to return

    Returns:
        List of dicts with 'album', 'artist', 'file_count', 'files' keys
    """
    # Special case: if checking for missing album, can't group by album
    if field_name == 'album':
        query = f"""
            SELECT path, artist
            FROM library_files
            WHERE {field_name} IS NULL OR {field_name} = ''
            ORDER BY artist, path
            LIMIT ?
        """
        rows = db.conn.execute(query, (top_n * 3,)).fetchall()

        # Group by artist for missing album case
        artist_groups = {}
        for row in rows:
            artist = row['artist'] or '[No Artist]'
            if artist not in artist_groups:
                artist_groups[artist] = []
            artist_groups[artist].append(row['path'])

        # Convert to result format
        results = []
        for artist, files in sorted(artist_groups.items(), key=lambda x: (-len(x[1]), x[0])):
            results.append({
                'album': None,
                'artist': artist,
                'file_count': len(files),
                'files': files[:5]  # Show max 5 files per artist
            })
            if len(results) >= top_n:
                break
        return results

    # Normal case: group by album
    query = f"""
        SELECT album, artist, COUNT(*) as file_count,
               GROUP_CONCAT(path, '|') as paths
        FROM library_files
        WHERE ({field_name} IS NULL OR {field_name} = '')
          AND album IS NOT NULL AND album != ''
        GROUP BY album, artist
        ORDER BY file_count DESC, album
        LIMIT ?
    """
    rows = db.conn.execute(query, (top_n,)).fetchall()

    results = []
    for row in rows:
        paths = row['paths'].split('|') if row['paths'] else []
        results.append({
            'album': row['album'],
            'artist': row['artist'] or '[No Artist]',
            'file_count': row['file_count'],
            'files': paths[:5]  # Show max 5 files per album
        })

    return results


def print_quality_report(report: QualityReport, min_bitrate_kbps: int = 320, db=None, top_n: int = 10):
    """
    Print formatted quality report to console with top offenders.

    Args:
        report: QualityReport instance
        min_bitrate_kbps: Minimum bitrate threshold used
        db: Database instance (optional, for showing top offenders)
        top_n: Number of top offenders to show per category
    """
    stats = report.get_summary_stats()

    logger.info("")
    logger.info("=" * 70)
    logger.info("LIBRARY METADATA QUALITY REPORT")
    logger.info("=" * 70)
    logger.info(f"Total files analyzed: {stats['total_files']}")
    logger.info("")
    logger.info("Missing Metadata:")
    logger.info(f"  Artist:  {stats['missing_artist']:5d} files ({stats['missing_artist_pct']:5.1f}%)")
    logger.info(f"  Title:   {stats['missing_title']:5d} files ({stats['missing_title_pct']:5.1f}%)")
    logger.info(f"  Album:   {stats['missing_album']:5d} files ({stats['missing_album_pct']:5.1f}%)")
    logger.info(f"  Year:    {stats['missing_year']:5d} files ({stats['missing_year_pct']:5.1f}%)")
    logger.info(f"  Multiple fields missing: {stats['missing_multiple']} files")
    logger.info("")
    logger.info(f"Bitrate Issues (< {min_bitrate_kbps} kbps):")
    logger.info(f"  Low bitrate: {stats['low_bitrate_count']:5d} files ({stats['low_bitrate_pct']:5.1f}%)")
    logger.info(f"  No bitrate info: {stats['files_without_bitrate']} files")
    logger.info("=" * 70)

    # Show top offenders per category (INFO mode) - grouped by album for maximum impact
    if db and (stats['missing_artist'] > 0 or stats['missing_album'] > 0 or stats['missing_year'] > 0):
        logger.info("")
        logger.info("Top Albums/Groups With Missing Metadata (Fix These For Maximum Impact!):")
        logger.info("")

        if stats['missing_year'] > 0:
            logger.info(click.style("  Missing Year (grouped by album):", fg='yellow', bold=True))
            offenders = _get_top_offenders_by_field_grouped(db, 'year', top_n)
            total_files_shown = 0
            for group in offenders:
                album = group['album'] or '[No Album]'
                artist = group['artist']
                count = group['file_count']

                logger.info(f"    {click.style(f'📁 {artist} - {album}', fg='cyan')} ({count} file{'s' if count != 1 else ''})")
                for file_path in group['files'][:3]:  # Show max 3 example files
                    logger.info(f"       • {file_path}")
                if len(group['files']) > 3:
                    logger.info(f"       ... and {len(group['files']) - 3} more from this album")
                total_files_shown += count

            if stats['missing_year'] > total_files_shown:
                logger.info(f"    ... and {stats['missing_year'] - total_files_shown} more files in {stats['missing_year'] - total_files_shown} other albums")
            logger.info("")

        if stats['missing_album'] > 0:
            logger.info(click.style("  Missing Album (grouped by artist):", fg='yellow', bold=True))
            offenders = _get_top_offenders_by_field_grouped(db, 'album', top_n)
            total_files_shown = 0
            for group in offenders:
                artist = group['artist']
                count = group['file_count']

                logger.info(f"    {click.style(f'👤 {artist}', fg='cyan')} ({count} file{'s' if count != 1 else ''})")
                for file_path in group['files'][:3]:  # Show max 3 example files
                    logger.info(f"       • {file_path}")
                if len(group['files']) > 3:
                    logger.info(f"       ... and {len(group['files']) - 3} more from this artist")
                total_files_shown += count

            if stats['missing_album'] > total_files_shown:
                logger.info(f"    ... and {stats['missing_album'] - total_files_shown} more files from other artists")
            logger.info("")

        if stats['missing_artist'] > 0:
            logger.info(click.style("  Missing Artist (grouped by album):", fg='yellow', bold=True))
            offenders = _get_top_offenders_by_field_grouped(db, 'artist', top_n)
            total_files_shown = 0
            for group in offenders:
                album = group['album'] or '[No Album]'
                count = group['file_count']

                logger.info(f"    {click.style(f'📁 {album}', fg='cyan')} ({count} file{'s' if count != 1 else ''})")
                for file_path in group['files'][:3]:  # Show max 3 example files
                    logger.info(f"       • {file_path}")
                if len(group['files']) > 3:
                    logger.info(f"       ... and {len(group['files']) - 3} more from this album")
                total_files_shown += count

            if stats['missing_artist'] > total_files_shown:
                logger.info(f"    ... and {stats['missing_artist'] - total_files_shown} more files in other albums")
            logger.info("")

    # Show detailed issues if debug logging is enabled
    if report.issues and logging.getLogger().isEnabledFor(logging.DEBUG):
        logger.info("")
        logger.info(f"Detailed Issues (showing first {len(report.issues)}):")
        logger.info("")

        for issue in report.issues:
            problems = []
            if issue.missing_fields:
                problems.append(f"missing: {', '.join(issue.missing_fields)}")
            if issue.low_bitrate and issue.bitrate_kbps:
                problems.append(f"low bitrate: {issue.bitrate_kbps} kbps")

            logger.info(f"  {issue.path}")
            logger.info(f"    → {'; '.join(problems)}")
            logger.info("")


__all__ = [
    'QualityIssue',
    'QualityReport',
    'analyze_library_quality',
    'print_quality_report',
]
