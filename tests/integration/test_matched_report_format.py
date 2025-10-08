"""Test matched tracks report format with file path column."""
from pathlib import Path
import csv
from psm.db import Database
from psm.reporting.generator import write_match_reports


def test_matched_tracks_report_has_file_path(tmp_path):
    """Verify matched tracks report includes file path column in correct position."""
    # Setup test database
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    
    # Insert test data
    db.conn.execute("""
        INSERT INTO tracks (id, name, artist, album, year)
        VALUES ('track1', 'Test Song', 'Test Artist', 'Test Album', 2024)
    """)
    
    db.conn.execute("""
        INSERT INTO library_files (id, path, artist, title, album, bitrate_kbps)
        VALUES (1, 'Z:\\Music\\test.mp3', 'Test Artist', 'Test Song', 'Test Album', 320)
    """)
    
    db.conn.execute("""
        INSERT INTO matches (track_id, file_id, method, score)
        VALUES ('track1', 1, 'MatchConfidence.CERTAIN', 1.0)
    """)
    
    db.conn.commit()
    
    # Generate reports
    out_dir = tmp_path / "reports"
    reports = write_match_reports(db, out_dir)
    
    # Verify CSV structure - New standardized format
    csv_path = reports['matched'][0]
    with csv_path.open('r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)
        
        # Check standardized header order: track_id, track_name, track_artist, track_album, track_duration, track_year, file_path, file_title, file_artist, file_album, file_duration, score, confidence
        assert headers[0] == "track_id"
        assert headers[1] == "track_name"
        assert headers[2] == "track_artist"
        assert headers[3] == "track_album"
        assert headers[4] == "track_duration"
        assert headers[5] == "track_year"
        assert headers[6] == "file_path"  # File path is in standardized position
        assert headers[7] == "file_title"
        assert headers[8] == "file_artist"
        assert headers[9] == "file_album"
        assert headers[10] == "file_duration"
        assert headers[11] == "score"
        assert headers[12] == "confidence"
        
        # Check data row - standardized format
        row = next(reader)
        assert row[0] == "track1"  # track_id (now first column)
        assert row[1] == "Test Song"  # track_name (now second column)
        assert row[2] == "Test Artist"  # track_artist
        assert row[6] == "Z:\\Music\\test.mp3"  # file_path (column 6)
        assert row[12] == "CERTAIN"  # confidence (last column)
    
    # Verify HTML was generated
    html_path = reports['matched'][1]
    assert html_path.exists()
    html_content = html_path.read_text(encoding='utf-8')
    
    # Check for file path in HTML
    assert "Z:\\Music\\test.mp3" in html_content
    
    # Check that background styling is removed (no gray background)
    assert "background: white;" in html_content
    assert "background: #f5f5f5;" not in html_content
    
    print("✓ Matched tracks report format verified")
    print("✓ File path column in correct position")
    print("✓ Background styling cleaned up")
