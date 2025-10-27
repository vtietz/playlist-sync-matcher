"""Matching package exposing scoring-based engine primitives.

Legacy strategy/engine modules have been removed in favor of the unified
scoring approach defined in `scoring.py`.
"""

from .scoring import (
    MatchConfidence,
    ScoreBreakdown,
    CandidateEvaluation,
    ScoringConfig,
    evaluate_pair,
    evaluate_against_candidates,
)

__all__ = [
    "MatchConfidence",
    "ScoreBreakdown",
    "CandidateEvaluation",
    "ScoringConfig",
    "evaluate_pair",
    "evaluate_against_candidates",
]
