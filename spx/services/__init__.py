"""Service layer for spotify-m3u-sync.

This package contains orchestration logic extracted from CLI commands,
providing cleaner separation of concerns and better testability.

Services handle:
- Business logic orchestration
- Coordination between multiple modules
- High-level workflows

This allows CLI commands to focus on:
- User interaction
- Input validation
- Output formatting
"""

from .pull_service import pull_spotify_data
from .match_service import run_matching
from .export_service import export_playlists
from .playlist_service import (
    pull_single_playlist,
    match_single_playlist,
    export_single_playlist,
    sync_single_playlist,
)
from .analysis_service import (
    analyze_library_quality,
    print_quality_report,
    QualityReport,
    QualityIssue,
)

__all__ = [
    'pull_spotify_data',
    'run_matching',
    'export_playlists',
    'pull_single_playlist',
    'match_single_playlist',
    'export_single_playlist',
    'sync_single_playlist',
    'analyze_library_quality',
    'print_quality_report',
    'QualityReport',
    'QualityIssue',
]
