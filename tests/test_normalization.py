from spx.utils.normalization import normalize_title_artist, normalize_token

def test_normalize_basic():
    nt, na, combo = normalize_title_artist("Song (Remastered 2011)", "The Beatles feat. Someone")
    assert "remastered" not in nt
    assert "beatles" in na
    assert "beatles" in combo


def test_token_removes_stopwords_and_diacritics():
    t = normalize_token("Án Thé (feat. Artist)")
    assert "the" not in t
    assert "an" not in t
    assert "feat" not in t
    assert "an" not in t  # diacritics removed
