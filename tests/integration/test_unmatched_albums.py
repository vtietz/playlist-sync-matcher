"""Basic unmatched album scenario using scoring engine.

Legacy diagnostic grouping by album popularity has been removed with the
strategy pipeline. This test now ensures no matches occur (no library
files) and tracks with album metadata do not cause errors.
"""
from pathlib import Path
from psm.db import Database
from psm.services.match_service import run_matching


def test_unmatched_albums_display(tmp_path: Path):
    db_path = tmp_path / "test.db"
    db = Database(db_path)

    # Create playlists
    db.upsert_playlist('pl1', 'Playlist 1', 'snap1', provider='spotify')
    db.upsert_playlist('pl2', 'Playlist 2', 'snap2', provider='spotify')

    # Beatles album (3 tracks)
    for i, title in enumerate(['Come Together', 'Something', 'Here Comes The Sun'], 1):
        db.upsert_track({
            'id': f'beatles_{i}', 'name': title, 'artist': 'The Beatles',
            'album': 'Abbey Road', 'duration_ms': 180000,
            'normalized': f'{title.lower()} beatles',
            'isrc': None, 'year': 1969
        }, provider='spotify')
    db.replace_playlist_tracks('pl2', [(i, f'beatles_{i}', None) for i in range(1, 4)], provider='spotify')

    # Pink Floyd album (2 tracks)
    for i, title in enumerate(['Another Brick', 'Comfortably Numb'], 1):
        db.upsert_track({
            'id': f'floyd_{i}', 'name': title, 'artist': 'Pink Floyd',
            'album': 'The Wall', 'duration_ms': 200000,
            'normalized': f'{title.lower()} floyd',
            'isrc': None, 'year': 1979
        }, provider='spotify')

    pl1_tracks = [(i, f'beatles_{i}', None) for i in range(1, 4)] + [(i+3, f'floyd_{i}', None) for i in range(1, 3)]
    db.replace_playlist_tracks('pl1', pl1_tracks, provider='spotify')

    # Obscure album (1 track, not in any playlist)
    db.upsert_track({
        'id': 'obscure_1', 'name': 'Random Song', 'artist': 'Obscure Artist',
        'album': 'Unknown Album', 'duration_ms': 150000,
        'normalized': 'random song obscure',
        'isrc': None, 'year': 2020
    }, provider='spotify')
    db.commit()

    result = run_matching(db, config={})
    assert result.matched == 0
    assert result.unmatched == 6  # 6 Spotify tracks with no library files to match

    db.close()
    print("\n✓ Unmatched album scenario executed (no library files)")


if __name__ == '__main__':
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        test_unmatched_albums_display(Path(tmpdir))
    print("\n✅ Test completed - check output above for album grouping")
