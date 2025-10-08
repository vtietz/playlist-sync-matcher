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
        """Get all playlists with track counts.
        
        Returns:
            List of dicts with id, name, owner_id, owner_name, track_count
        """
        return self.db.list_playlists(provider=self._provider)
    
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
