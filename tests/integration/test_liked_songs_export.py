"""Integration tests for Liked Songs virtual playlist export."""
from pathlib import Path
from psm.db import Database
from psm.services.export_service import export_playlists
from psm.reporting.reports.playlist_coverage import write_playlist_coverage_report


def test_liked_songs_exported_by_default(tmp_path):
    """Test that Liked Songs is exported as a virtual playlist by default."""
    db_path = tmp_path / "test.db"
    export_dir = tmp_path / "export"
    
    # Create database and add some liked tracks
    with Database(db_path) as db:
        # Add a track
        db.upsert_track({
            'id': 'track1',
            'name': 'Test Song',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'normalized': 'testsong testartist',
            'duration_ms': 180000,
        }, provider='spotify')
        
        # Add to liked tracks
        db.upsert_liked('track1', '2025-01-01T12:00:00Z', provider='spotify')
        
        # Add a library file and match
        db.add_library_file({
            'path': '/music/test.mp3',
            'title': 'Test Song',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'normalized': 'testsong testartist',
            'size': 1000,
            'mtime': 0.0,
        })
        # Get the file ID
        file_row = db.conn.execute("SELECT id FROM library_files WHERE path=?", ('/music/test.mp3',)).fetchone()
        file_id = file_row['id']
        db.add_match('track1', file_id, 0.95, 'test', provider='spotify')
        db.commit()
        
        # Export with default config (include_liked_songs=True)
        export_config = {
            'directory': str(export_dir),
            'mode': 'strict',
            'include_liked_songs': True
        }
        result = export_playlists(db, export_config)
        
        # Verify Liked Songs was counted
        assert result.playlist_count == 1, f"Expected 1 playlist (Liked Songs), got {result.playlist_count}"
    
    # Check that Liked Songs_*.m3u8 was created (with playlist ID prefix)
    m3u_files = list(export_dir.glob("Liked Songs_*.m3u8"))
    assert len(m3u_files) == 1, f"Expected 1 Liked Songs m3u8 file, found {len(m3u_files)}: {m3u_files}"
    liked_songs_m3u = m3u_files[0]
    
    # Verify content (strict mode should only include matched tracks)
    content = liked_songs_m3u.read_text(encoding='utf-8')
    assert '/music/test.mp3' in content, "Matched track not in Liked Songs playlist"


def test_liked_songs_can_be_disabled(tmp_path):
    """Test that Liked Songs export can be disabled via config."""
    db_path = tmp_path / "test.db"
    export_dir = tmp_path / "export"
    
    # Create database and add liked tracks
    with Database(db_path) as db:
        db.upsert_track({
            'id': 'track1',
            'name': 'Test Song',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'normalized': 'testsong testartist',
        }, provider='spotify')
        db.upsert_liked('track1', '2025-01-01T12:00:00Z', provider='spotify')
        db.commit()
        
        # Export with include_liked_songs=False
        export_config = {
            'directory': str(export_dir),
            'mode': 'strict',
            'include_liked_songs': False
        }
        result = export_playlists(db, export_config)
        
        # Verify no playlists exported
        assert result.playlist_count == 0, "Should not export any playlists when liked songs disabled"
    
    # Check that Liked Songs.m3u was NOT created
    m3u_files = list(export_dir.glob("Liked Songs_*.m3u8"))
    assert len(m3u_files) == 0, f"Liked Songs.m3u8 should not be created when disabled, found: {m3u_files}"


def test_liked_songs_in_playlist_coverage_report(tmp_path):
    """Test that Liked Songs appears in playlist coverage report."""
    db_path = tmp_path / "test.db"
    
    # Create database with liked tracks
    with Database(db_path) as db:
        # Add tracks
        for i in range(3):
            db.upsert_track({
                'id': f'track{i}',
                'name': f'Song {i}',
                'artist': 'Artist',
                'album': 'Album',
                'normalized': f'song{i} artist',
            }, provider='spotify')
            db.upsert_liked(f'track{i}', f'2025-01-0{i+1}T12:00:00Z', provider='spotify')
        
        # Match 2 out of 3
        for i in range(2):
            db.add_library_file({
                'path': f'/music/song{i}.mp3',
                'title': f'Song {i}',
                'artist': 'Artist',
                'normalized': f'song{i} artist',
                'size': 1000,
                'mtime': 0.0,
            })
            # Get the file ID
            file_row = db.conn.execute("SELECT id FROM library_files WHERE path=?", (f'/music/song{i}.mp3',)).fetchone()
            file_id = file_row['id']
            db.add_match(f'track{i}', file_id, 0.95, 'test', provider='spotify')
        
        db.commit()
        
        # Generate report
        out_dir = tmp_path / "reports"
        csv_path, html_path = write_playlist_coverage_report(db, out_dir, provider='spotify')
        
        # Verify Liked Songs in CSV
        csv_content = csv_path.read_text(encoding='utf-8')
        assert 'Liked Songs' in csv_content, "Liked Songs not in coverage report"
        assert '_liked_songs_virtual' in csv_content, "Virtual playlist ID not in report"
        
        # Verify coverage calculation (2/3 = 66.67%)
        assert '66.67' in csv_content or '66.66' in csv_content, "Coverage percentage incorrect"


def test_liked_songs_with_organize_by_owner(tmp_path):
    """Test that Liked Songs respects organize_by_owner flag."""
    db_path = tmp_path / "test.db"
    export_dir = tmp_path / "export"
    
    # Create database and set current user name
    with Database(db_path) as db:
        db.set_meta('current_user_name', 'TestUser')
        
        db.upsert_track({
            'id': 'track1',
            'name': 'Test Song',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'normalized': 'testsong testartist',
        }, provider='spotify')
        db.upsert_liked('track1', '2025-01-01T12:00:00Z', provider='spotify')
        
        # Add match
        db.add_library_file({
            'path': '/music/test.mp3',
            'title': 'Test Song',
            'artist': 'Test Artist',
            'normalized': 'testsong testartist',
            'size': 1000,
            'mtime': 0.0,
        })
        # Get the file ID
        file_row = db.conn.execute("SELECT id FROM library_files WHERE path=?", ('/music/test.mp3',)).fetchone()
        file_id = file_row['id']
        db.add_match('track1', file_id, 0.95, 'test', provider='spotify')
        db.commit()
        
        # Export with organize_by_owner
        export_config = {
            'directory': str(export_dir),
            'mode': 'strict',
            'include_liked_songs': True,
            'organize_by_owner': False  # Controlled via parameter
        }
        result = export_playlists(db, export_config, organize_by_owner=True)
    
    # Check that Liked Songs_*.m3u8 is in the user's folder
    user_dir = export_dir / "TestUser"
    m3u_files = list(user_dir.glob("Liked Songs_*.m3u8"))
    assert len(m3u_files) == 1, f"Expected 1 Liked Songs m3u8 in user folder, found {len(m3u_files)}. Export dir: {list(export_dir.rglob('*'))}"
    liked_songs_m3u = m3u_files[0]
    
    # Verify content
    content = liked_songs_m3u.read_text(encoding='utf-8')
    assert '/music/test.mp3' in content, "Track not in playlist"


def test_liked_songs_preserves_newest_first_order(tmp_path):
    """Test that Liked Songs maintains reverse chronological order (newest first)."""
    db_path = tmp_path / "test.db"
    export_dir = tmp_path / "export"
    
    with Database(db_path) as db:
        # Add tracks in order (oldest to newest added_at)
        tracks_info = [
            ('track1', 'Old Song', '2025-01-01T12:00:00Z'),
            ('track2', 'Middle Song', '2025-01-02T12:00:00Z'),
            ('track3', 'New Song', '2025-01-03T12:00:00Z'),
        ]
        
        for track_id, name, added_at in tracks_info:
            db.upsert_track({
                'id': track_id,
                'name': name,
                'artist': 'Artist',
                'album': 'Album',
                'normalized': f'{name.lower()} artist',
            }, provider='spotify')
            db.upsert_liked(track_id, added_at, provider='spotify')
            
            # Add match
            db.add_library_file({
                'path': f'/music/{track_id}.mp3',
                'title': name,
                'artist': 'Artist',
                'normalized': f'{name.lower()} artist',
                'size': 1000,
                'mtime': 0.0,
            })
            # Get the file ID
            file_row = db.conn.execute("SELECT id FROM library_files WHERE path=?", (f'/music/{track_id}.mp3',)).fetchone()
            file_id = file_row['id']
            db.add_match(track_id, file_id, 0.95, 'test', provider='spotify')
        
        db.commit()
        
        # Export
        export_config = {
            'directory': str(export_dir),
            'mode': 'strict',
            'include_liked_songs': True
        }
        export_playlists(db, export_config)
    
    # Read playlist
    m3u_files = list(export_dir.glob("Liked Songs_*.m3u8"))
    assert len(m3u_files) == 1, f"Expected 1 Liked Songs m3u8 file"
    liked_songs_m3u = m3u_files[0]
    content = liked_songs_m3u.read_text(encoding='utf-8')
    
    # Verify order: newest (track3) should appear before oldest (track1)
    track3_pos = content.find('track3.mp3')
    track1_pos = content.find('track1.mp3')
    
    assert track3_pos < track1_pos, \
        f"Tracks not in newest-first order. track3 at {track3_pos}, track1 at {track1_pos}\nContent:\n{content}"

