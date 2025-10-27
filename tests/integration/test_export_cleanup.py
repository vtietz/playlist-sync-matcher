"""Integration tests for export cleanup functionality."""

import pytest
from pathlib import Path
from psm.services.export_service import (
    export_playlists,
    _find_existing_m3u_files,
    _detect_obsolete_files,
    _clean_export_directory,
)
from tests.mocks.mock_database import MockDatabase


@pytest.fixture
def sample_db():
    """Create a mock database with a sample playlist."""
    db = MockDatabase()
    # Add a playlist using the proper method
    db.upsert_playlist("playlist123", "Test Playlist", "snap1", owner_id="owner1", owner_name="TestOwner")
    # Add a track (no local file, so strict mode produces empty playlist)
    db.upsert_track({"id": "track1", "name": "Song", "artist": "Artist", "duration_ms": 180000})
    db.replace_playlist_tracks("playlist123", [(0, "track1", None)])
    return db


def test_clean_before_export(tmp_path, sample_db):
    """Test that clean_before_export removes all existing .m3u files."""
    export_dir = tmp_path / "export"
    export_dir.mkdir()

    # Create some pre-existing .m3u files
    (export_dir / "old_playlist_1.m3u").write_text("#EXTM3U\nold_track.mp3")
    (export_dir / "old_playlist_2.m3u").write_text("#EXTM3U\nold_track2.mp3")

    # Verify files exist
    assert len(list(export_dir.glob("*.m3u"))) == 2

    # Export with clean_before_export=True
    export_config = {
        "directory": str(export_dir),
        "mode": "strict",
        "clean_before_export": True,
        "detect_obsolete": False,
        "include_liked_songs": False,
    }

    result = export_playlists(sample_db, export_config)

    # Old files should be deleted
    assert len(result.cleaned_files) == 2
    # Files were cleaned
    assert "old_playlist_1.m3u" in str(result.cleaned_files)
    assert "old_playlist_2.m3u" in str(result.cleaned_files)


def test_detect_obsolete_files(tmp_path, sample_db):
    """Test that obsolete files are detected but not deleted automatically."""
    export_dir = tmp_path / "export"
    export_dir.mkdir()

    # Create an obsolete .m3u file (not in database)
    obsolete_file = export_dir / "deleted_playlist_12345678.m3u"
    obsolete_file.write_text("#EXTM3U\nold_track.mp3")

    # Export with detect_obsolete=True (default)
    export_config = {
        "directory": str(export_dir),
        "mode": "strict",
        "clean_before_export": False,
        "detect_obsolete": True,
        "include_liked_songs": False,
    }

    result = export_playlists(sample_db, export_config)

    # Obsolete file should be detected
    assert len(result.obsolete_files) == 1
    assert obsolete_file.name in result.obsolete_files[0]
    # But not deleted
    assert obsolete_file.exists()


def test_no_obsolete_detection_when_clean_enabled(tmp_path, sample_db):
    """Test that obsolete detection is skipped when clean_before_export=True."""
    export_dir = tmp_path / "export"
    export_dir.mkdir()

    # Create an obsolete file
    (export_dir / "old_playlist.m3u").write_text("#EXTM3U\nold.mp3")

    # Export with both clean and detect enabled
    export_config = {
        "directory": str(export_dir),
        "mode": "strict",
        "clean_before_export": True,
        "detect_obsolete": True,  # Should be ignored when clean=True
        "include_liked_songs": False,
    }

    result = export_playlists(sample_db, export_config)

    # Obsolete detection should not run (no point after cleaning)
    assert len(result.obsolete_files) == 0
    assert len(result.cleaned_files) == 1


def test_detect_obsolete_disabled(tmp_path, sample_db):
    """Test that obsolete detection can be disabled."""
    export_dir = tmp_path / "export"
    export_dir.mkdir()

    # Create an obsolete file
    (export_dir / "old_playlist.m3u").write_text("#EXTM3U\nold.mp3")

    # Export with detect_obsolete=False
    export_config = {
        "directory": str(export_dir),
        "mode": "strict",
        "clean_before_export": False,
        "detect_obsolete": False,
        "include_liked_songs": False,
    }

    result = export_playlists(sample_db, export_config)

    # No obsolete detection
    assert len(result.obsolete_files) == 0


def test_find_existing_m3u_files(tmp_path):
    """Test finding .m3u files recursively."""
    export_dir = tmp_path / "export"
    export_dir.mkdir()

    # Create files in root
    (export_dir / "playlist1.m3u").touch()
    (export_dir / "playlist2.m3u").touch()
    (export_dir / "not_m3u.txt").touch()

    # Create files in subdirectory
    subdir = export_dir / "owner"
    subdir.mkdir()
    (subdir / "playlist3.m3u").touch()

    files = _find_existing_m3u_files(export_dir)

    assert len(files) == 3
    assert all(f.suffix == ".m3u" for f in files)


def test_detect_obsolete_files_helper():
    """Test the _detect_obsolete_files helper function."""
    existing = [Path("/export/playlist1.m3u"), Path("/export/playlist2.m3u"), Path("/export/old.m3u")]
    exported = ["/export/playlist1.m3u", "/export/playlist2.m3u"]

    obsolete = _detect_obsolete_files(existing, exported)

    assert len(obsolete) == 1
    assert obsolete[0].name == "old.m3u"


def test_clean_export_directory(tmp_path):
    """Test the _clean_export_directory helper function."""
    export_dir = tmp_path / "export"
    export_dir.mkdir()

    # Create .m3u files and other files
    (export_dir / "playlist1.m3u").write_text("#EXTM3U")
    (export_dir / "playlist2.m3u").write_text("#EXTM3U")
    (export_dir / "keep_this.txt").write_text("important")

    # Create in subdirectory
    subdir = export_dir / "subdir"
    subdir.mkdir()
    (subdir / "playlist3.m3u").write_text("#EXTM3U")

    deleted = _clean_export_directory(export_dir)

    # Only .m3u files deleted
    assert len(deleted) == 3
    assert not (export_dir / "playlist1.m3u").exists()
    assert not (export_dir / "playlist2.m3u").exists()
    assert not (subdir / "playlist3.m3u").exists()
    # Other files preserved
    assert (export_dir / "keep_this.txt").exists()


def test_clean_export_directory_nonexistent(tmp_path):
    """Test cleaning a directory that doesn't exist."""
    export_dir = tmp_path / "nonexistent"

    deleted = _clean_export_directory(export_dir)

    assert len(deleted) == 0
