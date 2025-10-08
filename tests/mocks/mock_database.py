from __future__ import annotations
"""In-memory mock implementation of DatabaseInterface for unit tests.

Stores data in simple Python data structures; provides minimal behavior
needed by service-layer logic. Extend incrementally.
"""
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from psm.db import DatabaseInterface, TrackRow, LibraryFileRow, MatchRow, PlaylistRow

class MockRow(dict):
    """Row-like mapping supporting dict-style access."""
    def __getattr__(self, item):  # pragma: no cover
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item)

class MockDatabase(DatabaseInterface):
    def __init__(self):
        self.playlists: Dict[Tuple[str,str], Dict[str, Any]] = {}
        self.playlist_tracks: Dict[Tuple[str,str], List[Tuple[int,str,str|None]]] = {}
        self.tracks: Dict[Tuple[str,str], Dict[str, Any]] = {}
        self.liked: Dict[Tuple[str,str], Dict[str, Any]] = {}
        self.library_files: Dict[str, Dict[str, Any]] = {}
        self.matches: List[Dict[str, Any]] = []
        self.meta: Dict[str,str] = {}
        self._closed = False
        self.call_log: List[str] = []
        self.conn = self._ConnShim(self)  # minimal shim for legacy raw SQL paths

    class _ConnShim:
        def __init__(self, outer: 'MockDatabase'):
            self._outer = outer

        def execute(self, sql: str, params: Tuple[Any,...] | Tuple[()] = ()):  # pragma: no cover - thin shim
            sql_lower = sql.lower().strip()
            # Very small subset of queries used in services; extend when needed.
            if 'from tracks' in sql_lower and 'select id' in sql_lower:
                rows = []
                for (tid,prov), data in self._outer.tracks.items():
                    rows.append(MockRow({
                        'id': tid,
                        'name': data.get('name'),
                        'artist': data.get('artist'),
                        'album': data.get('album'),
                        'year': data.get('year'),
                        'isrc': data.get('isrc'),
                        'duration_ms': data.get('duration_ms'),
                        'normalized': data.get('normalized'),
                    }))
                return self._Result(rows)
            if 'count(distinct album)' in sql_lower and 'from library_files' in sql_lower:
                albums = {data.get('album') for data in self._outer.library_files.values() if data.get('album')}
                return self._Result([ (len(albums),) ])
            if 'from library_files' in sql_lower:
                rows = []
                for i,(path,data) in enumerate(self._outer.library_files.items(), start=1):
                    rows.append(MockRow({
                        'file_id': i,
                        'id': i,
                        'path': path,
                        'title': data.get('title'),
                        'artist': data.get('artist'),
                        'album': data.get('album'),
                        'normalized': data.get('normalized'),
                        'duration': data.get('duration'),
                        'year': data.get('year'),
                    }))
                return self._Result(rows)
            # Default empty result
            return self._Result([])

        class _Result:
            def __init__(self, rows):
                self._rows = rows
            def fetchall(self):
                return self._rows
            def fetchone(self):
                return self._rows[0] if self._rows else None

    # --- playlist ---
    def upsert_playlist(self, pid: str, name: str, snapshot_id: str | None, owner_id: str | None = None, owner_name: str | None = None, provider: str = 'spotify') -> None:
        self.call_log.append('upsert_playlist')
        self.playlists[(pid,provider)] = {
            'id': pid,
            'provider': provider,
            'name': name,
            'snapshot_id': snapshot_id,
            'owner_id': owner_id,
            'owner_name': owner_name,
        }

    def playlist_snapshot_changed(self, pid: str, snapshot_id: str, provider: str = 'spotify') -> bool:
        self.call_log.append('playlist_snapshot_changed')
        existing = self.playlists.get((pid,provider))
        if not existing:
            return True
        return existing.get('snapshot_id') != snapshot_id

    def replace_playlist_tracks(self, pid: str, tracks: Sequence[Tuple[int, str, str | None]], provider: str = 'spotify'):
        self.call_log.append('replace_playlist_tracks')
        self.playlist_tracks[(pid,provider)] = list(tracks)

    def get_playlist_by_id(self, playlist_id: str, provider: str | None = None) -> Optional[PlaylistRow]:
        provider = provider or 'spotify'
        p = self.playlists.get((playlist_id, provider))
        if not p:
            return None
        track_count = len(self.playlist_tracks.get((playlist_id, provider), []))
        return PlaylistRow(
            id=p['id'],
            provider=p['provider'],
            name=p['name'],
            snapshot_id=p.get('snapshot_id'),
            owner_id=p.get('owner_id'),
            owner_name=p.get('owner_name'),
            track_count=track_count,
        )

    def get_all_playlists(self, provider: str | None = None) -> List[PlaylistRow]:
        provider = provider or 'spotify'
        rows = []
        for (pid, prov), data in self.playlists.items():
            if provider and prov != provider:
                continue
            track_count = len(self.playlist_tracks.get((pid, prov), []))
            rows.append(PlaylistRow(
                id=data['id'],
                provider=data['provider'],
                name=data['name'],
                snapshot_id=data.get('snapshot_id'),
                owner_id=data.get('owner_id'),
                owner_name=data.get('owner_name'),
                track_count=track_count,
            ))
        rows.sort(key=lambda r: r.name)
        return rows

    def count_playlists(self, provider: str | None = 'spotify') -> int:
        if provider:
            return sum(1 for (_,prov) in self.playlists if prov == provider)
        return len(self.playlists)

    # --- tracks / library ---
    def upsert_track(self, track: Dict[str, Any], provider: str = 'spotify'):
        self.call_log.append('upsert_track')
        tid = track.get('id')
        self.tracks[(tid,provider)] = track.copy()

    def upsert_liked(self, track_id: str, added_at: str, provider: str = 'spotify'):
        self.call_log.append('upsert_liked')
        self.liked[(track_id,provider)] = {'track_id': track_id, 'added_at': added_at}

    def add_library_file(self, data: Dict[str, Any]):
        self.call_log.append('add_library_file')
        self.library_files[data['path']] = data.copy()

    def add_match(self, track_id: str, file_id: int, score: float, method: str, provider: str = 'spotify'):
        self.call_log.append('add_match')
        self.matches.append({'track_id': track_id, 'file_id': file_id, 'score': score, 'method': method, 'provider': provider})

    def count_tracks(self, provider: str | None = 'spotify') -> int:
        if provider:
            return sum(1 for (_,prov) in self.tracks if prov == provider)
        return len(self.tracks)

    def count_unique_playlist_tracks(self, provider: str | None = 'spotify') -> int:
        seen: set[str] = set()
        for (pid,prov), items in self.playlist_tracks.items():
            if provider and prov != provider:
                continue
            for _, tid, _ in items:
                seen.add(tid)
        return len(seen)

    def count_liked_tracks(self, provider: str | None = 'spotify') -> int:
        if provider:
            return sum(1 for (_,prov) in self.liked if prov == provider)
        return len(self.liked)

    def count_library_files(self) -> int:
        return len(self.library_files)

    def count_matches(self) -> int:
        return len(self.matches)

    def get_missing_tracks(self) -> Iterable[Any]:
        matched_ids = {m['track_id'] for m in self.matches}
        for (tid,prov), data in self.tracks.items():
            if tid not in matched_ids:
                yield MockRow({'id': tid, 'name': data.get('name'), 'artist': data.get('artist'), 'album': data.get('album')})

    def set_meta(self, key: str, value: str):
        self.meta[key] = value

    def get_meta(self, key: str) -> Optional[str]:
        return self.meta.get(key)

    def commit(self):  # no-op
        pass

    def close(self):  # idempotent
        self._closed = True
    
    # --- Repository methods for matching engine ---
    
    def get_all_tracks(self, provider: str | None = None) -> List[TrackRow]:
        """Get all tracks with full metadata for matching."""
        rows = []
        for (tid, prov), data in self.tracks.items():
            if provider and prov != provider:
                continue
            rows.append(TrackRow(
                id=tid,
                provider=prov,
                name=data.get('name'),
                artist=data.get('artist'),
                album=data.get('album'),
                year=data.get('year'),
                isrc=data.get('isrc'),
                duration_ms=data.get('duration_ms'),
                normalized=data.get('normalized'),
                album_id=data.get('album_id'),
                artist_id=data.get('artist_id'),
            ))
        return rows
    
    def get_all_library_files(self) -> List[LibraryFileRow]:
        """Get all library files with full metadata for matching."""
        rows = []
        for i, (path, data) in enumerate(self.library_files.items(), start=1):
            rows.append(LibraryFileRow(
                id=i,
                path=path,
                title=data.get('title'),
                artist=data.get('artist'),
                album=data.get('album'),
                year=data.get('year'),
                duration=data.get('duration'),
                normalized=data.get('normalized'),
                size=data.get('size'),
                mtime=data.get('mtime'),
                partial_hash=data.get('partial_hash'),
                bitrate_kbps=data.get('bitrate_kbps'),
            ))
        return rows
    
    def get_tracks_by_ids(self, track_ids: List[str], provider: str | None = None) -> List[TrackRow]:
        """Get specific tracks by their IDs."""
        rows = []
        for tid in track_ids:
            for (stored_tid, prov), data in self.tracks.items():
                if stored_tid == tid and (not provider or prov == provider):
                    rows.append(TrackRow(
                        id=stored_tid,
                        provider=prov,
                        name=data.get('name'),
                        artist=data.get('artist'),
                        album=data.get('album'),
                        year=data.get('year'),
                        isrc=data.get('isrc'),
                        duration_ms=data.get('duration_ms'),
                        normalized=data.get('normalized'),
                        album_id=data.get('album_id'),
                        artist_id=data.get('artist_id'),
                    ))
        return rows
    
    def get_library_files_by_ids(self, file_ids: List[int]) -> List[LibraryFileRow]:
        """Get specific library files by their IDs."""
        # File IDs in mock are 1-based indices
        rows = []
        for file_id in file_ids:
            items = list(self.library_files.items())
            if 1 <= file_id <= len(items):
                path, data = items[file_id - 1]
                rows.append(LibraryFileRow(
                    id=file_id,
                    path=path,
                    title=data.get('title'),
                    artist=data.get('artist'),
                    album=data.get('album'),
                    year=data.get('year'),
                    duration=data.get('duration'),
                    normalized=data.get('normalized'),
                    size=data.get('size'),
                    mtime=data.get('mtime'),
                    partial_hash=data.get('partial_hash'),
                    bitrate_kbps=data.get('bitrate_kbps'),
                ))
        return rows
    
    def get_unmatched_tracks(self, provider: str | None = None) -> List[TrackRow]:
        """Get all tracks that don't have matches yet."""
        matched_ids = {m['track_id'] for m in self.matches}
        rows = []
        for (tid, prov), data in self.tracks.items():
            if tid not in matched_ids and (not provider or prov == provider):
                rows.append(TrackRow(
                    id=tid,
                    provider=prov,
                    name=data.get('name'),
                    artist=data.get('artist'),
                    album=data.get('album'),
                    year=data.get('year'),
                    isrc=data.get('isrc'),
                    duration_ms=data.get('duration_ms'),
                    normalized=data.get('normalized'),
                    album_id=data.get('album_id'),
                    artist_id=data.get('artist_id'),
                ))
        return rows
    
    def get_unmatched_library_files(self) -> List[LibraryFileRow]:
        """Get all library files that don't have matches yet."""
        matched_file_ids = {m['file_id'] for m in self.matches}
        rows = []
        for i, (path, data) in enumerate(self.library_files.items(), start=1):
            if i not in matched_file_ids:
                rows.append(LibraryFileRow(
                    id=i,
                    path=path,
                    title=data.get('title'),
                    artist=data.get('artist'),
                    album=data.get('album'),
                    year=data.get('year'),
                    duration=data.get('duration'),
                    normalized=data.get('normalized'),
                    size=data.get('size'),
                    mtime=data.get('mtime'),
                    partial_hash=data.get('partial_hash'),
                    bitrate_kbps=data.get('bitrate_kbps'),
                ))
        return rows
    
    def delete_matches_by_track_ids(self, track_ids: List[str]):
        """Delete all matches for given track IDs."""
        self.matches = [m for m in self.matches if m['track_id'] not in track_ids]
    
    def delete_matches_by_file_ids(self, file_ids: List[int]):
        """Delete all matches for given file IDs."""
        self.matches = [m for m in self.matches if m['file_id'] not in file_ids]
    
    def count_distinct_library_albums(self) -> int:
        """Count unique albums in library files."""
        albums = {data.get('album') for data in self.library_files.values() if data.get('album')}
        return len(albums)
    
    def get_match_confidence_counts(self) -> Dict[str, int]:
        """Get count of matches grouped by confidence level."""
        counts: Dict[str, int] = {}
        for m in self.matches:
            method = m.get('method', 'UNKNOWN')
            counts[method] = counts.get(method, 0) + 1
        return counts
    
    def get_playlist_occurrence_counts(self, track_ids: List[str]) -> Dict[str, int]:
        """Get count of playlists each track appears in."""
        counts: Dict[str, int] = {tid: 0 for tid in track_ids}
        for (pid, prov), items in self.playlist_tracks.items():
            for _, tid, _ in items:
                if tid in track_ids:
                    counts[tid] = counts.get(tid, 0) + 1
        return counts
    
    def get_liked_track_ids(self, track_ids: List[str], provider: str | None = None) -> List[str]:
        """Get which of the given track IDs are in liked_tracks."""
        result = []
        for tid in track_ids:
            for (liked_tid, prov) in self.liked.keys():
                if liked_tid == tid and (not provider or prov == provider):
                    result.append(tid)
                    break
        return result
    
    def count_playlist_tracks(self, playlist_id: str, provider: str | None = None) -> int:
        """Count tracks in a playlist."""
        tracks = self.playlist_tracks.get((playlist_id, provider or 'spotify'), [])
        return len(tracks)

__all__ = ["MockDatabase"]
