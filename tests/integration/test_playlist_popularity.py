"""Test unmatched tracks/albums reports include playlist popularity."""
from pathlib import Path
import csv
from psm.db import Database
from psm.reporting.generator import write_match_reports


def test_unmatched_tracks_has_playlist_count(tmp_path):
    """Verify unmatched tracks report includes playlist popularity column."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    
    # Insert test tracks
    db.conn.execute("""
        INSERT INTO tracks (id, name, artist, album, year)
        VALUES 
            ('track1', 'Popular Song', 'Artist A', 'Album A', 2024),
            ('track2', 'Less Popular Song', 'Artist B', 'Album B', 2024),
            ('track3', 'Not in Playlist', 'Artist C', 'Album C', 2024)
    """)
    
    # Insert playlists
    db.conn.execute("""
        INSERT INTO playlists (id, name, owner_id)
        VALUES 
            ('playlist1', 'Test Playlist 1', 'user1'),
            ('playlist2', 'Test Playlist 2', 'user1'),
            ('playlist3', 'Test Playlist 3', 'user1')
    """)
    
    # track1 appears in 3 playlists, track2 in 1 playlist, track3 in 0 playlists
    db.conn.execute("""
        INSERT INTO playlist_tracks (playlist_id, position, track_id)
        VALUES 
            ('playlist1', 0, 'track1'),
            ('playlist2', 0, 'track1'),
            ('playlist3', 0, 'track1'),
            ('playlist1', 1, 'track2')
    """)
    
    db.conn.commit()
    
    # Generate reports
    out_dir = tmp_path / "reports"
    reports = write_match_reports(db, out_dir)
    
    # Verify unmatched tracks CSV - Simple playlist count column
    csv_path = reports['unmatched_tracks'][0]
    with csv_path.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        
        # Should be sorted by playlist count DESC
        assert rows[0]['track_name'] == 'Popular Song'
        assert rows[0]['playlists'] == '3'
        
        assert rows[1]['track_name'] == 'Less Popular Song'
        assert rows[1]['playlists'] == '1'
        
        assert rows[2]['track_name'] == 'Not in Playlist'
        assert rows[2]['playlists'] == '0'
    
    print("✓ Unmatched tracks report includes playlist count")
    print("✓ Sorted by playlist count DESC")


def test_unmatched_albums_has_playlist_count(tmp_path):
    """Verify unmatched albums report includes playlist popularity column."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    
    # Insert test tracks for two albums
    db.conn.execute("""
        INSERT INTO tracks (id, name, artist, album, year)
        VALUES 
            ('track1', 'Song 1', 'Artist A', 'Popular Album', 2024),
            ('track2', 'Song 2', 'Artist A', 'Popular Album', 2024),
            ('track3', 'Song 3', 'Artist B', 'Less Popular Album', 2024)
    """)
    
    # Insert playlists
    db.conn.execute("""
        INSERT INTO playlists (id, name, owner_id)
        VALUES 
            ('playlist1', 'Test Playlist 1', 'user1'),
            ('playlist2', 'Test Playlist 2', 'user1')
    """)
    
    # Popular Album tracks appear in 2 playlists, Less Popular Album in 0
    db.conn.execute("""
        INSERT INTO playlist_tracks (playlist_id, position, track_id)
        VALUES 
            ('playlist1', 0, 'track1'),
            ('playlist2', 0, 'track1'),
            ('playlist1', 1, 'track2')
    """)
    
    db.conn.commit()
    
    # Generate reports
    out_dir = tmp_path / "reports"
    reports = write_match_reports(db, out_dir)
    
    # Verify unmatched albums CSV
    csv_path = reports['unmatched_albums'][0]
    with csv_path.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        
        # Should be sorted by playlist_count DESC
        assert rows[0]['album'] == 'Popular Album'
        assert rows[0]['track_count'] == '2'
        assert rows[0]['playlist_count'] == '2'  # 2 distinct playlists
        
        assert rows[1]['album'] == 'Less Popular Album'
        assert rows[1]['track_count'] == '1'
        assert rows[1]['playlist_count'] == '0'
    
    print("✓ Unmatched albums report includes playlist popularity")
    print("✓ Sorted by playlist count DESC, then track count DESC")
