"""Diagnostic service for troubleshooting why tracks don't match."""

from __future__ import annotations
from typing import Dict, Any, List, Tuple
from rapidfuzz import fuzz
import logging

from ..db import DatabaseInterface
from ..utils.normalization import normalize_title_artist

logger = logging.getLogger(__name__)


class DiagnosticResult:
    """Result of diagnosing why a track didn't match."""
    
    def __init__(
        self,
        track_found: bool,
        track_info: Dict[str, Any] | None = None,
        is_matched: bool = False,
        matched_file: Dict[str, Any] | None = None,
        match_score: float = 0.0,
        match_method: str = "",
        closest_files: List[Tuple[Dict[str, Any], float]] = None,
        total_files: int = 0,
        fuzzy_threshold: float = 0.78
    ):
        self.track_found = track_found
        self.track_info = track_info
        self.is_matched = is_matched
        self.matched_file = matched_file
        self.match_score = match_score
        self.match_method = match_method
        self.closest_files = closest_files or []
        self.total_files = total_files
        self.fuzzy_threshold = fuzzy_threshold


def diagnose_track(
    db: DatabaseInterface,
    track_id: str,
    provider: str = 'spotify',
    top_n: int = 5
) -> DiagnosticResult:
    """Diagnose why a track isn't matching.
    
    Args:
        db: Database instance
        track_id: Track ID to diagnose
        provider: Provider name (default: spotify)
        top_n: Number of closest files to return (default: 5)
    
    Returns:
        DiagnosticResult with detailed diagnostic information
    """
    # Get fuzzy threshold from config metadata (using correct table name)
    fuzzy_threshold = 0.78
    threshold_str = db.get_meta('fuzzy_threshold')
    if threshold_str:
        try:
            fuzzy_threshold = float(threshold_str)
        except (ValueError, TypeError):
            pass
    
    # 1. Find track in database using repository method
    track_row = db.get_track_by_id(track_id, provider)
    
    if not track_row:
        return DiagnosticResult(track_found=False)
    
    track_info = {
        'id': track_row.id,
        'name': track_row.name,
        'artist': track_row.artist,
        'album': track_row.album,
        'duration_ms': track_row.duration_ms,
        'year': track_row.year,
        'normalized': track_row.normalized,
        'isrc': track_row.isrc,
    }
    
    # 2. Check if already matched using repository method
    match_info = db.get_match_for_track(track_id, provider)
    
    if match_info:
        return DiagnosticResult(
            track_found=True,
            track_info=track_info,
            is_matched=True,
            matched_file=match_info,
            match_score=match_info['score'],
            match_method=match_info['method'],
            fuzzy_threshold=fuzzy_threshold
        )
    
    # 3. Find closest files using fuzzy matching
    track_norm = track_info.get('normalized') or ''
    
    # Get total file count and all files for matching
    total_files = db.count_library_files()
    
    if not track_norm:
        return DiagnosticResult(
            track_found=True,
            track_info=track_info,
            is_matched=False,
            total_files=total_files,
            fuzzy_threshold=fuzzy_threshold
        )
    
    # Fetch all files using repository method
    all_files = db.get_all_library_files()
    
    scored_files: List[Tuple[Dict[str, Any], float]] = []
    
    for file_row in all_files:
        file_norm = file_row.normalized or ''
        if not file_norm:
            continue
        
        # Calculate fuzzy score
        score = fuzz.token_set_ratio(track_norm, file_norm) / 100.0
        file_dict = {
            'id': file_row.id,
            'path': file_row.path,
            'title': file_row.title,
            'artist': file_row.artist,
            'album': file_row.album,
            'duration': file_row.duration,
            'normalized': file_row.normalized,
            'year': file_row.year,
        }
        scored_files.append((file_dict, score))
    
    # Sort by score descending and take top N
    scored_files.sort(key=lambda x: x[1], reverse=True)
    closest_files = scored_files[:top_n]
    
    return DiagnosticResult(
        track_found=True,
        track_info=track_info,
        is_matched=False,
        closest_files=closest_files,
        total_files=total_files,
        fuzzy_threshold=fuzzy_threshold
    )


def format_diagnostic_output(result: DiagnosticResult) -> str:
    """Format diagnostic result as human-readable output.
    
    Args:
        result: DiagnosticResult to format
    
    Returns:
        Formatted diagnostic output string
    """
    lines = []
    
    if not result.track_found:
        lines.append("❌ Track not found in database")
        lines.append("")
        lines.append("Possible reasons:")
        lines.append("  • Track ID is incorrect")
        lines.append("  • Track not in any of your playlists")
        lines.append("  • 'pull' command hasn't been run yet")
        lines.append("")
        lines.append("Try running: psm pull")
        return "\n".join(lines)
    
    # Track details
    track = result.track_info
    lines.append("🎵 Track Information")
    lines.append("=" * 70)
    lines.append(f"Track:    {track['artist']} - {track['name']}")
    if track.get('album'):
        lines.append(f"Album:    {track['album']}")
    if track.get('year'):
        lines.append(f"Year:     {track['year']}")
    if track.get('duration_ms'):
        duration_sec = track['duration_ms'] / 1000
        duration_str = f"{int(duration_sec // 60)}:{int(duration_sec % 60):02d}"
        lines.append(f"Duration: {duration_str} ({track['duration_ms']}ms)")
    if track.get('isrc'):
        lines.append(f"ISRC:     {track['isrc']}")
    lines.append(f"ID:       {track['id']}")
    lines.append("")
    lines.append(f"Normalized: {track.get('normalized', 'N/A')}")
    lines.append("")
    
    # Match status
    if result.is_matched:
        lines.append("✅ Track is already matched!")
        lines.append("=" * 70)
        matched = result.matched_file
        lines.append(f"Matched to:  {matched['path']}")
        lines.append(f"Score:       {result.match_score:.2%} ({result.match_method})")
        lines.append(f"File tags:   {matched.get('artist', 'N/A')} - {matched.get('title', 'N/A')}")
        if matched.get('duration'):
            file_duration_str = f"{int(matched['duration'] // 60)}:{int(matched['duration'] % 60):02d}"
            lines.append(f"Duration:    {file_duration_str} ({matched['duration']}s)")
        lines.append(f"Normalized:  {matched.get('normalized', 'N/A')}")
        return "\n".join(lines)
    
    # Unmatched - show diagnostics
    lines.append("❌ Track is UNMATCHED")
    lines.append("=" * 70)
    lines.append(f"Fuzzy threshold: {result.fuzzy_threshold:.0%}")
    lines.append(f"Library size:    {result.total_files:,} files")
    lines.append("")
    
    if not result.closest_files:
        lines.append("⚠️  No similar files found in library")
        lines.append("")
        lines.append("Possible reasons:")
        lines.append("  • File not in your library")
        lines.append("  • File metadata is missing or incorrect")
        lines.append("  • Library hasn't been scanned yet")
        lines.append("")
        lines.append("Try running: psm scan")
        return "\n".join(lines)
    
    # Show closest matches
    best_score = result.closest_files[0][1]
    lines.append(f"📊 Top {len(result.closest_files)} closest files:")
    lines.append("")
    
    for idx, (file_info, score) in enumerate(result.closest_files, 1):
        score_pct = score * 100
        
        # Status indicator
        if score >= result.fuzzy_threshold:
            status = "✅ ABOVE threshold (should match!)"
        elif score >= result.fuzzy_threshold - 0.05:
            status = "⚠️  Just below threshold"
        else:
            status = "❌ Below threshold"
        
        lines.append(f"{idx}. Score: {score_pct:.1f}% - {status}")
        lines.append(f"   Path:       {file_info['path']}")
        lines.append(f"   File tags:  {file_info.get('artist', 'N/A')} - {file_info.get('title', 'N/A')}")
        if file_info.get('album'):
            lines.append(f"   Album:      {file_info['album']}")
        if file_info.get('duration'):
            file_duration_str = f"{int(file_info['duration'] // 60)}:{int(file_info['duration'] % 60):02d}"
            track_duration_sec = track.get('duration_ms', 0) / 1000
            duration_diff = abs(file_info['duration'] - track_duration_sec)
            lines.append(f"   Duration:   {file_duration_str} (diff: {duration_diff:.1f}s)")
        lines.append(f"   Normalized: {file_info.get('normalized', 'N/A')}")
        lines.append("")
    
    # Recommendations
    lines.append("💡 Recommendations:")
    lines.append("=" * 70)
    
    # Special case: Perfect or near-perfect match (>=95%) but not matched
    if best_score >= 0.95:
        lines.append("• ⚠️  PERFECT OR NEAR-PERFECT MATCH FOUND but not matched!")
        lines.append("")
        lines.append("  This file should match based on metadata alone.")
        lines.append("  The issue is likely the DURATION FILTER blocking this match.")
        lines.append("")
        
        # Calculate duration difference
        best_file = result.closest_files[0][0]
        if best_file.get('duration') and track.get('duration_ms'):
            track_duration_sec = track['duration_ms'] / 1000
            file_duration_sec = best_file['duration']
            duration_diff = abs(file_duration_sec - track_duration_sec)
            
            lines.append(f"  Duration difference: {duration_diff:.1f} seconds")
            lines.append(f"  (Spotify: {int(track_duration_sec//60)}:{int(track_duration_sec%60):02d}, File: {int(file_duration_sec//60)}:{int(file_duration_sec%60):02d})")
            lines.append("")
            lines.append("  Recommended fix:")
            lines.append(f"  → Increase duration_tolerance from current value to at least {int(duration_diff) + 2} seconds")
            lines.append("  → Edit config or set: PSM__MATCHING__DURATION_TOLERANCE=" + str(int(duration_diff) + 2))
        else:
            lines.append("  Recommended fixes:")
            lines.append("  → Check if duration_filter is in your matching strategies")
            lines.append("  → Increase duration_tolerance (default: 2.0 seconds)")
            lines.append("  → Edit config: PSM__MATCHING__DURATION_TOLERANCE=5.0")
    
    # Normal case: Just below threshold
    elif best_score >= result.fuzzy_threshold - 0.05:
        lines.append("• The closest file is very close to the threshold!")
        # Calculate the right direction: need to LOWER threshold to be more permissive
        recommended_threshold = max(0.5, best_score - 0.02)
        lines.append(f"  → Consider lowering fuzzy_threshold from {result.fuzzy_threshold:.0%} to {recommended_threshold:.0%}")
        lines.append("  → Edit config or set: PSM__MATCHING__FUZZY_THRESHOLD=" + f"{recommended_threshold:.2f}")
    
    # Low scores: Tag issues
    elif best_score < 0.5:
        lines.append("• No close matches found. Possible issues:")
        lines.append("  → File tags don't match Spotify metadata")
        lines.append("  → File might be named differently than expected")
        lines.append(f"  → Check if file tags are correct for: {track['artist']} - {track['name']}")
    
    # Moderate scores: Tag improvements needed
    else:
        lines.append("• There are some similar files, but scores are too low.")
        lines.append("  → Check file metadata tags (artist, title, album)")
        lines.append("  → Ensure tags match Spotify metadata as closely as possible")
    
    lines.append("")
    lines.append("Run 'psm match' again after making changes.")
    
    return "\n".join(lines)
