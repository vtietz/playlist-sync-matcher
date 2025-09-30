from __future__ import annotations
from typing import Iterable, Dict, Any, List, Tuple
from rapidfuzz import fuzz
import sqlite3
import os, time
from ..utils.normalization import normalize_title_artist

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

def match_and_store(db, fuzzy_threshold: float = 0.78, use_year: bool = False):
    start = time.time()
    # Pull candidate sets from DB
    cur_tracks = db.conn.execute("SELECT id, name, artist, year, normalized, isrc FROM tracks")
    tracks = [dict(row) for row in cur_tracks.fetchall()]
    cur_files = db.conn.execute("SELECT id, normalized FROM library_files")
    files = [dict(row) for row in cur_files.fetchall()]
    # Backfill normalization if missing (old ingests)
    backfilled = 0
    for t in tracks:
        if not t.get('normalized'):
            # compute
            nt, na, combo = normalize_title_artist(t.get('name') or '', t.get('artist') or '')
            if use_year and t.get('year'):
                combo = f"{combo} {t['year']}"
            t['normalized'] = combo
            db.conn.execute("UPDATE tracks SET normalized=? WHERE id=?", (combo, t['id']))
            backfilled += 1
    if backfilled:
        db.commit()
    # need id for files (library_files has id PK autoinc)
    results = match_tracks(tracks, files, fuzzy_threshold=fuzzy_threshold)
    for track_id, file_id, score, method in results:
        db.add_match(track_id, file_id, score, method)
    db.commit()
    if os.environ.get('SPX_DEBUG'):
        dur = time.time() - start
        print(f"[match] tracks={len(tracks)} files={len(files)} matches={len(results)} threshold={fuzzy_threshold} backfilled={backfilled} in {dur:.2f}s")
        if not files:
            print("[match][warn] No library files present. Did you run 'scan'? Check library.paths config and that the directory has supported extensions.")
        # Show top 5 matches sample
        for t_id, f_id, sc, m in results[:5]:
            print(f"[match] sample t={t_id} f={f_id} score={sc:.3f} method={m}")
        # Unmatched diagnostics: show up to 5 unmatched track ids
        matched_ids = {r[0] for r in results}
        if tracks and len(matched_ids) < len(tracks):
            unmatched = [t['id'] for t in tracks if t['id'] not in matched_ids][:5]
            print(f"[match] unmatched sample (first {len(unmatched)}): {', '.join(unmatched)}")
    return len(results)

__all__ = ["match_tracks", "match_and_store"]
