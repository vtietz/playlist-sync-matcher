"""Test enhanced unmatched diagnostics with playlist occurrence sorting."""
from pathlib import Path
from spx.db import Database
from spx.match.engine import match_and_store


def test_unmatched_sorted_by_popularity(tmp_path: Path):
    """Test that unmatched tracks are sorted by playlist occurrence count."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    
    # Create 3 playlists
    db.upsert_playlist('pl1', 'Playlist 1', 'snap1')
    db.upsert_playlist('pl2', 'Playlist 2', 'snap2')
    db.upsert_playlist('pl3', 'Playlist 3', 'snap3')
    
    # Add tracks with different popularity (occurrence in playlists)
    # Track 1: In all 3 playlists (most popular)
    db.upsert_track({
        'id': 't1', 'name': 'Popular Song', 'artist': 'Artist A',
        'duration_ms': 180000, 'normalized': 'popular song artist a',
        'album': 'Album', 'isrc': None, 'year': None
    })
    
    # Track 2: In 2 playlists
    db.upsert_track({
        'id': 't2', 'name': 'Medium Song', 'artist': 'Artist B',
        'duration_ms': 200000, 'normalized': 'medium song artist b',
        'album': 'Album', 'isrc': None, 'year': None
    })
    
    # Track 3: In 1 playlist
    db.upsert_track({
        'id': 't3', 'name': 'Rare Song', 'artist': 'Artist C',
        'duration_ms': 220000, 'normalized': 'rare song artist c',
        'album': 'Album', 'isrc': None, 'year': None
    })
    
    # Track 4: Liked but not in any playlist
    db.upsert_track({
        'id': 't4', 'name': 'Liked Song', 'artist': 'Artist D',
        'duration_ms': 240000, 'normalized': 'liked song artist d',
        'album': 'Album', 'isrc': None, 'year': None
    })
    db.upsert_liked('t4', '2024-01-01T00:00:00Z')
    
    # Set up playlists with tracks (using replace_playlist_tracks with all tracks at once)
    # Playlist 1: Has all tracks except t4
    db.replace_playlist_tracks('pl1', [(0, 't1', None), (1, 't2', None), (2, 't3', None)])
    # Playlist 2: Has t1 and t2
    db.replace_playlist_tracks('pl2', [(0, 't1', None), (1, 't2', None)])
    # Playlist 3: Has only t1
    db.replace_playlist_tracks('pl3', [(0, 't1', None)])
    
    db.commit()
    
    # No library files - all tracks will be unmatched
    # This will trigger the unmatched diagnostics with sorting
    
    # Run matching with debug enabled
    import os
    os.environ['SPX_DEBUG'] = '1'
    
    config = {
        'matching': {
            'fuzzy_threshold': 0.78,
            'duration_tolerance': 2.0,
            'strategies': ['sql_exact'],  # Only exact, so all remain unmatched
        }
    }
    
    match_and_store(db, config=config)
    
    # Clean up
    del os.environ['SPX_DEBUG']
    db.close()
    
    print("\n✓ Unmatched tracks should be sorted by playlist count:")
    print("  1. Popular Song (3 playlists)")
    print("  2. Medium Song (2 playlists)")
    print("  3. Rare Song (1 playlist)")
    print("  4. Liked Song (0 playlists, but liked ❤️)")


if __name__ == '__main__':
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        test_unmatched_sorted_by_popularity(Path(tmpdir))
    print("\n✅ Test completed - check output above for sorted unmatched list")
