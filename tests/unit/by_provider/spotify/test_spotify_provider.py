"""Unit tests for SpotifyProvider factory class."""

import pytest
from psm.providers.spotify.provider import SpotifyProvider, SpotifyLinkGenerator
from psm.providers.spotify.auth import SpotifyAuthProvider
from psm.providers.spotify.client import SpotifyAPIClient


class TestSpotifyProvider:
    """Test the Spotify provider factory and configuration."""

    def test_provider_name(self):
        """Test that provider name is 'spotify'."""
        provider = SpotifyProvider()
        assert provider.name == "spotify"

    def test_create_auth_returns_auth_provider(self, tmp_path):
        """Test that create_auth returns SpotifyAuthProvider instance."""
        provider = SpotifyProvider()
        config = {
            "client_id": "test_client_123",
            "scope": "user-library-read",
            "redirect_port": 9876,
            "cache_file": str(tmp_path / "token.json"),
        }
        auth = provider.create_auth(config)

        assert isinstance(auth, SpotifyAuthProvider)
        assert auth.client_id == "test_client_123"
        assert auth.scope == "user-library-read"

    def test_create_auth_with_minimal_config(self, tmp_path):
        """Test create_auth with minimal required config."""
        provider = SpotifyProvider()
        config = {"client_id": "minimal123", "cache_file": str(tmp_path / "tok.json")}
        auth = provider.create_auth(config)

        assert isinstance(auth, SpotifyAuthProvider)
        assert auth.client_id == "minimal123"

    def test_create_auth_with_custom_redirect_settings(self, tmp_path):
        """Test create_auth respects custom redirect configuration."""
        provider = SpotifyProvider()
        config = {
            "client_id": "custom123",
            "cache_file": str(tmp_path / "tok.json"),
            "redirect_scheme": "https",
            "redirect_port": 5555,
            "redirect_path": "/callback",
            "redirect_host": "localhost",
        }
        auth = provider.create_auth(config)

        assert isinstance(auth, SpotifyAuthProvider)
        # Verify redirect URI is built correctly
        redirect_uri = auth.build_redirect_uri()
        assert redirect_uri == "https://localhost:5555/callback"

    def test_create_client_returns_api_client(self):
        """Test that create_client returns SpotifyAPIClient instance."""
        provider = SpotifyProvider()
        client = provider.create_client("dummy-access-token-123")

        assert isinstance(client, SpotifyAPIClient)
        assert client.token == "dummy-access-token-123"

    def test_create_client_with_different_tokens(self):
        """Test that create_client works with different token values."""
        provider = SpotifyProvider()

        client1 = provider.create_client("token-alpha")
        client2 = provider.create_client("token-beta")

        assert client1.token == "token-alpha"
        assert client2.token == "token-beta"
        assert client1 is not client2  # Different instances

    def test_validate_config_raises_on_missing_client_id(self):
        """Test that validate_config raises ValueError when client_id missing."""
        provider = SpotifyProvider()

        with pytest.raises(ValueError, match="client_id"):
            provider.validate_config({})

        with pytest.raises(ValueError, match="client_id"):
            provider.validate_config({"scope": "user-library-read"})

    def test_validate_config_accepts_valid_config(self):
        """Test that validate_config accepts config with client_id."""
        provider = SpotifyProvider()

        # Should not raise
        provider.validate_config({"client_id": "test123"})
        provider.validate_config({"client_id": "abc", "scope": "read"})

    def test_validate_config_accepts_empty_client_id(self):
        """Test that empty client_id is accepted (validation is lenient)."""
        provider = SpotifyProvider()

        # Current implementation only checks presence, not emptiness
        # This is acceptable as auth will fail with invalid credentials anyway
        provider.validate_config({"client_id": ""})  # Should not raise

    def test_get_default_config(self):
        """Test that get_default_config returns expected defaults."""
        provider = SpotifyProvider()
        defaults = provider.get_default_config()

        # Check key defaults are present with correct values
        assert "redirect_port" in defaults
        assert defaults["redirect_port"] == 9876
        assert "scope" in defaults
        assert "redirect_scheme" in defaults
        assert defaults["redirect_scheme"] == "http"
        assert "redirect_path" in defaults
        assert defaults["redirect_path"] == "/callback"
        assert "redirect_host" in defaults
        assert defaults["redirect_host"] == "127.0.0.1"
        assert "timeout_seconds" in defaults
        assert defaults["timeout_seconds"] == 300
        assert "cache_file" in defaults
        assert defaults["cache_file"] == "tokens.json"

    def test_get_default_config_is_complete(self):
        """Test that default config contains all expected keys."""
        provider = SpotifyProvider()
        defaults = provider.get_default_config()

        expected_keys = [
            "redirect_port",
            "redirect_scheme",
            "redirect_path",
            "redirect_host",
            "timeout_seconds",
            "scope",
            "cache_file",
        ]

        for key in expected_keys:
            assert key in defaults, f"Missing default config key: {key}"

    def test_get_link_generator(self):
        """Test that get_link_generator returns SpotifyLinkGenerator."""
        provider = SpotifyProvider()
        gen = provider.get_link_generator()

        assert isinstance(gen, SpotifyLinkGenerator)

    def test_get_link_generator_is_functional(self):
        """Test that returned link generator actually works."""
        provider = SpotifyProvider()
        gen = provider.get_link_generator()

        # Verify it can generate URLs
        track_url = gen.track_url("test123")
        assert track_url.startswith("https://open.spotify.com/track/")
        assert "test123" in track_url

    def test_provider_implements_provider_interface(self):
        """Test that SpotifyProvider has all required Provider methods."""
        provider = SpotifyProvider()

        # Check that all abstract methods are implemented
        assert hasattr(provider, "name")
        assert hasattr(provider, "create_auth")
        assert hasattr(provider, "create_client")
        assert hasattr(provider, "validate_config")
        assert hasattr(provider, "get_default_config")
        assert hasattr(provider, "get_link_generator")

        # Verify they're callable
        assert callable(provider.create_auth)
        assert callable(provider.create_client)
        assert callable(provider.validate_config)
        assert callable(provider.get_default_config)
        assert callable(provider.get_link_generator)
