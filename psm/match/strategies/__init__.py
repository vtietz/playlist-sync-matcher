"""Matching strategies for finding local files for Spotify tracks."""

from .base import MatchStrategy
from .exact import ExactMatchStrategy
from .fuzzy import FuzzyMatchStrategy

__all__ = ["MatchStrategy", "ExactMatchStrategy", "FuzzyMatchStrategy"]
