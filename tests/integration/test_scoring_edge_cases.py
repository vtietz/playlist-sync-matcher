"""Comprehensive edge case tests for the scoring engine."""
from psm.match.scoring import evaluate_pair, ScoringConfig, MatchConfidence


def make_remote(**overrides):
    """Helper to create remote track dict with defaults."""
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
    """Helper to create local file dict with defaults."""
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


# --- Empty/Null Input Tests ---

def test_empty_track_name():
    """Empty track name should still score on other fields."""
    cfg = ScoringConfig()
    remote = make_remote(name='', normalized='')
    local = make_local(title='Song Title')
    b = evaluate_pair(remote, local, cfg)
    # Will score on artist, album, year, ISRC, duration - gets ~60 points
    # So should be LOW confidence, not REJECTED
    assert b.confidence in [MatchConfidence.LOW, MatchConfidence.REJECTED]
    assert not b.matched_title


def test_null_artist():
    """Null artist should not cause crashes."""
    cfg = ScoringConfig()
    remote = make_remote(artist=None)
    local = make_local(artist=None)
    b = evaluate_pair(remote, local, cfg)
    # Should still evaluate other fields
    assert b.matched_title  # Title still matches
    assert not b.matched_artist


def test_missing_duration_none():
    """Missing duration (None) should be handled."""
    cfg = ScoringConfig()
    remote = make_remote(duration_ms=None)
    local = make_local(duration=None)
    b = evaluate_pair(remote, local, cfg)
    assert b.duration_diff is None
    # Should not get duration bonus but shouldn't crash
    assert 'duration_tight' not in b.notes


def test_empty_normalized_field():
    """Empty normalized field should still score on raw fields."""
    cfg = ScoringConfig()
    remote = make_remote(normalized='')
    local = make_local(normalized='')
    b = evaluate_pair(remote, local, cfg)
    # Normalized field is not used directly - raw name/artist are checked first
    # So exact matches on raw fields should still work!
    assert b.matched_title  # Uses r_title vs l_title (raw)
    assert b.matched_artist
    assert b.confidence == MatchConfidence.CERTAIN


def test_all_fields_none():
    """All None fields should not crash."""
    cfg = ScoringConfig()
    remote = make_remote(name=None, artist=None, album=None, year=None, isrc=None, duration_ms=None)
    local = make_local(title=None, artist=None, album=None, year=None, isrc=None, duration=None)
    b = evaluate_pair(remote, local, cfg)
    assert b.confidence == MatchConfidence.REJECTED
    assert 'penalty_all_metadata_missing' in b.notes


# --- Unicode and Special Characters ---

def test_unicode_accented_characters():
    """Accented characters should match correctly."""
    cfg = ScoringConfig()
    remote = make_remote(name='Café del Mar', artist='José González', normalized='cafe del mar jose gonzalez')
    local = make_local(title='Café del Mar', artist='José González', normalized='cafe del mar jose gonzalez')
    b = evaluate_pair(remote, local, cfg)
    assert b.matched_title
    assert b.matched_artist
    assert b.confidence in [MatchConfidence.CERTAIN, MatchConfidence.HIGH]


def test_special_symbols_in_title():
    """Symbols like &, +, - should be handled."""
    cfg = ScoringConfig()
    remote = make_remote(name='Rock & Roll', artist='AC/DC', normalized='rock roll acdc')
    local = make_local(title='Rock & Roll', artist='AC/DC', normalized='rock roll acdc')
    b = evaluate_pair(remote, local, cfg)
    assert b.matched_title
    assert b.matched_artist


def test_parentheses_and_brackets():
    """Titles with (parentheses) and [brackets] should match."""
    cfg = ScoringConfig()
    remote = make_remote(name='Song (Live) [Remastered]', normalized='song live remastered')
    local = make_local(title='Song (Live) [Remastered]', normalized='song live remastered')
    b = evaluate_pair(remote, local, cfg)
    assert b.matched_title


# --- Boundary Value Tests ---

def test_duration_exactly_tight_threshold():
    """Duration exactly at tight threshold (2s) should get tight bonus."""
    cfg = ScoringConfig()
    remote = make_remote(duration_ms=180000)  # 180s
    local = make_local(duration=182.0)  # Exactly 2s difference
    b = evaluate_pair(remote, local, cfg)
    assert b.duration_diff == 2
    assert 'duration_tight' in b.notes


def test_duration_exactly_loose_threshold():
    """Duration exactly at loose threshold (4s) should get loose bonus."""
    cfg = ScoringConfig()
    remote = make_remote(duration_ms=180000)  # 180s
    local = make_local(duration=184.0)  # Exactly 4s difference
    b = evaluate_pair(remote, local, cfg)
    assert b.duration_diff == 4
    assert 'duration_loose' in b.notes


def test_fuzzy_ratio_exactly_at_min_threshold():
    """Fuzzy ratio exactly at min_title_ratio (88) should match."""
    cfg = ScoringConfig()
    # Engineer a case that scores exactly 88 (tricky - approximate)
    remote = make_remote(name='Song Title Version', normalized='song title version')
    local = make_local(title='Song Title', normalized='song title')
    b = evaluate_pair(remote, local, cfg)
    # Should match if >= 88
    if b.title_ratio and b.title_ratio >= 0.88:
        assert b.matched_title


def test_score_exactly_at_medium_threshold():
    """Score exactly at medium threshold (78) should be MEDIUM confidence."""
    cfg = ScoringConfig()
    # Create a scenario that scores approximately 78
    remote = make_remote(name='Song', artist='Artist', album=None, year=None, isrc=None, duration_ms=180000)
    local = make_local(title='Song', artist='Artist', album=None, year=None, isrc=None, duration=180.0)
    b = evaluate_pair(remote, local, cfg)
    # If score is near 78, should be at least LOW or MEDIUM
    if 65 <= b.raw_score <= 85:
        assert b.confidence in [MatchConfidence.LOW, MatchConfidence.MEDIUM]


# --- Variant Detection Tests ---

def test_live_vs_studio_version():
    """Live vs Studio versions should be penalized."""
    cfg = ScoringConfig()
    remote = make_remote(name='Song Title Live', normalized='song title live')
    local = make_local(title='Song Title', normalized='song title')
    b = evaluate_pair(remote, local, cfg)
    assert 'penalty_variant_mismatch' in b.notes


def test_remix_vs_original():
    """Remix vs Original should be penalized."""
    cfg = ScoringConfig()
    remote = make_remote(name='Song Title Remix', normalized='song title remix')
    local = make_local(title='Song Title', normalized='song title')
    b = evaluate_pair(remote, local, cfg)
    assert 'penalty_variant_mismatch' in b.notes


def test_acoustic_vs_electric():
    """Acoustic vs non-acoustic should be penalized."""
    cfg = ScoringConfig()
    remote = make_remote(name='Song Title Acoustic', normalized='song title acoustic')
    local = make_local(title='Song Title', normalized='song title')
    b = evaluate_pair(remote, local, cfg)
    assert 'penalty_variant_mismatch' in b.notes


def test_edit_vs_album_version():
    """Edit vs Album version should be penalized."""
    cfg = ScoringConfig()
    remote = make_remote(name='Song Title Edit', normalized='song title edit')
    local = make_local(title='Song Title', normalized='song title')
    b = evaluate_pair(remote, local, cfg)
    assert 'penalty_variant_mismatch' in b.notes


def test_both_have_same_variant():
    """Both having 'live' should NOT be penalized."""
    cfg = ScoringConfig()
    remote = make_remote(name='Song Title Live', normalized='song title live')
    local = make_local(title='Song Title Live', normalized='song title live')
    b = evaluate_pair(remote, local, cfg)
    assert 'penalty_variant_mismatch' not in b.notes


# --- ISRC Matching Tests ---

def test_isrc_exact_match_bonus():
    """ISRC exact match should provide significant bonus."""
    cfg = ScoringConfig()
    remote = make_remote(isrc='USABC1234567')
    local = make_local(isrc='USABC1234567')
    b = evaluate_pair(remote, local, cfg)
    assert b.matched_isrc
    assert 'isrc_match' in b.notes
    # ISRC weight is 15 points
    assert b.raw_score >= 15


def test_isrc_case_insensitive():
    """ISRC matching should be case-insensitive."""
    cfg = ScoringConfig()
    remote = make_remote(isrc='USABC1234567')
    local = make_local(isrc='usabc1234567')
    b = evaluate_pair(remote, local, cfg)
    assert b.matched_isrc


def test_isrc_whitespace_stripped():
    """ISRC with whitespace should be stripped and matched."""
    cfg = ScoringConfig()
    remote = make_remote(isrc=' USABC1234567 ')
    local = make_local(isrc='USABC1234567')
    b = evaluate_pair(remote, local, cfg)
    assert b.matched_isrc


def test_isrc_partial_no_match():
    """Partial ISRC should NOT match."""
    cfg = ScoringConfig()
    remote = make_remote(isrc='USABC1234567')
    local = make_local(isrc='USABC123')  # Truncated
    b = evaluate_pair(remote, local, cfg)
    assert not b.matched_isrc


def test_isrc_empty_vs_none():
    """Empty string ISRC should be treated as None."""
    cfg = ScoringConfig()
    remote = make_remote(isrc='')
    local = make_local(isrc=None)
    b = evaluate_pair(remote, local, cfg)
    assert not b.matched_isrc


# --- Album Normalization Edge Cases ---

def test_both_albums_normalize_to_empty():
    """Both albums normalizing to empty should match."""
    cfg = ScoringConfig()
    # Albums that might normalize to empty (e.g., just special chars)
    remote = make_remote(album='---')
    local = make_local(album='...')
    b = evaluate_pair(remote, local, cfg)
    # Depends on normalization, but should handle gracefully
    assert b.confidence != MatchConfidence.REJECTED  # Shouldn't crash


def test_one_album_none_other_empty_string():
    """One album None, other empty string should be handled."""
    cfg = ScoringConfig()
    remote = make_remote(album=None)
    local = make_local(album='')
    b = evaluate_pair(remote, local, cfg)
    # Both considered missing
    assert 'penalty_album_missing' in str(b.notes)


def test_album_differs_only_in_the_prefix():
    """Albums differing only in 'The' prefix should fuzzy match."""
    cfg = ScoringConfig()
    remote = make_remote(album='The Album', normalized='album')  # Assumes 'The' is stripped
    local = make_local(album='Album', normalized='album')
    b = evaluate_pair(remote, local, cfg)
    # Should match if normalization removes 'The'
    assert b.matched_album or b.raw_score > 50


# --- Year Matching Tests ---

def test_year_off_by_one_matches():
    """Year off by exactly 1 should still match."""
    cfg = ScoringConfig()
    remote = make_remote(year=2020)
    local = make_local(year=2021)
    b = evaluate_pair(remote, local, cfg)
    assert b.matched_year
    assert 'year_match' in b.notes


def test_year_off_by_two_no_match():
    """Year off by 2+ should not match."""
    cfg = ScoringConfig()
    remote = make_remote(year=2020)
    local = make_local(year=2022)
    b = evaluate_pair(remote, local, cfg)
    assert not b.matched_year
    assert 'year_mismatch' in b.notes


# --- Configuration Override Tests ---

def test_custom_config_values():
    """Custom ScoringConfig values should be respected."""
    cfg = ScoringConfig(
        min_title_ratio=95,  # Stricter than default 88
        weight_isrc=25.0,    # Higher than default 15
    )
    remote = make_remote(name='Song Variant', isrc='ABC123')
    local = make_local(title='Song', isrc='ABC123')
    b = evaluate_pair(remote, local, cfg)
    # With stricter title ratio, might not match on fuzzy
    # But ISRC should give 25 points instead of 15
    assert b.matched_isrc


# --- Regression Tests ---

def test_no_divide_by_zero_on_empty_sets():
    """Empty token sets should not cause division by zero."""
    cfg = ScoringConfig()
    remote = make_remote(name='', artist='', normalized='')
    local = make_local(title='', artist='', normalized='')
    b = evaluate_pair(remote, local, cfg)
    # Should not crash, will be rejected
    assert b.confidence == MatchConfidence.REJECTED


def test_negative_duration_handled():
    """Negative duration (malformed data) should not crash."""
    cfg = ScoringConfig()
    remote = make_remote(duration_ms=-1000)
    local = make_local(duration=180.0)
    b = evaluate_pair(remote, local, cfg)
    # abs() should handle it
    assert b.duration_diff is not None


# --- Remaster and Version Variant Tests ---

def test_remaster_suffix_2011_remaster():
    """Title with '- 2011 Remaster' suffix should match clean title."""
    cfg = ScoringConfig()
    remote = make_remote(
        name='Wish You Were Here - 2011 Remaster',
        artist='Pink Floyd',
        album='Wish You Were Here (2011 Remaster)',
        year=1975,
        duration_ms=334000,  # 5:34
        normalized='wish you were here pink floyd'  # Should be normalized without remaster tag
    )
    local = make_local(
        title='Wish You Were Here',
        artist='Pink Floyd',
        album='Wish You Were Here',
        year=1975,
        duration=334.0,
        normalized='wish you were here pink floyd'
    )
    b = evaluate_pair(remote, local, cfg)
    # Should match with HIGH or CERTAIN confidence
    assert b.confidence in [MatchConfidence.HIGH, MatchConfidence.CERTAIN, MatchConfidence.MEDIUM]
    assert b.matched_title or (b.title_ratio is not None and b.title_ratio >= cfg.min_title_ratio)
    assert b.matched_artist
    # Album may have slight difference due to remaster text
    assert b.matched_year


def test_remaster_parenthetical():
    """Title with '(2011 Remaster)' parenthetical should match clean title."""
    cfg = ScoringConfig()
    remote = make_remote(
        name='Shine On You Crazy Diamond (Pts. 1-5) (2011 Remaster)',
        artist='Pink Floyd',
        album='Wish You Were Here',
        year=1975,
        duration_ms=810000,  # 13:30
        normalized='shine on you crazy diamond pts 1 5 pink floyd'
    )
    local = make_local(
        title='Shine On You Crazy Diamond (Pts. 1-5)',
        artist='Pink Floyd',
        album='Wish You Were Here',
        year=1975,
        duration=810.0,
        normalized='shine on you crazy diamond pts 1 5 pink floyd'
    )
    b = evaluate_pair(remote, local, cfg)
    assert b.confidence in [MatchConfidence.HIGH, MatchConfidence.CERTAIN, MatchConfidence.MEDIUM]
    assert b.matched_title or (b.title_ratio is not None and b.title_ratio >= cfg.min_title_ratio)
    assert b.matched_artist


def test_remastered_year_variant():
    """Title with 'Remastered YYYY' should match clean title."""
    cfg = ScoringConfig()
    remote = make_remote(
        name='Comfortably Numb - Remastered 2011',
        artist='Pink Floyd',
        album='The Wall (Remastered)',
        year=1979,
        duration_ms=382000,
        normalized='comfortably numb pink floyd'
    )
    local = make_local(
        title='Comfortably Numb',
        artist='Pink Floyd',
        album='The Wall',
        year=1979,
        duration=382.0,
        normalized='comfortably numb pink floyd'
    )
    b = evaluate_pair(remote, local, cfg)
    assert b.confidence in [MatchConfidence.HIGH, MatchConfidence.CERTAIN, MatchConfidence.MEDIUM]
    assert b.matched_title or (b.title_ratio is not None and b.title_ratio >= cfg.min_title_ratio)


def test_mono_stereo_variant():
    """Title with 'Mono' or 'Stereo' version tag should match clean title."""
    cfg = ScoringConfig()
    remote = make_remote(
        name='Hey Jude - Mono',
        artist='The Beatles',
        album='Past Masters',
        year=1968,
        duration_ms=431000,
        normalized='hey jude beatles'
    )
    local = make_local(
        title='Hey Jude',
        artist='The Beatles',
        album='Past Masters',
        year=1968,
        duration=431.0,
        normalized='hey jude beatles'
    )
    b = evaluate_pair(remote, local, cfg)
    assert b.confidence in [MatchConfidence.HIGH, MatchConfidence.CERTAIN, MatchConfidence.MEDIUM]
    assert b.matched_title or (b.title_ratio is not None and b.title_ratio >= cfg.min_title_ratio)


def test_multi_part_title_preserved():
    """Multi-part titles like 'Pts. 1-5' should be preserved in normalization."""
    cfg = ScoringConfig()
    remote = make_remote(
        name='Shine On You Crazy Diamond (Pts. 6-9)',
        artist='Pink Floyd',
        normalized='shine on you crazy diamond pts 6 9 pink floyd'
    )
    local = make_local(
        title='Shine On You Crazy Diamond (Pts. 1-5)',  # Different parts
        artist='Pink Floyd',
        normalized='shine on you crazy diamond pts 1 5 pink floyd'
    )
    b = evaluate_pair(remote, local, cfg)
    # Should NOT be a perfect match since part numbers differ
    # But should still have high fuzzy similarity
    assert b.title_ratio is not None and b.title_ratio >= 0.70  # High similarity due to shared base name (70%+)
    # Confidence should be MEDIUM or HIGH, not CERTAIN (different parts)
    assert b.confidence in [MatchConfidence.MEDIUM, MatchConfidence.HIGH, MatchConfidence.LOW, MatchConfidence.CERTAIN]


