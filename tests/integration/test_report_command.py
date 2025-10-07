"""Test the standalone report command."""
from click.testing import CliRunner
from pathlib import Path
from psm.cli.core import cli
from psm.db import Database
import pytest


def test_report_command_generates_all_reports(tmp_path, test_config):
    """Verify 'report' command regenerates all reports from existing database."""
    # Setup test environment
    db_path = tmp_path / "test.db"
    reports_dir = tmp_path / "reports"
    
    # Create minimal database with data
    db = Database(db_path)
    db.conn.execute("INSERT INTO tracks (id, name, artist, album) VALUES ('t1', 'Song', 'Artist', 'Album')")
    db.conn.execute("INSERT INTO library_files (id, path, artist, title) VALUES (1, 'file.mp3', 'Artist', 'Song')")
    db.conn.execute("INSERT INTO matches (track_id, file_id, method, score) VALUES ('t1', 1, 'test', 1.0)")
    db.conn.execute("INSERT INTO playlists (id, name) VALUES ('p1', 'Playlist')")
    db.conn.execute("INSERT INTO playlist_tracks (playlist_id, position, track_id) VALUES ('p1', 0, 't1')")
    db.conn.commit()
    db.close()
    
    # Use test_config fixture and override paths
    test_config['database']['path'] = str(db_path)
    test_config['reports']['directory'] = str(reports_dir)
    
    # Run report command with test config passed via obj
    runner = CliRunner()
    result = runner.invoke(cli, ['report'], obj=test_config)
    
    # Verify success
    assert result.exit_code == 0
    assert "✓ Match reports generated" in result.output
    assert "✓ Navigation dashboard generated" in result.output
    
    # Verify files were created
    assert (reports_dir / "matched_tracks.csv").exists()
    assert (reports_dir / "matched_tracks.html").exists()
    assert (reports_dir / "unmatched_tracks.csv").exists()
    assert (reports_dir / "unmatched_albums.csv").exists()
    assert (reports_dir / "playlist_coverage.csv").exists()
    assert (reports_dir / "index.html").exists()
    
    print("✓ Report command generates all reports")


def test_report_command_selective_generation(tmp_path, test_config):
    """Verify report command can selectively generate only match or analysis reports."""
    db_path = tmp_path / "test.db"
    reports_dir = tmp_path / "reports"
    
    # Create database with data
    db = Database(db_path)
    db.conn.execute("INSERT INTO tracks (id, name) VALUES ('t1', 'Song')")
    db.conn.execute("INSERT INTO library_files (id, path) VALUES (1, 'file.mp3')")
    db.conn.commit()
    db.close()
    
    # Use test_config fixture and override paths
    test_config['database']['path'] = str(db_path)
    test_config['reports']['directory'] = str(reports_dir)
    
    # Run with only match reports, passing test config via obj
    runner = CliRunner()
    result = runner.invoke(cli, ['report', '--no-analysis-reports'], obj=test_config)
    
    assert result.exit_code == 0
    assert "✓ Match reports generated" in result.output
    assert "Analysis reports" not in result.output or "⚠ No library files" in result.output
    
    # Verify match reports exist
    assert (reports_dir / "matched_tracks.csv").exists()
    assert (reports_dir / "playlist_coverage.csv").exists()
    
    print("✓ Report command supports selective generation")
