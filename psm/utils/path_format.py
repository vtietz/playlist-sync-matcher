"""Utilities for formatting file paths in M3U playlists.

Handles conversion between absolute/relative paths and reconstruction from library roots.
"""

from __future__ import annotations
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def format_path_for_m3u(
    file_path: str | Path, playlist_path: Path, path_format: str = "absolute", library_roots: list[str] | None = None
) -> str:
    r"""Format a file path for inclusion in an M3U playlist.

    Args:
        file_path: Path to the audio file (as stored in database)
        playlist_path: Path to the M3U playlist file being created
        path_format: "absolute" or "relative"
        library_roots: List of library root paths from config (for path reconstruction)

    Returns:
        Formatted path string for M3U file

    Note:
        If library_roots is provided, the function will try to reconstruct the path
        using the configured library root that matches. This ensures the exported path
        uses the same format as the user's configuration (e.g., Z:\ instead of \\server\share).
    """
    if not isinstance(file_path, Path):
        file_path = Path(file_path)

    # Try to reconstruct path using library roots (preserves user's configured format)
    if library_roots:
        reconstructed = _reconstruct_from_library_root(file_path, library_roots)
        if reconstructed:
            file_path = reconstructed

    # Handle relative paths
    if path_format == "relative":
        try:
            # Make path relative to playlist location
            rel_path = file_path.relative_to(playlist_path.parent)
            return str(rel_path)
        except ValueError:
            # Files not on same root - fall back to absolute
            logger.warning(
                f"Cannot create relative path from {file_path} to {playlist_path.parent}, "
                "using absolute path instead"
            )
            # Fall through to absolute handling

    # Return absolute path
    return str(file_path)


def _reconstruct_from_library_root(file_path: Path, library_roots: list[str]) -> Path | None:
    r"""Reconstruct file path using configured library roots.

    This function solves the network path problem: if a user scans Z:\Artists but the
    database stores \\server\share\Artists (due to path resolution), we want to export
    Z:\Artists to match the user's configuration.

    Args:
        file_path: Absolute file path from database
        library_roots: List of library root paths from config

    Returns:
        Reconstructed path using library root, or None if no match found

    Example:
        Database has: \\diskstation\music\Artists\Song.mp3
        Config has: Z:\Artists
        Result: Z:\Artists\Song.mp3
    """
    file_path_str = str(file_path).lower().replace("/", "\\")

    for root in library_roots:
        root_path = Path(root).resolve()  # Resolve to absolute (may convert Z:\ to \\server\share)
        root_str = str(root_path).lower().replace("/", "\\")

        # Check if file path starts with this resolved root
        if file_path_str.startswith(root_str):
            # Found a match! Reconstruct using the ORIGINAL root from config
            relative_part = str(file_path)[len(str(root_path)) :].lstrip("\\/")
            reconstructed = Path(root) / relative_part
            logger.debug(f"Reconstructed path: {file_path} -> {reconstructed} (using root: {root})")
            return reconstructed

    # No matching library root found
    return None


__all__ = ["format_path_for_m3u"]
