"""Spotify ingestion logic.

Functions for ingesting playlists and liked tracks from Spotify into the database.
Handles normalization, metadata extraction, and incremental updates.

Moved from psm.ingest.spotify to encapsulate all Spotify logic in the provider package.
"""

from __future__ import annotations
import time
import logging
import click
from typing import TYPE_CHECKING

from ...utils.normalization import normalize_title_artist
from ...utils.logging_helpers import format_summary

# Provider identifier for database operations
PROVIDER_NAME = 'spotify'

if TYPE_CHECKING:
    from .client import SpotifyAPIClient

logger = logging.getLogger(__name__)


def extract_year(release_date: str | None) -> int | None:
    """Extract year from Spotify release date string.
    
    Spotify returns dates in various formats: YYYY-MM-DD, YYYY-MM, or YYYY.
    
    Args:
        release_date: Release date string from Spotify API
        
    Returns:
        Year as integer, or None if extraction fails
    """
    if not release_date:
        return None
    # Spotify can return YYYY-MM-DD, YYYY-MM, or YYYY
    if len(release_date) >= 4 and release_date[:4].isdigit():
        return int(release_date[:4])
    return None


def ingest_playlists(db, client: 'SpotifyAPIClient', use_year: bool = False, force_refresh: bool = False):
    """Ingest playlists from Spotify API into database.
    
    Handles incremental updates using snapshot IDs. Only re-processes playlists
    that have changed since last sync, unless force_refresh is True.
    
    Args:
        db: Database instance
        client: SpotifyAPIClient instance
        use_year: Include year in normalization (from config matching.use_year)
        force_refresh: Force refresh all tracks even if playlists unchanged (populates new fields)
        
    Returns:
        set: Set of track IDs that were added or updated
    """
    click.echo(click.style("=== Pulling playlists from Spotify ===", fg='cyan', bold=True))
    if force_refresh:
        click.echo(click.style("🔄 Force refresh mode: Re-processing all tracks to populate new fields", fg='blue'))
    t0 = time.time()
    new_playlists = 0
    updated_playlists = 0
    unchanged_playlists = 0
    changed_track_ids = set()  # Track IDs that were upserted
    
    # Get and store current user ID for owner comparison
    try:
        user_profile = client.current_user_profile()
        user_id = user_profile.get('id')
        if user_id:
            current_stored_id = db.get_meta('current_user_id')
            if current_stored_id != user_id:
                db.set_meta('current_user_id', user_id)
                db.commit()
    except Exception as e:
        logger.error(f"Could not fetch current user profile: {e}")
    
    for pl in client.current_user_playlists():
        pid = pl['id']
        name = pl.get('name')
        snapshot_id = pl.get('snapshot_id')
        # Extract owner information
        owner = pl.get('owner', {})
        owner_id = owner.get('id') if owner else None
        owner_name = owner.get('display_name') if owner else None
        
        # Check if this is a new playlist or existing
        existing_playlist = db.conn.execute(
            "SELECT snapshot_id FROM playlists WHERE id = ?", (pid,)
        ).fetchone()
        
        if not force_refresh and not db.playlist_snapshot_changed(pid, snapshot_id, provider=PROVIDER_NAME):
            unchanged_playlists += 1
            # Still upsert playlist metadata (including owner fields) even when skipped
            # This ensures new schema fields get populated without reprocessing tracks
            db.upsert_playlist(pid, name, snapshot_id, owner_id, owner_name, provider=PROVIDER_NAME)
            track_count = pl.get('tracks', {}).get('total', 0) if isinstance(pl.get('tracks'), dict) else 0
            logger.info(f"{click.style('[skip]', fg='yellow')} {name} ({track_count} tracks) - unchanged snapshot")
            continue
        
        tracks = client.playlist_items(pid)
        simplified = []
        for idx, item in enumerate(tracks):
            track = item.get('track') or {}
            if not track:
                continue
            t_id = track.get('id')
            if not t_id:
                continue
            
            # Extract artist information
            artists = track.get('artists', [])
            artist_names = ', '.join(a['name'] for a in artists if a.get('name'))
            # Get the primary artist ID (first artist)
            artist_id = artists[0].get('id') if artists else None
            
            # Extract album information
            album_data = track.get('album') or {}
            album_name = album_data.get('name')
            album_id = album_data.get('id')
            
            # normalization
            nt, na, combo = normalize_title_artist(track.get('name') or '', artist_names)
            year = extract_year(album_data.get('release_date'))
            if use_year and year:
                combo = f"{combo} {year}"
            simplified.append((idx, t_id, item.get('added_at')))
            db.upsert_track({
                'id': t_id,
                'name': track.get('name'),
                'album': album_name,
                'artist': artist_names,
                'album_id': album_id,
                'artist_id': artist_id,
                'isrc': ((track.get('external_ids') or {}).get('isrc')),
                'duration_ms': track.get('duration_ms'),
                'normalized': combo,
                'year': year,
            }, provider=PROVIDER_NAME)
            changed_track_ids.add(t_id)  # Track this ID as changed
        db.upsert_playlist(pid, name, snapshot_id, owner_id, owner_name, provider=PROVIDER_NAME)
        db.replace_playlist_tracks(pid, simplified, provider=PROVIDER_NAME)
        db.commit()
        
        # Determine if new or updated
        if existing_playlist and not force_refresh:
            updated_playlists += 1
            action = "updated"
            color = "blue"
        elif existing_playlist and force_refresh:
            updated_playlists += 1
            action = "refreshed"
            color = "magenta"
        else:
            new_playlists += 1
            action = "new"
            color = "green"
        
        logger.info(f"{click.style(f'[{action}]', fg=color)} {name} ({len(simplified)} tracks) | owner={owner_name or owner_id or 'unknown'}")
    
    total_processed = new_playlists + updated_playlists
    t1 = time.time()
    summary = format_summary(
        new=new_playlists,
        updated=updated_playlists,
        unchanged=unchanged_playlists,
        duration_seconds=t1 - t0,
        item_name="Playlists"
    )
    logger.info(summary)
    
    return changed_track_ids


def ingest_liked(db, client: 'SpotifyAPIClient', use_year: bool = False):
    """Ingest liked tracks from Spotify API into database.
    
    Handles incremental updates by tracking the last added_at timestamp.
    Assumes Spotify returns liked tracks in reverse chronological order.
    
    Args:
        db: Database instance
        client: SpotifyAPIClient instance
        use_year: Include year in normalization (from config matching.use_year)
        
    Returns:
        set: Set of track IDs that were added or updated
    """
    click.echo(click.style("=== Pulling liked tracks ===", fg='cyan', bold=True))
    last_added_at = db.get_meta('liked_last_added_at')
    newest_seen = last_added_at
    t0 = time.time()
    new_tracks = 0
    updated_tracks = 0
    changed_track_ids = set()  # Track IDs that were upserted
    
    for item in client.liked_tracks():
        added_at = item.get('added_at')
        track = item.get('track') or {}
        if not track:
            continue
        if last_added_at and added_at <= last_added_at:
            # already ingested due to sorting newest-first assumption
            logger.info(f"Reached previously ingested liked track boundary at {added_at}; stopping.")
            break
        t_id = track.get('id')
        if not t_id:
            continue
        
        # Check if track already exists in database
        existing_track = db.conn.execute(
            "SELECT id FROM tracks WHERE id = ?", (t_id,)
        ).fetchone()
        
        # Extract artist information
        artists = track.get('artists', [])
        artist_names = ', '.join(a['name'] for a in artists if a.get('name'))
        # Get the primary artist ID (first artist)
        artist_id = artists[0].get('id') if artists else None
        
        # Extract album information
        album_data = track.get('album') or {}
        album_name = album_data.get('name')
        album_id = album_data.get('id')
        
        nt, na, combo = normalize_title_artist(track.get('name') or '', artist_names)
        year = extract_year(album_data.get('release_date'))
        if use_year and year:
            combo = f"{combo} {year}"
        db.upsert_track({
            'id': t_id,
            'name': track.get('name'),
            'album': album_name,
            'artist': artist_names,
            'album_id': album_id,
            'artist_id': artist_id,
            'isrc': ((track.get('external_ids') or {}).get('isrc')),
            'duration_ms': track.get('duration_ms'),
            'normalized': combo,
            'year': year,
        }, provider=PROVIDER_NAME)
        db.upsert_liked(t_id, added_at, provider=PROVIDER_NAME)
        changed_track_ids.add(t_id)  # Track this ID as changed
        
        # Determine if new or updated
        if existing_track:
            updated_tracks += 1
            action = "updated"
            color = "blue"
        else:
            new_tracks += 1
            action = "new"
            color = "green"
        
        track_name = track.get('name', 'Unknown')
        logger.debug(f"{click.style(f'[{action}]', fg=color)} ❤️  {track_name} | {artist_names}")
        
        if (not newest_seen) or added_at > newest_seen:
            newest_seen = added_at
    
    total_ingested = new_tracks + updated_tracks
    t1 = time.time()
    summary = format_summary(
        new=new_tracks,
        updated=updated_tracks,
        unchanged=0,  # Liked tracks don't track unchanged
        duration_seconds=t1 - t0,
        item_name="Liked tracks"
    )
    
    # Add newest timestamp info if available
    if newest_seen:
        summary += f" (newest={newest_seen})"
    
    logger.info(summary)
    if newest_seen and newest_seen != last_added_at:
        db.set_meta('liked_last_added_at', newest_seen)
    db.commit()
    
    return changed_track_ids


__all__ = ["extract_year", "ingest_playlists", "ingest_liked"]
