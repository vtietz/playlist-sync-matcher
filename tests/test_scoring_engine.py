from psm.match.scoring import evaluate_pair, ScoringConfig, MatchConfidence


def make_remote(**overrides):
    base = {
        'id': 'r1',
        'name': 'Song Title',
        'artist': 'Artist',
        'album': 'Album',
        'year': 2020,
        'isrc': 'ABC123',
        'duration_ms': 180000,
        'normalized': 'song title artist'
    }
    base.update(overrides)
    return base


def make_local(**overrides):
    base = {
        'id': 1,
        'path': 'file.mp3',
        'title': 'Song Title',
        'artist': 'Artist',
        'album': 'Album',
        'year': 2020,
        'isrc': 'ABC123',
        'duration': 180.0,
        'normalized': 'song title artist'
    }
    base.update(overrides)
    return base


def test_scoring_exact_all():
    cfg = ScoringConfig()
    b = evaluate_pair(make_remote(), make_local(), cfg)
    assert b.confidence == MatchConfidence.CERTAIN
    assert b.matched_title and b.matched_artist and b.matched_album and b.matched_year and b.matched_isrc


def test_scoring_missing_album_year_penalties():
    cfg = ScoringConfig()
    remote = make_remote(album=None, year=None, isrc=None)
    local = make_local(album=None, year=None, isrc=None)
    b = evaluate_pair(remote, local, cfg)
    assert 'penalty_album_missing_local' in b.notes
    assert 'penalty_album_missing_remote' in b.notes
    assert 'penalty_year_missing_local' in b.notes
    assert 'penalty_year_missing_remote' in b.notes
    assert 'penalty_all_metadata_missing' in b.notes
    assert b.raw_score < 60  # ensure demoted sufficiently


def test_scoring_fuzzy_title_artist():
    cfg = ScoringConfig()
    remote = make_remote(name='Song Title (Live)', artist='Artist')
    local = make_local(title='Song Title', artist='Artist')
    b = evaluate_pair(remote, local, cfg)
    assert b.matched_title
    assert b.matched_artist
    assert b.raw_score > 40  # got some title + artist score


def test_scoring_reject_low_similarity():
    cfg = ScoringConfig()
    remote = make_remote(name='Completely Different', artist='Someone Else', album='Other')
    local = make_local(title='Song Title', artist='Artist', album='Album')
    b = evaluate_pair(remote, local, cfg)
    assert b.confidence == MatchConfidence.REJECTED


def test_duration_tight_vs_loose():
    cfg = ScoringConfig()
    remote = make_remote(duration_ms=180000)
    local_tight = make_local(duration=180.5)
    local_loose = make_local(duration=183.5)
    b_tight = evaluate_pair(remote, local_tight, cfg)
    b_loose = evaluate_pair(remote, local_loose, cfg)
    assert b_tight.raw_score >= b_loose.raw_score
    assert 'duration_tight' in b_tight.notes
    assert 'duration_loose' in b_loose.notes or 'duration_far' in b_loose.notes
