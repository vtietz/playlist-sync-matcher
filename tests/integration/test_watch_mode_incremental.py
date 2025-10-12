"""Integration tests for watch mode incremental rebuild pipeline.

Tests the full watch mode workflow:
1. Library change detected → scan → match → affected playlists → scoped export/reports
2. Database change → incremental match → affected playlists → scoped export/reports
"""
from __future__ import annotations
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from psm.db import Database
from psm.services.watch_build_service import WatchBuildConfig, _handle_library_changes, _export_playlists, _generate_reports


@pytest.fixture
def temp_db(tmp_path: Path):
    """Create a temporary test database with playlists and tracks."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)

    # Create test playlists
    db.upsert_playlist('playlist1', 'Rock Classics', 'snap1', provider='spotify')
    db.upsert_playlist('playlist2', 'Jazz Collection', 'snap2', provider='spotify')
    db.upsert_playlist('playlist3', 'Workout Mix', 'snap3', provider='spotify')

    # Create test tracks
    db.upsert_track({
        'id': 'track1',
        'name': 'Wish You Were Here',
        'artist': 'Pink Floyd',
        'album': 'Wish You Were Here',
        'year': 1975,
        'duration_ms': 334000,
        'normalized': 'wish you were here pink floyd'
    }, provider='spotify')

    db.upsert_track({
        'id': 'track2',
        'name': 'Take Five',
        'artist': 'Dave Brubeck',
        'album': 'Time Out',
        'year': 1959,
        'duration_ms': 324000,
        'normalized': 'take five dave brubeck'
    }, provider='spotify')

    db.upsert_track({
        'id': 'track3',
        'name': 'Eye of the Tiger',
        'artist': 'Survivor',
        'album': 'Eye of the Tiger',
        'year': 1982,
        'duration_ms': 246000,
        'normalized': 'eye of the tiger survivor'
    }, provider='spotify')

    # Add tracks to playlists
    # playlist1 contains track1, track2
    # playlist2 contains track2
    # playlist3 contains track3
    db.replace_playlist_tracks('playlist1', [
        (0, 'track1', None),
        (1, 'track2', None)
    ], provider='spotify')

    db.replace_playlist_tracks('playlist2', [
        (0, 'track2', None)
    ], provider='spotify')

    db.replace_playlist_tracks('playlist3', [
        (0, 'track3', None)
    ], provider='spotify')

    # Add library files
    db.add_library_file({
        'path': str(tmp_path / 'music' / 'pink_floyd.mp3'),
        'title': 'Wish You Were Here',
        'artist': 'Pink Floyd',
        'album': 'Wish You Were Here',
        'year': 1975,
        'duration': 334.0,
        'normalized': 'wish you were here pink floyd',
        'size': 5000000,
        'mtime': 123.45,
        'partial_hash': 'abc123'
    })

    db.add_library_file({
        'path': str(tmp_path / 'music' / 'dave_brubeck.mp3'),
        'title': 'Take Five',
        'artist': 'Dave Brubeck',
        'album': 'Time Out',
        'year': 1959,
        'duration': 324.0,
        'normalized': 'take five dave brubeck',
        'size': 4500000,
        'mtime': 456.78,
        'partial_hash': 'def456'
    })

    db.commit()
    yield db
    db.close()


class TestWatchModeIncrementalPipeline:
    """Test watch mode incremental rebuild pipeline."""

    def test_get_playlists_containing_tracks_basic(self, temp_db: Database):
        """Test basic get_playlists_containing_tracks functionality."""
        # Track1 is in playlist1 only
        playlists = temp_db.get_playlists_containing_tracks(['track1'], provider='spotify')
        assert playlists == ['playlist1']

        # Track2 is in playlist1 and playlist2
        playlists = temp_db.get_playlists_containing_tracks(['track2'], provider='spotify')
        assert set(playlists) == {'playlist1', 'playlist2'}

        # Track1 and track2 together affect playlist1 and playlist2
        playlists = temp_db.get_playlists_containing_tracks(['track1', 'track2'], provider='spotify')
        assert set(playlists) == {'playlist1', 'playlist2'}

        # Track3 is only in playlist3
        playlists = temp_db.get_playlists_containing_tracks(['track3'], provider='spotify')
        assert playlists == ['playlist3']

        # Empty list returns empty
        playlists = temp_db.get_playlists_containing_tracks([], provider='spotify')
        assert playlists == []

        # Non-existent track returns empty
        playlists = temp_db.get_playlists_containing_tracks(['track999'], provider='spotify')
        assert playlists == []

    def test_library_change_creates_matches(self, temp_db: Database):
        """Test that library file changes trigger matches."""
        # Initially no matches
        assert temp_db.count_matches() == 0

        # Simulate matching the files
        temp_db.add_match('track1', 1, 0.95, 'score:HIGH:exact', provider='spotify')
        temp_db.add_match('track2', 2, 0.93, 'score:HIGH:fuzzy', provider='spotify')
        temp_db.commit()

        # Now we have matches
        assert temp_db.count_matches() == 2

        # Get affected playlists
        matched_track_ids = ['track1', 'track2']
        affected_playlists = temp_db.get_playlists_containing_tracks(matched_track_ids, provider='spotify')

        # Should affect playlist1 and playlist2 (both contain track2, playlist1 also has track1)
        assert set(affected_playlists) == {'playlist1', 'playlist2'}
        # Should NOT affect playlist3 (contains only track3 which wasn't matched)
        assert 'playlist3' not in affected_playlists

    @patch('psm.services.watch_build_service.export_playlists')
    @patch('psm.services.watch_build_service.write_match_reports')
    @patch('psm.services.watch_build_service.write_index_page')
    @patch('psm.services.watch_build_service.scan_specific_files')
    @patch('psm.services.watch_build_service.match_changed_files')
    def test_handle_library_changes_scoped_export(
        self,
        mock_match_changed_files,
        mock_scan_specific_files,
        mock_write_index_page,
        mock_write_match_reports,
        mock_export_playlists,
        temp_db: Database,
        tmp_path: Path
    ):
        """Test that library changes trigger scoped export for affected playlists only."""
        # Setup mocks
        mock_scan_result = Mock()
        mock_scan_result.inserted = 1
        mock_scan_result.updated = 0
        mock_scan_result.deleted = 0
        mock_scan_specific_files.return_value = mock_scan_result

        # Simulate matching files - return new matches and matched track IDs
        mock_match_changed_files.return_value = (2, ['track1', 'track2'])

        # Create watch config
        config = {
            'database': {'path': str(temp_db.path)},
            'provider': 'spotify',
            'export': {'directory': str(tmp_path / 'export')},
            'reports': {'directory': str(tmp_path / 'reports')}
        }

        watch_config = WatchBuildConfig(
            config=config,
            get_db_func=lambda cfg: temp_db,
            skip_export=False,
            skip_report=False
        )

        # Create fake file paths
        changed_files = [tmp_path / 'music' / 'new_song.mp3']

        # Add the file IDs that match will find
        temp_db.add_library_file({
            'path': str(changed_files[0]),
            'title': 'New Song',
            'artist': 'Artist',
            'album': 'Album',
            'year': 2020,
            'duration': 180.0,
            'normalized': 'new song artist',
            'size': 3000000,
            'mtime': 789.01,
            'partial_hash': 'ghi789'
        })
        temp_db.commit()

        # Add matches for the tracks
        temp_db.add_match('track1', 3, 0.95, 'score:HIGH:exact', provider='spotify')
        temp_db.add_match('track2', 3, 0.90, 'score:MEDIUM:fuzzy', provider='spotify')
        temp_db.commit()

        # Call the handler
        _handle_library_changes(changed_files, watch_config)

        # Verify scan was called
        mock_scan_specific_files.assert_called_once()

        # Verify match was called with file IDs
        assert mock_match_changed_files.called

        # Verify export was called with ONLY affected playlists
        assert mock_export_playlists.called
        export_call_args = mock_export_playlists.call_args

        # Check if playlist_ids parameter was passed
        if 'playlist_ids' in export_call_args.kwargs:
            exported_playlists = export_call_args.kwargs['playlist_ids']
            # Should export playlist1 and playlist2 (contain track1/track2), not playlist3
            assert exported_playlists is not None
            assert set(exported_playlists) == {'playlist1', 'playlist2'}

        # Verify reports were called with affected playlists
        assert mock_write_match_reports.called
        report_call_args = mock_write_match_reports.call_args
        if 'affected_playlist_ids' in report_call_args.kwargs:
            report_playlists = report_call_args.kwargs['affected_playlist_ids']
            assert report_playlists is not None
            assert set(report_playlists) == {'playlist1', 'playlist2'}

    def test_export_playlists_helper_skips_on_empty_list(self, temp_db: Database, tmp_path: Path):
        """Test that _export_playlists helper skips export when playlist_ids is empty list."""
        config = {
            'export': {
                'directory': str(tmp_path / 'export'),
                'organize_by_owner': False
            }
        }

        # Patch export_playlists to verify it's NOT called
        with patch('psm.services.watch_build_service.export_playlists') as mock_export:
            _export_playlists(temp_db, config, playlist_ids=[])

            # Export should NOT be called when list is empty
            mock_export.assert_not_called()

    def test_export_playlists_helper_calls_export_when_list_provided(self, temp_db: Database, tmp_path: Path):
        """Test that _export_playlists calls export with specific playlist IDs."""
        config = {
            'export': {
                'directory': str(tmp_path / 'export'),
                'organize_by_owner': False
            }
        }

        # Patch export_playlists to capture the call
        with patch('psm.services.watch_build_service.export_playlists') as mock_export:
            mock_export.return_value = Mock(playlist_count=2)

            _export_playlists(temp_db, config, playlist_ids=['playlist1', 'playlist2'])

            # Export should be called with the specific playlists
            assert mock_export.called
            call_args = mock_export.call_args
            assert call_args.kwargs['playlist_ids'] == ['playlist1', 'playlist2']

    def test_generate_reports_helper_skips_on_empty_list(self, temp_db: Database, tmp_path: Path):
        """Test that _generate_reports helper skips when playlist_ids is empty list."""
        config = {
            'reports': {
                'directory': str(tmp_path / 'reports')
            }
        }

        # Patch write_match_reports to verify it's NOT called
        with patch('psm.services.watch_build_service.write_match_reports') as mock_reports:
            with patch('psm.services.watch_build_service.write_index_page') as mock_index:
                _generate_reports(temp_db, config, affected_playlist_ids=[])

                # Reports should NOT be called when list is empty
                mock_reports.assert_not_called()
                mock_index.assert_not_called()

    def test_generate_reports_helper_calls_with_playlist_ids(self, temp_db: Database, tmp_path: Path):
        """Test that _generate_reports calls reports with specific playlist IDs."""
        config = {
            'reports': {
                'directory': str(tmp_path / 'reports')
            }
        }

        # Patch report functions to capture calls
        with patch('psm.services.watch_build_service.write_match_reports') as mock_reports:
            with patch('psm.services.watch_build_service.write_index_page') as mock_index:
                _generate_reports(temp_db, config, affected_playlist_ids=['playlist1'])

                # Reports should be called with the specific playlists
                assert mock_reports.called
                call_args = mock_reports.call_args
                assert call_args.kwargs['affected_playlist_ids'] == ['playlist1']

                # Index page should also be updated
                assert mock_index.called


class TestWatchModeEdgeCases:
    """Test edge cases in watch mode pipeline."""

    def test_no_matches_means_no_affected_playlists(self, temp_db: Database):
        """Test that when no matches occur, affected playlists is empty."""
        # No matches created
        matched_track_ids = []
        affected_playlists = temp_db.get_playlists_containing_tracks(matched_track_ids, provider='spotify')

        assert affected_playlists == []

    def test_matched_track_not_in_any_playlist(self, temp_db: Database):
        """Test that matched tracks not in any playlist result in empty affected list."""
        # Add a track that's not in any playlist
        temp_db.upsert_track({
            'id': 'track_orphan',
            'name': 'Orphan Song',
            'artist': 'Unknown',
            'album': 'Singles',
            'year': 2020,
            'duration_ms': 180000,
            'normalized': 'orphan song unknown'
        }, provider='spotify')
        temp_db.commit()

        # This track is not in any playlist
        affected_playlists = temp_db.get_playlists_containing_tracks(['track_orphan'], provider='spotify')

        assert affected_playlists == []

    def test_multiple_tracks_in_same_playlist_returns_once(self, temp_db: Database):
        """Test that playlist appears once even if multiple matched tracks are in it."""
        # Track1 and track2 are both in playlist1
        affected_playlists = temp_db.get_playlists_containing_tracks(['track1', 'track2'], provider='spotify')

        # Should return playlist1 only once (DISTINCT in SQL)
        assert affected_playlists.count('playlist1') == 1
        assert 'playlist1' in affected_playlists

    def test_matched_track_in_liked_songs_only(self, temp_db: Database):
        """Test that tracks in Liked Songs (but no playlists) are handled correctly."""
        # Add a track that's only in Liked Songs
        temp_db.upsert_track({
            'id': 'track_liked_only',
            'name': 'Liked Song',
            'artist': 'Artist',
            'album': 'Album',
            'year': 2020,
            'duration_ms': 180000,
            'normalized': 'liked song artist'
        }, provider='spotify')

        # Add to Liked Songs
        temp_db.upsert_liked('track_liked_only', '2025-01-01T00:00:00Z', provider='spotify')
        temp_db.commit()

        # Not in any playlist
        affected_playlists = temp_db.get_playlists_containing_tracks(['track_liked_only'], provider='spotify')
        assert affected_playlists == []

        # But IS in liked songs
        liked_track_ids = temp_db.get_liked_track_ids(['track_liked_only'], provider='spotify')
        assert liked_track_ids == ['track_liked_only']

    def test_get_liked_track_ids_basic(self, temp_db: Database):
        """Test get_liked_track_ids functionality."""
        # Add some tracks to liked
        temp_db.upsert_liked('track1', '2025-01-01T00:00:00Z', provider='spotify')
        temp_db.upsert_liked('track2', '2025-01-02T00:00:00Z', provider='spotify')
        temp_db.commit()

        # Query which tracks are liked
        liked_ids = temp_db.get_liked_track_ids(['track1', 'track2', 'track3'], provider='spotify')

        # Only track1 and track2 are liked
        assert set(liked_ids) == {'track1', 'track2'}

        # Empty list
        assert temp_db.get_liked_track_ids([], provider='spotify') == []

        # Non-existent track
        assert temp_db.get_liked_track_ids(['track999'], provider='spotify') == []
