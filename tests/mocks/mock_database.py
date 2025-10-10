from __future__ import annotations
"""In-memory mock implementation of DatabaseInterface for unit tests.

Stores data in simple Python data structures; provides minimal behavior
needed by service-layer logic. Extend incrementally.
"""
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from psm.db import DatabaseInterface
from psm.db.models import TrackRow, LibraryFileRow, MatchRow, PlaylistRow

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
    def upsert_playlist(self, pid: str, name: str, snapshot_id: str | None, owner_id: str | None = None, owner_name: str | None = None, provider: str | None = None) -> None:
        self.call_log.append('upsert_playlist')
        provider = provider or 'spotify'
        self.playlists[(pid,provider)] = {
            'id': pid,
            'provider': provider,
            'name': name,
            'snapshot_id': snapshot_id,
            'owner_id': owner_id,
            'owner_name': owner_name,
        }

    def playlist_snapshot_changed(self, pid: str, snapshot_id: str, provider: str | None = None) -> bool:
        self.call_log.append('playlist_snapshot_changed')
        provider = provider or 'spotify'
        existing = self.playlists.get((pid,provider))
        if not existing:
            return True
        return existing.get('snapshot_id') != snapshot_id

    def replace_playlist_tracks(self, pid: str, tracks: Sequence[Tuple[int, str, str | None]], provider: str | None = None):
        self.call_log.append('replace_playlist_tracks')
        provider = provider or 'spotify'
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
    def upsert_track(self, track: Dict[str, Any], provider: str | None = None):
        self.call_log.append('upsert_track')
        provider = provider or 'spotify'
        tid = track.get('id')
        if tid is not None:
            self.tracks[(tid, provider)] = track.copy()

    def upsert_liked(self, track_id: str, added_at: str, provider: str | None = None):
        self.call_log.append('upsert_liked')
        provider = provider or 'spotify'
        self.liked[(track_id,provider)] = {'track_id': track_id, 'added_at': added_at}

    def add_library_file(self, data: Dict[str, Any]):
        self.call_log.append('add_library_file')
        self.library_files[data['path']] = data.copy()

    def add_match(self, track_id: str, file_id: int, score: float, method: str, provider: str | None = None):
        self.call_log.append('add_match')
        provider = provider or 'spotify'
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
    
    def delete_all_matches(self):
        """Delete all track-to-file matches (for full re-match scenarios)."""
        self.matches = []
    
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
    
    def get_match_confidence_tier_counts(self) -> Dict[str, int]:
        """Get count of matches grouped by confidence tier (extracted from method)."""
        counts: Dict[str, int] = {}
        for m in self.matches:
            method = m.get('method', 'UNKNOWN')
            # Extract tier from "score:TIER" or "score:TIER:details" format
            if method.startswith('score:'):
                parts = method.split(':')
                tier = parts[1] if len(parts) > 1 else 'UNKNOWN'
            else:
                tier = method
            counts[tier] = counts.get(tier, 0) + 1
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
    
    # --- Export service methods ---
    
    def list_playlists(self, playlist_ids: Optional[List[str]] = None, provider: str | None = None) -> List[Dict[str, Any]]:
        """List playlists with stable ordering."""
        provider = provider or 'spotify'
        playlists = []
        for (pid, prov), data in self.playlists.items():
            if prov != provider:
                continue
            if playlist_ids and pid not in playlist_ids:
                continue
            playlists.append({
                'id': data['id'],
                'name': data['name'],
                'owner_id': data.get('owner_id'),
                'owner_name': data.get('owner_name'),
            })
        # Sort by owner_name then name
        playlists.sort(key=lambda p: (p.get('owner_name') or '', p.get('name') or ''))
        return playlists
    
    def get_playlist_tracks_with_local_paths(self, playlist_id: str, provider: str | None = None) -> List[Dict[str, Any]]:
        """Get playlist tracks with matched local file paths (best match only per track)."""
        provider = provider or 'spotify'
        tracks = self.playlist_tracks.get((playlist_id, provider), [])
        result = []
        
        # Build best matches map (highest score per track)
        best_matches: Dict[str, Dict[str, Any]] = {}
        for m in self.matches:
            if m['provider'] != provider:
                continue
            track_id = m['track_id']
            if track_id not in best_matches or m['score'] > best_matches[track_id]['score']:
                best_matches[track_id] = m
        
        # Build library files index
        lib_files = {i+1: (path, data) for i, (path, data) in enumerate(self.library_files.items())}
        
        for pos, track_id, added_at in tracks:
            track_data = self.tracks.get((track_id, provider), {})
            local_path = None
            
            # Get best match if exists
            if track_id in best_matches:
                file_id = best_matches[track_id]['file_id']
                if file_id in lib_files:
                    local_path = lib_files[file_id][0]
            
            result.append({
                'position': pos,
                'track_id': track_id,
                'name': track_data.get('name'),
                'artist': track_data.get('artist'),
                'album': track_data.get('album'),
                'duration_ms': track_data.get('duration_ms'),
                'local_path': local_path,
            })
        
        return result
    
    def get_liked_tracks_with_local_paths(self, provider: str | None = None) -> List[Dict[str, Any]]:
        """Get liked tracks with matched local file paths (best match only per track), newest first."""
        provider = provider or 'spotify'
        
        # Build best matches map
        best_matches: Dict[str, Dict[str, Any]] = {}
        for m in self.matches:
            if m['provider'] != provider:
                continue
            track_id = m['track_id']
            if track_id not in best_matches or m['score'] > best_matches[track_id]['score']:
                best_matches[track_id] = m
        
        # Build library files index
        lib_files = {i+1: (path, data) for i, (path, data) in enumerate(self.library_files.items())}
        
        # Get liked tracks for this provider
        liked_tracks = []
        for (track_id, prov), data in self.liked.items():
            if prov != provider:
                continue
            track_data = self.tracks.get((track_id, prov), {})
            local_path = None
            
            # Get best match if exists
            if track_id in best_matches:
                file_id = best_matches[track_id]['file_id']
                if file_id in lib_files:
                    local_path = lib_files[file_id][0]
            
            liked_tracks.append({
                'added_at': data.get('added_at'),
                'track_id': track_id,
                'name': track_data.get('name'),
                'artist': track_data.get('artist'),
                'album': track_data.get('album'),
                'duration_ms': track_data.get('duration_ms'),
                'local_path': local_path,
            })
        
        # Sort by added_at DESC (newest first)
        liked_tracks.sort(key=lambda t: t.get('added_at') or '', reverse=True)
        return liked_tracks
    
    def get_track_by_id(self, track_id: str, provider: str | None = None) -> Optional[TrackRow]:
        """Get a single track by ID."""
        provider = provider or 'spotify'
        data = self.tracks.get((track_id, provider))
        if not data:
            return None
        return TrackRow(
            id=track_id,
            provider=provider,
            name=data.get('name'),
            artist=data.get('artist'),
            album=data.get('album'),
            year=data.get('year'),
            isrc=data.get('isrc'),
            duration_ms=data.get('duration_ms'),
            normalized=data.get('normalized'),
            album_id=data.get('album_id'),
            artist_id=data.get('artist_id'),
        )
    
    def get_match_for_track(self, track_id: str, provider: str | None = None) -> Optional[Dict[str, Any]]:
        """Get match details for a track if it exists."""
        provider = provider or 'spotify'
        
        # Find match for this track
        match = None
        for m in self.matches:
            if m['track_id'] == track_id and m['provider'] == provider:
                match = m
                break
        
        if not match:
            return None
        
        # Get library file details
        lib_files = list(self.library_files.items())
        file_id = match['file_id']
        if 1 <= file_id <= len(lib_files):
            path, data = lib_files[file_id - 1]
            return {
                'file_id': file_id,
                'score': match['score'],
                'method': match['method'],
                'path': path,
                'title': data.get('title'),
                'artist': data.get('artist'),
                'album': data.get('album'),
                'duration': data.get('duration'),
                'normalized': data.get('normalized'),
                'year': data.get('year'),
            }
        
        return None
    
    # --- Missing abstract methods (added for test compatibility) ---
    
    def get_distinct_albums(self, provider: str | None = None) -> List[str]:
        """Get list of distinct albums from library files."""
        albums = set()
        for data in self.library_files.values():
            album = data.get('album')
            if album:
                albums.add(album)
        return sorted(list(albums))
    
    def get_distinct_artists(self, provider: str | None = None) -> List[str]:
        """Get list of distinct artists from library files."""
        artists = set()
        for data in self.library_files.values():
            artist = data.get('artist')
            if artist:
                artists.add(artist)
        return sorted(list(artists))
    
    def get_distinct_years(self, provider: str | None = None) -> List[int]:
        """Get list of distinct years from library files."""
        years = set()
        for data in self.library_files.values():
            year = data.get('year')
            if year:
                years.add(year)
        return sorted(list(years))
    
    def get_playlist_coverage(self, provider: str | None = None) -> List[Dict[str, Any]]:
        """Get playlist coverage statistics."""
        provider = provider or 'spotify'
        result = []
        for (pid, prov), playlist in self.playlists.items():
            if prov != provider:
                continue
            tracks_in_playlist = self.playlist_tracks.get((pid, prov), [])
            total = len(tracks_in_playlist)
            matched = sum(1 for _, tid, _ in tracks_in_playlist 
                         if any(m.get('track_id') == tid and m.get('provider') == prov 
                               for m in self.matches))
            result.append({
                'id': pid,
                'name': playlist['name'],
                'total': total,
                'matched': matched,
                'coverage_pct': int((matched / total * 100) if total > 0 else 0)
            })
        return result
    
    def get_playlists_for_track_ids(self, track_ids: List[str], provider: str | None = None) -> Dict[str, str]:
        """Get comma-separated playlist names for each track ID."""
        provider = provider or 'spotify'
        result = {}
        for track_id in track_ids:
            playlists = []
            for (pid, prov), tracks in self.playlist_tracks.items():
                if prov != provider:
                    continue
                if any(tid == track_id for _, tid, _ in tracks):
                    playlist = self.playlists.get((pid, prov))
                    if playlist:
                        playlists.append(playlist['name'])
            result[track_id] = ', '.join(sorted(playlists))
        return result
    
    def get_track_ids_for_playlist(self, playlist_name: str, provider: str | None = None) -> set:
        """Get set of track IDs in a playlist."""
        provider = provider or 'spotify'
        track_ids = set()
        for (pid, prov), playlist in self.playlists.items():
            if prov != provider or playlist.get('name') != playlist_name:
                continue
            tracks = self.playlist_tracks.get((pid, prov), [])
            for _, tid, _ in tracks:
                track_ids.add(tid)
        return track_ids
    
    def list_unified_tracks_min(
        self,
        provider: str | None = None,
        sort_column: Optional[str] = None,
        sort_order: str = 'ASC',
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get minimal unified tracks data (for GUI)."""
        provider = provider or 'spotify'
        result = []
        for (tid, prov), track in self.tracks.items():
            if prov != provider:
                continue
            # Find match
            match = next((m for m in self.matches 
                         if m.get('track_id') == tid and m.get('provider') == prov), None)
            
            result.append({
                'id': tid,
                'name': track.get('name'),
                'artist': track.get('artist'),
                'album': track.get('album'),
                'year': track.get('year'),
                'matched': match is not None,
                'confidence': match.get('confidence') if match else None,
                'quality': match.get('quality') if match else None,
                'local_path': match.get('path') if match else None,
                'playlists': ''  # Populated separately
            })
        
        # Simple sorting if requested
        if sort_column and sort_column in ['name', 'artist', 'album', 'year']:
            result.sort(key=lambda x: x.get(sort_column) or '', reverse=(sort_order == 'DESC'))
        
        # Apply pagination
        if limit:
            result = result[offset:offset+limit]
        elif offset:
            result = result[offset:]
        
        return result

__all__ = ["MockDatabase"]
