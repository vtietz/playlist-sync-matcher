"""Logging helper utilities for consistent progress reporting."""

import logging
import click

logger = logging.getLogger(__name__)


def log_progress(
    processed: int,
    total: int | None,
    new: int = 0,
    updated: int = 0,
    skipped: int = 0,
    elapsed_seconds: float = 0.0,
    item_name: str = "files"
) -> None:
    """Log progress info with consistent formatting.
    
    Args:
        processed: Number of items processed so far
        total: Total number of items (None if unknown)
        new: Count of new items
        updated: Count of updated items
        skipped: Count of skipped/unchanged items
        elapsed_seconds: Time elapsed since start
        item_name: Name of items being processed (e.g., "files", "tracks")
    """
    parts = [
        f"{click.style(f'{processed}', fg='cyan')} {item_name} processed"
    ]
    
    if total:
        pct = (processed / total * 100) if total > 0 else 0
        parts[0] = f"{click.style(f'{processed}/{total}', fg='cyan')} {item_name} ({pct:.0f}%)"
    
    if new > 0:
        parts.append(f"{click.style(f'{new} new', fg='green')}")
    if updated > 0:
        parts.append(f"{click.style(f'{updated} updated', fg='blue')}")
    if skipped > 0:
        parts.append(f"{click.style(f'{skipped} skipped', fg='yellow')}")
    
    if elapsed_seconds > 0:
        rate = processed / elapsed_seconds if elapsed_seconds > 0 else 0
        parts.append(f"{rate:.1f} {item_name}/s")
    
    logger.info(" | ".join(parts))


def format_summary(
    new: int,
    updated: int,
    unchanged: int,
    deleted: int = 0,
    duration_seconds: float = 0.0,
    item_name: str = "items"
) -> str:
    """Format a summary line with colored counts.
    
    Args:
        new: Count of new items
        updated: Count of updated items
        unchanged: Count of unchanged items
        deleted: Count of deleted items
        duration_seconds: Total duration in seconds
        item_name: Name of items (e.g., "Library", "Playlists")
        
    Returns:
        Formatted summary string with colors
    """
    parts = [
        click.style('✓', fg='green'),
        f"{item_name}:",
        click.style(f'{new} new', fg='green'),
        click.style(f'{updated} updated', fg='blue'),
        click.style(f'{unchanged} unchanged', fg='yellow')
    ]
    
    if deleted > 0:
        parts.append(click.style(f'{deleted} deleted', fg='red'))
    
    if duration_seconds > 0:
        parts.append(f"in {duration_seconds:.2f}s")
    
    return " ".join(parts)


__all__ = ["log_progress", "format_summary"]
