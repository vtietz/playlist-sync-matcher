from __future__ import annotations
from typing import Iterable, Dict, Any, List, Tuple
from rapidfuzz import fuzz
import sqlite3
import os, time
import click
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
    """Match tracks to files. Returns list of (track_id, file_id, score, method) tuples.
    
    Logs progress during fuzzy matching to show which track is currently being processed.
    """
    debug = os.environ.get('SPX_DEBUG')
    tracks_list = list(tracks)
    files_list = list(files)
    results: List[Tuple[str, int, float, str]] = []
    
    # Build a hash map for exact matches (O(1) lookup instead of O(m) scan)
    file_norm_map: Dict[str, int] = {}
    for f in files_list:
        f_norm = f.get("normalized") or ""
        if f_norm and f_norm not in file_norm_map:
            file_norm_map[f_norm] = f["id"]
    
    # Progress tracking
    start_time = time.time()
    progress_interval = max(1, len(tracks_list) // 100)  # Report every 1% of tracks
    
    for idx, t in enumerate(tracks_list, 1):
        t_norm = t.get("normalized") or ""
        
        # Fast path: exact match via hash lookup (O(1) instead of O(m))
        if t_norm and t_norm in file_norm_map:
            results.append((t["id"], file_norm_map[t_norm], 1.0, "exact"))
            continue
        
        # Slow path: fuzzy matching (only if no exact match)
        # Show which track is being processed
        if debug and idx % progress_interval == 0:
            elapsed = time.time() - start_time
            tracks_per_sec = idx / elapsed if elapsed > 0 else 0
            eta = (len(tracks_list) - idx) / tracks_per_sec if tracks_per_sec > 0 else 0
            pct = (idx / len(tracks_list)) * 100
            print(f"[match][fuzzy] Processing: {idx}/{len(tracks_list)} tracks ({pct:.0f}%) - {len(results)} matches - {tracks_per_sec:.1f} tracks/sec - ETA {eta:.0f}s")
            print(f"  → Currently matching: {t.get('artist', '')} - {t.get('name', '')}")
        
        best = (None, 0.0, "")  # file_id, score, method
        for f in files_list:
            f_norm = f.get("normalized") or ""
            if not t_norm or not f_norm:
                continue
            
            fuzzy = score_fuzzy(t_norm, f_norm)
            if fuzzy >= fuzzy_threshold and fuzzy > best[1]:
                best = (f["id"], fuzzy, "fuzzy")
        
        if best[0] is not None:
            results.append((t["id"], best[0], best[1], best[2]))
    
    return results

def match_and_store(db, fuzzy_threshold: float = 0.78, use_year: bool = False):
    start = time.time()
    debug = os.environ.get('SPX_DEBUG')
    
    # Pull candidate sets from DB
    if debug:
        print("[match] Loading tracks and files from database...")
    cur_tracks = db.conn.execute("SELECT id, name, artist, year, normalized, isrc FROM tracks")
    tracks = [dict(row) for row in cur_tracks.fetchall()]
    cur_files = db.conn.execute("SELECT id, path, normalized FROM library_files")
    files = [dict(row) for row in cur_files.fetchall()]
    
    # Build file lookup maps for detailed logging
    file_by_id = {f['id']: f for f in files}
    track_by_id = {t['id']: t for t in tracks}
    
    if debug:
        print(f"[match] Loaded {len(tracks)} tracks and {len(files)} library files")
    
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
        if debug:
            print(f"[match] Backfilled normalization for {backfilled} tracks")
    
    # STAGE 1: SQL-based exact matching (leverages indexed normalized columns)
    if debug:
        print(f"[match][stage1] SQL exact matching via indexed normalized field...")
    stage1_start = time.time()
    
    # Use SQL JOIN to find exact matches - SQLite will use the normalized indices efficiently
    sql_exact = """
        SELECT t.id as track_id, lf.id as file_id
        FROM tracks t
        INNER JOIN library_files lf ON t.normalized = lf.normalized
        WHERE t.normalized IS NOT NULL AND t.normalized != ''
    """
    exact_matches = db.conn.execute(sql_exact).fetchall()
    
    # Store SQL exact matches
    matched_track_ids = set()
    for row in exact_matches:
        track_id = row['track_id']
        file_id = row['file_id']
        db.add_match(track_id, file_id, 1.0, "sql_exact")
        matched_track_ids.add(track_id)
        
        # Detailed logging of each match
        if debug:
            track = track_by_id.get(track_id, {})
            file_path = file_by_id.get(file_id, {}).get('path', 'unknown')
            print(f"{click.style('[sql_exact]', fg='green')} {track.get('artist', '')} - {track.get('name', '')} → {file_path}")
    
    stage1_duration = time.time() - stage1_start
    if debug:
        print(f"[match][stage1] Found {len(exact_matches)} exact matches via SQL in {stage1_duration:.2f}s")
    
    # STAGE 2: Fuzzy matching for unmatched tracks only
    unmatched_tracks = [t for t in tracks if t['id'] not in matched_track_ids]
    stage2_matches = 0
    stage2_duration = 0.0
    
    if unmatched_tracks:
        if debug:
            print(f"[match][stage2] Fuzzy matching {len(unmatched_tracks)} unmatched tracks against {len(files)} files (threshold={fuzzy_threshold})...")
        stage2_start = time.time()
        
        # Run fuzzy matching only on unmatched tracks
        fuzzy_results = match_tracks(unmatched_tracks, files, fuzzy_threshold=fuzzy_threshold)
        
        # Store fuzzy matches with detailed logging
        progress_interval = max(1, len(fuzzy_results) // 100)  # Report every 1% of matches
        for idx, (track_id, file_id, score, method) in enumerate(fuzzy_results, 1):
            db.add_match(track_id, file_id, score, method)
            matched_track_ids.add(track_id)
            
            # Detailed logging of each fuzzy match
            if debug:
                track = track_by_id.get(track_id, {})
                file_path = file_by_id.get(file_id, {}).get('path', 'unknown')
                # Color code by score: high (cyan), medium (yellow), low (magenta)
                color = 'cyan' if score >= 0.9 else 'yellow' if score >= fuzzy_threshold else 'magenta'
                print(f"{click.style('[fuzzy]', fg=color)} {track.get('artist', '')} - {track.get('name', '')} → {file_path} (score={score:.2f})")
                
                # Progress update every N matches
                if idx % progress_interval == 0:
                    elapsed = time.time() - stage2_start
                    pct = (idx / len(fuzzy_results)) * 100
                    print(f"[match][stage2] Progress: {idx}/{len(fuzzy_results)} fuzzy matches stored ({pct:.0f}%) - {elapsed:.1f}s elapsed")
        
        stage2_matches = len(fuzzy_results)
        stage2_duration = time.time() - stage2_start
        if debug:
            print(f"[match][stage2] Found {stage2_matches} fuzzy matches in {stage2_duration:.2f}s")
    else:
        if debug:
            print(f"[match][stage2] Skipped - all tracks matched in stage 1")
    
    db.commit()
    
    # Summary (always show, not just debug)
    dur = time.time() - start
    total_matches = len(exact_matches) + stage2_matches
    match_rate = (total_matches / len(tracks) * 100) if tracks else 0
    print(f"[match] Matched {total_matches}/{len(tracks)} tracks ({match_rate:.1f}%) - exact={len(exact_matches)} fuzzy={stage2_matches} - {dur:.2f}s")
    
    # Detailed debug info
    if debug:
        if not files:
            print("[match][warn] No library files present. Did you run 'scan'? Check library.paths config and that the directory has supported extensions.")
        # Show breakdown
        print(f"[match] Stage 1 (SQL): {len(exact_matches)} matches in {stage1_duration:.2f}s")
        if unmatched_tracks:
            print(f"[match] Stage 2 (Fuzzy): {stage2_matches}/{len(unmatched_tracks)} remaining tracks in {stage2_duration:.2f}s")
        # Unmatched diagnostics: show up to 5 unmatched track ids
        if tracks and len(matched_track_ids) < len(tracks):
            unmatched = [t['id'] for t in tracks if t['id'] not in matched_track_ids][:5]
            print(f"{click.style('[unmatched]', fg='red')} Sample tracks (first {len(unmatched)}):")
            for track_id in unmatched:
                track = track_by_id.get(track_id, {})
                print(f"  - {track.get('artist', '')} - {track.get('name', '')} (normalized: {track.get('normalized', '')})")
    
    return total_matches

__all__ = ["match_tracks", "match_and_store"]
