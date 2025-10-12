"""Base class for matching strategies."""
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Set
from abc import ABC, abstractmethod


class MatchStrategy(ABC):
    """Base class for all matching strategies.

    Each strategy attempts to match tracks to files and returns:
    - List of (track_id, file_id, score, method) tuples
    - Set of matched track IDs
    """

    def __init__(self, db, config: Dict[str, Any], debug: bool = False):
        self.db = db
        self.config = config
        self.debug = debug

    @abstractmethod
    def match(self, tracks: List[Dict[str, Any]], files: List[Dict[str, Any]],
              already_matched: Set[str]) -> Tuple[List[Tuple[str, int, float, str]], Set[str]]:
        """Execute matching strategy.

        Args:
            tracks: List of track dictionaries with keys: id, name, artist, album, duration_ms, normalized, year
            files: List of file dictionaries with keys: id, path, normalized, duration, year
            already_matched: Set of track IDs that have already been matched (to skip)

        Returns:
            Tuple of (matches, matched_track_ids) where:
            - matches: List of (track_id, file_id, score, method) tuples
            - matched_track_ids: Set of track IDs that were matched in this strategy
        """

    @abstractmethod
    def get_name(self) -> str:
        """Return the strategy name for logging."""
