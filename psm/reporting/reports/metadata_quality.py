"""Metadata quality report generator."""

import csv
from pathlib import Path

from ...services.analysis_service import QualityReport
from ..formatting import format_badge, get_quality_badge_class, get_quality_status_text, shorten_path
from ..html_templates import get_html_template
from .base import format_liked, format_playlist_count


def write_metadata_quality_report(
    report: QualityReport, out_dir: Path, min_bitrate_kbps: int = 320
) -> tuple[Path, Path]:
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

        rows.append(
            {
                "path": issue.path,
                "has_artist": has_artist,
                "has_title": has_title,
                "has_album": has_album,
                "has_year": has_year,
                "missing_count": missing_count,
                "bitrate": bitrate_num,
                "playlist_count": issue.playlist_count,
                "is_liked": issue.is_liked,
            }
        )

    # Write CSV
    csv_path = out_dir / "metadata_quality.csv"
    _write_csv(csv_path, rows, min_bitrate_kbps)

    # Write HTML
    html_path = out_dir / "metadata_quality.html"
    _write_html(html_path, rows, report, min_bitrate_kbps)

    return (csv_path, html_path)


def _write_csv(csv_path: Path, rows: list[dict], min_bitrate_kbps: int = 320) -> None:
    """Write metadata quality CSV report."""
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            ["file_path", "title", "artist", "album", "year", "bitrate_kbps", "playlists", "liked", "quality_status"]
        )
        for row in rows:
            quality_status = get_quality_status_text(row["missing_count"], row["bitrate"], min_bitrate_kbps)
            w.writerow(
                [
                    row["path"],
                    "✓" if row["has_title"] else "✗",
                    "✓" if row["has_artist"] else "✗",
                    "✓" if row["has_album"] else "✗",
                    "✓" if row["has_year"] else "✗",
                    row["bitrate"],
                    format_playlist_count(row["playlist_count"]),
                    format_liked(row["is_liked"]),
                    quality_status,
                ]
            )


def _write_html(html_path: Path, rows: list[dict], report: QualityReport, min_bitrate_kbps: int) -> None:
    """Write metadata quality HTML report."""
    html_rows = []
    for row in rows:
        # Shorten file path for display
        short_path = shorten_path(row["path"], max_length=60)
        path_display = f'<span class="path-short" title="{row["path"]}">{short_path}</span>'

        # Create quality status badge
        quality_status = get_quality_status_text(row["missing_count"], row["bitrate"], min_bitrate_kbps)
        quality_badge_class = get_quality_badge_class(row["missing_count"], row["bitrate"], min_bitrate_kbps)
        quality_badge = format_badge(quality_status, quality_badge_class)

        # Playlist count and liked status
        playlist_display = format_playlist_count(row["playlist_count"])
        liked_display = format_liked(row["is_liked"])

        html_rows.append(
            [
                path_display,
                '<span class="check-yes">✓</span>' if row["has_title"] else '<span class="check-no">✗</span>',
                '<span class="check-yes">✓</span>' if row["has_artist"] else '<span class="check-no">✗</span>',
                '<span class="check-yes">✓</span>' if row["has_album"] else '<span class="check-no">✗</span>',
                '<span class="check-yes">✓</span>' if row["has_year"] else '<span class="check-no">✗</span>',
                f"{row['bitrate']} kbps" if row["bitrate"] > 0 else "N/A",
                playlist_display,
                liked_display,
                quality_badge,
            ]
        )

    stats = report.get_summary_stats()
    description = (
        f"Total files: {stats['total_files']:,} | "
        f"Missing artist: {stats['missing_artist']} ({stats['missing_artist_pct']}%) | "
        f"Missing title: {stats['missing_title']} ({stats['missing_title_pct']}%) | "
        f"Missing album: {stats['missing_album']} ({stats['missing_album_pct']}%) | "
        f"Missing year: {stats['missing_year']} ({stats['missing_year_pct']}%) | "
        f"Low bitrate (<{min_bitrate_kbps}kbps): {stats['low_bitrate_count']} ({stats['low_bitrate_pct']}%)"
    )

    html_content = get_html_template(
        title="Metadata Quality Analysis",
        columns=["File", "Title", "Artist", "Album", "Year", "Bitrate", "Playlists", "Liked", "Status"],
        rows=html_rows,
        description=description,
        default_order=[[8, "desc"], [5, "asc"]],  # Sort by Status, then Bitrate
        csv_filename="metadata_quality.csv",
        active_page="metadata_quality",
    )

    html_path.write_text(html_content, encoding="utf-8")
