"""Unit tests for duration filtering using CandidateSelector.

These tests verify that CandidateSelector.duration_prefilter() correctly
filters candidate files based on duration tolerance.
"""
import pytest
from psm.match.candidate_selector import CandidateSelector


@pytest.mark.unit
def test_duration_filter_reduces_candidates():
    """Test that duration filtering reduces candidates to only compatible files."""
    selector = CandidateSelector()

    tracks = [
        {'id': 't1', 'name': 'Song One', 'artist': 'Artist A', 'duration_ms': 180000},
        {'id': 't2', 'name': 'Song Two', 'artist': 'Artist B', 'duration_ms': 240000},
    ]
    files = [
        {'id': 1, 'path': 'file1.mp3', 'duration': 181.0},
        {'id': 2, 'path': 'file2.mp3', 'duration': 60.0},
        {'id': 3, 'path': 'file3.mp3', 'duration': 239.5},
        {'id': 4, 'path': 'file4.mp3', 'duration': 600.0},
    ]

    # Filter for track 1 (180s)
    candidates_t1 = selector.duration_prefilter(tracks[0], files, dur_tolerance=2.0)
    assert len(candidates_t1) == 1
    assert candidates_t1[0]['id'] == 1  # only file1

    # Filter for track 2 (240s)
    candidates_t2 = selector.duration_prefilter(tracks[1], files, dur_tolerance=2.0)
    assert len(candidates_t2) == 1
    assert candidates_t2[0]['id'] == 3  # only file3


@pytest.mark.unit
def test_duration_filter_handles_missing_durations():
    """Test that files/tracks with missing duration are not filtered out."""
    selector = CandidateSelector()

    track = {'id': 't1', 'name': 'Song', 'artist': 'Artist', 'duration_ms': None}
    files = [
        {'id': 1, 'path': 'file1.mp3', 'duration': 180.0},
        {'id': 2, 'path': 'file2.mp3', 'duration': None},
    ]

    # Track has no duration - all files should be returned
    candidates = selector.duration_prefilter(track, files, dur_tolerance=2.0)
    assert len(candidates) == 2
    assert {c['id'] for c in candidates} == {1, 2}


@pytest.mark.unit
def test_duration_filter_with_tolerance():
    """Test that duration tolerance window is correctly applied."""
    selector = CandidateSelector()

    track = {'id': 't1', 'name': 'Song', 'artist': 'Artist', 'duration_ms': 180000}  # 180s
    files = [
        {'id': 1, 'path': 'file1.mp3', 'duration': 176.0},  # -4s (within window)
        {'id': 2, 'path': 'file2.mp3', 'duration': 184.0},  # +4s (within window)
        {'id': 3, 'path': 'file3.mp3', 'duration': 175.0},  # -5s (outside window)
        {'id': 4, 'path': 'file4.mp3', 'duration': 185.0},  # +5s (outside window)
    ]

    # With tolerance=2.0, window = max(4, 2.0*2) = 4s
    # Should include files within ±4s of 180s
    candidates = selector.duration_prefilter(track, files, dur_tolerance=2.0)
    assert len(candidates) == 2
    assert {c['id'] for c in candidates} == {1, 2}


@pytest.mark.unit
def test_duration_filter_none_tolerance_disables_filtering():
    """Test that None tolerance disables filtering."""
    selector = CandidateSelector()

    track = {'id': 't1', 'name': 'Song', 'artist': 'Artist', 'duration_ms': 180000}
    files = [
        {'id': 1, 'path': 'file1.mp3', 'duration': 60.0},   # Very different
        {'id': 2, 'path': 'file2.mp3', 'duration': 600.0},  # Very different
    ]

    # None tolerance should return all files
    candidates = selector.duration_prefilter(track, files, dur_tolerance=None)
    assert len(candidates) == 2
    assert {c['id'] for c in candidates} == {1, 2}

