from pathlib import Path
from click.testing import CliRunner
from spx.cli import cli
from spx.db import Database
import yaml


def test_scan_deleted_cleanup(tmp_path: Path):
    """Test that deleted files are removed from DB during scan."""
    # Set up test directory structure
    music_dir = tmp_path / 'music'
    music_dir.mkdir()
    
    # Create two test files
    f1 = music_dir / 'track1.mp3'
    f1.write_bytes(b'ID3dummy1')
    f2 = music_dir / 'track2.mp3'
    f2.write_bytes(b'ID3dummy2')
    
    db_path = tmp_path / 'db.sqlite'
    reports_dir = tmp_path / 'reports'
    reports_dir.mkdir()
    
    # Create explicit config file
    config_file = tmp_path / 'config.yaml'
    config = {
        'database': {'path': str(db_path)},
        'library': {
            'paths': [str(music_dir)],
            'extensions': ['.mp3', '.flac', '.m4a', '.ogg'],
            'skip_unchanged': True,
            'commit_interval': 10,
        },
        'reports': {'directory': str(reports_dir)},
        'spotify': {
            'client_id': '',
            'scope': 'user-library-read playlist-read-private',
            'cache_file': str(tmp_path / 'tokens.json'),
            'redirect_port': 8888,
        },
        'matching': {'fuzzy_threshold': 0.78},
        'export': {'mode': 'strict', 'directory': str(tmp_path / 'playlists')},
        'debug': True,
    }
    config_file.write_text(yaml.dump(config), encoding='utf-8')
    
    runner = CliRunner()
    
    # First scan (should insert both files)
    r1 = runner.invoke(cli, ['--config-file', str(config_file), 'scan'])
    assert r1.exit_code == 0, f"First scan failed: {r1.output}"
    assert '[new]' in r1.output or 'Scan complete' in r1.output
    
    # Verify both files are in DB
    with Database(db_path) as db:
        count = db.conn.execute('SELECT count(*) FROM library_files').fetchone()[0]
    assert count == 2, f"Expected 2 files after first scan, found {count}"
    
    # Delete one file from filesystem
    f2.unlink()
    
    # Second scan (should detect deletion and remove from DB)
    r2 = runner.invoke(cli, ['--config-file', str(config_file), 'scan'])
    assert r2.exit_code == 0, f"Second scan failed: {r2.output}"
    
    # Verify only one file remains in DB
    with Database(db_path) as db:
        count = db.conn.execute('SELECT count(*) FROM library_files').fetchone()[0]
        remaining_path = db.conn.execute('SELECT path FROM library_files').fetchone()[0]
    
    assert count == 1, f"Expected 1 file after deletion, found {count}"
    assert str(f1) in remaining_path, f"Expected {f1} to remain, but got {remaining_path}"
    
    # Check that deleted message appears in output (when debug is on)
    assert '[deleted]' in r2.output or 'deleted=1' in r2.output, f"Expected deletion log in output: {r2.output}"


def test_scan_action_labels(tmp_path: Path):
    """Test that scan logs show correct action labels: [new], [updated], [skip], and verify DB cardinality."""
    music_dir = tmp_path / 'music'
    music_dir.mkdir()
    f = music_dir / 'track.mp3'
    f.write_bytes(b'ID3dummy')
    
    db_path = tmp_path / 'db.sqlite'
    reports_dir = tmp_path / 'reports'
    reports_dir.mkdir()
    
    config_file = tmp_path / 'config.yaml'
    config = {
        'database': {'path': str(db_path)},
        'library': {
            'paths': [str(music_dir)],
            'extensions': ['.mp3'],
            'skip_unchanged': True,
        },
        'reports': {'directory': str(reports_dir)},
        'spotify': {'client_id': '', 'scope': '', 'cache_file': str(tmp_path / 'tokens.json')},
        'matching': {'fuzzy_threshold': 0.78},
        'export': {'mode': 'strict', 'directory': str(tmp_path / 'playlists')},
        'debug': True,
    }
    config_file.write_text(yaml.dump(config), encoding='utf-8')
    
    runner = CliRunner()
    
    # First scan - should see [new]
    r1 = runner.invoke(cli, ['--config-file', str(config_file), 'scan'])
    assert r1.exit_code == 0
    assert '[new]' in r1.output, f"Expected [new] label in first scan: {r1.output}"
    
    # Verify DB has exactly one file after first scan
    with Database(db_path) as db:
        count1 = db.conn.execute('SELECT count(*) FROM library_files').fetchone()[0]
    assert count1 == 1, f"Expected 1 file after first scan, found {count1}"
    
    # Second scan without changes - should see [skip] and verify skip_unchanged behavior
    r2 = runner.invoke(cli, ['--config-file', str(config_file), 'scan'])
    assert r2.exit_code == 0
    assert '[skip]' in r2.output, f"Expected [skip] label in second scan: {r2.output}"
    
    # Verify DB still has exactly one file (skip_unchanged didn't create duplicate)
    with Database(db_path) as db:
        count2 = db.conn.execute('SELECT count(*) FROM library_files').fetchone()[0]
    assert count2 == 1, f"Expected 1 file after skip scan, found {count2} (skip_unchanged failed)"
    
    # Modify file and scan again - should see [updated]
    import time
    time.sleep(1.1)  # Ensure mtime changes beyond epsilon
    f.write_bytes(b'ID3modified')
    r3 = runner.invoke(cli, ['--config-file', str(config_file), 'scan'])
    assert r3.exit_code == 0
    assert '[updated]' in r3.output, f"Expected [updated] label after modification: {r3.output}"
    
    # Verify DB still has exactly one file (updated, not inserted new)
    with Database(db_path) as db:
        count3 = db.conn.execute('SELECT count(*) FROM library_files').fetchone()[0]
    assert count3 == 1, f"Expected 1 file after update, found {count3}"
