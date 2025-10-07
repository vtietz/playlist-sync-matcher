"""Album completeness report generator."""

import csv
from pathlib import Path
from typing import Any, Iterable

from ...db import Database


def write_album_completeness_report(db: Database, out_dir: Path) -> Path:
    """Write album completeness report to CSV.
    
    Args:
        db: Database instance
        out_dir: Output directory for reports
    
    Returns:
        Path to generated CSV file
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "album_completeness.csv"
    
    rows = list(_compute_album_completeness(db))
    
    # Sort: status priority (MISSING, PARTIAL, COMPLETE) then artist/album
    status_order = {'MISSING': 0, 'PARTIAL': 1, 'COMPLETE': 2}
    rows.sort(key=lambda r: (status_order.get(r['status'], 99), r['artist'] or '', r['album'] or ''))
    
    with path.open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(["artist", "album", "total", "matched", "missing", "percent_complete", "status"])
        for r in rows:
            w.writerow([
                r['artist'], r['album'], r['total'], r['matched'],
                r['missing'], r['percent_complete'], r['status']
            ])
    
    return path


def _compute_album_completeness(db: Database) -> Iterable[dict[str, Any]]:
    """Compute album completeness statistics.
    
    Yields stats per (artist, album): total_spotify_tracks, matched_local,
    missing_count, percent_complete, status.
    """
    # Gather all Spotify tracks that have album & artist
    album_rows = db.conn.execute(
        """
        SELECT artist, album, COUNT(*) as total
        FROM tracks
        WHERE album IS NOT NULL AND artist IS NOT NULL
        GROUP BY artist, album
        """
    ).fetchall()
    
    # Pre-compute matched track_ids
    matched_rows = db.conn.execute("SELECT DISTINCT track_id FROM matches").fetchall()
    matched_set = {r['track_id'] for r in matched_rows}
    
    for row in album_rows:
        artist = row['artist']
        album = row['album']
        total = row['total']
        
        # Count matched in this album
        matched_in_album = db.conn.execute(
            "SELECT COUNT(*) FROM tracks WHERE artist=? AND album=? AND id IN (SELECT track_id FROM matches)",
            (artist, album),
        ).fetchone()[0]
        
        missing = total - matched_in_album
        percent = (matched_in_album / total) * 100.0 if total else 0.0
        
        if matched_in_album == 0:
            status = 'MISSING'
        elif missing == 0:
            status = 'COMPLETE'
        else:
            status = 'PARTIAL'
        
        yield {
            'artist': artist,
            'album': album,
            'total': total,
            'matched': matched_in_album,
            'missing': missing,
            'percent_complete': round(percent, 2),
            'status': status,
        }
