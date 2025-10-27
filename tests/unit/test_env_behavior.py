"""Consolidated environment configuration tests with parametrization."""

import pytest
from psm.config import load_config


class TestEnvironmentOverrides:
    """Test environment variable precedence and parsing."""

    def test_env_file_loading(self, tmp_path, monkeypatch):
        """Test .env file loading with PSM_ENABLE_DOTENV enabled."""
        # Create temporary .env
        env_file = tmp_path / ".env"
        env_file.write_text("PSM__EXPORT__MODE=placeholders\n", encoding="utf-8")
        # chdir into tmp_path to simulate project root where .env resides
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PSM_ENABLE_DOTENV", "1")
        cfg = load_config()
        assert cfg["export"]["mode"] == "placeholders"
        # explicit OS environment should override .env
        monkeypatch.setenv("PSM__EXPORT__MODE", "mirrored")
        cfg2 = load_config()
        assert cfg2["export"]["mode"] == "mirrored"

    def test_pure_env_override(self, monkeypatch):
        """Test environment variable overrides without .env file."""
        # Ensure no dotenv auto-loading or prior env variable contamination
        monkeypatch.delenv("PSM_ENABLE_DOTENV", raising=False)
        monkeypatch.delenv("PSM__EXPORT__MODE", raising=False)
        cfg_default = load_config()
        assert cfg_default["export"]["mode"] == "strict"
        # Override via environment
        monkeypatch.setenv("PSM__EXPORT__MODE", "mirrored")
        cfg = load_config()
        assert cfg["export"]["mode"] == "mirrored"

    def test_json_array_parsing(self, monkeypatch):
        """Test JSON array parsing for list-valued config."""
        # default single path
        cfg_default = load_config()
        assert isinstance(cfg_default["library"]["paths"], list)
        assert cfg_default["library"]["paths"][0] == "music"
        # override with JSON array
        monkeypatch.setenv("PSM__LIBRARY__PATHS", '["X:/Music","Y:/Other","Z:/More"]')
        cfg = load_config()
        assert cfg["library"]["paths"] == ["X:/Music", "Y:/Other", "Z:/More"]

    @pytest.mark.parametrize(
        "env_value,expected",
        [
            ("true", True),
            ("True", True),
            ("1", True),
            ("yes", True),
            ("false", False),
            ("False", False),
            ("0", False),
            ("no", False),
        ],
    )
    def test_boolean_coercion(self, monkeypatch, env_value, expected):
        """Test various boolean string representations are coerced correctly."""
        monkeypatch.setenv("PSM__LIBRARY__SKIP_UNCHANGED", env_value)
        cfg = load_config()
        assert cfg["library"]["skip_unchanged"] is expected

    @pytest.mark.parametrize(
        "env_value,expected",
        [
            ("42", 42),
            ("100", 100),
            ("0", 0),
            ("-5", -5),
        ],
    )
    def test_integer_coercion(self, monkeypatch, env_value, expected):
        """Test integer string representations are coerced correctly."""
        monkeypatch.setenv("PSM__LIBRARY__COMMIT_INTERVAL", env_value)
        cfg = load_config()
        assert cfg["library"]["commit_interval"] == expected

    @pytest.mark.parametrize(
        "env_value,expected",
        [
            ("0.78", 0.78),
            ("0.9", 0.9),
            ("1.0", 1.0),
        ],
    )
    def test_float_coercion(self, monkeypatch, env_value, expected):
        """Test float string representations are coerced correctly."""
        monkeypatch.setenv("PSM__MATCHING__FUZZY_THRESHOLD", env_value)
        cfg = load_config()
        assert cfg["matching"]["fuzzy_threshold"] == expected


class TestEnvironmentPrecedence:
    """Test configuration precedence: defaults <- file <- .env <- environment <- overrides."""

    def test_precedence_order(self, tmp_path, monkeypatch):
        """Test that environment variables override .env file, which overrides yaml."""
        # Create config.yaml
        config_file = tmp_path / "config.yaml"
        config_file.write_text("export:\n  mode: strict\n")

        # Create .env
        env_file = tmp_path / ".env"
        env_file.write_text("PSM__EXPORT__MODE=placeholders\n")

        # Test: yaml only
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("PSM_ENABLE_DOTENV", raising=False)
        monkeypatch.delenv("PSM__EXPORT__MODE", raising=False)
        cfg1 = load_config("config.yaml")
        assert cfg1["export"]["mode"] == "strict", "YAML should override default"

        # Test: yaml + .env
        monkeypatch.setenv("PSM_ENABLE_DOTENV", "1")
        cfg2 = load_config("config.yaml")
        assert cfg2["export"]["mode"] == "placeholders", ".env should override YAML"

        # Test: yaml + .env + environment
        monkeypatch.setenv("PSM__EXPORT__MODE", "mirrored")
        cfg3 = load_config("config.yaml")
        assert cfg3["export"]["mode"] == "mirrored", "Environment should override .env"
