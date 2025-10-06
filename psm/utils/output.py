"""Output formatting utilities for consistent CLI reporting."""

import click
from pathlib import Path


def section_header(text: str) -> str:
    """Format a section header with color.
    
    Args:
        text: Header text
        
    Returns:
        Formatted header string
    """
    return click.style(f"▶ {text}", fg='cyan', bold=True)


def success(text: str, prefix: str = "✓") -> str:
    """Format a success message.
    
    Args:
        text: Message text
        prefix: Prefix character (default: ✓)
        
    Returns:
        Formatted success string
    """
    return f"{click.style(prefix, fg='green')} {text}"


def error(text: str, prefix: str = "✗") -> str:
    """Format an error message.
    
    Args:
        text: Message text
        prefix: Prefix character (default: ✗)
        
    Returns:
        Formatted error string
    """
    return f"{click.style(prefix, fg='red')} {text}"


def warning(text: str, prefix: str = "⚠") -> str:
    """Format a warning message.
    
    Args:
        text: Message text
        prefix: Prefix character (default: ⚠)
        
    Returns:
        Formatted warning string
    """
    return f"{click.style(prefix, fg='yellow')} {text}"


def info(text: str) -> str:
    """Format an info message.
    
    Args:
        text: Message text
        
    Returns:
        Formatted info string
    """
    return f"  {click.style('•', fg='blue')} {text}"


def file_path(path: Path | str, label: str | None = None) -> str:
    """Format a file path with optional label.
    
    Args:
        path: File path to format
        label: Optional label to show before path
        
    Returns:
        Formatted path string
    """
    path_str = str(Path(path).resolve())
    if label:
        return f"  {click.style('•', fg='blue')} {label}: {click.style(path_str, fg='yellow')}"
    return f"  {click.style(path_str, fg='yellow')}"


def clickable_path(path: Path | str, label: str | None = None) -> str:
    """Format a clickable file path (absolute path for terminal clicking).
    
    Args:
        path: File path to format
        label: Optional label to show before path
        
    Returns:
        Formatted clickable path string
    """
    abs_path = Path(path).resolve()
    path_str = str(abs_path)
    
    if label:
        return f"  {click.style('•', fg='blue')} {label}: {click.style(path_str, fg='cyan', underline=True)}"
    return f"  {click.style(path_str, fg='cyan', underline=True)}"


def report_files(csv_path: Path | str, html_path: Path | str, label: str) -> str:
    """Format report file paths (CSV and HTML).
    
    Args:
        csv_path: Path to CSV file
        html_path: Path to HTML file
        label: Report label
        
    Returns:
        Formatted report files string
    """
    csv = click.style(str(Path(csv_path).resolve()), fg='yellow')
    html = click.style(str(Path(html_path).resolve()), fg='yellow')
    return f"  {click.style('•', fg='blue')} {label}:\n    CSV:  {csv}\n    HTML: {html}"


def count_badge(count: int, label: str, color: str = 'cyan') -> str:
    """Format a count badge.
    
    Args:
        count: Count to display
        label: Label for the count
        color: Color for the count (default: cyan)
        
    Returns:
        Formatted count badge
    """
    return f"{click.style(str(count), fg=color, bold=True)} {label}"


def divider() -> str:
    """Return a visual divider line.
    
    Returns:
        Divider string
    """
    return click.style("─" * 60, fg='bright_black')


__all__ = [
    "section_header",
    "success",
    "error", 
    "warning",
    "info",
    "file_path",
    "clickable_path",
    "report_files",
    "count_badge",
    "divider",
]
