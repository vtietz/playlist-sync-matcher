"""Unit tests for Spotify link generator."""

import pytest
from psm.providers.spotify.provider import SpotifyLinkGenerator


class TestSpotifyLinkGenerator:
    """Test URL generation for Spotify resources."""
    
    def test_track_url(self):
        """Test track URL generation."""
        gen = SpotifyLinkGenerator()
        assert gen.track_url('abc123') == 'https://open.spotify.com/track/abc123'
        assert gen.track_url('7ouMYWpwJ422jRcDASZB7P') == 'https://open.spotify.com/track/7ouMYWpwJ422jRcDASZB7P'
        assert gen.track_url('') == 'https://open.spotify.com/track/'
    
    def test_album_url(self):
        """Test album URL generation."""
        gen = SpotifyLinkGenerator()
        assert gen.album_url('xyz789') == 'https://open.spotify.com/album/xyz789'
        assert gen.album_url('4aawyAB9vmqN3uQ7FjRGTy') == 'https://open.spotify.com/album/4aawyAB9vmqN3uQ7FjRGTy'
        assert gen.album_url('') == 'https://open.spotify.com/album/'
    
    def test_artist_url(self):
        """Test artist URL generation."""
        gen = SpotifyLinkGenerator()
        assert gen.artist_url('art456') == 'https://open.spotify.com/artist/art456'
        assert gen.artist_url('0OdUWJ0sBjDrqHygGUXeCF') == 'https://open.spotify.com/artist/0OdUWJ0sBjDrqHygGUXeCF'
        assert gen.artist_url('') == 'https://open.spotify.com/artist/'
    
    def test_playlist_url(self):
        """Test playlist URL generation."""
        gen = SpotifyLinkGenerator()
        assert gen.playlist_url('pl999') == 'https://open.spotify.com/playlist/pl999'
        assert gen.playlist_url('37i9dQZF1DXcBWIGoYBM5M') == 'https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M'
        assert gen.playlist_url('') == 'https://open.spotify.com/playlist/'
    
    def test_urls_use_https(self):
        """Test that all URLs use HTTPS protocol."""
        gen = SpotifyLinkGenerator()
        assert gen.track_url('test').startswith('https://')
        assert gen.album_url('test').startswith('https://')
        assert gen.artist_url('test').startswith('https://')
        assert gen.playlist_url('test').startswith('https://')
    
    def test_urls_use_open_spotify_domain(self):
        """Test that all URLs use open.spotify.com domain."""
        gen = SpotifyLinkGenerator()
        assert 'open.spotify.com' in gen.track_url('test')
        assert 'open.spotify.com' in gen.album_url('test')
        assert 'open.spotify.com' in gen.artist_url('test')
        assert 'open.spotify.com' in gen.playlist_url('test')
