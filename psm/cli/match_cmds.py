"""Matching engine command."""

from __future__ import annotations
import click
import logging
from pathlib import Path
import time

from .helpers import cli, get_db
from ..services.match_service import run_matching
from ..reporting.generator import write_match_reports, write_index_page
from ..ingest.library import extract_tags, normalize_library_path, partial_hash
from ..utils.normalization import normalize_title_artist
import mutagen
import re

logger = logging.getLogger(__name__)


def _resolve_file_for_match(db, file_id: int | None, file_path: str | None, cfg: dict, ctx: click.Context) -> int:
    """Resolve file ID from either file_id parameter or file_path parameter.

    Args:
        db: Database connection
        file_id: Optional file ID (takes precedence if provided)
        file_path: Optional file path
        cfg: Configuration dict
        ctx: Click context for error handling

    Returns:
        Resolved file ID

    Raises:
        ctx.exit(1) on error
    """
    if file_id:
        # Verify file exists in library
        files = db.get_library_files_by_ids([file_id])
        if not files:
            click.echo(click.style(f"Error: File ID {file_id} not found in library", fg="red"))
            ctx.exit(1)
        click.echo(f"File: {files[0].path}")
        return file_id

    # file_path case
    path = Path(file_path)
    normalized_path = normalize_library_path(path)

    # Check if file already in library
    existing_file = db.get_library_file_by_path(normalized_path)
    if existing_file:
        click.echo(f"File: {existing_file.path} (already in library)")
        return existing_file.id

    # File not in library - ingest it
    return _ingest_file_to_library(db, path, normalized_path, cfg, ctx)


def _ingest_file_to_library(db, path: Path, normalized_path: str, cfg: dict, ctx: click.Context) -> int:
    """Ingest a new file into the library database.

    Args:
        db: Database connection
        path: Original file path
        normalized_path: Normalized file path for database
        cfg: Configuration dict
        ctx: Click context for error handling

    Returns:
        File ID of the ingested file

    Raises:
        ctx.exit(1) on error
    """
    click.echo(f"File not in library, ingesting: {normalized_path}")

    # Get file stats
    try:
        st = path.stat()
    except OSError as e:
        click.echo(click.style(f"Error: Cannot access file: {e}", fg="red"))
        ctx.exit(1)

    # Extract audio metadata
    try:
        audio = mutagen.File(path)
    except Exception as e:
        click.echo(click.style(f"Warning: Could not read audio tags: {e}", fg="yellow"))
        audio = None

    tags = extract_tags(audio)
    title = tags.get("title") or path.stem
    artist = tags.get("artist") or ""
    album = tags.get("album") or ""
    year = _extract_year_from_tags(tags)
    duration = _extract_duration(audio)
    bitrate_kbps = _extract_bitrate(audio)
    ph = partial_hash(path)

    # Build normalized string for matching
    use_year = cfg.get("matching", {}).get("use_year", False)
    nt, na, combo = normalize_title_artist(title, artist)
    if use_year and year is not None:
        combo = f"{combo} {year}"

    # Add to library
    db.add_library_file(
        {
            "path": normalized_path,
            "size": st.st_size,
            "mtime": st.st_mtime,
            "partial_hash": ph,
            "title": title,
            "album": album,
            "artist": artist,
            "duration": duration,
            "normalized": combo,
            "year": year,
            "bitrate_kbps": bitrate_kbps,
        }
    )

    # Retrieve the newly inserted file to get its ID
    existing_file = db.get_library_file_by_path(normalized_path)
    if not existing_file:
        click.echo(click.style("Error: Failed to add file to library", fg="red"))
        ctx.exit(1)

    click.echo(f"File added to library with ID: {existing_file.id}")
    return existing_file.id


def _extract_year_from_tags(tags: dict) -> int | None:
    """Extract year from audio tags."""
    year_raw = tags.get("year") or ""
    if year_raw:
        m = re.search(r"(19|20)\d{2}", str(year_raw))
        if m:
            return int(m.group(0))
    return None


def _extract_duration(audio) -> float | None:
    """Extract duration from audio file info."""
    if audio and getattr(audio, "info", None) and getattr(audio.info, "length", None):
        return float(audio.info.length)
    return None


def _extract_bitrate(audio) -> int | None:
    """Extract bitrate from audio file info."""
    if not audio or not getattr(audio, "info", None):
        return None

    if hasattr(audio.info, "bitrate") and audio.info.bitrate:
        return int(audio.info.bitrate / 1000)

    if hasattr(audio.info, "sample_rate") and hasattr(audio.info, "bits_per_sample"):
        sample_rate = audio.info.sample_rate
        bits_per_sample = audio.info.bits_per_sample
        channels = getattr(audio.info, "channels", 2)
        return int((sample_rate * bits_per_sample * channels) / 1000)

    return None


def _get_tracks_for_propagation(db, track_id: str, provider: str, propagate: bool) -> list[str]:
    """Get list of track IDs to match, including duplicates if propagate is enabled.

    Args:
        db: Database connection
        track_id: Primary track ID
        provider: Provider name
        propagate: Whether to include duplicate tracks

    Returns:
        List of track IDs to match (always includes primary track_id)
    """
    tracks_to_match = [track_id]  # Always match the original track

    if not propagate:
        return tracks_to_match

    duplicates = db.get_duplicate_tracks_by_isrc(track_id, provider)
    if duplicates:
        duplicate_ids = [dup.id for dup in duplicates]
        tracks_to_match.extend(duplicate_ids)
        click.echo("")
        click.echo(
            click.style(
                f"✓ Found {len(duplicates)} duplicate track(s) with same ISRC",
                fg="cyan",
            )
        )
        for dup in duplicates:
            click.echo(f"  - {dup.artist} - {dup.name}")
        click.echo(f"  Total tracks to match: {len(tracks_to_match)}")
    else:
        click.echo("")
        click.echo(
            click.style(
                "ℹ No duplicates found (track has no ISRC or no other tracks share it)",
                fg="yellow",
            )
        )

    return tracks_to_match


@cli.command()
@click.option("--top-tracks", type=int, default=20, help="Number of top unmatched tracks to show")
@click.option("--top-albums", type=int, default=10, help="Number of top unmatched albums to show")
@click.option("--full", is_flag=True, help="Force full re-match of all tracks (default: skip already-matched)")
@click.option("--track-id", type=str, help="Match only a specific track by ID")
@click.pass_context
def match(ctx: click.Context, top_tracks: int, top_albums: int, full: bool, track_id: str | None):
    """Match streaming tracks to local library files (scoring engine).

    Default mode: Smart incremental matching (skips already-matched tracks)
    Use --full to force complete re-match of all tracks
    Use --track-id <id> to match only a specific track

    Automatically generates detailed reports:
    - matched_tracks.csv / .html: All matched tracks with confidence scores
    - unmatched_tracks.csv / .html: All unmatched tracks
    - unmatched_albums.csv / .html: Unmatched albums grouped by popularity
    """
    cfg = ctx.obj

    # Handle single track matching
    if track_id:
        from ..services.match_service import match_changed_tracks

        with get_db(cfg) as db:
            # Get track info for logging
            track = db.get_track_by_id(track_id)

            if track:
                click.echo(click.style(f"=== Matching single track: {track_id} ===", fg="cyan", bold=True))
                click.echo(f"Track: {track.name}")
                click.echo(f"Artist: {track.artist}")
            else:
                click.echo(click.style(f"=== Matching single track: {track_id} ===", fg="cyan", bold=True))
                click.echo(click.style("⚠ Track not found in database", fg="yellow"))
                return

            matched_count = match_changed_tracks(db, cfg, track_ids=[track_id])

            if matched_count > 0:
                click.echo(f"✓ Matched track {track_id}")
            else:
                click.echo("⚠ No match found for track")

        return

    # Print styled header for user experience
    if full:
        click.echo(click.style("=== Matching tracks to library files (full re-match) ===", fg="cyan", bold=True))
    else:
        click.echo(click.style("=== Matching tracks to library files ===", fg="cyan", bold=True))

    # Use short-lived connection; avoid holding DB beyond required scope
    result = None
    with get_db(cfg) as db:
        result = run_matching(
            db,
            config=cfg,
            verbose=False,
            top_unmatched_tracks=top_tracks,
            top_unmatched_albums=top_albums,
            force_full=full,
        )

        # Auto-generate match reports
        if result.matched > 0 or result.unmatched > 0:
            out_dir = Path(cfg["reports"]["directory"])
            write_match_reports(db, out_dir)
            write_index_page(out_dir, db)
            logger.info("")
            logger.info(f"✓ Generated match reports in: {out_dir}")
            logger.info("  Open index.html to navigate all reports")

    # At this point context manager closed the DB ensuring lock release
    if result is not None:
        click.echo(f"Matched {result.matched} tracks")


@cli.command()
@click.option("--track-id", required=True, type=str, help="Spotify track ID to manually match")
@click.option("--file-path", type=click.Path(exists=True), help="Absolute path to the local file to match to")
@click.option("--file-id", type=int, help="Library file ID to match to (alternative to --file-path)")
@click.option(
    "--propagate",
    is_flag=True,
    help="Apply this match to all duplicate tracks with the same ISRC",
)
@click.pass_context
def set_match(ctx: click.Context, track_id: str, file_path: str | None, file_id: int | None, propagate: bool):
    """Manually override the match for a track.

    Set a manual match between a Spotify track and a local file. Manual matches
    are always preferred over automatic matches and are shown with confidence=MANUAL
    in diagnostic output.

    You must specify either --file-path OR --file-id (but not both).

    Use --propagate to apply this match to all tracks with the same ISRC code.
    This is useful when you have the same song on multiple albums or playlists.

    Examples:
        psm set-match --track-id 3n3Ppam7vgaVa1iaRUc9Lp --file-path "C:\\Music\\song.mp3"
        psm set-match --track-id 3n3Ppam7vgaVa1iaRUc9Lp --file-id 12345
        psm set-match --track-id 3n3Ppam7vgaVa1iaRUc9Lp --file-path "C:\\Music\\song.mp3" --propagate
    """
    cfg = ctx.obj

    # Validate options
    if not file_path and not file_id:
        click.echo(click.style("Error: Must specify either --file-path or --file-id", fg="red"))
        ctx.exit(1)

    if file_path and file_id:
        click.echo(click.style("Error: Cannot specify both --file-path and --file-id", fg="red"))
        ctx.exit(1)

    provider = cfg.get("provider", "spotify")

    with get_db(cfg) as db:
        # 1. Validate track exists
        track = db.get_track_by_id(track_id, provider)
        if not track:
            click.echo(click.style(f"Error: Track {track_id} not found in database", fg="red"))
            click.echo("Have you run 'psm pull' to fetch your tracks?")
            ctx.exit(1)

        click.echo(f"Track: {track.artist} - {track.name}")

        # 2. Resolve file ID (from file_id parameter or by ingesting file_path)
        resolved_file_id = _resolve_file_for_match(db, file_id, file_path, cfg, ctx)

        # 3. Get tracks to match (original + duplicates if --propagate)
        tracks_to_match = _get_tracks_for_propagation(db, track_id, provider, propagate)

        # 4. Delete any existing matches for all tracks
        db.delete_matches_by_track_ids(tracks_to_match)

        # 5. Insert manual match(es) with MANUAL confidence
        for tid in tracks_to_match:
            db.add_match(
                track_id=tid,
                file_id=resolved_file_id,
                score=1.00,
                method="score:MANUAL:manual-selected",
                provider=provider,
                confidence="MANUAL",
            )

        # 6. Trigger GUI refresh
        db.set_meta("last_write_epoch", str(time.time()))
        db.set_meta("last_write_source", "manual")
        db.commit()

        click.echo("")
        click.echo(click.style("✓ Manual match created successfully", fg="green", bold=True))
        if len(tracks_to_match) > 1:
            click.echo(click.style(f"✓ Applied to {len(tracks_to_match)} track(s)", fg="green", bold=True))
        click.echo("")
        click.echo("This match will be prioritized over automatic matches.")
        click.echo(f"Run 'psm diagnose {track_id}' to verify.")


@cli.command()
@click.option("--track-id", required=True, type=str, help="Track ID to remove match for")
@click.pass_context
def remove_match(ctx: click.Context, track_id: str):
    """Remove the match for a track (manual or automatic).

    Deletes all matches for the specified track. The track will appear as
    unmatched until you run 'psm match' again to create new automatic matches.

    This is useful for:
    - Removing incorrect manual matches
    - Clearing automatic matches before setting manual ones
    - Resetting tracks to allow re-matching with updated matching rules

    Examples:
        psm remove-match --track-id 3n3Ppam7vgaVa1iaRUc9Lp

    Note: After removing a match, run 'psm match --track-id <id>' to create
    a new automatic match, or use 'psm set-match' for a manual match.
    """
    cfg = ctx.obj
    provider = cfg.get("provider", "spotify")

    with get_db(cfg) as db:
        # 1. Validate track exists
        track = db.get_track_by_id(track_id, provider)
        if not track:
            click.echo(click.style(f"Error: Track {track_id} not found in database", fg="red"))
            click.echo("Have you run 'psm pull' to fetch your tracks?")
            ctx.exit(1)

        click.echo(f"Track: {track.artist} - {track.name}")

        # 2. Check if track has any matches
        match_info = db.get_match_for_track(track_id)

        if not match_info:
            click.echo(click.style("⚠ Track has no existing match", fg="yellow"))
            click.echo("Nothing to remove.")
            return

        # Show what we're removing
        match_file_id = match_info.get("file_id")
        match_confidence = match_info.get("confidence", "AUTOMATIC")
        match_score = match_info.get("score", 0.0)

        files = db.get_library_files_by_ids([match_file_id]) if match_file_id else []
        file_path = files[0].path if files else "<unknown>"

        click.echo(f"Current match: {file_path}")
        click.echo(f"Confidence: {match_confidence}, Score: {match_score:.2f}")
        click.echo("")

        # 3. Delete the match
        db.delete_matches_by_track_ids([track_id])

        # 4. Trigger GUI refresh
        db.set_meta("last_write_epoch", str(time.time()))
        db.set_meta("last_write_source", "manual")
        db.commit()

        click.echo(click.style("✓ Match removed successfully", fg="green", bold=True))
        click.echo("")
        click.echo("Track is now unmatched.")
        click.echo(f"Run 'psm match --track-id {track_id}' to create a new automatic match,")
        click.echo(f"or 'psm set-match --track-id {track_id} --file-path <path>' for manual match.")


__all__ = ["match", "set_match", "remove_match"]
