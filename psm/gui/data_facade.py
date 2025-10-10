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
        
        Includes a special virtual "❤️ Liked Songs" playlist at the top.
        
        Returns:
            List of dicts with id, name, owner_id, owner_name, track_count,
            matched_count, unmatched_count, coverage (percentage), relevance.
            Relevance = track_count * (100 - coverage%) / 100 (high tracks + low coverage = high relevance)
        """
        # Use SQL aggregation for performance (single query instead of N+1)
        playlists = self.db.get_playlist_coverage(provider=self._provider)
        
        # Add relevance score to each playlist
        for playlist in playlists:
            track_count = playlist.get('track_count', 0)
            coverage_pct = playlist.get('coverage', 0)
            # Relevance: high track count + low coverage = high relevance
            relevance = track_count * (100 - coverage_pct) / 100
            playlist['relevance'] = round(relevance, 1)
        
        # Create virtual "Liked Songs" playlist entry
        # Get liked songs stats from database
        liked_track_count = self.db.count_liked_tracks(provider=self._provider)
        
        if liked_track_count > 0:
            # Count matched liked tracks
            liked_tracks_data = self.db.get_liked_tracks_with_local_paths(provider=self._provider)
            matched_count = sum(1 for t in liked_tracks_data if t.get('local_path'))
            unmatched_count = liked_track_count - matched_count
            coverage_pct = int((matched_count / liked_track_count * 100)) if liked_track_count > 0 else 0
            relevance = liked_track_count * (100 - coverage_pct) / 100
            
            # Get current user info for owner
            user = self.db.get_meta('spotify_user_id') or 'You'
            
            liked_playlist = {
                'id': '__LIKED_SONGS__',  # Special ID to identify virtual playlist
                'name': ' ❤️ Liked Songs',  # Leading space ensures it sorts to the top
                'owner_id': user,
                'owner_name': user,
                'track_count': liked_track_count,
                'matched_count': matched_count,
                'unmatched_count': unmatched_count,
                'coverage': coverage_pct,
                'relevance': round(relevance, 1),
            }
            
            # Insert at the beginning of the list
            playlists.insert(0, liked_playlist)
        
        return playlists
    
    def get_playlist_detail(self, playlist_id: str) -> List[Dict[str, Any]]:
        """Get tracks in a playlist with best-match local paths.
        
        Handles both regular playlists and the special "❤️ Liked Songs" virtual playlist.
        
        Args:
            playlist_id: Playlist ID to retrieve (or '__LIKED_SONGS__' for liked songs)
            
        Returns:
            List of dicts with position, track_id, name, artist, album, 
            duration_ms, local_path (best match only, provider-aware)
        """
        # Handle virtual Liked Songs playlist
        if playlist_id == '__LIKED_SONGS__':
            return self.db.get_liked_tracks_with_local_paths(provider=self._provider)
        
        # Regular playlist
        return self.db.get_playlist_tracks_with_local_paths(
            playlist_id, 
            provider=self._provider
        )
    
    def get_playlist_by_id(self, playlist_id: str) -> Optional[PlaylistRow]:
        """Get playlist metadata by ID.
        
        Handles both regular playlists and the special "❤️ Liked Songs" virtual playlist.
        
        Args:
            playlist_id: Playlist ID (or '__LIKED_SONGS__' for liked songs)
            
        Returns:
            PlaylistRow or None if not found
        """
        # Handle virtual Liked Songs playlist
        if playlist_id == '__LIKED_SONGS__':
            from psm.db.models import PlaylistRow
            liked_count = self.db.count_liked_tracks(provider=self._provider)
            user = self.db.get_meta('spotify_user_id') or 'You'
            
            # Create a PlaylistRow-like object for Liked Songs
            return PlaylistRow(
                id='__LIKED_SONGS__',
                provider=self._provider,
                name='❤️ Liked Songs',
                snapshot_id=None,
                owner_id=user,
                owner_name=user,
                track_count=liked_count
            )
        
        # Regular playlist
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
        
        Handles both regular playlists and the special " ❤️ Liked Songs" virtual playlist.
        
        Args:
            playlist_name: Name of playlist to filter by (or ' ❤️ Liked Songs')
            
        Returns:
            Set of track IDs in the playlist
        """
        # Handle virtual Liked Songs playlist (with leading space for sorting)
        if playlist_name == ' ❤️ Liked Songs':
            # Get all liked track IDs
            cursor = self.db.conn.execute(
                "SELECT track_id FROM liked_tracks WHERE provider = ?",
                (self._provider,)
            )
            return {row[0] for row in cursor.fetchall()}
        
        # Regular playlist
        return self.db.get_track_ids_for_playlist(playlist_name, provider=self._provider)
    
    def get_artist_for_album(self, album_name: str) -> Optional[str]:
        """Get the primary artist name for a given album.
        
        Args:
            album_name: Album name to look up
            
        Returns:
            Artist name for this album, or None if not found.
            If album has multiple artists, returns the most common one.
        """
        rows = self.db.conn.execute("""
            SELECT artist, COUNT(*) as track_count
            FROM tracks
            WHERE album = ? AND provider = ? AND artist IS NOT NULL
            GROUP BY artist
            ORDER BY track_count DESC
            LIMIT 1
        """, (album_name, self._provider)).fetchall()
        
        if rows:
            return rows[0]['artist']
        return None
    
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
    
    def list_albums(self) -> List[Dict[str, Any]]:
        """Get all albums with aggregated statistics.
        
        Returns:
            List of dicts with album, artist, track_count, playlist_count, coverage, relevance.
            Coverage format: "75% (75/100)" (percentage of matched tracks).
            Relevance = track_count * (100 - coverage%) / 100 (high tracks + low coverage = high relevance)
        """
        rows = self.db.conn.execute("""
            SELECT 
                t.album,
                t.artist,
                COUNT(DISTINCT t.id) as track_count,
                COUNT(DISTINCT pt.playlist_id) as playlist_count,
                COUNT(DISTINCT CASE WHEN m.track_id IS NOT NULL THEN t.id END) as matched_count
            FROM tracks t
            LEFT JOIN playlist_tracks pt ON t.id = pt.track_id AND t.provider = pt.provider
            LEFT JOIN matches m ON t.id = m.track_id AND t.provider = m.provider
            WHERE t.provider = ?
              AND t.album IS NOT NULL
              AND t.artist IS NOT NULL
            GROUP BY t.album, t.artist
            ORDER BY playlist_count DESC, track_count DESC, t.artist, t.album
        """, (self._provider,)).fetchall()
        
        results = []
        for row in rows:
            track_count = row['track_count']
            matched_count = row['matched_count']
            percentage = int((matched_count / track_count * 100)) if track_count > 0 else 0
            coverage = f"{percentage}% ({matched_count}/{track_count})"
            
            # Relevance: high track count + low coverage = high relevance
            relevance = track_count * (100 - percentage) / 100
            
            results.append({
                'album': row['album'],
                'artist': row['artist'],
                'track_count': track_count,
                'playlist_count': row['playlist_count'],
                'coverage': coverage,
                'relevance': round(relevance, 1),
            })
        
        return results
    
    def list_artists(self) -> List[Dict[str, Any]]:
        """Get all artists with aggregated statistics.
        
        Returns:
            List of dicts with artist, track_count, album_count, playlist_count, coverage, relevance.
            Coverage format: "75% (75/100)" (percentage of matched tracks).
            Relevance = track_count * (100 - coverage%) / 100 (high tracks + low coverage = high relevance)
        """
        rows = self.db.conn.execute("""
            SELECT 
                t.artist,
                COUNT(DISTINCT t.id) as track_count,
                COUNT(DISTINCT t.album) as album_count,
                COUNT(DISTINCT pt.playlist_id) as playlist_count,
                COUNT(DISTINCT CASE WHEN m.track_id IS NOT NULL THEN t.id END) as matched_count
            FROM tracks t
            LEFT JOIN playlist_tracks pt ON t.id = pt.track_id AND t.provider = pt.provider
            LEFT JOIN matches m ON t.id = m.track_id AND t.provider = m.provider
            WHERE t.provider = ?
              AND t.artist IS NOT NULL
            GROUP BY t.artist
            ORDER BY playlist_count DESC, track_count DESC, t.artist
        """, (self._provider,)).fetchall()
        
        results = []
        for row in rows:
            track_count = row['track_count']
            matched_count = row['matched_count']
            percentage = int((matched_count / track_count * 100)) if track_count > 0 else 0
            coverage = f"{percentage}% ({matched_count}/{track_count})"
            
            # Relevance: high track count + low coverage = high relevance
            relevance = track_count * (100 - percentage) / 100
            
            results.append({
                'artist': row['artist'],
                'track_count': track_count,
                'album_count': row['album_count'],
                'playlist_count': row['playlist_count'],
                'coverage': coverage,
                'relevance': round(relevance, 1),
            })
        
        return results
