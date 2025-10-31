"""Integration tests for build command."""

import pytest
from click.testing import CliRunner
from psm.cli.core import cli
from psm.db import Database
from pathlib import Path
import tempfile


@pytest.fixture
def temp_config(tmp_path):
    """Create a minimal test config."""
    config_dir = tmp_path / ".psm"
    config_dir.mkdir()

    config_file = config_dir / "config.toml"
    config_file.write_text(
        """
[providers.spotify]
client_id = "test_client_id"
client_secret = "test_client_secret"

[library]
paths = []

[matching]
fuzzy_threshold = 0.78
"""
    )

    return tmp_path


def test_build_without_watch(temp_config, monkeypatch):
    """Test that 'psm build' works without --watch flag.

    Regression test for: AttributeError: 'Sentinel' object has no attribute 'strip'

    This was caused by ctx.invoke(scan) not passing explicit parameter values,
    which made Click pass Sentinel objects for unset optional parameters.
    """
    monkeypatch.chdir(temp_config)
    monkeypatch.setenv("PSM_CONFIG_DIR", str(temp_config / ".psm"))

    runner = CliRunner()

    # This should NOT raise AttributeError about Sentinel
    # We expect it to fail for other reasons (no auth, no library), but not Sentinel errors
    result = runner.invoke(cli, ["build", "--no-export", "--no-report"], obj={"config_dir": temp_config / ".psm"})

    # The command will fail, but it should NOT fail with the Sentinel error
    assert "Sentinel" not in result.output
    if result.exception:
        assert "'Sentinel' object has no attribute" not in str(result.exception)
        assert "'Sentinel' object has no attribute 'strip'" not in str(result.exception)


def test_parse_time_string_with_none():
    """Test that parse_time_string handles None gracefully."""
    from psm.ingest.library import parse_time_string

    with pytest.raises(ValueError, match="cannot be empty or None"):
        parse_time_string(None)


def test_parse_time_string_with_empty_string():
    """Test that parse_time_string handles empty string gracefully."""
    from psm.ingest.library import parse_time_string

    with pytest.raises(ValueError, match="cannot be empty or None"):
        parse_time_string("")


def test_parse_time_string_valid_values():
    """Test that parse_time_string works with valid inputs."""
    from psm.ingest.library import parse_time_string
    import time

    # Unix timestamp
    ts = parse_time_string("1728123456.789")
    assert ts == 1728123456.789

    # Relative time (approximate check)
    now = time.time()
    two_hours_ago = parse_time_string("2 hours ago")
    assert now - two_hours_ago >= 7000  # ~2 hours in seconds
    assert now - two_hours_ago <= 7400  # with some tolerance
