from __future__ import annotations
"""Database interface abstraction for testability.

This interface defines the contract used by service-layer code. A concrete
SQLite implementation (`Database`) and an in-memory mock used in unit tests
both implement this for dependency injection.

Only methods required by services and reporting are included; extend
incrementally when new read/write paths are exercised. Keep write
operations explicit (no generic execute) to preserve test clarity.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Protocol

# Import domain models for typed returns
from .models import TrackRow, LibraryFileRow, MatchRow, PlaylistRow

class SupportsRowMapping(Protocol):  # pragma: no cover - structural helper
    def __getitem__(self, key: str) -> Any: ...

class DatabaseInterface(ABC):
    # --- Playlist metadata ---
    @abstractmethod
    def upsert_playlist(self, pid: str, name: str, snapshot_id: str | None, owner_id: str | None = None, owner_name: str | None = None, provider: str | None = None) -> None: ...

    @abstractmethod
    def playlist_snapshot_changed(self, pid: str, snapshot_id: str, provider: str | None = None) -> bool: ...

    @abstractmethod
    def replace_playlist_tracks(self, pid: str, tracks: Sequence[Tuple[int, str, str | None]], provider: str | None = None): ...

    @abstractmethod
    def get_playlist_by_id(self, playlist_id: str, provider: str | None = None) -> Optional[PlaylistRow]: ...

    @abstractmethod
    def get_all_playlists(self, provider: str | None = None) -> List[PlaylistRow]: ...

    @abstractmethod
    def count_playlists(self, provider: str | None = None) -> int: ...
    
    # --- Tracks & library ---
    @abstractmethod
    def upsert_track(self, track: Dict[str, Any], provider: str | None = None): ...

    @abstractmethod
    def upsert_liked(self, track_id: str, added_at: str, provider: str | None = None): ...

    @abstractmethod
    def add_library_file(self, data: Dict[str, Any]): ...

    @abstractmethod
    def add_match(self, track_id: str, file_id: int, score: float, method: str, provider: str | None = None, confidence: str | None = None): ...

    @abstractmethod
    def count_tracks(self, provider: str | None = None) -> int: ...

    @abstractmethod
    def count_unique_playlist_tracks(self, provider: str | None = None) -> int: ...

    @abstractmethod
    def count_liked_tracks(self, provider: str | None = None) -> int: ...

    @abstractmethod
    def count_library_files(self) -> int: ...

    @abstractmethod
    def count_matches(self) -> int: ...

    # --- Reporting / queries ---
    @abstractmethod
    def get_missing_tracks(self) -> Iterable[Any]: ...
    
    # --- Repository methods for matching engine ---
    @abstractmethod
    def get_all_tracks(self, provider: str | None = None) -> List[TrackRow]:
        """Get all tracks with full metadata for matching.
        
        Returns:
            List of TrackRow objects with id, name, artist, album, year, isrc, duration_ms, normalized
        """
        ...
    
    @abstractmethod
    def get_all_library_files(self) -> List[LibraryFileRow]:
        """Get all library files with full metadata for matching.
        
        Returns:
            List of LibraryFileRow objects with id, path, title, artist, album, year, duration, normalized
        """
        ...
    
    @abstractmethod
    def get_tracks_by_ids(self, track_ids: List[str], provider: str | None = None) -> List[TrackRow]:
        """Get specific tracks by their IDs.
        
        Args:
            track_ids: List of track IDs to retrieve
            provider: Provider name filter
            
        Returns:
            List of matching TrackRow objects
        """
        ...
    
    @abstractmethod
    def get_library_files_by_ids(self, file_ids: List[int]) -> List[LibraryFileRow]:
        """Get specific library files by their IDs.
        
        Args:
            file_ids: List of file IDs to retrieve
            
        Returns:
            List of matching LibraryFileRow objects
        """
        ...
    
    @abstractmethod
    def get_unmatched_tracks(self, provider: str | None = None) -> List[TrackRow]:
        """Get all tracks that don't have matches yet.
        
        Args:
            provider: Provider name filter
            
        Returns:
            List of unmatched TrackRow objects
        """
        ...
    
    @abstractmethod
    def get_unmatched_library_files(self) -> List[LibraryFileRow]:
        """Get all library files that don't have matches yet.
        
        Returns:
            List of unmatched LibraryFileRow objects
        """
        ...
    
    @abstractmethod
    def delete_matches_by_track_ids(self, track_ids: List[str]): ...
    
    @abstractmethod
    def delete_matches_by_file_ids(self, file_ids: List[int]): ...
    
    @abstractmethod
    def delete_all_matches(self):
        """Delete all track-to-file matches (for full re-match scenarios)."""
        ...
    
    @abstractmethod
    def count_distinct_library_albums(self) -> int:
        """Count unique albums in library files.
        
        Returns:
            Number of distinct albums
        """
        ...
    
    @abstractmethod
    def get_match_confidence_counts(self) -> Dict[str, int]:
        """Get count of matches grouped by confidence level.
        
        Returns:
            Dict mapping confidence level to count (e.g., {'CERTAIN': 10, 'HIGH': 5})
        """
        ...
    
    @abstractmethod
    def get_match_confidence_tier_counts(self) -> Dict[str, int]:
        """Get count of matches grouped by confidence tier (extracted from method string).
        
        This method robustly parses the method column (format: "score:TIER" or "score:TIER:details")
        and groups by the confidence tier (CERTAIN, HIGH, MEDIUM, LOW).
        
        Returns:
            Dict mapping confidence tier to count (e.g., {'CERTAIN': 10, 'HIGH': 5})
        """
        ...
    
    @abstractmethod
    def get_playlist_occurrence_counts(self, track_ids: List[str]) -> Dict[str, int]:
        """Get count of playlists each track appears in.
        
        Args:
            track_ids: List of track IDs to check
            
        Returns:
            Dict mapping track_id to playlist count
        """
        ...
    
    @abstractmethod
    def get_liked_track_ids(self, track_ids: List[str], provider: str | None = None) -> List[str]:
        """Get which of the given track IDs are in liked_tracks.
        
        Args:
            track_ids: List of track IDs to check
            provider: Provider name filter
            
        Returns:
            List of track IDs that are liked
        """
        ...

    # --- Export service methods ---
    @abstractmethod
    def list_playlists(self, playlist_ids: Optional[List[str]] = None, provider: str | None = None) -> List[Dict[str, Any]]:
        """List playlists with stable ordering.
        
        Args:
            playlist_ids: Optional filter to specific playlist IDs
            provider: Provider name filter (required)
            
        Returns:
            List of playlist dicts with id, name, owner_id, owner_name, sorted by owner then name
        """
        ...
    
    @abstractmethod
    def get_playlist_tracks_with_local_paths(self, playlist_id: str, provider: str | None = None) -> List[Dict[str, Any]]:
        """Get playlist tracks with matched local file paths (best match only per track).
        
        Args:
            playlist_id: Playlist ID
            provider: Provider name filter (required)
            
        Returns:
            List of dicts with position, track_id, name, artist, album, duration_ms, local_path (best match only)
        """
        ...
    
    @abstractmethod
    def get_liked_tracks_with_local_paths(self, provider: str | None = None) -> List[Dict[str, Any]]:
        """Get liked tracks with matched local file paths (best match only per track), newest first.
        
        Args:
            provider: Provider name filter (required)
            
        Returns:
            List of dicts with added_at, track_id, name, artist, album, duration_ms, local_path, ordered by added_at DESC
        """
        ...
    
    @abstractmethod
    def get_track_by_id(self, track_id: str, provider: str | None = None) -> Optional[TrackRow]:
        """Get a single track by ID.
        
        Args:
            track_id: Track ID to retrieve
            provider: Provider name filter (required)
            
        Returns:
            TrackRow if found, None otherwise
        """
        ...
    
    @abstractmethod
    def get_match_for_track(self, track_id: str, provider: str | None = None) -> Optional[Dict[str, Any]]:
        """Get match details for a track if it exists.
        
        Args:
            track_id: Track ID
            provider: Provider name filter (required)
            
        Returns:
            Dict with file_id, score, method, and library file details (path, title, artist, album, etc.)
        """
        ...

    # --- Performance / Analytics queries ---
    @abstractmethod
    def get_distinct_artists(self, provider: str | None = None) -> List[str]:
        """Get unique artist names from tracks (SQL DISTINCT).
        
        Args:
            provider: Provider name filter (required)
            
        Returns:
            Sorted list of unique artist names (excluding empty/None)
        """
        ...
    
    @abstractmethod
    def get_distinct_albums(self, provider: str | None = None) -> List[str]:
        """Get unique album names from tracks (SQL DISTINCT).
        
        Args:
            provider: Provider name filter (required)
            
        Returns:
            Sorted list of unique album names (excluding empty/None)
        """
        ...
    
    @abstractmethod
    def get_distinct_years(self, provider: str | None = None) -> List[int]:
        """Get unique years from tracks (SQL DISTINCT).
        
        Args:
            provider: Provider name filter (required)
            
        Returns:
            Sorted list of unique years (newest first, excluding None)
        """
        ...
    
    @abstractmethod
    def get_playlist_coverage(self, provider: str | None = None) -> List[Dict[str, Any]]:
        """Get playlist coverage statistics in a single SQL query.
        
        Computes total tracks and matched tracks per playlist using aggregation
        to avoid N+1 queries.
        
        Args:
            provider: Provider name filter (required)
            
        Returns:
            List of dicts with id, name, owner_id, owner_name, track_count,
            matched_count, unmatched_count, coverage (percentage)
        """
        ...
    
    @abstractmethod
    def list_unified_tracks_min(
        self,
        provider: str | None = None,
        sort_column: Optional[str] = None,
        sort_order: str = 'ASC',
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get minimal unified tracks (one row per track, no playlists aggregation).
        
        Returns core track metadata with matched flag computed in SQL.
        Defers playlist name concatenation to lazy loading for performance.
        
        Args:
            provider: Provider name filter (required)
            sort_column: Column name to sort by (name, artist, album, year)
            sort_order: 'ASC' or 'DESC'
            limit: Maximum rows to return (for paging)
            offset: Row offset (for paging)
            
        Returns:
            List of dicts with: id, name, artist, album, year, matched (bool), local_path
        """
        ...
    
    @abstractmethod
    def get_playlists_for_track_ids(
        self,
        track_ids: List[str],
        provider: str | None = None
    ) -> Dict[str, str]:
        """Get comma-separated playlist names for each track ID.
        
        Uses SQL GROUP_CONCAT for performance instead of Python loops.
        
        Args:
            track_ids: List of track IDs to look up
            provider: Provider name filter (required)
            
        Returns:
            Dict mapping track_id -> "Playlist A, Playlist B, ..." (sorted)
        """
        ...
    
    @abstractmethod
    def get_track_ids_for_playlist(
        self,
        playlist_name: str,
        provider: str | None = None
    ) -> set:
        """Get set of track IDs that belong to a specific playlist.
        
        Used for efficient playlist filtering in GUI without loading playlists column.
        
        Args:
            playlist_name: Name of playlist to filter by
            provider: Provider name filter (required)
            
        Returns:
            Set of track IDs in the playlist
        """
        ...
    
    @abstractmethod
    def get_playlists_containing_tracks(
        self,
        track_ids: List[str],
        provider: str | None = None
    ) -> List[str]:
        """Get playlist IDs that contain any of the given track IDs.
        
        Used in watch mode to determine which playlists are affected by track matches.
        
        Args:
            track_ids: List of track IDs to check
            provider: Provider name filter (required)
            
        Returns:
            Sorted list of distinct playlist IDs containing at least one of the tracks
        """
        ...

    # --- Meta ---
    @abstractmethod
    def set_meta(self, key: str, value: str): ...

    @abstractmethod
    def get_meta(self, key: str) -> Optional[str]: ...

    # --- Connection / lifecycle ---
    @abstractmethod
    def commit(self): ...

    @abstractmethod
    def close(self): ...

__all__ = ["DatabaseInterface"]
