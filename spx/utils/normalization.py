from __future__ import annotations
import re
import unicodedata
from typing import Tuple

_feat_pattern = re.compile(r"\bfeat\.?|ft\.?", re.IGNORECASE)
_paren_remaster_pattern = re.compile(r"\((?:remaster(?:ed)?\s*\d{2,4})\)", re.IGNORECASE)
_punct_pattern = re.compile(r"[\s\-_.]+")

_stopwords = {"the", "a", "an"}


def normalize_token(s: str) -> str:
    s = s.lower().strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = _feat_pattern.sub("", s)
    s = _paren_remaster_pattern.sub("", s)
    # remove content inside brackets often variant info
    s = re.sub(r"[\[\](){}]", " ", s)
    s = re.sub(r"feat\..*", "", s)
    # collapse punctuation
    s = _punct_pattern.sub(" ", s)
    # remove non alnum except space
    s = re.sub(r"[^a-z0-9 ]+", "", s)
    tokens = [t for t in s.split() if t and t not in _stopwords]
    return " ".join(tokens)


def normalize_title_artist(title: str, artist: str) -> Tuple[str, str, str]:
    nt = normalize_token(title)
    na = normalize_token(artist)
    combo = f"{na} {nt}".strip()
    return nt, na, combo

__all__ = ["normalize_title_artist", "normalize_token"]
