"""Library metadata quality analysis service.

This module provides comprehensive analysis of library metadata quality,
including missing tags and bitrate issues. The service is designed to help
users identify and fix tagging problems that negatively impact matching.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class QualityIssue:
    """Represents a metadata quality issue for a file."""
    path: str
    missing_fields: List[str] = field(default_factory=list)
    low_bitrate: bool = False
    bitrate_kbps: int | None = None


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


def analyze_library_quality(db, min_bitrate_kbps: int = 320, max_issues: int = 50) -> QualityReport:
    """
    Analyze library metadata quality.
    
    Args:
        db: Database instance
        min_bitrate_kbps: Minimum acceptable bitrate in kbps (default: 320)
        max_issues: Maximum number of detailed issues to collect (default: 50)
    
    Returns:
        QualityReport with detailed issue breakdown
    """
    logger.info("[analyze] Analyzing library metadata quality...")
    
    report = QualityReport()
    issues_collected = 0
    
    # Query all files with their metadata
    rows = db.conn.execute("""
        SELECT path, artist, title, album, year, bitrate_kbps
        FROM library_files
        ORDER BY path
    """).fetchall()
    
    report.total_files = len(rows)
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
        bitrate = row.get('bitrate_kbps')
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
                bitrate_kbps=bitrate
            ))
            issues_collected += 1
    
    logger.info(f"[analyze] Analysis complete. Found issues in {len(report.issues)} files (showing first {max_issues})")
    
    return report


def print_quality_report(report: QualityReport, min_bitrate_kbps: int = 320):
    """
    Print formatted quality report to console.
    
    Args:
        report: QualityReport instance
        min_bitrate_kbps: Minimum bitrate threshold used
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
