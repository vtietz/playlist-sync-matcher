from __future__ import annotations
import re
import unicodedata
from functools import lru_cache
from typing import Tuple

_feat_pattern = re.compile(r"\bfeat\.?|ft\.?|featuring", re.IGNORECASE)
# Enhanced remaster pattern to catch more variants:
# - "2011 Remaster", "(2011 Remaster)", "(Remastered 2011)", "- 2011 Remaster"
# - "Remastered", "(Remaster)", "- Remaster", "Mono", "Stereo"
_remaster_pattern = re.compile(
    r"""
    (?:
        [\(\[\-\s]+                       # Leading paren, bracket, dash, or space
        (?:
            (?:19|20)\d{2}\s*remaster(?:ed)?  # Year + remaster/remastered
            | remaster(?:ed)?(?:\s*(?:19|20)\d{2})?  # Remaster(ed) with optional year
            | mono | stereo | mono\s*version | stereo\s*version
        )
        [\)\]]*                           # Optional closing paren/bracket
    )
    """,
    re.IGNORECASE | re.VERBOSE
)
_version_pattern = re.compile(r"\b(radio|album|single|extended|live|acoustic|remix|mix|edit|version|demo|deluxe|bonus|explicit|clean|instrumental)\b", re.IGNORECASE)
_punct_pattern = re.compile(r"[\s\-_.]+")

_stopwords = {"the", "a", "an", "and", "or", "of", "in", "on", "at", "to", "for", "with", "from"}


@lru_cache(maxsize=8192)
def normalize_token(s: str) -> str:
    s = s.lower().strip()
    # Unicode normalization (handle accents, diacritics)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    # Remove featuring/feat/ft
    s = _feat_pattern.sub("", s)
    # Remove remaster info (enhanced pattern)
    s = _remaster_pattern.sub("", s)
    # Remove version descriptors (radio edit, live, etc.)
    s = _version_pattern.sub("", s)
    # Remove content inside brackets/parens (often variant info)
    s = re.sub(r"[\[\](){}]", " ", s)
    # Remove trailing "feat..." that might remain
    s = re.sub(r"feat\..*", "", s)
    # Collapse punctuation and special chars to spaces
    s = _punct_pattern.sub(" ", s)
    # Remove everything except alphanumeric and space
    s = re.sub(r"[^a-z0-9 ]+", "", s)
    # Tokenize and remove stopwords
    tokens = [t for t in s.split() if t and t not in _stopwords]
    # Sort tokens to handle word order differences (e.g., "Beatles, The" vs "The Beatles")
    tokens.sort()
    return " ".join(tokens)


def normalize_title_artist(title: str, artist: str) -> Tuple[str, str, str]:
    nt = normalize_token(title)
    na = normalize_token(artist)
    combo = f"{na} {nt}".strip()
    return nt, na, combo

__all__ = ["normalize_title_artist", "normalize_token"]
