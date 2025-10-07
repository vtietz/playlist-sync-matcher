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

class SupportsRowMapping(Protocol):  # pragma: no cover - structural helper
    def __getitem__(self, key: str) -> Any: ...

class DatabaseInterface(ABC):
    # --- Playlist metadata ---
    @abstractmethod
    def upsert_playlist(self, pid: str, name: str, snapshot_id: str | None, owner_id: str | None = None, owner_name: str | None = None, provider: str = 'spotify') -> None: ...

    @abstractmethod
    def playlist_snapshot_changed(self, pid: str, snapshot_id: str, provider: str = 'spotify') -> bool: ...

    @abstractmethod
    def replace_playlist_tracks(self, pid: str, tracks: Sequence[Tuple[int, str, str | None]], provider: str = 'spotify'): ...

    @abstractmethod
    def get_playlist_by_id(self, playlist_id: str, provider: str = 'spotify') -> Optional[SupportsRowMapping]: ...

    @abstractmethod
    def get_all_playlists(self, provider: str | None = 'spotify') -> List[SupportsRowMapping]: ...

    @abstractmethod
    def count_playlists(self, provider: str | None = 'spotify') -> int: ...
    
    # --- Tracks & library ---
    @abstractmethod
    def upsert_track(self, track: Dict[str, Any], provider: str = 'spotify'): ...

    @abstractmethod
    def upsert_liked(self, track_id: str, added_at: str, provider: str = 'spotify'): ...

    @abstractmethod
    def add_library_file(self, data: Dict[str, Any]): ...

    @abstractmethod
    def add_match(self, track_id: str, file_id: int, score: float, method: str, provider: str = 'spotify'): ...

    @abstractmethod
    def count_tracks(self, provider: str | None = 'spotify') -> int: ...

    @abstractmethod
    def count_unique_playlist_tracks(self, provider: str | None = 'spotify') -> int: ...

    @abstractmethod
    def count_liked_tracks(self, provider: str | None = 'spotify') -> int: ...

    @abstractmethod
    def count_library_files(self) -> int: ...

    @abstractmethod
    def count_matches(self) -> int: ...

    # --- Reporting / queries ---
    @abstractmethod
    def get_missing_tracks(self) -> Iterable[Any]: ...

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
