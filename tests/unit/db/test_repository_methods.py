"""Unit tests for typed repository methods.

Tests the new repository layer methods that return typed dataclass objects
instead of raw sqlite3.Row objects, ensuring proper encapsulation of SQL queries.
"""
from __future__ import annotations
import pytest
from psm.db import Database, TrackRow, LibraryFileRow, MatchRow, PlaylistRow
from pathlib import Path


@pytest.fixture
def db(tmp_path: Path):
    """Create an in-memory test database."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    yield db
    db.close()


class TestTrackRepository:
    """Test track-related repository methods."""
    
    def test_get_all_tracks_empty(self, db: Database):
        """Test get_all_tracks with no tracks."""
        tracks = db.get_all_tracks(provider='spotify')
        assert tracks == []
    
    def test_get_all_tracks_returns_track_rows(self, db: Database):
        """Test get_all_tracks returns TrackRow objects."""
        # Add some tracks
        db.upsert_track({
            'id': 't1',
            'name': 'Song 1',
            'artist': 'Artist A',
            'album': 'Album X',
            'year': 2020,
            'isrc': 'ISRC1',
            'duration_ms': 180000,
            'normalized': 'song 1 artist a',
        }, provider='spotify')
        
        db.upsert_track({
            'id': 't2',
            'name': 'Song 2',
            'artist': 'Artist B',
            'album': 'Album Y',
            'year': 2021,
            'isrc': 'ISRC2',
            'duration_ms': 200000,
            'normalized': 'song 2 artist b',
        }, provider='spotify')
        
        db.commit()
        
        tracks = db.get_all_tracks(provider='spotify')
        
        assert len(tracks) == 2
        assert all(isinstance(t, TrackRow) for t in tracks)
        assert tracks[0].id == 't1'
        assert tracks[0].name == 'Song 1'
        assert tracks[0].artist == 'Artist A'
        assert tracks[0].provider == 'spotify'
        assert tracks[1].id == 't2'
    
    def test_get_tracks_by_ids(self, db: Database):
        """Test get_tracks_by_ids returns specific tracks."""
        # Add tracks
        for i in range(5):
            db.upsert_track({
                'id': f't{i}',
                'name': f'Song {i}',
                'artist': 'Artist',
                'album': 'Album',
                'year': 2020,
                'isrc': None,
                'duration_ms': 180000,
                'normalized': f'song {i} artist',
            }, provider='spotify')
        
        db.commit()
        
        # Get specific tracks
        tracks = db.get_tracks_by_ids(['t1', 't3'], provider='spotify')
        
        assert len(tracks) == 2
        track_ids = {t.id for t in tracks}
        assert track_ids == {'t1', 't3'}
    
    def test_get_tracks_by_ids_empty_list(self, db: Database):
        """Test get_tracks_by_ids with empty list."""
        tracks = db.get_tracks_by_ids([], provider='spotify')
        assert tracks == []
    
    def test_get_unmatched_tracks(self, db: Database):
        """Test get_unmatched_tracks returns only tracks without matches."""
        # Add tracks
        db.upsert_track({'id': 't1', 'name': 'Song 1', 'artist': 'A', 'album': 'X', 
                        'year': 2020, 'isrc': None, 'duration_ms': 180000, 'normalized': 's1'}, 
                       provider='spotify')
        db.upsert_track({'id': 't2', 'name': 'Song 2', 'artist': 'B', 'album': 'Y',
                        'year': 2021, 'isrc': None, 'duration_ms': 200000, 'normalized': 's2'}, 
                       provider='spotify')
        
        # Add a library file
        db.add_library_file({'path': '/music/song.mp3', 'title': 'Song 1', 'artist': 'A',
                            'album': 'X', 'year': 2020, 'duration': 180.0, 'normalized': 's1',
                            'size': 1000, 'mtime': 0.0, 'partial_hash': 'abc'})
        
        # Match only t1
        db.add_match('t1', 1, 0.95, 'score:HIGH:manual', provider='spotify')
        db.commit()
        
        # Get unmatched
        unmatched = db.get_unmatched_tracks(provider='spotify')
        
        assert len(unmatched) == 1
        assert unmatched[0].id == 't2'
        assert isinstance(unmatched[0], TrackRow)


class TestLibraryFileRepository:
    """Test library file repository methods."""
    
    def test_get_all_library_files_empty(self, db: Database):
        """Test get_all_library_files with no files."""
        files = db.get_all_library_files()
        assert files == []
    
    def test_get_all_library_files_returns_file_rows(self, db: Database):
        """Test get_all_library_files returns LibraryFileRow objects."""
        db.add_library_file({
            'path': '/music/song1.mp3',
            'title': 'Song 1',
            'artist': 'Artist A',
            'album': 'Album X',
            'year': 2020,
            'duration': 180.0,
            'normalized': 'song 1 artist a',
            'size': 1000,
            'mtime': 123.45,
            'partial_hash': 'abc',
            'bitrate_kbps': 320,
        })
        
        db.add_library_file({
            'path': '/music/song2.mp3',
            'title': 'Song 2',
            'artist': 'Artist B',
            'album': 'Album Y',
            'year': 2021,
            'duration': 200.0,
            'normalized': 'song 2 artist b',
            'size': 2000,
            'mtime': 456.78,
            'partial_hash': 'def',
            'bitrate_kbps': 256,
        })
        
        db.commit()
        
        files = db.get_all_library_files()
        
        assert len(files) == 2
        assert all(isinstance(f, LibraryFileRow) for f in files)
        assert files[0].id == 1
        assert files[0].path == '/music/song1.mp3'
        assert files[0].title == 'Song 1'
        assert files[0].bitrate_kbps == 320
        assert files[1].id == 2
    
    def test_get_library_files_by_ids(self, db: Database):
        """Test get_library_files_by_ids returns specific files."""
        for i in range(5):
            db.add_library_file({
                'path': f'/music/song{i}.mp3',
                'title': f'Song {i}',
                'artist': 'Artist',
                'album': 'Album',
                'year': 2020,
                'duration': 180.0,
                'normalized': f'song {i}',
                'size': 1000,
                'mtime': 0.0,
                'partial_hash': f'hash{i}',
            })
        
        db.commit()
        
        # Get specific files
        files = db.get_library_files_by_ids([2, 4])
        
        assert len(files) == 2
        file_ids = {f.id for f in files}
        assert file_ids == {2, 4}
    
    def test_get_library_files_by_ids_empty_list(self, db: Database):
        """Test get_library_files_by_ids with empty list."""
        files = db.get_library_files_by_ids([])
        assert files == []
    
    def test_get_unmatched_library_files(self, db: Database):
        """Test get_unmatched_library_files returns only files without matches."""
        # Add files
        db.add_library_file({'path': '/music/f1.mp3', 'title': 'F1', 'artist': 'A', 'album': 'X',
                            'year': 2020, 'duration': 180.0, 'normalized': 'f1',
                            'size': 1000, 'mtime': 0.0, 'partial_hash': 'a'})
        db.add_library_file({'path': '/music/f2.mp3', 'title': 'F2', 'artist': 'B', 'album': 'Y',
                            'year': 2021, 'duration': 200.0, 'normalized': 'f2',
                            'size': 2000, 'mtime': 0.0, 'partial_hash': 'b'})
        
        # Add a track
        db.upsert_track({'id': 't1', 'name': 'Track', 'artist': 'A', 'album': 'X',
                        'year': 2020, 'isrc': None, 'duration_ms': 180000, 'normalized': 'f1'},
                       provider='spotify')
        
        # Match only file 1
        db.add_match('t1', 1, 0.95, 'score:HIGH:manual', provider='spotify')
        db.commit()
        
        # Get unmatched
        unmatched = db.get_unmatched_library_files()
        
        assert len(unmatched) == 1
        assert unmatched[0].id == 2
        assert isinstance(unmatched[0], LibraryFileRow)


class TestMatchRepository:
    """Test match-related repository methods."""
    
    def test_delete_matches_by_track_ids(self, db: Database):
        """Test delete_matches_by_track_ids removes matches for specific tracks."""
        # Setup data
        db.upsert_track({'id': 't1', 'name': 'Song 1', 'artist': 'A', 'album': 'X',
                        'year': 2020, 'isrc': None, 'duration_ms': 180000, 'normalized': 's1'},
                       provider='spotify')
        db.upsert_track({'id': 't2', 'name': 'Song 2', 'artist': 'B', 'album': 'Y',
                        'year': 2021, 'isrc': None, 'duration_ms': 200000, 'normalized': 's2'},
                       provider='spotify')
        
        db.add_library_file({'path': '/f1.mp3', 'title': 'F1', 'artist': 'A', 'album': 'X',
                            'year': 2020, 'duration': 180.0, 'normalized': 's1',
                            'size': 1000, 'mtime': 0.0, 'partial_hash': 'a'})
        db.add_library_file({'path': '/f2.mp3', 'title': 'F2', 'artist': 'B', 'album': 'Y',
                            'year': 2021, 'duration': 200.0, 'normalized': 's2',
                            'size': 2000, 'mtime': 0.0, 'partial_hash': 'b'})
        
        db.add_match('t1', 1, 0.95, 'method1', provider='spotify')
        db.add_match('t2', 2, 0.90, 'method2', provider='spotify')
        db.commit()
        
        assert db.count_matches() == 2
        
        # Delete matches for t1
        db.delete_matches_by_track_ids(['t1'])
        
        assert db.count_matches() == 1
    
    def test_delete_matches_by_file_ids(self, db: Database):
        """Test delete_matches_by_file_ids removes matches for specific files."""
        # Setup data
        db.upsert_track({'id': 't1', 'name': 'Song 1', 'artist': 'A', 'album': 'X',
                        'year': 2020, 'isrc': None, 'duration_ms': 180000, 'normalized': 's1'},
                       provider='spotify')
        
        db.add_library_file({'path': '/f1.mp3', 'title': 'F1', 'artist': 'A', 'album': 'X',
                            'year': 2020, 'duration': 180.0, 'normalized': 's1',
                            'size': 1000, 'mtime': 0.0, 'partial_hash': 'a'})
        db.add_library_file({'path': '/f2.mp3', 'title': 'F2', 'artist': 'B', 'album': 'Y',
                            'year': 2021, 'duration': 200.0, 'normalized': 's2',
                            'size': 2000, 'mtime': 0.0, 'partial_hash': 'b'})
        
        db.add_match('t1', 1, 0.95, 'method1', provider='spotify')
        db.add_match('t1', 2, 0.90, 'method2', provider='spotify')
        db.commit()
        
        assert db.count_matches() == 2
        
        # Delete matches for file 1
        db.delete_matches_by_file_ids([1])
        
        assert db.count_matches() == 1
    
    def test_get_match_confidence_counts(self, db: Database):
        """Test get_match_confidence_counts returns method counts."""
        # Setup data
        db.upsert_track({'id': 't1', 'name': 'S1', 'artist': 'A', 'album': 'X',
                        'year': 2020, 'isrc': None, 'duration_ms': 180000, 'normalized': 's1'},
                       provider='spotify')
        db.upsert_track({'id': 't2', 'name': 'S2', 'artist': 'B', 'album': 'Y',
                        'year': 2021, 'isrc': None, 'duration_ms': 200000, 'normalized': 's2'},
                       provider='spotify')
        db.upsert_track({'id': 't3', 'name': 'S3', 'artist': 'C', 'album': 'Z',
                        'year': 2022, 'isrc': None, 'duration_ms': 220000, 'normalized': 's3'},
                       provider='spotify')
        
        for i in range(3):
            db.add_library_file({'path': f'/f{i}.mp3', 'title': f'F{i}', 'artist': 'A', 'album': 'X',
                                'year': 2020, 'duration': 180.0, 'normalized': f's{i}',
                                'size': 1000, 'mtime': 0.0, 'partial_hash': 'a'})
        
        db.add_match('t1', 1, 0.98, 'score:CERTAIN:isrc', provider='spotify')
        db.add_match('t2', 2, 0.85, 'score:HIGH:fuzzy', provider='spotify')
        db.add_match('t3', 3, 0.85, 'score:HIGH:fuzzy', provider='spotify')
        db.commit()
        
        counts = db.get_match_confidence_counts()
        
        assert counts['score:CERTAIN:isrc'] == 1
        assert counts['score:HIGH:fuzzy'] == 2
    
    def test_get_match_confidence_tier_counts(self, db: Database):
        """Test get_match_confidence_tier_counts robustly extracts tiers."""
        # Setup data
        db.upsert_track({'id': 't1', 'name': 'S1', 'artist': 'A', 'album': 'X',
                        'year': 2020, 'isrc': None, 'duration_ms': 180000, 'normalized': 's1'},
                       provider='spotify')
        db.upsert_track({'id': 't2', 'name': 'S2', 'artist': 'B', 'album': 'Y',
                        'year': 2021, 'isrc': None, 'duration_ms': 200000, 'normalized': 's2'},
                       provider='spotify')
        db.upsert_track({'id': 't3', 'name': 'S3', 'artist': 'C', 'album': 'Z',
                        'year': 2022, 'isrc': None, 'duration_ms': 220000, 'normalized': 's3'},
                       provider='spotify')
        db.upsert_track({'id': 't4', 'name': 'S4', 'artist': 'D', 'album': 'W',
                        'year': 2023, 'isrc': None, 'duration_ms': 240000, 'normalized': 's4'},
                       provider='spotify')
        
        for i in range(4):
            db.add_library_file({'path': f'/f{i}.mp3', 'title': f'F{i}', 'artist': 'A', 'album': 'X',
                                'year': 2020, 'duration': 180.0, 'normalized': f's{i}',
                                'size': 1000, 'mtime': 0.0, 'partial_hash': 'a'})
        
        # Add matches with different tiers and formats
        db.add_match('t1', 1, 0.98, 'score:CERTAIN:isrc', provider='spotify')
        db.add_match('t2', 2, 0.85, 'score:HIGH:fuzzy', provider='spotify')
        db.add_match('t3', 3, 0.85, 'score:HIGH:title_match', provider='spotify')
        db.add_match('t4', 4, 0.70, 'score:MEDIUM', provider='spotify')  # No details
        db.commit()
        
        tier_counts = db.get_match_confidence_tier_counts()
        
        # Should group by tier, not full method string
        # Both 'score:HIGH:fuzzy' and 'score:HIGH:title_match' should be grouped as 'HIGH'
        assert tier_counts.get('CERTAIN', 0) == 1
        assert tier_counts.get('HIGH', 0) == 2  # Both HIGH methods combined
        assert tier_counts.get('MEDIUM', 0) == 1


class TestStatisticsRepository:
    """Test statistics-related repository methods."""
    
    def test_count_distinct_library_albums(self, db: Database):
        """Test count_distinct_library_albums counts unique albums."""
        db.add_library_file({'path': '/f1.mp3', 'title': 'Song 1', 'artist': 'Artist A', 'album': 'Album X',
                            'year': 2020, 'duration': 180.0, 'normalized': 's1',
                            'size': 1000, 'mtime': 0.0, 'partial_hash': 'a'})
        db.add_library_file({'path': '/f2.mp3', 'title': 'Song 2', 'artist': 'Artist A', 'album': 'Album X',
                            'year': 2020, 'duration': 200.0, 'normalized': 's2',
                            'size': 2000, 'mtime': 0.0, 'partial_hash': 'b'})
        db.add_library_file({'path': '/f3.mp3', 'title': 'Song 3', 'artist': 'Artist B', 'album': 'Album Y',
                            'year': 2021, 'duration': 190.0, 'normalized': 's3',
                            'size': 1500, 'mtime': 0.0, 'partial_hash': 'c'})
        db.commit()
        
        count = db.count_distinct_library_albums()
        assert count == 2  # Album X and Album Y
    
    def test_get_playlist_occurrence_counts(self, db: Database):
        """Test get_playlist_occurrence_counts returns track playlist counts."""
        # Create playlists
        db.upsert_playlist('p1', 'Playlist 1', 's1', provider='spotify')
        db.upsert_playlist('p2', 'Playlist 2', 's2', provider='spotify')
        db.upsert_playlist('p3', 'Playlist 3', 's3', provider='spotify')
        
        # Add tracks to playlists
        # t1 appears in p1 and p2 (2 playlists)
        db.replace_playlist_tracks('p1', [(0, 't1', None), (1, 't2', None)], provider='spotify')
        db.replace_playlist_tracks('p2', [(0, 't1', None), (1, 't3', None)], provider='spotify')
        db.replace_playlist_tracks('p3', [(0, 't2', None)], provider='spotify')
        
        db.commit()
        
        counts = db.get_playlist_occurrence_counts(['t1', 't2', 't3', 't4'])
        
        assert counts['t1'] == 2  # In p1 and p2
        assert counts['t2'] == 2  # In p1 and p3
        assert counts['t3'] == 1  # Only in p2
        assert counts['t4'] == 0  # Not in any playlist
    
    def test_get_liked_track_ids(self, db: Database):
        """Test get_liked_track_ids returns liked tracks from list."""
        db.upsert_liked('t1', '2024-01-01', provider='spotify')
        db.upsert_liked('t2', '2024-01-02', provider='spotify')
        db.upsert_liked('t5', '2024-01-05', provider='spotify')
        db.commit()
        
        liked = db.get_liked_track_ids(['t1', 't2', 't3', 't4'], provider='spotify')
        
        assert set(liked) == {'t1', 't2'}


class TestPlaylistRepository:
    """Test playlist repository methods return typed objects."""
    
    def test_get_playlist_by_id_returns_playlist_row(self, db: Database):
        """Test get_playlist_by_id returns PlaylistRow."""
        db.upsert_playlist('p1', 'My Playlist', 's1', owner_id='user1', owner_name='User One', provider='spotify')
        db.commit()
        
        playlist = db.get_playlist_by_id('p1', provider='spotify')
        
        assert playlist is not None
        assert isinstance(playlist, PlaylistRow)
        assert playlist.id == 'p1'
        assert playlist.name == 'My Playlist'
        assert playlist.owner_id == 'user1'
        assert playlist.provider == 'spotify'
    
    def test_get_all_playlists_returns_playlist_rows(self, db: Database):
        """Test get_all_playlists returns list of PlaylistRow objects."""
        db.upsert_playlist('p1', 'Playlist A', 's1', provider='spotify')
        db.upsert_playlist('p2', 'Playlist B', 's2', provider='spotify')
        db.commit()
        
        playlists = db.get_all_playlists(provider='spotify')
        
        assert len(playlists) == 2
        assert all(isinstance(p, PlaylistRow) for p in playlists)
        assert playlists[0].name == 'Playlist A'  # Sorted by name
    
    def test_get_playlists_containing_tracks_returns_distinct_ids(self, db: Database):
        """Test get_playlists_containing_tracks returns distinct playlist IDs for given tracks."""
        # Create playlists
        db.upsert_playlist('p1', 'Rock Classics', 's1', provider='spotify')
        db.upsert_playlist('p2', 'Workout Mix', 's2', provider='spotify')
        db.upsert_playlist('p3', 'Chill Vibes', 's3', provider='spotify')
        
        # Add tracks to playlists
        # p1 contains t1, t2
        # p2 contains t2, t3
        # p3 contains t4 (not in our query)
        db.replace_playlist_tracks('p1', [(0, 't1', None), (1, 't2', None)], provider='spotify')
        db.replace_playlist_tracks('p2', [(0, 't2', None), (1, 't3', None)], provider='spotify')
        db.replace_playlist_tracks('p3', [(0, 't4', None)], provider='spotify')
        db.commit()
        
        # Query for playlists containing t1, t2, or t3
        affected_playlists = db.get_playlists_containing_tracks(['t1', 't2', 't3'], provider='spotify')
        
        # Should return p1 and p2 (not p3)
        assert set(affected_playlists) == {'p1', 'p2'}
        assert len(affected_playlists) == 2
        
        # Test with single track
        playlists_with_t1 = db.get_playlists_containing_tracks(['t1'], provider='spotify')
        assert playlists_with_t1 == ['p1']
        
        # Test with track that appears in multiple playlists (t2 in p1 and p2)
        playlists_with_t2 = db.get_playlists_containing_tracks(['t2'], provider='spotify')
        assert set(playlists_with_t2) == {'p1', 'p2'}
        
        # Test with empty list
        playlists_empty = db.get_playlists_containing_tracks([], provider='spotify')
        assert playlists_empty == []
        
        # Test with non-existent track
        playlists_none = db.get_playlists_containing_tracks(['t999'], provider='spotify')
        assert playlists_none == []


class TestDomainModelCompatibility:
    """Test that domain models provide dict-like compatibility."""
    
    def test_track_row_dict_compatibility(self, db: Database):
        """Test TrackRow provides dict-like access."""
        db.upsert_track({'id': 't1', 'name': 'Song', 'artist': 'Artist', 'album': 'Album',
                        'year': 2020, 'isrc': 'ISRC1', 'duration_ms': 180000, 'normalized': 'song'},
                       provider='spotify')
        db.commit()
        
        tracks = db.get_all_tracks(provider='spotify')
        track = tracks[0]
        
        # Test subscript access
        assert track['id'] == 't1'
        assert track['name'] == 'Song'
        
        # Test keys()
        assert 'id' in track.keys()
        assert 'name' in track.keys()
        
        # Test to_dict()
        track_dict = track.to_dict()
        assert isinstance(track_dict, dict)
        assert track_dict['id'] == 't1'
    
    def test_library_file_row_dict_compatibility(self, db: Database):
        """Test LibraryFileRow provides dict-like access."""
        db.add_library_file({'path': '/music/song.mp3', 'title': 'Song', 'artist': 'Artist',
                            'album': 'Album', 'year': 2020, 'duration': 180.0, 'normalized': 'song',
                            'size': 1000, 'mtime': 0.0, 'partial_hash': 'abc'})
        db.commit()
        
        files = db.get_all_library_files()
        file = files[0]
        
        # Test subscript access
        assert file['path'] == '/music/song.mp3'
        assert file['title'] == 'Song'
        
        # Test keys()
        assert 'path' in file.keys()
        assert 'title' in file.keys()
        
        # Test to_dict()
        file_dict = file.to_dict()
        assert isinstance(file_dict, dict)
        assert file_dict['path'] == '/music/song.mp3'
