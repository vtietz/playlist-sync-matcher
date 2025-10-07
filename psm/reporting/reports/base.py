"""Base utilities for report generation."""

import csv
from pathlib import Path
from typing import Any, Iterable

from ..html_templates import get_html_template


def write_csv_report(
    csv_path: Path,
    headers: list[str],
    rows: Iterable[list[Any]]
) -> None:
    """Write CSV report with given headers and rows.
    
    Args:
        csv_path: Path to output CSV file
        headers: List of column headers
        rows: Iterable of row data (each row is a list matching headers)
    """
    with csv_path.open('w', newline='', encoding='utf-8') as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)
        writer.writerows(rows)


def write_html_report(
    html_path: Path,
    title: str,
    columns: list[str],
    rows: list[list[Any]],
    description: str = "",
    default_order: list[list[Any]] | None = None
) -> None:
    """Write HTML report using standard template.
    
    Args:
        html_path: Path to output HTML file
        title: Report title
        columns: List of column names
        rows: List of row data
        description: Optional description text
        default_order: DataTables default sort order (e.g., [[0, "asc"]])
    """
    html_content = get_html_template(
        title=title,
        columns=columns,
        rows=rows,
        description=description,
        default_order=default_order
    )
    html_path.write_text(html_content, encoding='utf-8')


def safe_str(value: Any, default: str = "") -> str:
    """Safely convert value to string, returning default if None."""
    return str(value) if value is not None else default


def format_duration(seconds: int | None) -> str:
    """Format duration in seconds as MM:SS."""
    if seconds is None:
        return ""
    minutes, secs = divmod(seconds, 60)
    return f"{minutes}:{secs:02d}"


def format_playlist_count(count: int) -> str:
    """Format playlist count (empty if zero)."""
    return str(count) if count > 0 else ""


def format_liked(is_liked: bool) -> str:
    """Format liked status as heart emoji or empty."""
    return "❤️" if is_liked else ""
