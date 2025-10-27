"""Tests for centralized progress logging configuration and behavior."""

from psm.config_types import LoggingConfig


def test_logging_config_defaults():
    """Test LoggingConfig default values."""
    config = LoggingConfig()

    assert config.progress_enabled is True
    assert config.progress_interval == 100
    assert config.scan_progress_interval == 500
    assert config.item_name_overrides == {}


def test_logging_config_custom_values():
    """Test LoggingConfig with custom values."""
    config = LoggingConfig(
        progress_enabled=False,
        progress_interval=50,
        scan_progress_interval=250,
        item_name_overrides={"tracks": "songs"},
    )

    assert config.progress_enabled is False
    assert config.progress_interval == 50
    assert config.scan_progress_interval == 250
    assert config.item_name_overrides == {"tracks": "songs"}


def test_logging_config_to_dict():
    """Test LoggingConfig conversion to dictionary."""
    config = LoggingConfig(
        progress_enabled=False, progress_interval=75, scan_progress_interval=300, item_name_overrides={"files": "items"}
    )

    result = config.to_dict()

    assert result == {
        "progress_enabled": False,
        "progress_interval": 75,
        "scan_progress_interval": 300,
        "item_name_overrides": {"files": "items"},
    }
