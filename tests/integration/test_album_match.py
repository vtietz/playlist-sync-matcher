"""Test album-based matching strategy."""
import pytest
from psm.db import Database
from psm.match.strategies.album import AlbumMatchStrategy
from psm.config import load_config


@pytest.fixture
def db_with_albums(tmp_path):
    """Database with library files having different albums."""
    db = Database(tmp_path / "test.db")

    # Same artist+title, different albums
    db.add_library_file({
        'path': "C:/Music/Beatles/Abbey Road/Come Together.mp3",
        'size': 4000000,
        'mtime': 1234567890.0,
        'partial_hash': "hash1",
        'title': "Come Together",
        'album': "Abbey Road",
        'artist': "The Beatles",
        'duration': 259.0,
        'normalized': "come together the beatles",
        'year': 1969,
        'bitrate_kbps': 320
    })

    db.add_library_file({
        'path': "C:/Music/Beatles/Greatest Hits/Come Together.mp3",
        'size': 3500000,
        'mtime': 1234567891.0,
        'partial_hash': "hash2",
        'title': "Come Together",
        'album': "Greatest Hits",
        'artist': "The Beatles",
        'duration': 259.0,
        'normalized': "come together the beatles",
        'year': 2000,
        'bitrate_kbps': 256
    })

    db.add_library_file({
        'path': "C:/Music/Beatles/Live/Come Together.mp3",
        'size': 4200000,
        'mtime': 1234567892.0,
        'partial_hash': "hash3",
        'title': "Come Together",
        'album': "Live at Hollywood Bowl",
        'artist': "The Beatles",
        'duration': 280.0,
        'normalized': "come together the beatles",
        'year': 1977,
        'bitrate_kbps': 320
    })

    # Different song, same album
    db.add_library_file({
        'path': "C:/Music/Beatles/Abbey Road/Here Comes The Sun.mp3",
        'size': 3000000,
        'mtime': 1234567893.0,
        'partial_hash': "hash4",
        'title': "Here Comes the Sun",
        'album': "Abbey Road",
        'artist': "The Beatles",
        'duration': 185.0,
        'normalized': "here comes the sun the beatles",
        'year': 1969,
        'bitrate_kbps': 320
    })

    # File without album
    db.add_library_file({
        'path': "C:/Music/Downloads/Something.mp3",
        'size': 2900000,
        'mtime': 1234567894.0,
        'partial_hash': "hash5",
        'title': "Something",
        'album': None,
        'artist': "The Beatles",
        'duration': 182.0,
        'normalized': "something the beatles",
        'year': None,
        'bitrate_kbps': 192
    })

    db.commit()
    return db


def test_album_match_exact(db_with_albums):
    """Album match finds correct file when album matches."""
    config = load_config()
    strategy = AlbumMatchStrategy(db_with_albums, config, debug=False)

    # Get all files from DB
    files = list(db_with_albums.conn.execute(
        "SELECT id, path, title, artist, album, duration, normalized FROM library_files"
    ))
    files = [dict(row) for row in files]

    # Create Spotify track for Abbey Road version
    tracks = [{
        'id': 'track1',
        'name': 'Come Together',
        'artist': 'The Beatles',
        'album': 'Abbey Road',
        'normalized': 'come together the beatles',
        'duration_ms': 259000
    }]

    matches, matched_ids = strategy.match(tracks, files, set())

    assert len(matches) == 1
    track_id, file_id, score, method = matches[0]
    assert track_id == 'track1'
    assert score == 1.0
    assert method == 'album_match'
    assert 'track1' in matched_ids

    # Verify it matched the correct file
    matched_file = next((f for f in files if f['id'] == file_id), None)
    assert matched_file is not None
    assert "Abbey Road" in matched_file['path']


def test_album_match_distinguishes_versions(db_with_albums):
    """Album match distinguishes between different album versions."""
    config = load_config()
    strategy = AlbumMatchStrategy(db_with_albums, config, debug=False)

    files = list(db_with_albums.conn.execute(
        "SELECT id, path, title, artist, album, duration, normalized FROM library_files"
    ))
    files = [dict(row) for row in files]

    # Test Greatest Hits version
    tracks = [{
        'id': 'track1',
        'name': 'Come Together',
        'artist': 'The Beatles',
        'album': 'Greatest Hits',
        'normalized': 'come together the beatles',
        'duration_ms': 259000
    }]

    matches, _ = strategy.match(tracks, files, set())
    assert len(matches) == 1
    matched_file = next((f for f in files if f['id'] == matches[0][1]), None)
    assert "Greatest Hits" in matched_file['path']

    # Test Live version
    tracks = [{
        'id': 'track2',
        'name': 'Come Together',
        'artist': 'The Beatles',
        'album': 'Live at Hollywood Bowl',
        'normalized': 'come together the beatles',
        'duration_ms': 280000
    }]

    matches, _ = strategy.match(tracks, files, set())
    assert len(matches) == 1
    matched_file = next((f for f in files if f['id'] == matches[0][1]), None)
    assert "Live" in matched_file['path']


def test_album_match_no_match_different_album(db_with_albums):
    """Album match returns empty when album doesn't exist."""
    config = load_config()
    strategy = AlbumMatchStrategy(db_with_albums, config, debug=False)

    files = list(db_with_albums.conn.execute(
        "SELECT id, path, title, artist, album, duration, normalized FROM library_files"
    ))
    files = [dict(row) for row in files]

    tracks = [{
        'id': 'track1',
        'name': 'Come Together',
        'artist': 'The Beatles',
        'album': 'Nonexistent Album',
        'normalized': 'come together the beatles',
        'duration_ms': 259000
    }]

    matches, _ = strategy.match(tracks, files, set())
    assert len(matches) == 0


def test_album_match_skips_already_matched(db_with_albums):
    """Album match skips tracks that are already matched."""
    config = load_config()
    strategy = AlbumMatchStrategy(db_with_albums, config, debug=False)

    files = list(db_with_albums.conn.execute(
        "SELECT id, path, title, artist, album, duration, normalized FROM library_files"
    ))
    files = [dict(row) for row in files]

    tracks = [{
        'id': 'track1',
        'name': 'Come Together',
        'artist': 'The Beatles',
        'album': 'Abbey Road',
        'normalized': 'come together the beatles',
        'duration_ms': 259000
    }]

    # Mark track1 as already matched
    matches, _ = strategy.match(tracks, files, {'track1'})
    assert len(matches) == 0


def test_album_match_missing_album_field(db_with_albums):
    """Album match handles missing album field in track."""
    config = load_config()
    strategy = AlbumMatchStrategy(db_with_albums, config, debug=False)

    files = list(db_with_albums.conn.execute(
        "SELECT id, path, title, artist, album, duration, normalized FROM library_files"
    ))
    files = [dict(row) for row in files]

    # Track without album should be skipped
    tracks = [{
        'id': 'track1',
        'name': 'Something',
        'artist': 'The Beatles',
        'album': None,
        'normalized': 'something the beatles',
        'duration_ms': 182000
    }]

    matches, _ = strategy.match(tracks, files, set())
    assert len(matches) == 0


def test_album_match_normalization(db_with_albums):
    """Album match handles normalization correctly."""
    config = load_config()
    strategy = AlbumMatchStrategy(db_with_albums, config, debug=False)

    files = list(db_with_albums.conn.execute(
        "SELECT id, path, title, artist, album, duration, normalized FROM library_files"
    ))
    files = [dict(row) for row in files]

    # Test with different casing (normalized should still match)
    tracks = [{
        'id': 'track1',
        'name': 'COME TOGETHER',
        'artist': 'THE BEATLES',
        'album': 'ABBEY ROAD',
        'normalized': 'come together the beatles',  # Normalization already done by Spotify ingest
        'duration_ms': 259000
    }]

    matches, _ = strategy.match(tracks, files, set())
    assert len(matches) == 1
    matched_file = next((f for f in files if f['id'] == matches[0][1]), None)
    assert "Abbey Road" in matched_file['path']


def test_album_match_debug_mode(db_with_albums):
    """Album match debug mode doesn't break functionality."""
    config = load_config()
    strategy = AlbumMatchStrategy(db_with_albums, config, debug=True)

    files = list(db_with_albums.conn.execute(
        "SELECT id, path, title, artist, album, duration, normalized FROM library_files"
    ))
    files = [dict(row) for row in files]

    tracks = [{
        'id': 'track1',
        'name': 'Come Together',
        'artist': 'The Beatles',
        'album': 'Abbey Road',
        'normalized': 'come together the beatles',
        'duration_ms': 259000
    }]

    matches, _ = strategy.match(tracks, files, set())
    assert len(matches) == 1
    assert matches[0][2] == 1.0  # score

