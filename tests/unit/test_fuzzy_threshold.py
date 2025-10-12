from psm.match.scoring import evaluate_pair, ScoringConfig, MatchConfidence


def test_scoring_fuzzy_influence():
    """Ensure near-miss title still accepted at LOW or better while very weak mismatch is rejected.

    We craft two local candidates: one with a minor title typo and one with a
    large deviation. We expect the minor typo to yield >= LOW confidence and
    the heavily altered title to be rejected.
    """
    cfg = ScoringConfig()
    remote = {
        'id': 't1', 'name': 'Hello World', 'artist': 'Artist', 'album': 'Album',
        'year': 2024, 'isrc': None, 'duration_ms': 180000, 'normalized': 'hello world artist'
    }
    close_local = {
        'id': 1, 'title': 'Hello Wrld', 'artist': 'Artist', 'album': 'Album',
        'year': 2024, 'duration': 180.0, 'normalized': 'hello wrld artist'
    }
    far_local = {
        'id': 2, 'title': 'Completely Different', 'artist': 'Different', 'album': 'Other',
        'year': 2024, 'duration': 180.0, 'normalized': 'completely different'
    }

    close_score = evaluate_pair(remote, close_local, cfg)
    far_score = evaluate_pair(remote, far_local, cfg)

    assert close_score.confidence in {MatchConfidence.CERTAIN, MatchConfidence.HIGH, MatchConfidence.MEDIUM, MatchConfidence.LOW}
    assert far_score.confidence == MatchConfidence.REJECTED
    assert close_score.raw_score > far_score.raw_score
