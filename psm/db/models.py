"""Domain model types for database entities.

These dataclasses provide type-safe representations of database rows,
improving IDE support, type checking, and making the data contracts explicit.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any


@dataclass
class TrackRow:
    """Represents a track from the tracks table."""
    id: str
    provider: str
    name: Optional[str]
    artist: Optional[str]
    album: Optional[str]
    year: Optional[int]
    isrc: Optional[str]
    duration_ms: Optional[int]
    normalized: Optional[str]
    album_id: Optional[str] = None
    artist_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for compatibility with existing code."""
        return asdict(self)

    def keys(self):
        """Provide dict-like keys() method for compatibility."""
        return self.to_dict().keys()

    def __getitem__(self, key: str) -> Any:
        """Provide dict-like subscript access for compatibility."""
        return getattr(self, key)

    @classmethod
    def from_row(cls, row) -> TrackRow:
        """Convert sqlite3.Row to TrackRow.

        Args:
            row: sqlite3.Row object with track columns

        Returns:
            TrackRow instance
        """
        return cls(
            id=row['id'],
            provider=row['provider'],
            name=row['name'],
            artist=row['artist'],
            album=row['album'],
            year=row['year'],
            isrc=row['isrc'],
            duration_ms=row['duration_ms'],
            normalized=row['normalized'],
            album_id=row['album_id'] if 'album_id' in row.keys() else None,
            artist_id=row['artist_id'] if 'artist_id' in row.keys() else None,
        )


@dataclass
class LibraryFileRow:
    """Represents a file from the library_files table."""
    id: int
    path: str
    title: Optional[str]
    artist: Optional[str]
    album: Optional[str]
    year: Optional[int]
    duration: Optional[float]
    normalized: Optional[str]
    size: Optional[int] = None
    mtime: Optional[float] = None
    partial_hash: Optional[str] = None
    bitrate_kbps: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for compatibility with existing code."""
        return asdict(self)

    def keys(self):
        """Provide dict-like keys() method for compatibility."""
        return self.to_dict().keys()

    def __getitem__(self, key: str) -> Any:
        """Provide dict-like subscript access for compatibility."""
        return getattr(self, key)

    @classmethod
    def from_row(cls, row) -> LibraryFileRow:
        """Convert sqlite3.Row to LibraryFileRow.

        Args:
            row: sqlite3.Row object with library_file columns

        Returns:
            LibraryFileRow instance
        """
        return cls(
            id=row['id'],
            path=row['path'],
            title=row['title'],
            artist=row['artist'],
            album=row['album'],
            year=row['year'],
            duration=row['duration'],
            normalized=row['normalized'],
            size=row['size'] if 'size' in row.keys() else None,
            mtime=row['mtime'] if 'mtime' in row.keys() else None,
            partial_hash=row['partial_hash'] if 'partial_hash' in row.keys() else None,
            bitrate_kbps=row['bitrate_kbps'] if 'bitrate_kbps' in row.keys() else None,
        )


@dataclass
class MatchRow:
    """Represents a match from the matches table."""
    track_id: str
    provider: str
    file_id: int
    score: float
    method: str
    confidence: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for compatibility with existing code."""
        return asdict(self)

    def keys(self):
        """Provide dict-like keys() method for compatibility."""
        return self.to_dict().keys()

    def __getitem__(self, key: str) -> Any:
        """Provide dict-like subscript access for compatibility."""
        return getattr(self, key)

    @classmethod
    def from_row(cls, row) -> MatchRow:
        """Convert sqlite3.Row to MatchRow.

        Args:
            row: sqlite3.Row object with match columns

        Returns:
            MatchRow instance
        """
        return cls(
            track_id=row['track_id'],
            provider=row['provider'],
            file_id=row['file_id'],
            score=row['score'],
            method=row['method'],
            confidence=row['confidence'] if 'confidence' in row.keys() else None,
        )


@dataclass
class PlaylistRow:
    """Represents a playlist from the playlists table."""
    id: str
    provider: str
    name: str
    snapshot_id: Optional[str]
    owner_id: Optional[str] = None
    owner_name: Optional[str] = None
    track_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for compatibility with existing code."""
        return asdict(self)

    def keys(self):
        """Provide dict-like keys() method for compatibility."""
        return self.to_dict().keys()

    def __getitem__(self, key: str) -> Any:
        """Provide dict-like subscript access for compatibility."""
        return getattr(self, key)

    @classmethod
    def from_row(cls, row) -> PlaylistRow:
        """Convert sqlite3.Row to PlaylistRow.

        Args:
            row: sqlite3.Row object with playlist columns

        Returns:
            PlaylistRow instance
        """
        return cls(
            id=row['id'],
            provider=row['provider'],
            name=row['name'],
            snapshot_id=row['snapshot_id'],
            owner_id=row['owner_id'] if 'owner_id' in row.keys() else None,
            owner_name=row['owner_name'] if 'owner_name' in row.keys() else None,
            track_count=row['track_count'] if 'track_count' in row.keys() else 0,
        )


__all__ = [
    'TrackRow',
    'LibraryFileRow',
    'MatchRow',
    'PlaylistRow',
]
