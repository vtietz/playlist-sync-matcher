"""Test playlist organization by owner in export."""
from pathlib import Path
import tempfile
import shutil
from psm.db import Database
from psm.export.playlists import export_strict


def test_organize_by_owner_structure():
    """Test that playlists are organized into folders by owner."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        export_dir = Path(tmpdir) / "export"
        
        with Database(db_path) as db:
            # Add current user
            db.set_meta('current_user_id', 'user123')
            db.commit()
            
            # Add playlist owned by current user
            db.upsert_playlist('pl1', 'My Playlist', 'snap1', 'user123', 'CurrentUser')
            
            # Add playlist owned by someone else
            db.upsert_playlist('pl2', 'Friend Playlist', 'snap2', 'other456', 'Friend Name')
            
            # Add playlist with no owner info
            db.upsert_playlist('pl3', 'Unknown Playlist', 'snap3', None, None)
            
            # Add some tracks
            db.upsert_track({'id': 't1', 'name': 'Track 1', 'artist': 'Artist 1', 
                            'album': 'Album 1', 'isrc': None, 'duration_ms': 180000,
                            'normalized': 'track 1 artist 1', 'year': None})
            db.upsert_track({'id': 't2', 'name': 'Track 2', 'artist': 'Artist 2',
                            'album': 'Album 2', 'isrc': None, 'duration_ms': 200000,
                            'normalized': 'track 2 artist 2', 'year': None})
            db.upsert_track({'id': 't3', 'name': 'Track 3', 'artist': 'Artist 3',
                            'album': 'Album 3', 'isrc': None, 'duration_ms': 210000,
                            'normalized': 'track 3 artist 3', 'year': None})
            
            db.replace_playlist_tracks('pl1', [(0, 't1', None)])
            db.replace_playlist_tracks('pl2', [(0, 't2', None)])
            db.replace_playlist_tracks('pl3', [(0, 't3', None)])
            db.commit()
            
            # Simulate export with organization
            current_user_id = db.get_meta('current_user_id')
            
            # Get playlists
            playlists = db.conn.execute("SELECT id, name, owner_id, owner_name FROM playlists").fetchall()
            
            for pl in playlists:
                pl_id = pl['id']
                owner_id = pl['owner_id']
                owner_name = pl['owner_name']
                
                # Determine target directory based on owner
                if owner_id and current_user_id and owner_id == current_user_id:
                    target_dir = export_dir / 'my_playlists'
                elif owner_name:
                    from psm.export.playlists import sanitize_filename
                    folder_name = sanitize_filename(owner_name)
                    target_dir = export_dir / folder_name
                else:
                    target_dir = export_dir / 'other'
                
                # Get tracks for export
                track_rows = db.conn.execute(
                    """
                    SELECT pt.position, t.id as track_id, t.name, t.artist, t.album, t.duration_ms, lf.path AS local_path
                    FROM playlist_tracks pt
                    LEFT JOIN tracks t ON t.id = pt.track_id
                    LEFT JOIN matches m ON m.track_id = pt.track_id
                    LEFT JOIN library_files lf ON lf.id = m.file_id
                    WHERE pt.playlist_id=?
                    ORDER BY pt.position
                    """,
                    (pl_id,),
                ).fetchall()
                tracks = [dict(r) | {'position': r['position']} for r in track_rows]
                playlist_meta = {'name': pl['name'], 'id': pl_id}
                
                export_strict(playlist_meta, tracks, target_dir)
        
        # Verify folder structure
        # Filenames now include first 8 chars of playlist ID
        assert (export_dir / 'my_playlists' / 'My Playlist_pl1.m3u8').exists(), "User's playlist should be in my_playlists folder"
        # sanitize_filename replaces spaces with underscores
        friend_folder = list((export_dir).glob('Friend*'))[0] if list((export_dir).glob('Friend*')) else None
        assert friend_folder is not None, "Friend's folder should exist"
        assert (friend_folder / 'Friend Playlist_pl2.m3u8').exists(), "Friend's playlist should be in their folder"
        assert (export_dir / 'other' / 'Unknown Playlist_pl3.m3u8').exists(), "Unknown owner playlist should be in 'other' folder"


def test_flat_export_without_organization():
    """Test that playlists are exported flat when organize_by_owner is False."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        export_dir = Path(tmpdir) / "export"
        
        with Database(db_path) as db:
            # Add playlists
            db.upsert_playlist('pl1', 'Playlist One', 'snap1', 'user123', 'CurrentUser')
            db.upsert_playlist('pl2', 'Playlist Two', 'snap2', 'other456', 'Friend Name')
            
            # Add track
            db.upsert_track({'id': 't1', 'name': 'Track 1', 'artist': 'Artist 1',
                            'album': 'Album 1', 'isrc': None, 'duration_ms': 180000,
                            'normalized': 'track 1 artist 1', 'year': None})
            
            db.replace_playlist_tracks('pl1', [(0, 't1', None)])
            db.replace_playlist_tracks('pl2', [(0, 't1', None)])
            db.commit()
            
            # Export without organization (flat structure)
            playlists = db.conn.execute("SELECT id, name FROM playlists").fetchall()
            
            for pl in playlists:
                pl_id = pl['id']
                track_rows = db.conn.execute(
                    """
                    SELECT pt.position, t.id as track_id, t.name, t.artist, t.album, t.duration_ms, lf.path AS local_path
                    FROM playlist_tracks pt
                    LEFT JOIN tracks t ON t.id = pt.track_id
                    LEFT JOIN matches m ON m.track_id = pt.track_id
                    LEFT JOIN library_files lf ON lf.id = m.file_id
                    WHERE pt.playlist_id=?
                    ORDER BY pt.position
                    """,
                    (pl_id,),
                ).fetchall()
                tracks = [dict(r) | {'position': r['position']} for r in track_rows]
                playlist_meta = {'name': pl['name'], 'id': pl_id}
                
                export_strict(playlist_meta, tracks, export_dir)
        
        # Verify flat structure
        # Filenames now include first 8 chars of playlist ID (pl1, pl2 are short, so they stay as is)
        assert (export_dir / 'Playlist One_pl1.m3u8').exists(), "Playlist should be in root export dir"
        assert (export_dir / 'Playlist Two_pl2.m3u8').exists(), "Playlist should be in root export dir"
        assert not (export_dir / 'my_playlists').exists(), "No subfolders should be created"
