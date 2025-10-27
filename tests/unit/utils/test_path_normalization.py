"""Unit tests for path normalization utilities."""

from __future__ import annotations
import pytest
import sys
from pathlib import Path
from psm.utils.fs import normalize_library_path


class TestNormalizeLibraryPath:
    """Test path normalization for database storage."""

    def test_normalize_absolute_path(self, tmp_path: Path):
        """Test normalization of absolute path."""
        test_file = tmp_path / "music" / "song.mp3"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("test")

        normalized = normalize_library_path(test_file)

        # Should be absolute
        assert Path(normalized).is_absolute()
        # Should exist
        assert Path(normalized).exists()
        # Should match resolved path
        assert normalized == str(test_file.resolve())

    def test_normalize_relative_path(self, tmp_path: Path):
        """Test normalization converts relative to absolute."""
        test_file = tmp_path / "song.mp3"
        test_file.write_text("test")

        # Create a relative path by using parent navigation
        import os

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            # Use relative path
            normalized = normalize_library_path("./song.mp3")

            # Should be absolute
            assert Path(normalized).is_absolute()
            # Should resolve to the actual file
            assert Path(normalized).exists()
        finally:
            os.chdir(old_cwd)

    def test_normalize_path_object(self, tmp_path: Path):
        """Test normalization accepts Path objects."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("test")

        normalized = normalize_library_path(test_file)

        assert isinstance(normalized, str)
        assert Path(normalized).exists()

    def test_normalize_string_path(self, tmp_path: Path):
        """Test normalization accepts string paths."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("test")

        normalized = normalize_library_path(str(test_file))

        assert isinstance(normalized, str)
        assert Path(normalized).exists()

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
    def test_normalize_windows_drive_letter_uppercase(self, tmp_path: Path):
        """Test Windows drive letters are normalized to uppercase."""
        test_file = tmp_path / "music.mp3"
        test_file.write_text("test")

        # Get normalized path
        normalized = normalize_library_path(test_file)

        # On Windows, drive letter should be uppercase
        if len(normalized) >= 2 and normalized[1] == ":":
            assert normalized[0].isupper(), f"Expected uppercase drive letter in {normalized}"

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
    def test_normalize_windows_backslashes(self, tmp_path: Path):
        """Test Windows paths use backslashes."""
        test_file = tmp_path / "sub" / "music.mp3"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("test")

        normalized = normalize_library_path(test_file)

        # Should contain backslashes, not forward slashes
        assert "\\" in normalized or "/" not in normalized
        # After normalization, forward slashes should be replaced
        assert "/" not in normalized, f"Found forward slash in Windows path: {normalized}"

    def test_normalize_idempotent(self, tmp_path: Path):
        """Test normalizing a normalized path returns the same result."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("test")

        normalized1 = normalize_library_path(test_file)
        normalized2 = normalize_library_path(normalized1)

        assert normalized1 == normalized2

    def test_normalize_trailing_separator(self, tmp_path: Path):
        """Test paths with trailing separators are handled correctly."""
        test_dir = tmp_path / "music"
        test_dir.mkdir()
        test_file = test_dir / "song.mp3"
        test_file.write_text("test")

        # Add trailing separator to directory
        path_with_separator = str(test_file) + "/"

        normalized = normalize_library_path(path_with_separator)

        # Should still resolve correctly
        assert Path(normalized).exists()
        # Should not have trailing separator
        assert not normalized.endswith(("/", "\\"))

    def test_normalize_handles_symlinks(self, tmp_path: Path):
        """Test symlinks are resolved to their target."""
        # Create a real file
        real_file = tmp_path / "real.mp3"
        real_file.write_text("test")

        # Create a symlink
        link_file = tmp_path / "link.mp3"
        try:
            link_file.symlink_to(real_file)
        except (OSError, NotImplementedError):
            # Skip if symlinks not supported (e.g., Windows without admin)
            pytest.skip("Symlinks not supported on this system")

        normalized = normalize_library_path(link_file)

        # Should resolve to the real file
        assert Path(normalized).resolve() == real_file.resolve()
        # Both should normalize to the same path
        assert normalized == normalize_library_path(real_file)

    def test_normalize_nonexistent_path(self):
        """Test normalization of non-existent paths still produces canonical form."""
        # Non-existent path should still be normalized
        fake_path = Path("/this/path/does/not/exist/song.mp3")

        # Should not raise an error
        normalized = normalize_library_path(fake_path)

        # Should be a string
        assert isinstance(normalized, str)
        # Should be absolute
        assert Path(normalized).is_absolute()
