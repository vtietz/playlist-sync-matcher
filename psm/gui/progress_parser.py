"""Progress parser for CLI output.

Maps CLI output lines to progress updates for the progress bar.

Supports standardized progress formats from psm.utils.progress:
- Step progress: "[1/4] Operation name"
- Item progress: "Progress: 123/456 items (27%)"
- Completion: "✓ Operation completed in 1.23s"
- Status: "→ Status message"

Also supports legacy formats for backward compatibility.
"""
import re
from typing import Optional, Tuple

# Regex patterns for standardized progress formats
PATTERNS = {
    # Standard step format: "[1/4] Scanning library"
    'step': re.compile(r'\[(\d+)/(\d+)\]\s+(.+)'),
    
    # Standard item progress: "Progress: 150/500 tracks (30%)"
    'items': re.compile(r'Progress:\s+(\d+)/(\d+)\s+(.+?)\s+\((\d+)%\)'),
    
    # Matching progress: "Progress: 500/12974 tracks (3%) | 245 matched (49.0% match rate) | 125.5 tracks/s"
    'match_progress': re.compile(r'Progress:\s+(\d+)/(\d+)\s+tracks\s+\((\d+)%\)'),
    
    # Standard indeterminate progress: "Progress: 150 tracks processed"
    'items_indeterminate': re.compile(r'Progress:\s+(\d+)\s+(.+?)\s+processed'),
    
    # Standard completion: "✓ Library scan completed in 2.5s"
    'completion': re.compile(r'✓\s+(.+?)\s+completed(?:\s+in\s+[\d.]+s)?'),
    
    # Additional completion patterns from CLI
    'completion_export': re.compile(r'^✓\s+Exported\s+(\d+)\s+playlists?'),
    'completion_incremental': re.compile(r'^✓\s+Incremental rebuild complete'),
    'completion_sync': re.compile(r'^✓\s+Database sync complete'),
    
    # Standard status: "→ Found 42 playlists"
    'status': re.compile(r'→\s+(.+)'),
    
    # Section headers: "=== Matching tracks to library files ==="
    'section': re.compile(r'^===\s+(.+?)\s+==='),
    
    # Legacy patterns (backward compatibility)
    'legacy_files': re.compile(r'(\d+)\s+files\s+processed'),
    'legacy_match': re.compile(r'Matched\s+(\d+)/(\d+)\s+tracks'),
    'legacy_export': re.compile(r'Exported\s+(\d+)/(\d+)\s+playlists'),
}


def parse_progress(line: str) -> Optional[Tuple[int, int, str]]:
    """Parse a CLI output line for progress information.
    
    Args:
        line: CLI output line
        
    Returns:
        Tuple of (current, total, message) if progress found, else None
        - For percentage progress: (current, total, message)
        - For indeterminate progress: (current, 0, message)
        - For completion: (100, 100, message)
    """
    line = line.strip()
    
    # Standard step format: "[1/4] Scanning library"
    match = PATTERNS['step'].search(line)
    if match:
        current = int(match.group(1))
        total = int(match.group(2))
        message = match.group(3)
        return (current, total, message)
    
    # Matching progress: "Progress: 500/12974 tracks (3%) | 245 matched (49.0% match rate) | 125.5 tracks/s"
    match = PATTERNS['match_progress'].search(line)
    if match:
        current = int(match.group(1))
        total = int(match.group(2))
        percent = int(match.group(3))
        return (current, total, f"Matching: {current}/{total}")
    
    # Standard item progress: "Progress: 150/500 tracks (30%)"
    match = PATTERNS['items'].search(line)
    if match:
        current = int(match.group(1))
        total = int(match.group(2))
        item_type = match.group(3)
        percent = int(match.group(4))
        return (current, total, f"{item_type}: {current}/{total}")
    
    # Standard indeterminate progress: "Progress: 150 tracks processed"
    match = PATTERNS['items_indeterminate'].search(line)
    if match:
        current = int(match.group(1))
        item_type = match.group(2)
        return (current, 0, f"{item_type}: {current}")
    
    # Standard completion: "✓ Library scan completed in 2.5s"
    match = PATTERNS['completion'].search(line)
    if match:
        operation = match.group(1)
        return (100, 100, f"✓ {operation}")
    
    # Additional completion patterns
    match = PATTERNS['completion_export'].search(line)
    if match:
        count = match.group(1)
        return (100, 100, f"✓ Exported {count} playlists")
    
    match = PATTERNS['completion_incremental'].search(line)
    if match:
        return (100, 100, "✓ Incremental rebuild complete")
    
    match = PATTERNS['completion_sync'].search(line)
    if match:
        return (100, 100, "✓ Database sync complete")
    
    # Section headers
    match = PATTERNS['section'].search(line)
    if match:
        section = match.group(1)
        return (0, 0, f"→ {section}")
    
    # Standard status: "→ Found 42 playlists"
    match = PATTERNS['status'].search(line)
    if match:
        message = match.group(1)
        return (0, 0, message)
    
    # Legacy: "100 files processed"
    match = PATTERNS['legacy_files'].search(line)
    if match:
        processed = int(match.group(1))
        return (processed, 0, f"Files processed: {processed}")
    
    # Legacy: "Matched 150/500 tracks"
    match = PATTERNS['legacy_match'].search(line)
    if match:
        current = int(match.group(1))
        total = int(match.group(2))
        return (current, total, f"Matching: {current}/{total}")
    
    # Legacy: "Exported 5/10 playlists"
    match = PATTERNS['legacy_export'].search(line)
    if match:
        current = int(match.group(1))
        total = int(match.group(2))
        return (current, total, f"Exporting: {current}/{total}")
    
    return None


def is_completion_marker(line: str) -> bool:
    """Check if line indicates operation completion.
    
    Args:
        line: CLI output line
        
    Returns:
        True if line indicates completion
    """
    return bool(
        PATTERNS['completion'].search(line) or
        PATTERNS['completion_export'].search(line) or
        PATTERNS['completion_incremental'].search(line) or
        PATTERNS['completion_sync'].search(line)
    )
