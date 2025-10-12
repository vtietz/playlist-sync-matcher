"""Formatting utilities for GUI display.

Reuses report formatting logic for consistency between GUI and reports.
"""
from typing import Optional


def format_boolean_check(value: bool) -> str:
    """Format boolean as check/cross mark.

    Args:
        value: Boolean value

    Returns:
        '✓' for True, '✗' for False
    """
    return "✓" if value else "✗"


def extract_confidence(method_str: str) -> str:
    """Extract confidence from method string.

    Handles formats like:
    - 'MatchConfidence.CERTAIN' -> 'CERTAIN'
    - 'score:HIGH:89.50' -> 'HIGH'

    Args:
        method_str: Method string from database

    Returns:
        Confidence level (CERTAIN, HIGH, MEDIUM, LOW, UNKNOWN)
    """
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


def get_quality_status_text(missing_count: int, bitrate_kbps: Optional[int] = None, min_bitrate: int = 320) -> str:
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


def format_score_percentage(score: float) -> str:
    """Format match score as percentage.

    Args:
        score: Match score (0.0 to 1.0)

    Returns:
        Formatted percentage string (e.g., "89%")
    """
    if score is None:
        return ""
    return f"{score * 100:.0f}%"


def get_confidence_tooltip(method_str: str) -> str:
    """Generate tooltip explaining confidence level.

    Args:
        method_str: Method string from database

    Returns:
        Tooltip explaining the confidence level
    """
    confidence = extract_confidence(method_str)

    tooltips = {
        "CERTAIN": "Exact match using unique identifiers (ISRC, Spotify ID)",
        "HIGH": "Strong match with high similarity score (>85%)",
        "MODERATE": "Reasonable match with moderate similarity (70-85%)",
        "LOW": "Weak match with low similarity (<70%)",
        "UNKNOWN": "Matching method not recorded"
    }

    return tooltips.get(confidence, "Confidence level unknown")


def get_quality_tooltip(missing_count: int, bitrate_kbps: Optional[int],
                        missing_fields: Optional[list] = None) -> str:
    """Generate tooltip explaining quality assessment.

    Args:
        missing_count: Number of missing metadata fields
        bitrate_kbps: Audio bitrate in kbps (optional)
        missing_fields: List of missing field names (optional)

    Returns:
        Tooltip explaining the quality factors
    """
    parts = []

    # Metadata completeness
    if missing_count == 0:
        parts.append("✓ All metadata present")
    else:
        if missing_fields:
            fields_str = ", ".join(missing_fields)
            parts.append(f"⚠ Missing: {fields_str}")
        else:
            parts.append(f"⚠ {missing_count} metadata field(s) missing")

    # Bitrate quality
    if bitrate_kbps is not None:
        if bitrate_kbps >= 320:
            parts.append(f"✓ High quality audio ({bitrate_kbps} kbps)")
        elif bitrate_kbps >= 192:
            parts.append(f"⚠ Good audio quality ({bitrate_kbps} kbps)")
        elif bitrate_kbps >= 128:
            parts.append(f"⚠ Moderate audio quality ({bitrate_kbps} kbps)")
        else:
            parts.append(f"✗ Low audio quality ({bitrate_kbps} kbps)")
    else:
        parts.append("ℹ Bitrate unknown")

    return "\n".join(parts)


__all__ = [
    'format_boolean_check',
    'extract_confidence',
    'get_quality_status_text',
    'format_score_percentage',
    'get_confidence_tooltip',
    'get_quality_tooltip',
]
