"""Test the standalone report command."""
from click.testing import CliRunner
from pathlib import Path
from psm.cli.core import cli
from psm.db import Database
import pytest


def test_report_command_generates_all_reports(tmp_path, monkeypatch):
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
    
    # Mock config
    monkeypatch.setenv('PSM__DATABASE__PATH', str(db_path))
    monkeypatch.setenv('PSM__REPORTS__DIRECTORY', str(reports_dir))
    
    # Run report command
    runner = CliRunner()
    result = runner.invoke(cli, ['report'])
    
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


def test_report_command_selective_generation(tmp_path, monkeypatch):
    """Verify report command can selectively generate only match or analysis reports."""
    db_path = tmp_path / "test.db"
    reports_dir = tmp_path / "reports"
    
    # Create database with data
    db = Database(db_path)
    db.conn.execute("INSERT INTO tracks (id, name) VALUES ('t1', 'Song')")
    db.conn.execute("INSERT INTO library_files (id, path) VALUES (1, 'file.mp3')")
    db.conn.commit()
    db.close()
    
    monkeypatch.setenv('PSM__DATABASE__PATH', str(db_path))
    monkeypatch.setenv('PSM__REPORTS__DIRECTORY', str(reports_dir))
    
    # Run with only match reports
    runner = CliRunner()
    result = runner.invoke(cli, ['report', '--no-analysis-reports'])
    
    assert result.exit_code == 0
    assert "✓ Match reports generated" in result.output
    assert "Analysis reports" not in result.output or "⚠ No library files" in result.output
    
    # Verify match reports exist
    assert (reports_dir / "matched_tracks.csv").exists()
    assert (reports_dir / "playlist_coverage.csv").exists()
    
    print("✓ Report command supports selective generation")
