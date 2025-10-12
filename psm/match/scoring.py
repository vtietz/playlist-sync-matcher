from __future__ import annotations
"""Scoring-based matching engine for track-to-file matching.

This module defines dataclasses and a scoring function that evaluates a remote track
(Spotify) against a library file row. It does NOT perform DB access itself; callers
should provide already-fetched dictionaries.

Design goals:
- Weighted additive scoring with penalties
- Map raw score to confidence tiers
- Transparent breakdown for diagnostics
- Keep pure / side-effect free for easy unit testing

NOTE: This first iteration reuses existing single normalized field and the already
available duration/year/album columns. Future migration can persist additional
pre-normalized columns if needed.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple
import re
from rapidfuzz import fuzz
from ..utils.normalization import normalize_token

# --- Confidence Enum -------------------------------------------------------

class MatchConfidence(str, Enum):
    CERTAIN = "certain"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    REJECTED = "rejected"

# --- Dataclasses -----------------------------------------------------------

@dataclass
class ScoreBreakdown:
    raw_score: float
    confidence: MatchConfidence
    matched_title: bool
    matched_artist: bool
    matched_album: bool
    matched_year: bool
    matched_isrc: bool
    duration_diff: Optional[int]
    title_ratio: Optional[float]
    artist_ratio: Optional[float]
    notes: List[str] = field(default_factory=list)

@dataclass
class CandidateEvaluation:
    track_id: str
    file_id: int
    score: ScoreBreakdown

# --- Scoring Configuration -------------------------------------------------

@dataclass
class ScoringConfig:
    """Configuration for scoring engine weights, thresholds, and penalties.

    Scoring Scenarios Analysis:

    1. Perfect Match (CERTAIN = 100+):
       - Title exact (45) + Artist exact (30) + Album exact (18) + Year (6) + Duration tight (6) = 105
       - OR: Title exact + Artist exact + ISRC (15) + Duration = 96 (below threshold!)

    2. Strong Match without Album/Year (HIGH = 90+):
       - Title exact (45) + Artist exact (30) + Duration tight (6) = 81
       - Minus: Album missing local (8) + Album missing remote (5) + Year missing (8) = -21
       - Total: 81 - 21 = 60 (falls to LOW, below MEDIUM!)

    3. Strong Match with missing metadata requires ISRC:
       - Title exact (45) + Artist exact (30) + ISRC (15) + Duration (6) = 96 (HIGH)
       - Minus: Album penalties (13) + Year penalties (8) = -21
       - Total: 96 - 21 = 75 (REJECTED if below min_accept=65, but reaches LOW 65-78)

    4. Fuzzy title but strong artist + duration:
       - Title fuzzy max (30) + Artist exact (30) + Duration (6) = 66 (LOW)
       - With album: +18 = 84 (HIGH)

    Observation: Current thresholds are too strict for files with missing album/year
    but strong title/artist/duration matches. This is common for:
    - Singles (no album)
    - Compilations (year mismatch)
    - User-ripped files (incomplete metadata)

    Recommended adjustments:
    - Lower confidence_certain_threshold: 100 → 95 (allows ISRC path without all metadata)
    - Lower confidence_high_threshold: 90 → 82 (allows exact title+artist+duration)
    - Reduce penalty_complete_metadata_missing: 20 → 15 (less harsh on singles)
    - OR: Add bonus for strong core match (title+artist+duration all exact)
    """
    # fuzzy thresholds
    min_title_ratio: int = 88
    strong_title_ratio: int = 96
    min_artist_ratio: int = 92
    strong_artist_ratio: int = 96
    min_album_fuzzy_ratio: int = 95
    # duration tolerances (seconds)
    tight_duration: int = 2
    loose_duration: int = 4
    # score weights
    weight_title_exact: float = 45
    weight_title_fuzzy_max: float = 30  # scaled when fuzzy not exact
    weight_artist_exact: float = 30
    weight_artist_fuzzy: float = 20
    weight_album_exact: float = 18
    weight_album_fuzzy: float = 12
    weight_year: float = 6
    weight_duration_tight: float = 6
    weight_duration_loose: float = 3
    weight_isrc: float = 15
    # penalties
    penalty_album_missing_local: float = 8
    penalty_album_missing_remote: float = 5
    penalty_year_missing: float = 4
    penalty_variant_mismatch: float = 6
    penalty_complete_metadata_missing: float = 15.0  # Reduced from 20 (less harsh on singles)
    # confidence thresholds (adjusted for real-world metadata gaps)
    confidence_certain_threshold: float = 95.0  # Lowered from 100 (allows ISRC matches)
    confidence_high_threshold: float = 82.0  # Lowered from 90 (allows title+artist+duration)
    confidence_medium_threshold: float = 78.0
    # acceptance
    min_accept_score: float = 65

# --- Utility Normalization -------------------------------------------------

def _canonical_artist(artist: str) -> str:
    return normalize_token(artist)

def _canonical_title(title: str) -> str:
    return normalize_token(title)

# --- Variant Detection -----------------------------------------------------

# Compile regex patterns for variant detection (performance optimization)
_VARIANT_PATTERN = re.compile(
    r'''
    (?:                                  # Non-capturing group for alternatives
        \b(?:live|remix|acoustic|edit|mix|version|demo|remaster(?:ed)?|instrumental|radio|explicit|clean|deluxe|bonus|extended|unplugged)\b |  # Word boundary keywords
        \((?:live|remix|acoustic|edit|mix|version|demo|remaster(?:ed)?|instrumental|radio|explicit|clean|deluxe|bonus|extended|unplugged)\b[^\)]*\) |  # Parenthesized variants
        \[(?:live|remix|acoustic|edit|mix|version|demo|remaster(?:ed)?|instrumental|radio|explicit|clean|deluxe|bonus|extended|unplugged)\b[^\]]*\]     # Bracketed variants
    )
    ''',
    re.IGNORECASE | re.VERBOSE
)

def _has_variant(title: str) -> bool:
    """Check if title contains variant keywords using regex.

    Handles multiple contexts:
    - Word boundary matches: "Live at..."
    - Parenthesized: "(Live 2023)", "(Remastered)"
    - Bracketed: "[Radio Edit]", "[2024 Remaster]"

    Args:
        title: Track title to check

    Returns:
        True if variant keyword detected, False otherwise
    """
    if not title:
        return False
    return bool(_VARIANT_PATTERN.search(title))

# --- Core Scoring Logic ----------------------------------------------------

def evaluate_pair(remote: Dict[str, Any], local: Dict[str, Any], cfg: ScoringConfig) -> ScoreBreakdown:
    """Compute a score breakdown for a remote track vs local file.

    Expected keys:
      remote: id, name, artist, album, year, isrc, duration_ms, normalized
      local: id, path, artist, album, year, duration, normalized
    """
    notes: List[str] = []

    # Basic fields
    r_title = remote.get("name") or ""
    l_title = local.get("title") or local.get("name") or local.get("path", "")
    r_artist = remote.get("artist") or ""
    l_artist = local.get("artist") or ""
    r_album = remote.get("album") or None
    l_album = local.get("album") or None
    r_year = remote.get("year")
    l_year = local.get("year")
    r_isrc = (remote.get("isrc") or "").strip().lower() or None
    l_isrc = (local.get("isrc") or "").strip().lower() or None

    # Duration: remote ms vs local seconds
    r_dur_ms = remote.get("duration_ms")
    l_dur_s = local.get("duration")
    duration_diff_sec: Optional[int] = None
    if r_dur_ms is not None and l_dur_s is not None:
        duration_diff_sec = int(abs(r_dur_ms/1000 - l_dur_s))

    # Normalized tokens
    r_title_norm = _canonical_title(r_title)
    l_title_norm = _canonical_title(l_title)
    r_artist_norm = _canonical_artist(r_artist)
    l_artist_norm = _canonical_artist(l_artist)
    # Preserve original presence flags (avoid penalizing if normalization strips tokens)
    r_album_present = bool(r_album)
    l_album_present = bool(l_album)
    r_album_norm = _canonical_title(r_album) if r_album_present else None
    l_album_norm = _canonical_title(l_album) if l_album_present else None

    raw_score = 0.0

    matched_title = False
    matched_artist = False
    matched_album = False
    matched_year = False
    matched_isrc = False

    title_ratio = None
    artist_ratio = None

    # Title scoring
    if r_title_norm and l_title_norm:
        if r_title_norm == l_title_norm:
            raw_score += cfg.weight_title_exact
            matched_title = True
            notes.append("title_exact")
        else:
            title_ratio_val = fuzz.token_set_ratio(r_title_norm, l_title_norm)
            title_ratio = title_ratio_val / 100.0
            if title_ratio_val >= cfg.min_title_ratio:
                matched_title = True
                # scale contribution: min->0, strong->max
                span = max(1, cfg.strong_title_ratio - cfg.min_title_ratio)
                scaled = (min(title_ratio_val, cfg.strong_title_ratio) - cfg.min_title_ratio) / span
                raw_score += scaled * cfg.weight_title_fuzzy_max
                notes.append(f"title_fuzzy:{title_ratio_val}")
            else:
                notes.append(f"title_no_match:{title_ratio_val}")

    # Artist scoring
    if r_artist_norm and l_artist_norm:
        if r_artist_norm == l_artist_norm:
            raw_score += cfg.weight_artist_exact
            matched_artist = True
            notes.append("artist_exact")
        else:
            artist_ratio_val = fuzz.token_set_ratio(r_artist_norm, l_artist_norm)
            artist_ratio = artist_ratio_val / 100.0
            if artist_ratio_val >= cfg.min_artist_ratio:
                matched_artist = True
                raw_score += cfg.weight_artist_fuzzy
                notes.append(f"artist_fuzzy:{artist_ratio_val}")
            else:
                notes.append(f"artist_no_match:{artist_ratio_val}")

    # Album scoring (based on original presence not purely normalization result)
    if r_album_present and l_album_present:
        # If normalization emptied both, consider them matching (common generic names like 'Album')
        if (not r_album_norm and not l_album_norm) or r_album_norm == l_album_norm:
            raw_score += cfg.weight_album_exact
            matched_album = True
            notes.append("album_exact")
        else:
            if r_album_norm and l_album_norm:
                album_ratio_val = fuzz.token_set_ratio(r_album_norm, l_album_norm)
                if album_ratio_val >= cfg.min_album_fuzzy_ratio:
                    matched_album = True
                    raw_score += cfg.weight_album_fuzzy
                    notes.append(f"album_fuzzy:{album_ratio_val}")
                else:
                    notes.append(f"album_mismatch:{album_ratio_val}")
            else:
                # One normalized empty (descriptor stripped) treat as fuzzy exact
                matched_album = True
                raw_score += cfg.weight_album_fuzzy
                notes.append("album_norm_empty_match")
    else:
        if not l_album_present:
            raw_score -= cfg.penalty_album_missing_local
            notes.append("penalty_album_missing_local")
        if not r_album_present:
            raw_score -= cfg.penalty_album_missing_remote
            notes.append("penalty_album_missing_remote")

    # Year scoring
    if r_year is not None and l_year is not None:
        if r_year == l_year or abs(r_year - l_year) == 1:
            raw_score += cfg.weight_year
            matched_year = True
            notes.append("year_match")
        else:
            notes.append("year_mismatch")
    else:
        if r_year is None:
            raw_score -= cfg.penalty_year_missing
            notes.append("penalty_year_missing_remote")
        if l_year is None:
            raw_score -= cfg.penalty_year_missing
            notes.append("penalty_year_missing_local")

    # Combined penalties to demote low-metadata items
    if (not r_album_present and not l_album_present) and (r_year is None and l_year is None):
        raw_score -= cfg.penalty_complete_metadata_missing
        notes.append("penalty_all_metadata_missing")

    # Duration scoring
    if duration_diff_sec is not None:
        if duration_diff_sec <= cfg.tight_duration:
            raw_score += cfg.weight_duration_tight
            notes.append("duration_tight")
        elif duration_diff_sec <= cfg.loose_duration:
            raw_score += cfg.weight_duration_loose
            notes.append("duration_loose")
        else:
            notes.append(f"duration_far:{duration_diff_sec}")

    # ISRC boost
    if r_isrc and l_isrc and r_isrc == l_isrc:
        raw_score += cfg.weight_isrc
        matched_isrc = True
        notes.append("isrc_match")

    # Variant penalty: detect if one has variant markers and other doesn't
    # Use original titles (before normalization which may strip these keywords)
    if r_title and l_title:
        if _has_variant(r_title) != _has_variant(l_title):
            raw_score -= cfg.penalty_variant_mismatch
            notes.append("penalty_variant_mismatch")

    # Confidence mapping based on configured thresholds
    # Perfect metadata path
    if matched_title and matched_artist and matched_album and matched_year and matched_isrc:
        confidence = MatchConfidence.CERTAIN
    else:
        if raw_score >= cfg.confidence_certain_threshold:
            confidence = MatchConfidence.CERTAIN
        elif raw_score >= cfg.confidence_high_threshold:
            confidence = MatchConfidence.HIGH
        elif raw_score >= cfg.confidence_medium_threshold:
            confidence = MatchConfidence.MEDIUM
        elif raw_score >= cfg.min_accept_score:
            confidence = MatchConfidence.LOW
        else:
            confidence = MatchConfidence.REJECTED

    return ScoreBreakdown(
        raw_score=raw_score,
        confidence=confidence,
        matched_title=matched_title,
        matched_artist=matched_artist,
        matched_album=matched_album,
        matched_year=matched_year,
        matched_isrc=matched_isrc,
        duration_diff=duration_diff_sec,
        title_ratio=title_ratio,
        artist_ratio=artist_ratio,
        notes=notes,
    )

# --- Batch Evaluation Helper -----------------------------------------------

def evaluate_against_candidates(remote: Dict[str, Any], candidates: List[Dict[str, Any]], cfg: ScoringConfig) -> Optional[CandidateEvaluation]:
    """Return best CandidateEvaluation above minimum acceptance or None."""
    best: Tuple[Optional[CandidateEvaluation], float] = (None, 0.0)
    for local in candidates:
        breakdown = evaluate_pair(remote, local, cfg)
        if breakdown.confidence == MatchConfidence.REJECTED:
            continue
        if best[0] is None or breakdown.raw_score > best[1]:
            best = (CandidateEvaluation(track_id=remote['id'], file_id=local['id'], score=breakdown), breakdown.raw_score)
    return best[0]

__all__ = [
    "MatchConfidence",
    "ScoreBreakdown",
    "CandidateEvaluation",
    "ScoringConfig",
    "evaluate_pair",
    "evaluate_against_candidates",
]
