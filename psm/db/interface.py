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
    def add_match(self, track_id: str, file_id: int, score: float, method: str, provider: str | None = None): ...

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
