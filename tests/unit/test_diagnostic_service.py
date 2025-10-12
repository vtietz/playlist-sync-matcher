"""Unit tests for diagnostic service output formatting."""

from psm.services.diagnostic_service import DiagnosticResult, format_diagnostic_output


def test_threshold_recommendation_shows_meaningful_difference():
    """Test that threshold recommendations don't suggest the same value.

    Regression test for bug where recommendations like "from 78% to 78%"
    were shown due to rounding issues.
    """
    # Setup: Best score is 0.76, threshold is 0.78
    # This triggers the "close to threshold" recommendation
    result = DiagnosticResult(
        track_found=True,
        track_info={
            'id': 'test123',
            'name': 'Test Song',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'duration_ms': 180000,
            'year': 2024,
            'normalized': 'test artist test song',
            'isrc': None,
        },
        is_matched=False,
        matched_file=None,
        closest_files=[
            (
                {
                    'path': '/music/test.mp3',
                    'artist': 'Test Artist',
                    'title': 'Test Song',
                    'album': 'Test Album',
                    'duration': 180.0,
                    'normalized': 'test artist test song'
                },
                0.76  # Score just below 0.78 threshold
            )
        ],
        total_files=100,
        fuzzy_threshold=0.78
    )

    output = format_diagnostic_output(result)

    # Verify output contains recommendation section
    assert "💡 Recommendations:" in output
    assert "The closest file is very close to the threshold!" in output

    # Verify the recommendation shows DIFFERENT values (not "78% to 78%")
    # Should show something like "78.0% to 71.0%" with at least 5% difference
    lines = output.split('\n')
    recommendation_line = [l for l in lines if 'Consider lowering fuzzy_threshold' in l]

    assert len(recommendation_line) == 1, "Should have exactly one threshold recommendation"

    rec_line = recommendation_line[0]

    # Extract the two percentage values using simple string parsing
    # Format: "from XX.X% to YY.Y%"
    assert 'from' in rec_line and 'to' in rec_line

    # Split and extract percentages
    parts = rec_line.split('from')[1].split('to')
    from_value = parts[0].strip().rstrip('%')
    to_value = parts[1].strip().split()[0].rstrip('%')  # Get first word after 'to'

    from_pct = float(from_value)
    to_pct = float(to_value)

    # The values should be different (at least 3% difference to be meaningful)
    difference = from_pct - to_pct
    assert difference >= 3.0, f"Recommendation should suggest at least 3% reduction, got {difference}%"

    # The 'to' value should be lower (more permissive)
    assert to_pct < from_pct, "Recommended threshold should be lower than current"

    # Sanity checks
    assert from_pct == 78.0, "Should show current threshold as 78.0%"
    assert to_pct <= 71.0, "Should recommend 71.0% or lower (76 - 5 = 71)"


def test_near_perfect_match_recommendation():
    """Test that near-perfect matches suggest duration tolerance instead of threshold."""
    result = DiagnosticResult(
        track_found=True,
        track_info={
            'id': 'test123',
            'name': 'Test Song',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'duration_ms': 180000,  # 3:00
            'year': 2024,
            'normalized': 'test artist test song',
            'isrc': None,
        },
        is_matched=False,
        matched_file=None,
        closest_files=[
            (
                {
                    'path': '/music/test.mp3',
                    'artist': 'Test Artist',
                    'title': 'Test Song',
                    'album': 'Test Album',
                    'duration': 195.0,  # 3:15 (15 seconds difference)
                    'normalized': 'test artist test song'
                },
                0.97  # Near-perfect score
            )
        ],
        total_files=100,
        fuzzy_threshold=0.78
    )

    output = format_diagnostic_output(result)

    # Should recommend duration_tolerance, not fuzzy_threshold
    assert "PERFECT OR NEAR-PERFECT MATCH FOUND" in output
    assert "DURATION FILTER" in output
    assert "PSM__MATCHING__DURATION_TOLERANCE" in output
    assert "PSM__MATCHING__FUZZY_THRESHOLD" not in output


def test_low_score_recommendation():
    """Test that low scores suggest tag/metadata issues."""
    result = DiagnosticResult(
        track_found=True,
        track_info={
            'id': 'test123',
            'name': 'Test Song',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'duration_ms': 180000,
            'year': 2024,
            'normalized': 'test artist test song',
            'isrc': None,
        },
        is_matched=False,
        matched_file=None,
        closest_files=[
            (
                {
                    'path': '/music/other.mp3',
                    'artist': 'Other Artist',
                    'title': 'Other Song',
                    'album': 'Other Album',
                    'duration': 200.0,
                    'normalized': 'other artist other song'
                },
                0.35  # Low score
            )
        ],
        total_files=100,
        fuzzy_threshold=0.78
    )

    output = format_diagnostic_output(result)

    # Should suggest tag/metadata issues, not threshold changes
    assert "No close matches found" in output
    assert "File tags don't match Spotify metadata" in output or "tags" in output.lower()
    assert "PSM__MATCHING__FUZZY_THRESHOLD" not in output
