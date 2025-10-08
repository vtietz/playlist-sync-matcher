"""Integration tests for incremental scan CLI commands."""
import pytest
from pathlib import Path
from click.testing import CliRunner
import time
from psm.cli import cli
from psm.db import Database


def test_scan_since_flag(tmp_path, test_config):
    """Test scan --since flag filters files by modification time."""
    music_dir = tmp_path / 'music'
    music_dir.mkdir()
    
    # Create first file
    f1 = music_dir / 'old_track.mp3'
    f1.write_bytes(b'ID3old')
    time.sleep(0.1)
    
    # Record time between files
    cutoff = time.time()
    time.sleep(0.1)
    
    # Create second file (newer)
    f2 = music_dir / 'new_track.mp3'
    f2.write_bytes(b'ID3new')
    
    db_path = tmp_path / 'db.sqlite'
    test_config['database']['path'] = str(db_path)
    test_config['library']['paths'] = [str(music_dir)]
    test_config['library']['skip_unchanged'] = False  # Ensure all files are processed
    test_config['reports']['directory'] = str(tmp_path / 'reports')
    test_config['spotify']['client_id'] = ''
    test_config['spotify']['cache_file'] = str(tmp_path / 'tokens.json')
    test_config['export']['directory'] = str(tmp_path / 'playlists')
    
    runner = CliRunner()
    
    # First: scan with --since cutoff (should only get new_track.mp3)
    cutoff_str = str(cutoff)
    result = runner.invoke(cli, ['scan', '--since', cutoff_str], obj=test_config)
    assert result.exit_code == 0, f"Scan failed: {result.output}"
    
    # Verify only the new file was added
    with Database(db_path) as db:
        count = db.conn.execute('SELECT count(*) FROM library_files').fetchone()[0]
        paths = [row['path'] for row in db.conn.execute('SELECT path FROM library_files')]
    
    # Should only have new_track.mp3
    assert count == 1, f"Expected 1 file, got {count}"
    assert any('new_track.mp3' in p for p in paths), f"new_track.mp3 not found in {paths}"


def test_scan_quick_mode(tmp_path, test_config):
    """Test scan --quick uses last scan time."""
    music_dir = tmp_path / 'music'
    music_dir.mkdir()
    
    f1 = music_dir / 'track.mp3'
    f1.write_bytes(b'ID3dummy')
    
    db_path = tmp_path / 'db.sqlite'
    test_config['database']['path'] = str(db_path)
    test_config['library']['paths'] = [str(music_dir)]
    test_config['reports']['directory'] = str(tmp_path / 'reports')
    test_config['spotify']['client_id'] = ''
    test_config['spotify']['cache_file'] = str(tmp_path / 'tokens.json')
    test_config['export']['directory'] = str(tmp_path / 'playlists')
    
    runner = CliRunner()
    
    # First full scan
    r1 = runner.invoke(cli, ['scan'], obj=test_config)
    assert r1.exit_code == 0
    
    # Verify last_scan_time was set
    with Database(db_path) as db:
        last_scan = db.get_meta('last_scan_time')
    assert last_scan is not None, "last_scan_time should be set after scan"
    
    # Add new file
    time.sleep(0.2)
    f2 = music_dir / 'new.mp3'
    f2.write_bytes(b'ID3new')
    
    # Quick scan should only pick up the new file
    r2 = runner.invoke(cli, ['scan', '--quick'], obj=test_config)
    assert r2.exit_code == 0
    assert 'Quick mode' in r2.output or 'Scan complete' in r2.output
    
    # Verify both files are in DB
    with Database(db_path) as db:
        count = db.conn.execute('SELECT count(*) FROM library_files').fetchone()[0]
    assert count == 2, f"Expected 2 files after quick scan, got {count}"


def test_scan_specific_paths(tmp_path, test_config):
    """Test scan --paths for scanning specific directories."""
    music_dir = tmp_path / 'music'
    music_dir.mkdir()
    
    # Create subdirectories
    dir1 = music_dir / 'album1'
    dir1.mkdir()
    dir2 = music_dir / 'album2'
    dir2.mkdir()
    
    f1 = dir1 / 'track1.mp3'
    f1.write_bytes(b'ID31')
    f2 = dir2 / 'track2.mp3'
    f2.write_bytes(b'ID32')
    
    db_path = tmp_path / 'db.sqlite'
    test_config['database']['path'] = str(db_path)
    test_config['library']['paths'] = [str(music_dir)]
    test_config['reports']['directory'] = str(tmp_path / 'reports')
    test_config['spotify']['client_id'] = ''
    test_config['spotify']['cache_file'] = str(tmp_path / 'tokens.json')
    test_config['export']['directory'] = str(tmp_path / 'playlists')
    
    runner = CliRunner()
    
    # Scan only album1
    result = runner.invoke(cli, ['scan', '--paths', str(dir1)], obj=test_config)
    assert result.exit_code == 0
    
    # Verify only album1 track was added
    with Database(db_path) as db:
        count = db.conn.execute('SELECT count(*) FROM library_files').fetchone()[0]
        paths = [row['path'] for row in db.conn.execute('SELECT path FROM library_files')]
    
    assert count == 1, f"Expected 1 file, got {count}"
    assert any('album1' in p for p in paths), f"album1 not found in {paths}"
    assert not any('album2' in p for p in paths), f"album2 should not be in {paths}"


def test_scan_since_and_quick_conflict(tmp_path, test_config):
    """Test that --since and --quick cannot be used together."""
    db_path = tmp_path / 'db.sqlite'
    test_config['database']['path'] = str(db_path)
    test_config['library']['paths'] = [str(tmp_path / 'music')]
    test_config['reports']['directory'] = str(tmp_path / 'reports')
    test_config['spotify']['client_id'] = ''
    test_config['spotify']['cache_file'] = str(tmp_path / 'tokens.json')
    test_config['export']['directory'] = str(tmp_path / 'playlists')
    
    runner = CliRunner()
    
    result = runner.invoke(cli, ['scan', '--since', '1 hour ago', '--quick'], obj=test_config)
    assert result.exit_code != 0
    assert 'Cannot use both --since and --quick' in result.output


def test_scan_invalid_time_format(tmp_path, test_config):
    """Test that invalid --since format shows helpful error."""
    db_path = tmp_path / 'db.sqlite'
    test_config['database']['path'] = str(db_path)
    test_config['library']['paths'] = [str(tmp_path / 'music')]
    test_config['reports']['directory'] = str(tmp_path / 'reports')
    test_config['spotify']['client_id'] = ''
    test_config['spotify']['cache_file'] = str(tmp_path / 'tokens.json')
    test_config['export']['directory'] = str(tmp_path / 'playlists')
    
    runner = CliRunner()
    
    result = runner.invoke(cli, ['scan', '--since', 'invalid'], obj=test_config)
    assert result.exit_code != 0
    assert 'Unable to parse time string' in result.output
