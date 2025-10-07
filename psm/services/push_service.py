from __future__ import annotations
"""Playlist push (experimental).

Supports previewing and (optionally) applying a full replace of a remote
playlist's track order either from:
  * An exported M3U file (file mode)
  * The current database state (ID-only mode)

Safety constraints (MVP):
  * Only supports existing playlists (no creation)
  * Only allows modification if current user owns the playlist
  * Preview by default; --apply required to perform remote writes
  * Full replace semantics (remote order becomes desired order)

Remote operations are implemented for Spotify only (provider abstraction kept
minimal). If desired track count exceeds 100 (Spotify replace limit), we clear
then batch-add in chunks of 100.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Dict, Any, Optional, Tuple
import logging

from ..db import Database, DatabaseInterface
from ..push.m3u_parser import parse_m3u_paths

logger = logging.getLogger(__name__)


@dataclass
class PushPreview:
    playlist_id: str
    playlist_name: str | None
    current_count: int
    new_count: int
    positional_changes: int
    added: int
    removed: int
    unmatched_file_paths: int
    changed: bool
    applied: bool = False


def _map_paths_to_track_ids(db: DatabaseInterface, paths: Sequence[str]) -> Tuple[List[str], int]:
    """Map local file system paths back to playlist track IDs via matches.

    Returns list of track IDs (duplicates preserved to reflect ordering) and
    count of file paths that could not be resolved.
    """
    track_ids: List[str] = []
    unresolved = 0
    # Prepare statement once for efficiency
    cur = db.conn.cursor()
    for p in paths:
        row = cur.execute(
            "SELECT m.track_id FROM library_files lf JOIN matches m ON m.file_id = lf.id WHERE lf.path = ?",
            (p,),
        ).fetchone()
        if row and row[0]:
            track_ids.append(row[0])
        else:
            unresolved += 1
    return track_ids, unresolved


def _desired_track_ids_from_file(db: DatabaseInterface, playlist_id: str, m3u_path: Path) -> Tuple[List[str], int]:
    paths = parse_m3u_paths(m3u_path)
    return _map_paths_to_track_ids(db, paths)


def _desired_track_ids_from_db(db: DatabaseInterface, playlist_id: str) -> List[str]:
    cur = db.conn.execute(
        "SELECT track_id FROM playlist_tracks WHERE playlist_id=? ORDER BY position",
        (playlist_id,),
    )
    return [r[0] for r in cur.fetchall()]


def _diff(current: Sequence[str], desired: Sequence[str]) -> Tuple[int, int, int, bool]:
    common = min(len(current), len(desired))
    positional_changes = sum(1 for i in range(common) if current[i] != desired[i])
    added = max(0, len(desired) - len(current))
    removed = max(0, len(current) - len(desired))
    changed = positional_changes > 0 or added > 0 or removed > 0
    return positional_changes, added, removed, changed


def _remote_playlist_items(client, playlist_id: str) -> List[str]:  # pragma: no cover (thin wrapper)
    items = client.playlist_items(playlist_id, verbose=False)
    ids: List[str] = []
    for it in items:
        track = it.get('track') if isinstance(it, dict) else None
        if track and track.get('id'):
            ids.append(track['id'])
    return ids


def _fetch_playlist_meta(client, db: DatabaseInterface, playlist_id: str) -> Dict[str, Any]:
    # Prefer DB metadata, fallback to API
    row = db.get_playlist_by_id(playlist_id)
    meta: Dict[str, Any] = {}
    if row:
        meta = {k: row[k] for k in row.keys()}
    try:
        detail = client.get_playlist(playlist_id)
        if detail:
            meta.setdefault('name', detail.get('name'))
            owner = detail.get('owner') or {}
            meta.setdefault('owner_id', owner.get('id'))
            meta.setdefault('owner_name', owner.get('display_name'))
    except Exception as e:  # pragma: no cover (network variability)
        logger.debug(f"Could not fetch playlist detail: {e}")
    return meta


def _ensure_owner(meta: Dict[str, Any], db: DatabaseInterface) -> None:
    current_user_id = db.get_meta('current_user_id')
    owner_id = meta.get('owner_id')
    if current_user_id and owner_id and current_user_id != owner_id:
        raise PermissionError(
            f"Refusing to push: playlist owned by '{owner_id}' but current user is '{current_user_id}'"
        )


def _apply_remote_replace(client, playlist_id: str, track_ids: Sequence[str]):  # pragma: no cover (network)
    if hasattr(client, 'replace_playlist_tracks_remote'):
        client.replace_playlist_tracks_remote(playlist_id, list(track_ids))
    else:
        raise RuntimeError('Provider client lacks replace capability')


def push_playlist(
    db: DatabaseInterface,
    playlist_id: str,
    client,
    m3u_path: Path | None = None,
    apply: bool = False,
) -> PushPreview:
    """Preview (and optionally apply) a push.

    Args:
        db: Database instance
        playlist_id: Target playlist ID
        client: Provider client (SpotifyProviderClient / SpotifyClient with write methods)
        m3u_path: Optional path to exported M3U file. If omitted, DB mode is used.
        apply: Execute remote replacement if True
        verbose: Emit detailed diff logging
    """
    meta = _fetch_playlist_meta(client, db, playlist_id)
    _ensure_owner(meta, db)

    if m3u_path:
        desired, unresolved = _desired_track_ids_from_file(db, playlist_id, m3u_path)
    else:
        desired = _desired_track_ids_from_db(db, playlist_id)
        unresolved = 0

    current_remote = _remote_playlist_items(client, playlist_id)
    positional_changes, added, removed, changed = _diff(current_remote, desired)

    preview = PushPreview(
        playlist_id=playlist_id,
        playlist_name=meta.get('name'),
        current_count=len(current_remote),
        new_count=len(desired),
        positional_changes=positional_changes,
        added=added,
        removed=removed,
        unmatched_file_paths=unresolved,
        changed=changed,
        applied=False,
    )

    # Always log a summary (even if not verbose) for visibility
    logger.info(
        f"preview playlist={playlist_id} name='{preview.playlist_name}' current={preview.current_count} new={preview.new_count} positional={positional_changes} added={added} removed={removed} unresolved_paths={unresolved} changed={changed}"
    )
    if changed:
        # Optionally log first few differences for diagnostics
        logger.debug("detailed diff logging not yet implemented (future enhancement)")
    if apply:
        if not changed:
            logger.info('No changes detected; skipping apply')
        else:
            # Enforce capability if advertised
            if hasattr(client, 'capabilities'):
                caps = getattr(client, 'capabilities')
                if not getattr(caps, 'replace_playlist', False):
                    raise RuntimeError('Provider does not advertise replace_playlist capability')
            _apply_remote_replace(client, playlist_id, desired)
            logger.info(f"applied replace playlist={playlist_id} new_count={len(desired)}")
            preview.applied = True
    return preview

__all__ = ["push_playlist", "PushPreview"]
