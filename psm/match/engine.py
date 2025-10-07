from __future__ import annotations
from typing import Iterable, Dict, Any, List, Tuple
from rapidfuzz import fuzz
import sqlite3
import os, time
import logging
import click
from ..utils.normalization import normalize_title_artist
from .strategies import ExactMatchStrategy, DurationFilterStrategy, FuzzyMatchStrategy

logger = logging.getLogger(__name__)

# Track dict expected keys: id,name,artist,album,isrc,normalized
# File dict expected keys: id,path,normalized


def score_exact(t_norm: str, f_norm: str) -> float:
    """Legacy function for exact matching (kept for backward compatibility)."""
    if t_norm == f_norm:
        return 1.0
    return 0.0


def score_fuzzy(t_norm: str, f_norm: str) -> float:
    """Legacy function for fuzzy matching (kept for backward compatibility)."""
    # token set ratio returns 0-100
    return fuzz.token_set_ratio(t_norm, f_norm) / 100.0


def match_tracks(tracks: Iterable[Dict[str, Any]], files: Iterable[Dict[str, Any]], fuzzy_threshold: float = 0.78) -> List[Tuple[str, int, float, str]]:
    """Match tracks to files. Returns list of (track_id, file_id, score, method) tuples.
    
    Logs progress during fuzzy matching to show which track is currently being processed.
    """
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
        if idx % progress_interval == 0:
            elapsed = time.time() - start_time
            tracks_per_sec = idx / elapsed if elapsed > 0 else 0
            eta = (len(tracks_list) - idx) / tracks_per_sec if tracks_per_sec > 0 else 0
            pct = (idx / len(tracks_list)) * 100
            logger.debug(f"[match][fuzzy] Processing: {idx}/{len(tracks_list)} tracks ({pct:.0f}%) - {len(results)} matches - {tracks_per_sec:.1f} tracks/sec - ETA {eta:.0f}s")
            logger.debug(f"  → Currently matching: {t.get('artist', '')} - {t.get('name', '')}")
        
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

def match_and_store(db, config: Dict[str, Any] | None = None, fuzzy_threshold: float = 0.78, use_year: bool = False):
    """Match tracks to files using configurable strategies.
    
    Args:
        db: Database instance
        config: Configuration dictionary (optional, will use defaults if not provided)
        fuzzy_threshold: Fuzzy matching threshold (deprecated, use config instead)
        use_year: Whether to include year in normalization (deprecated, use config instead)
    
    The matching process applies strategies in order from config.matching.strategies:
    - sql_exact: Fast indexed SQL join on normalized field
    - duration_filter: Prefilter candidates by duration tolerance (reduces fuzzy work)
    - fuzzy: RapidFuzz token_set_ratio on remaining unmatched tracks
    """
    start = time.time()
    
    # Handle config (allow None for backward compatibility)
    if config is None:
        config = {
            'matching': {
                'fuzzy_threshold': fuzzy_threshold,
                'use_year': use_year,
                'duration_tolerance': 2.0,
                'strategies': ['sql_exact', 'duration_filter', 'fuzzy'],
            }
        }
    
    # Extract matching config
    matching_config = config.get('matching', {})
    enabled_strategies = matching_config.get('strategies', ['sql_exact', 'duration_filter', 'fuzzy'])
    duration_tolerance = matching_config.get('duration_tolerance', 2.0)
    
    # Pull candidate sets from DB
    logger.debug("[match] Loading tracks and files from database...")
    cur_tracks = db.conn.execute("SELECT id, name, artist, album, year, normalized, isrc, duration_ms FROM tracks")
    tracks = [dict(row) for row in cur_tracks.fetchall()]
    cur_files = db.conn.execute("SELECT id, path, normalized, duration, year FROM library_files")
    files = [dict(row) for row in cur_files.fetchall()]
    
    # Build file lookup maps for detailed logging
    file_by_id = {f['id']: f for f in files}
    track_by_id = {t['id']: t for t in tracks}
    
    logger.debug(f"[match] Loaded {len(tracks)} tracks and {len(files)} library files")
    logger.debug(f"[match] Enabled strategies: {', '.join(enabled_strategies)}")
    
    # Check if debug logging is enabled for strategies
    is_debug = logger.isEnabledFor(logging.DEBUG)
    
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
        logger.debug(f"[match] Backfilled normalization for {backfilled} tracks")
    
    # Track overall matches and timing
    all_matches: List[Tuple[str, int, float, str]] = []
    matched_track_ids = set()
    strategy_stats = {}
    candidate_file_ids: Dict[str, List[int]] | None = None  # Initialize to avoid unbound variable
    
    # Apply strategies in order
    for strategy_name in enabled_strategies:
        if strategy_name == 'sql_exact':
            # Stage 1: SQL-based exact matching
            logger.debug(f"[match][{strategy_name}] Running SQL exact matching strategy...")
            
            strategy = ExactMatchStrategy(db, config, debug=is_debug)
            matches, new_matched = strategy.match(tracks, files, matched_track_ids)
            
            # Store matches
            provider = config.get('provider', 'spotify')
            for track_id, file_id, score, method in matches:
                db.add_match(track_id, file_id, score, method, provider=provider)
            
            all_matches.extend(matches)
            matched_track_ids.update(new_matched)
            strategy_stats[strategy_name] = len(matches)
        
        elif strategy_name == 'album_match':
            # Stage 2: Album-based matching
            logger.debug(f"[match][{strategy_name}] Running album-based matching strategy...")
            
            from .strategies.album import AlbumMatchStrategy
            strategy = AlbumMatchStrategy(db, config, debug=is_debug)
            matches, new_matched = strategy.match(tracks, files, matched_track_ids)
            
            # Store matches
            provider = config.get('provider', 'spotify')
            for track_id, file_id, score, method in matches:
                db.add_match(track_id, file_id, score, method, provider=provider)
            
            all_matches.extend(matches)
            matched_track_ids.update(new_matched)
            strategy_stats[strategy_name] = len(matches)
        
        elif strategy_name == 'year_match':
            # Stage 3: Year-based matching
            logger.debug(f"[match][{strategy_name}] Running year-based matching strategy...")
            
            from .strategies.year import YearMatchStrategy
            strategy = YearMatchStrategy(db, config, debug=is_debug)
            matches, new_matched = strategy.match(tracks, files, matched_track_ids)
            
            # Store matches
            provider = config.get('provider', 'spotify')
            for track_id, file_id, score, method in matches:
                db.add_match(track_id, file_id, score, method, provider=provider)
            
            all_matches.extend(matches)
            matched_track_ids.update(new_matched)
            strategy_stats[strategy_name] = len(matches)
        
        elif strategy_name == 'duration_filter':
            # Stage: Duration filtering (preprocess for fuzzy)
            # This doesn't produce matches itself but filters candidates
            logger.debug(f"[match][{strategy_name}] Applying duration-based candidate filtering...")
            
            filter_strategy = DurationFilterStrategy(
                tolerance_seconds=duration_tolerance
            )
            # Store candidate map for use by fuzzy strategy
            candidate_file_ids = filter_strategy.filter_candidates(tracks, files, matched_track_ids)
            strategy_stats[strategy_name] = "filtering"
        
        elif strategy_name == 'fuzzy':
            # Stage 3: Fuzzy matching (optionally with prefiltered candidates)
            logger.debug(f"[match][{strategy_name}] Running fuzzy matching strategy...")
            
            # Check if duration_filter was run before this
            candidate_map = candidate_file_ids if 'duration_filter' in enabled_strategies else None
            
            strategy = FuzzyMatchStrategy(
                db, config,
                debug=is_debug,
                candidate_file_ids=candidate_map
            )
            matches, new_matched = strategy.match(tracks, files, matched_track_ids)
            
            # Store matches
            provider = config.get('provider', 'spotify')
            for track_id, file_id, score, method in matches:
                db.add_match(track_id, file_id, score, method, provider=provider)
            
            all_matches.extend(matches)
            matched_track_ids.update(new_matched)
            strategy_stats[strategy_name] = len(matches)
        
        else:
            logger.debug(f"[match][warn] Unknown strategy '{strategy_name}' - skipping")
    
    db.commit()
    
    # Summary (always show, not just debug)
    dur = time.time() - start
    total_matches = len(all_matches)
    match_rate = (total_matches / len(tracks) * 100) if tracks else 0
    
    # Build stats summary
    exact_count = strategy_stats.get('sql_exact', 0)
    album_count = strategy_stats.get('album_match', 0)
    year_count = strategy_stats.get('year_match', 0)
    fuzzy_count = strategy_stats.get('fuzzy', 0)
    
    logger.info(f"[match] Matched {total_matches}/{len(tracks)} tracks ({match_rate:.1f}%) - "
          f"exact={exact_count} album={album_count} year={year_count} fuzzy={fuzzy_count} - {dur:.2f}s")
    
    # Detailed debug info
    if not files:
        logger.debug("[match][warn] No library files present. Did you run 'scan'? "
              "Check library.paths config and that the directory has supported extensions.")
    
    # Show strategy breakdown
    for strategy_name in enabled_strategies:
        stat = strategy_stats.get(strategy_name, 0)
        if stat == "filtering":
            logger.debug(f"[match] Strategy '{strategy_name}': candidate filtering applied")
        else:
            logger.debug(f"[match] Strategy '{strategy_name}': {stat} matches")
        
    # Unmatched diagnostics: show top N sorted by playlist occurrence count
    if tracks and len(matched_track_ids) < len(tracks):
        max_tracks = matching_config.get('show_unmatched_tracks', 50)
        max_albums = matching_config.get('show_unmatched_albums', 20)
        
        unmatched_ids = [t['id'] for t in tracks if t['id'] not in matched_track_ids]
        
        # Get occurrence count for each unmatched track (how many playlists contain it)
        logger.debug(f"[match] Analyzing {len(unmatched_ids)} unmatched tracks for diagnostics...")
        
        # Batch query: get all playlist counts in one query instead of one per track
        occurrence_counts = {}
        if unmatched_ids:
            placeholders = ','.join('?' * len(unmatched_ids))
            count_rows = db.conn.execute(
                f"SELECT track_id, COUNT(DISTINCT playlist_id) as count FROM playlist_tracks "
                f"WHERE track_id IN ({placeholders}) GROUP BY track_id",
                unmatched_ids
            ).fetchall()
            occurrence_counts = {row['track_id']: row['count'] for row in count_rows}
            # Fill in zero counts for tracks not in any playlist
            for track_id in unmatched_ids:
                if track_id not in occurrence_counts:
                    occurrence_counts[track_id] = 0
        
        # Also check if it's a liked track
        liked_ids = set(row['track_id'] for row in db.conn.execute(
            "SELECT track_id FROM liked_tracks WHERE track_id IN ({})".format(
                ','.join('?' * len(unmatched_ids))
            ), unmatched_ids
        ).fetchall())
        
        # Sort by occurrence count (descending), then by artist/name for ties
        sorted_unmatched = sorted(
            unmatched_ids,
            key=lambda tid: (
                -occurrence_counts[tid],  # Negative for descending
                track_by_id.get(tid, {}).get('artist', '').lower(),
                track_by_id.get(tid, {}).get('name', '').lower()
            )
        )
        
        # Show top N tracks (or fewer if less unmatched)
        display_count = min(max_tracks, len(sorted_unmatched))
        total_unmatched = len(sorted_unmatched)
        
        logger.debug(f"{click.style('[unmatched]', fg='red')} Top {display_count} unmatched tracks "
              f"(of {total_unmatched} total, sorted by playlist popularity):")
        
        for track_id in sorted_unmatched[:display_count]:
            track = track_by_id.get(track_id, {})
            count = occurrence_counts[track_id]
            is_liked = track_id in liked_ids
            liked_marker = " ❤️" if is_liked else ""
            
            # Show: count, artist - title, (liked marker)
            logger.debug(f"  [{count:2d} playlist{'s' if count != 1 else ' '}] "
                  f"{track.get('artist', '')} - {track.get('name', '')}{liked_marker}")
        
        if total_unmatched > display_count:
            logger.debug(f"  ... and {total_unmatched - display_count} more unmatched tracks")
        
        # Album analysis: Group unmatched tracks by album and show top N albums
        if max_albums > 0:
            album_stats = {}  # album_key -> {'artist': ..., 'album': ..., 'track_count': ..., 'total_occurrences': ...}
            
            for track_id in unmatched_ids:
                track = track_by_id.get(track_id, {})
                artist = track.get('artist', '')
                album = track.get('album', '')
                
                if not album or album == '':
                    continue  # Skip tracks without album info
                
                # Use artist + album as key (case-insensitive)
                album_key = f"{artist.lower()}|{album.lower()}"
                
                if album_key not in album_stats:
                    album_stats[album_key] = {
                        'artist': artist,
                        'album': album,
                        'track_count': 0,
                        'total_occurrences': 0,
                    }
                
                album_stats[album_key]['track_count'] += 1
                album_stats[album_key]['total_occurrences'] += occurrence_counts[track_id]
            
            # Sort albums by total occurrences (descending), then by track count
            sorted_albums = sorted(
                album_stats.items(),
                key=lambda item: (-item[1]['total_occurrences'], -item[1]['track_count'], item[1]['artist'].lower())
            )
            
            if sorted_albums:
                display_album_count = min(max_albums, len(sorted_albums))
                logger.debug(f"\n{click.style('[unmatched]', fg='red')} Top {display_album_count} missing albums "
                      f"(of {len(sorted_albums)} total, by playlist popularity):")
                
                for _, album_info in sorted_albums[:display_album_count]:
                    artist = album_info['artist']
                    album = album_info['album']
                    track_count = album_info['track_count']
                    total_occ = album_info['total_occurrences']
                    
                    # Show: total occurrences, artist - album, (track count)
                    logger.debug(f"  [{total_occ:2d} occurrences] {artist} - {album} ({track_count} track{'s' if track_count != 1 else ''})")
                
                if len(sorted_albums) > display_album_count:
                    logger.debug(f"  ... and {len(sorted_albums) - display_album_count} more albums")
    
    return total_matches

__all__ = ["match_tracks", "match_and_store"]
