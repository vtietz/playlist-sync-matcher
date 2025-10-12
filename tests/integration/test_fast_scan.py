"""Test fast_scan mode - skips audio parsing for unchanged files."""
from psm.db import Database
from psm.ingest.library import scan_library
import time


def test_fast_scan_mode_skips_parsing(tmp_path, test_config):
    """Test that fast_scan=True reuses existing tags without parsing audio files."""

    music_dir = tmp_path / "music"
    music_dir.mkdir()

    # Update test config for this test
    test_config['library']['paths'] = [str(music_dir)]
    test_config['library']['extensions'] = ['.mp3', '.flac']
    test_config['library']['skip_unchanged'] = True
    test_config['library']['fast_scan'] = True
    test_config['database']['path'] = str(tmp_path / 'test.db')

    # Create a test file (doesn't need valid audio - we're testing skip logic)
    test_file = music_dir / "test.mp3"
    test_file.write_text("fake mp3 content")

    db_path = tmp_path / "test.db"

    # First scan: will parse the file (or fail gracefully on invalid audio)
    with Database(db_path) as db:
        scan_library(db, test_config)

        # Manually insert known metadata since our fake file won't parse
        db.conn.execute("""
            UPDATE library_files
            SET title='Test Song', artist='Test Artist', album='Test Album',
                normalized='test song test artist', year=2024, duration=180.0
            WHERE path=?
        """, (str(test_file),))
        db.commit()

    # Verify metadata exists
    with Database(db_path) as db:
        row = db.conn.execute(
            "SELECT title, artist, album, year, duration, normalized FROM library_files WHERE path=?",
            (str(test_file),)
        ).fetchone()
        assert row is not None
        assert row['title'] == 'Test Song'
        assert row['artist'] == 'Test Artist'
        assert row['normalized'] == 'test song test artist'

    # Second scan: Should skip parsing and reuse existing tags
    # Wait a tiny bit to ensure mtime comparison works
    time.sleep(0.01)

    with Database(db_path) as db:
        scan_library(db, test_config)

        # Metadata should remain unchanged (not overwritten by filename fallback)
        row = db.conn.execute(
            "SELECT title, artist, album, year, duration, normalized FROM library_files WHERE path=?",
            (str(test_file),)
        ).fetchone()
        assert row is not None
        assert row['title'] == 'Test Song', "Fast scan should preserve existing title"
        assert row['artist'] == 'Test Artist', "Fast scan should preserve existing artist"
        assert row['normalized'] == 'test song test artist', "Fast scan should preserve normalization"


def test_fast_scan_disabled_still_works(tmp_path, test_config):
    """Test that fast_scan=False continues to work (parses every time)."""

    music_dir = tmp_path / "music"
    music_dir.mkdir()

    # Update test config
    test_config['library']['paths'] = [str(music_dir)]
    test_config['library']['extensions'] = ['.mp3']
    test_config['library']['skip_unchanged'] = True
    test_config['library']['fast_scan'] = False
    test_config['database']['path'] = str(tmp_path / 'test.db')

    test_file = music_dir / "test.mp3"
    test_file.write_text("fake content")

    db_path = tmp_path / "test.db"

    # Scan with fast_scan disabled
    with Database(db_path) as db:
        scan_library(db, test_config)

        # Should have entry (with filename fallback for title)
        row = db.conn.execute("SELECT title FROM library_files WHERE path=?", (str(test_file),)).fetchone()
        assert row is not None
        assert row['title'] == 'test'  # Filename fallback

