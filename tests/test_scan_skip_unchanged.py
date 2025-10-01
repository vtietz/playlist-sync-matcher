from pathlib import Path
from click.testing import CliRunner
from spx.cli import cli
from spx.db import Database
import yaml


def test_scan_skip_unchanged(tmp_path: Path):
    """Test that skip_unchanged works correctly - fully isolated with explicit config."""
    # Set up test directory structure
    music_dir = tmp_path / 'music'
    music_dir.mkdir()
    f = music_dir / 'track1.mp3'
    f.write_bytes(b'ID3dummy')
    
    db_path = tmp_path / 'db.sqlite'
    reports_dir = tmp_path / 'reports'
    reports_dir.mkdir()
    
    # Create explicit config file for full isolation (no env var parsing issues)
    config_file = tmp_path / 'config.yaml'
    config = {
        'database': {'path': str(db_path)},
        'library': {
            'paths': [str(music_dir)],
            'extensions': ['.mp3', '.flac', '.m4a', '.ogg'],
            'skip_unchanged': True,
            'commit_interval': 1,
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
    
    # First scan (should insert the file)
    r1 = runner.invoke(cli, ['--config-file', str(config_file), 'scan'])
    assert r1.exit_code == 0, f"First scan failed:\nExit code: {r1.exit_code}\nOutput:\n{r1.output}\nException: {r1.exception}"
    assert 'Scan complete' in r1.output
    
    # Second scan (should skip unchanged file)
    r2 = runner.invoke(cli, ['--config-file', str(config_file), 'scan'])
    assert r2.exit_code == 0, f"Second scan failed:\nExit code: {r2.exit_code}\nOutput:\n{r2.output}"
    assert 'Scan complete' in r2.output
    
    # Verify skip_unchanged worked - should still have exactly one row
    with Database(db_path) as db:
        count = db.conn.execute('SELECT count(*) FROM library_files').fetchone()[0]
    assert count == 1, f"Expected 1 library file, found {count}"