"""Enhanced reporting utilities for standardized table structure."""
from __future__ import annotations
from pathlib import Path
from typing import Optional


def format_duration(duration_ms: Optional[int] = None, duration_sec: Optional[float] = None) -> str:
    """Format duration as MM:SS.
    
    Args:
        duration_ms: Duration in milliseconds
        duration_sec: Duration in seconds
        
    Returns:
        Formatted duration string in MM:SS format
    """
    if duration_ms is not None:
        seconds = duration_ms // 1000
    elif duration_sec is not None:
        seconds = int(duration_sec)
    else:
        return ""
    
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes}:{seconds:02d}"


def shorten_path(full_path: str, base_dir: Optional[str] = None, max_length: int = 60) -> str:
    """Shorten file path for display.
    
    Args:
        full_path: Full absolute path
        base_dir: Base directory to make path relative to
        max_length: Maximum length before shortening to basename
        
    Returns:
        Shortened path for display
    """
    path = Path(full_path)
    
    # Try relative to base_dir
    if base_dir:
        try:
            relative = path.relative_to(base_dir)
            if len(str(relative)) <= max_length:
                return str(relative)
        except ValueError:
            pass
    
    # Fallback to basename if path is too long
    if len(str(path)) > max_length:
        return path.name
    
    return str(path)


def get_confidence_badge_class(confidence: str) -> str:
    """Get Bootstrap badge class for match confidence.
    
    Args:
        confidence: Confidence level (CERTAIN, HIGH, MEDIUM, LOW, UNKNOWN)
        
    Returns:
        CSS class name for badge styling
    """
    confidence_upper = confidence.upper()
    
    if confidence_upper == "CERTAIN":
        return "badge-success"
    elif confidence_upper == "HIGH":
        return "badge-primary"
    elif confidence_upper == "MEDIUM":
        return "badge-warning"
    elif confidence_upper == "LOW":
        return "badge-danger"
    else:  # UNKNOWN or anything else
        return "badge-secondary"


def get_quality_badge_class(missing_count: int, bitrate_kbps: int | None = None, min_bitrate: int = 320) -> str:
    """Get Bootstrap badge class for metadata quality.
    
    Args:
        missing_count: Number of missing metadata fields
        bitrate_kbps: Audio bitrate in kbps (optional)
        min_bitrate: Minimum bitrate for EXCELLENT quality (default: 320)
        
    Returns:
        CSS class name for badge styling
    """
    quality = get_quality_status_text(missing_count, bitrate_kbps, min_bitrate)
    
    if quality == "EXCELLENT":
        return "badge-success"
    elif quality == "GOOD":
        return "badge-primary"
    elif quality == "PARTIAL":
        return "badge-warning"
    else:  # POOR
        return "badge-danger"


def get_coverage_badge_class(percentage: float) -> str:
    """Get Bootstrap badge class for coverage percentage.
    
    Args:
        percentage: Coverage percentage (0-100)
        
    Returns:
        CSS class name for badge styling
    """
    if percentage >= 100:
        return "badge-success"  # COMPLETE
    elif percentage >= 80:
        return "badge-primary"  # HIGH
    elif percentage >= 50:
        return "badge-warning"  # PARTIAL
    else:
        return "badge-danger"   # LOW


def format_badge(text: str, badge_class: str) -> str:
    """Format a status badge for HTML display.
    
    Args:
        text: Badge text content
        badge_class: CSS class name (e.g., 'badge-success')
        
    Returns:
        HTML span element with badge styling
    """
    return f'<span class="badge {badge_class}">{text}</span>'


def get_quality_status_text(missing_count: int, bitrate_kbps: int | None = None, min_bitrate: int = 320) -> str:
    """Get quality status text based on missing field count and bitrate.
    
    Quality is determined by both metadata completeness and audio quality:
    - POOR: 3+ missing fields OR bitrate < 128 kbps
    - PARTIAL: 2 missing fields OR bitrate 128-191 kbps
    - GOOD: 1 missing field OR bitrate 192-319 kbps
    - EXCELLENT: No missing fields AND bitrate >= 320 kbps (or no bitrate info)
    
    Args:
        missing_count: Number of missing metadata fields (0-4)
        bitrate_kbps: Audio bitrate in kbps (optional)
        min_bitrate: Minimum bitrate for EXCELLENT quality (default: 320)
        
    Returns:
        Quality status text
    """
    # Start with metadata-based quality
    if missing_count >= 3:
        metadata_quality = "POOR"
    elif missing_count == 2:
        metadata_quality = "PARTIAL"
    elif missing_count == 1:
        metadata_quality = "GOOD"
    else:
        metadata_quality = "EXCELLENT"
    
    # Factor in bitrate if available
    if bitrate_kbps is not None:
        if bitrate_kbps < 128:
            bitrate_quality = "POOR"
        elif bitrate_kbps < 192:
            bitrate_quality = "PARTIAL"
        elif bitrate_kbps < min_bitrate:
            bitrate_quality = "GOOD"
        else:
            bitrate_quality = "EXCELLENT"
        
        # Return the worse of the two qualities
        quality_order = {"POOR": 0, "PARTIAL": 1, "GOOD": 2, "EXCELLENT": 3}
        if quality_order[bitrate_quality] < quality_order[metadata_quality]:
            return bitrate_quality
        else:
            return metadata_quality
    
    return metadata_quality


def get_coverage_status_text(percentage: float) -> str:
    """Get coverage status text based on percentage.
    
    Args:
        percentage: Coverage percentage (0-100)
        
    Returns:
        Coverage status text
    """
    if percentage >= 100:
        return "COMPLETE"
    elif percentage >= 80:
        return "HIGH"
    elif percentage >= 50:
        return "PARTIAL"
    else:
        return "LOW"


def format_playlist_count_badge(count: int) -> str:
    """Format playlist count as a priority badge.
    
    Args:
        count: Number of playlists containing the track
        
    Returns:
        HTML badge showing priority based on playlist count
    """
    if count >= 5:
        badge_class = "badge-danger"   # HIGH priority (many playlists)
        text = f"HIGH ({count})"
    elif count >= 2:
        badge_class = "badge-warning"  # MEDIUM priority
        text = f"MEDIUM ({count})"
    elif count == 1:
        badge_class = "badge-primary"  # LOW priority
        text = f"LOW ({count})"
    else:
        badge_class = "badge-secondary" # No playlists
        text = "NONE"
    
    return format_badge(text, badge_class)


def format_playlist_count_simple(count: int) -> str:
    """Format playlist count as a simple colored number badge.
    
    Args:
        count: Number of playlists containing the track
        
    Returns:
        HTML badge showing just the count with color-coding
    """
    if count >= 5:
        badge_class = "badge-danger"   # HIGH priority (many playlists)
    elif count >= 2:
        badge_class = "badge-warning"  # MEDIUM priority
    elif count == 1:
        badge_class = "badge-primary"  # LOW priority
    else:
        badge_class = "badge-secondary" # No playlists
    
    text = str(count) if count > 0 else "0"
    return format_badge(text, badge_class)