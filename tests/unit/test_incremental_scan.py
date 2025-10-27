"""Unit tests for incremental scan functionality."""

import pytest
from datetime import datetime, timedelta
from psm.ingest.library import parse_time_string, ScanResult


class TestParseTimeString:
    """Test time string parsing for --since flag."""

    def test_parse_unix_timestamp(self):
        """Should parse Unix timestamp strings."""
        ts = 1728123456.789
        result = parse_time_string(str(ts))
        assert result == ts

    def test_parse_iso_format(self):
        """Should parse ISO format datetime strings."""
        iso_str = "2025-10-08 10:30:00"
        result = parse_time_string(iso_str)
        expected = datetime(2025, 10, 8, 10, 30, 0).timestamp()
        assert abs(result - expected) < 1.0  # Allow 1 second tolerance

    def test_parse_relative_time_hours(self):
        """Should parse relative time like '2 hours ago'."""
        result = parse_time_string("2 hours ago")
        expected = (datetime.now() - timedelta(hours=2)).timestamp()
        assert abs(result - expected) < 10  # Allow 10 second tolerance for test execution time

    def test_parse_relative_time_minutes(self):
        """Should parse '30 minutes ago'."""
        result = parse_time_string("30 minutes ago")
        expected = (datetime.now() - timedelta(minutes=30)).timestamp()
        assert abs(result - expected) < 10

    def test_parse_relative_time_days(self):
        """Should parse '1 day ago'."""
        result = parse_time_string("1 day ago")
        expected = (datetime.now() - timedelta(days=1)).timestamp()
        assert abs(result - expected) < 10

    def test_parse_relative_time_plural(self):
        """Should handle plural forms like '3 days ago'."""
        result = parse_time_string("3 days ago")
        expected = (datetime.now() - timedelta(days=3)).timestamp()
        assert abs(result - expected) < 10

    def test_parse_relative_time_weeks(self):
        """Should parse '2 weeks ago'."""
        result = parse_time_string("2 weeks ago")
        expected = (datetime.now() - timedelta(weeks=2)).timestamp()
        assert abs(result - expected) < 10

    def test_parse_invalid_format_raises(self):
        """Should raise ValueError for invalid format."""
        with pytest.raises(ValueError, match="Unable to parse time string"):
            parse_time_string("invalid time format")

    def test_parse_case_insensitive(self):
        """Should be case-insensitive."""
        result = parse_time_string("2 Hours Ago")
        expected = (datetime.now() - timedelta(hours=2)).timestamp()
        assert abs(result - expected) < 10


class TestScanResult:
    """Test ScanResult dataclass."""

    def test_default_values(self):
        """Should initialize with default zero values."""
        result = ScanResult()
        assert result.files_seen == 0
        assert result.inserted == 0
        assert result.updated == 0
        assert result.skipped == 0
        assert result.deleted == 0
        assert result.errors == 0
        assert result.duration_seconds == 0.0

    def test_custom_values(self):
        """Should allow setting custom values."""
        result = ScanResult(
            files_seen=100, inserted=25, updated=10, skipped=60, deleted=5, errors=2, duration_seconds=12.5
        )
        assert result.files_seen == 100
        assert result.inserted == 25
        assert result.updated == 10
        assert result.skipped == 60
        assert result.deleted == 5
        assert result.errors == 2
        assert result.duration_seconds == 12.5
