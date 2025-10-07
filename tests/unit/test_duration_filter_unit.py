import pytest
from psm.services.match_service import build_duration_candidate_map


@pytest.mark.unit
def test_duration_filter_reduces_candidates():
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
    candidates = build_duration_candidate_map(tracks, files, dur_tol=2.0)
    assert candidates['t1'] == [1]  # only file1
    assert candidates['t2'] == [3]  # only file3


@pytest.mark.unit
def test_duration_filter_handles_missing_durations():
    tracks = [
        {'id': 't1', 'name': 'Song', 'artist': 'Artist', 'duration_ms': None},
    ]
    files = [
        {'id': 1, 'path': 'file1.mp3', 'duration': 180.0},
        {'id': 2, 'path': 'file2.mp3', 'duration': None},
    ]
    candidates = build_duration_candidate_map(tracks, files, dur_tol=2.0)
    assert set(candidates['t1']) == {1, 2}


@pytest.mark.unit
def test_duration_filter_simple_skip_simulation():
    tracks = [
        {'id': 't1', 'name': 'Song One', 'artist': 'Artist A', 'duration_ms': 180000},
        {'id': 't2', 'name': 'Song Two', 'artist': 'Artist B', 'duration_ms': 240000},
    ]
    files = [
        # Duration chosen to be within tolerance of t2 (240s) so both tracks see it before filtering
        {'id': 1, 'path': 'file1.mp3', 'duration': 240.5},
    ]
    candidates = build_duration_candidate_map(tracks, files, dur_tol=2.0)
    # Simulate already matched removal externally
    del candidates['t1']
    assert candidates['t2'] == [1]
