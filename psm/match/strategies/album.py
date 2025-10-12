"""Album-based matching strategy.

This strategy matches tracks using normalized artist + title + album name.
It's more reliable than year for distinguishing between versions like:
- Studio album vs. live album
- Original release vs. greatest hits compilation
- Different album releases of the same song
"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Set
import logging
from .base import MatchStrategy

logger = logging.getLogger(__name__)


class AlbumMatchStrategy(MatchStrategy):
    """Match using normalized artist + title + album."""

    def get_name(self) -> str:
        return "album_match"

    def match(self, tracks: List[Dict[str, Any]], files: List[Dict[str, Any]],
              already_matched: Set[str]) -> Tuple[List[Tuple[str, int, float, str]], Set[str]]:
        """Execute album-based matching on unmatched tracks."""

        # Filter to unmatched tracks that have album info
        unmatched_tracks = [t for t in tracks
                           if t['id'] not in already_matched
                           and t.get('album') and t.get('normalized')]

        if not unmatched_tracks:
            if self.debug:
                print(f"[{self.get_name()}] No unmatched tracks with album info to process")
            return [], set()

        # Build file index: (normalized, album_normalized) -> file_id
        # We need to normalize album names too
        from ...utils.normalization import normalize_title_artist

        file_index: Dict[Tuple[str, str], int] = {}
        file_by_id = {f['id']: f for f in files}

        for f in files:
            if f.get('normalized') and f.get('album'):
                norm_album, _, _ = normalize_title_artist(f['album'], '')
                key = (f['normalized'], norm_album)
                # First match wins (don't overwrite)
                if key not in file_index:
                    file_index[key] = f['id']

        if self.debug:
            print(f"[{self.get_name()}] Built index with {len(file_index)} (track+album) combinations")
            print(f"[{self.get_name()}] Matching {len(unmatched_tracks)} tracks with album info")

        matches: List[Tuple[str, int, float, str]] = []
        matched_track_ids: Set[str] = set()

        for track in unmatched_tracks:
            track_id = track['id']
            track_norm = track.get('normalized', '')
            track_album = track.get('album', '')

            if not track_norm or not track_album:
                continue

            # Normalize album name
            norm_album, _, _ = normalize_title_artist(track_album, '')
            key = (track_norm, norm_album)

            if key in file_index:
                file_id = file_index[key]
                matches.append((track_id, file_id, 1.0, self.get_name()))
                matched_track_ids.add(track_id)

                if self.debug:
                    file_path = file_by_id[file_id].get('path', 'unknown')
                    print(f"[{self.get_name()}] [MATCH] Album: "
                          f"{track.get('artist', '')} - {track.get('name', '')} "
                          f"[{track_album}] -> {file_path}")

        if self.debug:
            print(f"[{self.get_name()}] Found {len(matches)} album-based matches")

        return matches, matched_track_ids
