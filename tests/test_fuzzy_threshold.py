from psm.match.engine import match_tracks


def test_fuzzy_threshold_exclusion_inclusion():
    tracks = [
        {'id': 't1', 'normalized': 'hello world artist'},
    ]
    files = [
        {'id': 1, 'normalized': 'hello wrld artist'},  # small edit distance
    ]
    # High threshold blocks match
    res_high = match_tracks(tracks, files, fuzzy_threshold=0.99)
    assert res_high == []
    # Lower threshold allows
    res_low = match_tracks(tracks, files, fuzzy_threshold=0.5)
    assert len(res_low) == 1
    track_id, file_id, score, method = res_low[0]
    assert track_id == 't1'
    assert file_id == 1
    assert method in ('fuzzy', 'exact')
    assert 0.5 <= score <= 1.0