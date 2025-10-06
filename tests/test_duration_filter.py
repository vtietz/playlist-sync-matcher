"""Test duration-based candidate filtering."""
from pathlib import Path
from psm.db import Database
from psm.match.strategies.duration_filter import DurationFilterStrategy


def test_duration_filter_reduces_candidates(tmp_path: Path):
    """Test that duration filtering reduces candidate set significantly."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    
    # Add tracks with specific durations
    db.upsert_track({
        'id': 't1', 'name': 'Song One', 'artist': 'Artist A', 
        'duration_ms': 180000,  # 3 minutes (180 seconds)
        'normalized': 'song one artist a', 'album': 'Album', 'isrc': None
    })
    db.upsert_track({
        'id': 't2', 'name': 'Song Two', 'artist': 'Artist B',
        'duration_ms': 240000,  # 4 minutes (240 seconds)
        'normalized': 'song two artist b', 'album': 'Album', 'isrc': None
    })
    db.commit()
    
    # Add library files with various durations
    db.add_library_file({
        'path': '/music/file1.mp3', 'size': 1000, 'mtime': 1.0,
        'partial_hash': 'h1', 'title': 'File One', 'artist': 'Artist A',
        'duration': 181.0,  # Close to t1 (within 2s tolerance)
        'normalized': 'file one artist a', 'album': 'Album', 'year': None
    })
    db.add_library_file({
        'path': '/music/file2.mp3', 'size': 1000, 'mtime': 1.0,
        'partial_hash': 'h2', 'title': 'File Two', 'artist': 'Artist B',
        'duration': 60.0,  # Very short, should not match either track
        'normalized': 'file two artist b', 'album': 'Album', 'year': None
    })
    db.add_library_file({
        'path': '/music/file3.mp3', 'size': 1000, 'mtime': 1.0,
        'partial_hash': 'h3', 'title': 'File Three', 'artist': 'Artist C',
        'duration': 239.5,  # Close to t2 (within 2s tolerance)
        'normalized': 'file three artist c', 'album': 'Album', 'year': None
    })
    db.add_library_file({
        'path': '/music/file4.mp3', 'size': 1000, 'mtime': 1.0,
        'partial_hash': 'h4', 'title': 'File Four', 'artist': 'Artist D',
        'duration': 600.0,  # Very long, should not match either track
        'normalized': 'file four artist d', 'album': 'Album', 'year': None
    })
    db.commit()
    
    # Fetch tracks and files
    tracks = [dict(row) for row in db.conn.execute("SELECT id, name, artist, duration_ms, normalized FROM tracks").fetchall()]
    files = [dict(row) for row in db.conn.execute("SELECT id, path, duration, normalized FROM library_files").fetchall()]
    
    # Apply duration filter with 2-second tolerance
    filter_strategy = DurationFilterStrategy(tolerance_seconds=2.0, debug=False)
    candidates = filter_strategy.filter_candidates(tracks, files, set())
    
    # Check that t1 (180s) only matches file1 (181s)
    assert 't1' in candidates
    t1_candidates = candidates['t1']
    assert len(t1_candidates) == 1  # Should filter out 3 of 4 files
    # Find file1's ID
    file1_id = next(f['id'] for f in files if f['path'] == '/music/file1.mp3')
    assert file1_id in t1_candidates
    
    # Check that t2 (240s) only matches file3 (239.5s)
    assert 't2' in candidates
    t2_candidates = candidates['t2']
    assert len(t2_candidates) == 1  # Should filter out 3 of 4 files
    file3_id = next(f['id'] for f in files if f['path'] == '/music/file3.mp3')
    assert file3_id in t2_candidates
    
    db.close()
    print(f"✓ Duration filter correctly reduced candidates from {len(files)} to 1 per track")


def test_duration_filter_handles_missing_durations(tmp_path: Path):
    """Test that tracks/files without duration are handled gracefully."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    
    # Track without duration
    db.upsert_track({
        'id': 't1', 'name': 'Song', 'artist': 'Artist',
        'duration_ms': None,  # No duration
        'normalized': 'song artist', 'album': 'Album', 'isrc': None
    })
    db.commit()
    
    # Files with and without duration
    db.add_library_file({
        'path': '/music/file1.mp3', 'size': 1000, 'mtime': 1.0,
        'partial_hash': 'h1', 'title': 'File One', 'artist': 'Artist',
        'duration': 180.0,
        'normalized': 'file one', 'album': 'Album', 'year': None
    })
    db.add_library_file({
        'path': '/music/file2.mp3', 'size': 1000, 'mtime': 1.0,
        'partial_hash': 'h2', 'title': 'File Two', 'artist': 'Artist',
        'duration': None,  # No duration
        'normalized': 'file two', 'album': 'Album', 'year': None
    })
    db.commit()
    
    tracks = [dict(row) for row in db.conn.execute("SELECT id, name, artist, duration_ms, normalized FROM tracks").fetchall()]
    files = [dict(row) for row in db.conn.execute("SELECT id, path, duration, normalized FROM library_files").fetchall()]
    
    filter_strategy = DurationFilterStrategy(tolerance_seconds=2.0, debug=False)
    candidates = filter_strategy.filter_candidates(tracks, files, set())
    
    # Track without duration should match all files
    assert 't1' in candidates
    assert len(candidates['t1']) == len(files)
    
    db.close()
    print("✓ Duration filter handles missing durations correctly")


def test_duration_filter_skips_already_matched(tmp_path: Path):
    """Test that already matched tracks are skipped."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    
    # Add two tracks
    db.upsert_track({
        'id': 't1', 'name': 'Song One', 'artist': 'Artist A',
        'duration_ms': 180000, 'normalized': 'song one', 'album': 'Album', 'isrc': None
    })
    db.upsert_track({
        'id': 't2', 'name': 'Song Two', 'artist': 'Artist B',
        'duration_ms': 240000, 'normalized': 'song two', 'album': 'Album', 'isrc': None
    })
    db.commit()
    
    # Add a file
    db.add_library_file({
        'path': '/music/file1.mp3', 'size': 1000, 'mtime': 1.0,
        'partial_hash': 'h1', 'title': 'File', 'artist': 'Artist',
        'duration': 181.0, 'normalized': 'file', 'album': 'Album', 'year': None
    })
    db.commit()
    
    tracks = [dict(row) for row in db.conn.execute("SELECT id, name, artist, duration_ms, normalized FROM tracks").fetchall()]
    files = [dict(row) for row in db.conn.execute("SELECT id, path, duration, normalized FROM library_files").fetchall()]
    
    # Mark t1 as already matched
    already_matched = {'t1'}
    
    filter_strategy = DurationFilterStrategy(tolerance_seconds=2.0, debug=False)
    candidates = filter_strategy.filter_candidates(tracks, files, already_matched)
    
    # t1 should not be in candidates (already matched)
    assert 't1' not in candidates
    # t2 should be in candidates
    assert 't2' in candidates
    
    db.close()
    print("✓ Duration filter correctly skips already matched tracks")


if __name__ == '__main__':
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        test_duration_filter_reduces_candidates(Path(tmpdir))
        test_duration_filter_handles_missing_durations(Path(tmpdir))
        test_duration_filter_skips_already_matched(Path(tmpdir))
    print("\n✅ All duration filter tests passed!")
