"""Test playlist coverage report and index page generation."""
from pathlib import Path
import csv
from psm.db import Database
from psm.reporting.generator import write_match_reports, write_index_page


def test_playlist_coverage_report(tmp_path):
    """Verify playlist coverage report shows match percentage for each playlist."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    
    # Insert test tracks
    db.conn.execute("""
        INSERT INTO tracks (id, name, artist, album)
        VALUES 
            ('track1', 'Matched Song 1', 'Artist A', 'Album A'),
            ('track2', 'Matched Song 2', 'Artist A', 'Album A'),
            ('track3', 'Unmatched Song', 'Artist B', 'Album B')
    """)
    
    # Insert library files
    db.conn.execute("""
        INSERT INTO library_files (id, path, artist, title, album)
        VALUES 
            (1, 'file1.mp3', 'Artist A', 'Matched Song 1', 'Album A'),
            (2, 'file2.mp3', 'Artist A', 'Matched Song 2', 'Album A')
    """)
    
    # Match only track1 and track2
    db.conn.execute("""
        INSERT INTO matches (track_id, file_id, method, score)
        VALUES 
            ('track1', 1, 'MatchConfidence.CERTAIN', 1.0),
            ('track2', 2, 'MatchConfidence.CERTAIN', 1.0)
    """)
    
    # Create playlists
    db.conn.execute("""
        INSERT INTO playlists (id, name, owner_id, owner_name)
        VALUES 
            ('playlist1', 'Good Coverage Playlist', 'user1', 'User One'),
            ('playlist2', 'Poor Coverage Playlist', 'user1', 'User One')
    """)
    
    # playlist1: 2/2 tracks matched (100%)
    # playlist2: 1/2 tracks matched (50%)
    db.conn.execute("""
        INSERT INTO playlist_tracks (playlist_id, position, track_id)
        VALUES 
            ('playlist1', 0, 'track1'),
            ('playlist1', 1, 'track2'),
            ('playlist2', 0, 'track1'),
            ('playlist2', 1, 'track3')
    """)
    
    db.conn.commit()
    
    # Generate reports
    out_dir = tmp_path / "reports"
    reports = write_match_reports(db, out_dir)
    
    # Verify playlist coverage report exists
    assert 'playlist_coverage' in reports
    csv_path, html_path = reports['playlist_coverage']
    
    # Verify CSV content
    with csv_path.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        
        # Should be sorted by coverage ASC (worst first)
        assert len(rows) == 2
        
        # Poor coverage playlist first
        assert rows[0]['playlist_name'] == 'Poor Coverage Playlist'
        assert rows[0]['total_tracks'] == '2'
        assert rows[0]['matched_tracks'] == '1'
        assert rows[0]['missing_tracks'] == '1'
        assert rows[0]['coverage_percent'] == '50.0'
        
        # Good coverage playlist second
        assert rows[1]['playlist_name'] == 'Good Coverage Playlist'
        assert rows[1]['total_tracks'] == '2'
        assert rows[1]['matched_tracks'] == '2'
        assert rows[1]['missing_tracks'] == '0'
        assert rows[1]['coverage_percent'] == '100.0'
    
    # Verify HTML exists and contains coverage badges
    assert html_path.exists()
    html_content = html_path.read_text(encoding='utf-8')
    assert 'Good Coverage Playlist' in html_content
    assert 'Poor Coverage Playlist' in html_content
    assert 'badge' in html_content  # Coverage badges should be present
    
    print("✓ Playlist coverage report generated correctly")
    print("✓ Sorted by coverage ASC (worst first)")


def test_index_page_generation(tmp_path):
    """Verify index.html is generated with links to all reports."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    
    # Insert minimal data
    db.conn.execute("INSERT INTO tracks (id, name) VALUES ('t1', 'Track 1')")
    db.conn.execute("INSERT INTO library_files (id, path) VALUES (1, 'file.mp3')")
    db.conn.execute("INSERT INTO matches (track_id, file_id, method, score) VALUES ('t1', 1, 'test', 1.0)")
    db.conn.execute("INSERT INTO playlists (id, name) VALUES ('p1', 'Test Playlist')")
    db.conn.commit()
    
    # Generate reports first
    out_dir = tmp_path / "reports"
    write_match_reports(db, out_dir)
    
    # Generate index page
    index_path = write_index_page(out_dir, db)
    
    # Verify index.html exists
    assert index_path.exists()
    assert index_path.name == "index.html"
    
    # Verify content
    html_content = index_path.read_text(encoding='utf-8')
    
    # Should have title
    assert "Playlist Sync Matcher" in html_content
    
    # Should link to all report types
    assert "matched_tracks.html" in html_content
    assert "unmatched_tracks.html" in html_content
    assert "unmatched_albums.html" in html_content
    assert "playlist_coverage.html" in html_content
    
    # Should have section headers
    assert "Match Reports" in html_content
    
    print("✓ Index page generated with all report links")
    print("✓ Contains proper navigation structure")
