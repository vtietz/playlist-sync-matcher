"""Data facade providing read-only access to database via DatabaseInterface.

This module provides a clean API for the GUI to retrieve data without
writing SQL. All methods use the existing DatabaseInterface.
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
from psm.db.interface import DatabaseInterface
from psm.db.models import TrackRow, PlaylistRow
import logging

logger = logging.getLogger(__name__)


class DataFacade:
    """Read-only data access layer for GUI using DatabaseInterface only."""
    
    def __init__(self, db: DatabaseInterface, provider: str = 'spotify'):
        """Initialize with a database instance.
        
        Args:
            db: DatabaseInterface implementation (typically sqlite_impl.Database)
            provider: Provider name (default: 'spotify')
        """
        self.db = db
        self._provider = provider
    
    def list_playlists(self) -> List[Dict[str, Any]]:
        """Get all playlists with track counts and match statistics.
        
        Returns:
            List of dicts with id, name, owner_id, owner_name, track_count,
            matched_count, unmatched_count, coverage (percentage).
        """
        # Use SQL aggregation for performance (single query instead of N+1)
        return self.db.get_playlist_coverage(provider=self._provider)
    
    def get_playlist_detail(self, playlist_id: str) -> List[Dict[str, Any]]:
        """Get tracks in a playlist with best-match local paths.
        
        Args:
            playlist_id: Playlist ID to retrieve
            
        Returns:
            List of dicts with position, track_id, name, artist, album, 
            duration_ms, local_path (best match only, provider-aware)
        """
        return self.db.get_playlist_tracks_with_local_paths(
            playlist_id, 
            provider=self._provider
        )
    
    def get_playlist_by_id(self, playlist_id: str) -> Optional[PlaylistRow]:
        """Get playlist metadata by ID.
        
        Args:
            playlist_id: Playlist ID
            
        Returns:
            PlaylistRow or None if not found
        """
        return self.db.get_playlist_by_id(playlist_id, provider=self._provider)
    
    def list_unmatched_tracks(self) -> List[Dict[str, Any]]:
        """Get all tracks without local file matches.
        
        Returns:
            List of dicts with id, name, artist, album, year, isrc, duration_ms
        """
        all_tracks = self.db.get_all_tracks(provider=self._provider)
        unmatched = []
        
        for track in all_tracks:
            match = self.db.get_match_for_track(track.id, provider=self._provider)
            if match is None:
                unmatched.append({
                    'id': track.id,
                    'name': track.name,
                    'artist': track.artist,
                    'album': track.album,
                    'year': track.year,
                    'isrc': track.isrc,
                    'duration_ms': track.duration_ms,
                })
        
        return unmatched
    
    def list_matched_tracks(self) -> List[Dict[str, Any]]:
        """Get all tracks with local file matches.
        
        Returns:
            List of dicts with id, name, artist, album, local_path, 
            score, method
        """
        all_tracks = self.db.get_all_tracks(provider=self._provider)
        matched = []
        
        for track in all_tracks:
            match = self.db.get_match_for_track(track.id, provider=self._provider)
            if match is not None:
                matched.append({
                    'id': track.id,
                    'name': track.name,
                    'artist': track.artist,
                    'album': track.album,
                    'local_path': match.get('path', ''),
                    'score': match.get('score', 0.0),
                    'method': match.get('method', 'UNKNOWN'),
                })
        
        return matched
    
    def list_playlist_coverage(self) -> List[Dict[str, Any]]:
        """Get coverage statistics for all playlists.
        
        Returns:
            List of dicts with id, name, total, matched, coverage_pct
        """
        playlists = self.list_playlists()
        coverage = []
        
        for pl in playlists:
            playlist_id = pl['id']
            tracks = self.db.get_playlist_tracks_with_local_paths(
                playlist_id, 
                provider=self._provider
            )
            
            total = len(tracks)
            matched = sum(1 for t in tracks if t.get('local_path'))
            pct = (matched / total * 100) if total > 0 else 0.0
            
            coverage.append({
                'id': playlist_id,
                'name': pl['name'],
                'total': total,
                'matched': matched,
                'coverage_pct': pct,
            })
        
        return coverage
    
    def list_unmatched_albums(self) -> List[Dict[str, Any]]:
        """Get albums with missing tracks.
        
        Returns:
            List of dicts with artist, album, total, matched, missing, 
            percent_complete
        """
        all_tracks = self.db.get_all_tracks(provider=self._provider)
        
        # Group by (artist, album)
        albums: Dict[tuple, Dict[str, Any]] = {}
        
        for track in all_tracks:
            if not track.artist or not track.album:
                continue
            
            key = (track.artist, track.album)
            if key not in albums:
                albums[key] = {
                    'artist': track.artist,
                    'album': track.album,
                    'total': 0,
                    'matched': 0,
                }
            
            albums[key]['total'] += 1
            
            # Check if matched
            match = self.db.get_match_for_track(track.id, provider=self._provider)
            if match is not None:
                albums[key]['matched'] += 1
        
        # Compute missing and percent, filter to only incomplete albums
        result = []
        for album_data in albums.values():
            total = album_data['total']
            matched = album_data['matched']
            missing = total - matched
            
            if missing > 0:  # Only show incomplete albums
                result.append({
                    'artist': album_data['artist'],
                    'album': album_data['album'],
                    'total': total,
                    'matched': matched,
                    'missing': missing,
                    'percent_complete': (matched / total * 100) if total > 0 else 0.0,
                })
        
        # Sort by percent complete ascending (most incomplete first)
        result.sort(key=lambda x: x['percent_complete'])
        
        return result
    
    def list_liked_tracks(self) -> List[Dict[str, Any]]:
        """Get liked tracks with best-match local paths.
        
        Returns:
            List of dicts with track info and local_path (newest first)
        """
        return self.db.get_liked_tracks_with_local_paths(provider=self._provider)
    
    def get_counts(self) -> Dict[str, int]:
        """Get summary counts for the database.
        
        Returns:
            Dict with playlists, tracks, library_files, matches counts
        """
        # Use count methods if available, otherwise fallback to list lengths
        try:
            playlists = self.db.count_playlists(provider=self._provider)
        except (AttributeError, NotImplementedError):
            playlists = len(self.db.list_playlists(provider=self._provider))
        
        try:
            tracks = self.db.count_tracks(provider=self._provider)
        except (AttributeError, NotImplementedError):
            tracks = len(self.db.get_all_tracks(provider=self._provider))
        
        try:
            library_files = self.db.count_library_files()
        except (AttributeError, NotImplementedError):
            library_files = 0
        
        try:
            matches = self.db.count_matches()
        except (AttributeError, NotImplementedError):
            matches = 0
        
        try:
            liked = self.db.count_liked_tracks(provider=self._provider)
        except (AttributeError, NotImplementedError):
            liked = 0
        
        return {
            'playlists': playlists,
            'tracks': tracks,
            'library_files': library_files,
            'matches': matches,
            'liked': liked,
        }
    
    def list_all_tracks_unified(self) -> List[Dict[str, Any]]:
        """Get all unique tracks with concatenated playlist names.
        
        Returns:
            List of dicts with: name, artist, album, year, matched (Yes/No),
            local_path, playlists (comma-separated names)
        """
        from collections import defaultdict
        from typing import Dict, List, Any
        
        # Group tracks by track_id to concatenate playlists
        track_map: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'playlists': [],
            'data': None
        })
        
        # Get all playlists
        playlists = self.db.list_playlists(provider=self._provider)
        
        for playlist in playlists:
            playlist_id = playlist['id']
            playlist_name = playlist['name']
            
            # Get tracks for this playlist
            tracks = self.db.get_playlist_tracks_with_local_paths(
                playlist_id,
                provider=self._provider
            )
            
            for track in tracks:
                track_id = track.get('track_id', '')
                if not track_id:
                    continue
                
                # Add playlist name to this track
                track_map[track_id]['playlists'].append(playlist_name)
                
                # Store track data (use first occurrence)
                if track_map[track_id]['data'] is None:
                    has_match = bool(track.get('local_path'))
                    matched_str = "Yes" if has_match else "No"
                    
                    track_map[track_id]['data'] = {
                        'id': track_id,
                        'name': track.get('name', ''),
                        'artist': track.get('artist', ''),
                        'album': track.get('album', ''),
                        'year': track.get('year'),  # May be None
                        'matched': matched_str,
                        'local_path': track.get('local_path', ''),
                    }
        
        # Build result with concatenated playlists
        result: List[Dict[str, Any]] = []
        for track_id, track_info in track_map.items():
            if track_info['data'] is None:
                continue
            
            data = dict(track_info['data'])  # Create a copy
            # Concatenate playlist names (sorted for consistency)
            playlists_list = track_info['playlists']
            data['playlists'] = ', '.join(sorted(playlists_list))
            result.append(data)
        
        return result
    
    def list_all_tracks_unified_fast(self) -> List[Dict[str, Any]]:
        """Get all unique tracks with minimal fields (fast path).
        
        Returns one row per track without pre-aggregating playlists.
        Use this for initial load, then lazy-load playlists for visible rows.
        
        Returns:
            List of dicts with: id, name, artist, album, year, matched (bool),
            local_path, playlists (empty string - to be filled lazily)
        """
        tracks = self.db.list_unified_tracks_min(provider=self._provider)
        
        # Add empty playlists field for compatibility with existing model
        for track in tracks:
            track['playlists'] = ''  # Will be populated lazily for visible rows
        
        return tracks
    
    def get_playlists_for_tracks(self, track_ids: List[str]) -> Dict[str, str]:
        """Get comma-separated playlist names for given track IDs.
        
        Args:
            track_ids: List of track IDs
            
        Returns:
            Dict mapping track_id -> "Playlist A, Playlist B, ..."
        """
        return self.db.get_playlists_for_track_ids(track_ids, provider=self._provider)
    
    def get_track_ids_for_playlist(self, playlist_name: str) -> set:
        """Get set of track IDs that belong to a specific playlist.
        
        Args:
            playlist_name: Name of playlist to filter by
            
        Returns:
            Set of track IDs in the playlist
        """
        return self.db.get_track_ids_for_playlist(playlist_name, provider=self._provider)
    
    def get_unique_owners(self) -> List[str]:
        """Get list of unique playlist owners.
        
        Returns:
            Sorted list of unique owner names
        """
        playlists = self.db.list_playlists(provider=self._provider)
        owners = set()
        for p in playlists:
            owner = p.get('owner_name', p.get('owner_id', 'Unknown'))
            if owner:
                owners.add(owner)
        return sorted(owners)
    
    def get_unique_artists(self) -> List[str]:
        """Get list of unique artists from all tracks.
        
        Returns:
            Sorted list of unique artist names (excluding empty)
        """
        # Use SQL DISTINCT for performance
        return self.db.get_distinct_artists(provider=self._provider)
    
    def get_unique_albums(self) -> List[str]:
        """Get list of unique albums from all tracks.
        
        Returns:
            Sorted list of unique album names (excluding empty)
        """
        # Use SQL DISTINCT for performance
        return self.db.get_distinct_albums(provider=self._provider)
    
    def get_unique_years(self) -> List[int]:
        """Get list of unique years from all tracks.
        
        Returns:
            Sorted list of unique years (excluding None)
        """
        # Use SQL DISTINCT for performance
        return self.db.get_distinct_years(provider=self._provider)
