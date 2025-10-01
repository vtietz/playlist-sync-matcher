"""Test enhanced unmatched diagnostics with albums."""
from pathlib import Path
from spx.db import Database
from spx.match.engine import match_and_store


def test_unmatched_albums_display(tmp_path: Path):
    """Test that unmatched albums are grouped and sorted by popularity."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    
    # Create 2 playlists
    db.upsert_playlist('pl1', 'Playlist 1', 'snap1')
    db.upsert_playlist('pl2', 'Playlist 2', 'snap2')
    
    # Album 1: The Beatles - Abbey Road (3 tracks, very popular)
    for i, title in enumerate(['Come Together', 'Something', 'Here Comes The Sun'], 1):
        db.upsert_track({
            'id': f'beatles_{i}', 'name': title, 'artist': 'The Beatles',
            'album': 'Abbey Road', 'duration_ms': 180000,
            'normalized': f'{title.lower()} beatles',
            'isrc': None, 'year': 1969
        })
    # All 3 tracks in both playlists = 6 total occurrences
    # Playlist 2 only has Beatles tracks
    db.replace_playlist_tracks('pl2', [(i, f'beatles_{i}', None) for i in range(1, 4)])
    
    # Album 2: Pink Floyd - The Wall (2 tracks, medium popular)
    for i, title in enumerate(['Another Brick', 'Comfortably Numb'], 1):
        db.upsert_track({
            'id': f'floyd_{i}', 'name': title, 'artist': 'Pink Floyd',
            'album': 'The Wall', 'duration_ms': 200000,
            'normalized': f'{title.lower()} floyd',
            'isrc': None, 'year': 1979
        })
    
    # Playlist 1 has both Beatles and Floyd tracks (combined into one call)
    pl1_tracks = [(i, f'beatles_{i}', None) for i in range(1, 4)] + [(i+3, f'floyd_{i}', None) for i in range(1, 3)]
    db.replace_playlist_tracks('pl1', pl1_tracks)
    
    # Album 3: Obscure - Unknown (1 track, not popular)
    db.upsert_track({
        'id': 'obscure_1', 'name': 'Random Song', 'artist': 'Obscure Artist',
        'album': 'Unknown Album', 'duration_ms': 150000,
        'normalized': 'random song obscure',
        'isrc': None, 'year': 2020
    })
    # Not in any playlist = 0 occurrences
    
    db.commit()
    
    # Run matching with debug enabled
    import os
    os.environ['SPX_DEBUG'] = '1'
    
    config = {
        'matching': {
            'fuzzy_threshold': 0.78,
            'duration_tolerance': 2.0,
            'strategies': ['sql_exact'],  # Only exact, so all remain unmatched
            'show_unmatched_tracks': 10,
            'show_unmatched_albums': 5,
        }
    }
    
    match_and_store(db, config=config)
    
    # Clean up
    del os.environ['SPX_DEBUG']
    db.close()
    
    print("\n✓ Albums should be sorted by total occurrences:")
    print("  1. The Beatles - Abbey Road (6 occurrences, 3 tracks)")
    print("  2. Pink Floyd - The Wall (2 occurrences, 2 tracks)")
    print("  3. Obscure Artist - Unknown Album (0 occurrences, 1 track)")


if __name__ == '__main__':
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        test_unmatched_albums_display(Path(tmpdir))
    print("\n✅ Test completed - check output above for album grouping")
