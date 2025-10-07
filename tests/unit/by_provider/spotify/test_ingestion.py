"""Unit tests for Spotify ingestion utilities."""

import pytest
from psm.providers.spotify.ingestion import extract_year


class TestExtractYear:
    """Test year extraction from Spotify release date strings."""
    
    def test_extract_year_full_date(self):
        """Test extraction from full ISO date (YYYY-MM-DD)."""
        assert extract_year('2024-12-31') == 2024
        assert extract_year('2023-01-01') == 2023
        assert extract_year('1999-06-15') == 1999
        assert extract_year('2000-02-29') == 2000
    
    def test_extract_year_partial_date(self):
        """Test extraction from partial date (YYYY-MM)."""
        assert extract_year('2024-12') == 2024
        assert extract_year('2023-01') == 2023
        assert extract_year('1995-08') == 1995
    
    def test_extract_year_only(self):
        """Test extraction from year only (YYYY)."""
        assert extract_year('2024') == 2024
        assert extract_year('1990') == 1990
        assert extract_year('2000') == 2000
    
    def test_extract_year_empty_string(self):
        """Test handling of empty string."""
        assert extract_year('') is None
    
    def test_extract_year_none(self):
        """Test handling of None value."""
        assert extract_year(None) is None
    
    def test_extract_year_invalid_format(self):
        """Test handling of invalid date formats."""
        assert extract_year('invalid') is None
        assert extract_year('abc-def-ghi') is None
        assert extract_year('20-24-12-31') is None
        assert extract_year('not a date') is None
    
    def test_extract_year_partial_invalid(self):
        """Test handling of strings too short to contain a year."""
        assert extract_year('202') is None
        assert extract_year('20') is None
        assert extract_year('2') is None
    
    def test_extract_year_non_numeric(self):
        """Test handling of non-numeric year component."""
        assert extract_year('abcd-12-31') is None
        assert extract_year('20XX-01-01') is None
