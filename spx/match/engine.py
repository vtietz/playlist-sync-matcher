from __future__ import annotations
from typing import Iterable, Dict, Any, List, Tuple
from rapidfuzz import fuzz
import sqlite3

# Track dict expected keys: id,name,artist,album,isrc,normalized
# File dict expected keys: id,path,normalized


def score_exact(t_norm: str, f_norm: str) -> float:
    if t_norm == f_norm:
        return 1.0
    return 0.0


def score_fuzzy(t_norm: str, f_norm: str) -> float:
    # token set ratio returns 0-100
    return fuzz.token_set_ratio(t_norm, f_norm) / 100.0


def match_tracks(tracks: Iterable[Dict[str, Any]], files: Iterable[Dict[str, Any]], fuzzy_threshold: float = 0.78) -> List[Tuple[str, int, float, str]]:
    files_list = list(files)
    results: List[Tuple[str, int, float, str]] = []
    for t in tracks:
        t_norm = t.get("normalized") or ""
        isrc = t.get("isrc")
        # ISRC direct match placeholder (needs mapping) - skip for now
        best = (None, 0.0, "")  # file_id, score, method
        for f in files_list:
            f_norm = f.get("normalized") or ""
            exact = score_exact(t_norm, f_norm)
            if exact > best[1]:
                best = (f["id"], exact, "exact")
            if best[1] < 1.0:  # only fuzzy if not perfect
                fuzzy = score_fuzzy(t_norm, f_norm)
                if fuzzy >= fuzzy_threshold and fuzzy > best[1]:
                    best = (f["id"], fuzzy, "fuzzy")
        if best[0] is not None:
            results.append((t["id"], best[0], best[1], best[2]))
    return results

def match_and_store(db, fuzzy_threshold: float = 0.78):
    # Pull candidate sets from DB
    cur_tracks = db.conn.execute("SELECT id, normalized, isrc FROM tracks")
    tracks = [dict(row) for row in cur_tracks.fetchall()]
    cur_files = db.conn.execute("SELECT id, normalized FROM library_files")
    files = [dict(row) for row in cur_files.fetchall()]
    # need id for files (library_files has id PK autoinc)
    results = match_tracks(tracks, files, fuzzy_threshold=fuzzy_threshold)
    for track_id, file_id, score, method in results:
        db.add_match(track_id, file_id, score, method)
    db.commit()
    return len(results)

__all__ = ["match_tracks", "match_and_store"]
