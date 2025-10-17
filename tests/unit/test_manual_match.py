"""Tests for manual match override functionality (M1 solution)."""

import pytest
from psm.db.sqlite_impl import Database
from psm.services.diagnostic_service import diagnose_track, format_diagnostic_output
from pathlib import Path


class TestManualMatchRanking:
    """Test that manual matches are prioritized over automatic matches via SQL ranking."""

    def test_get_library_file_by_path(self, tmp_path):
        """Test new get_library_file_by_path method."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)

        # Add a library file
        db.add_library_file({
            'path': '/music/song.mp3',
            'size': 1000,
            'mtime': 123456.0,
            'partial_hash': 'abc123',
            'title': 'Test Song',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'duration': 180.0,
            'normalized': 'test artist test song',
            'year': 2020,
            'bitrate_kbps': 320,
        })
        db.commit()

        # Lookup by path should succeed
        file = db.get_library_file_by_path('/music/song.mp3')
        assert file is not None
        assert file.path == '/music/song.mp3'
        assert file.title == 'Test Song'
        assert file.artist == 'Test Artist'

        # Non-existent path should return None
        file = db.get_library_file_by_path('/music/nonexistent.mp3')
        assert file is None

        db.close()

    def test_manual_match_prioritized_in_unified_view(self, tmp_path):
        """Test that manual matches are selected over higher-scoring automatic matches."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)

        # Setup: Add a track
        db.upsert_track({
            'id': 'track123',
            'name': 'Test Track',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'duration_ms': 180000,
            'normalized': 'test artist test track',
        }, provider='spotify')

        # Add two library files
        db.add_library_file({
            'path': '/music/automatic.mp3',
            'size': 1000,
            'mtime': 123456.0,
            'partial_hash': 'auto123',
            'title': 'Test Track',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'duration': 180.0,
            'normalized': 'test artist test track',
            'year': 2020,
            'bitrate_kbps': 320,
        })

        db.add_library_file({
            'path': '/music/manual.mp3',
            'size': 1000,
            'mtime': 123456.0,
            'partial_hash': 'manual123',
            'title': 'Test Track',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'duration': 180.0,
            'normalized': 'test artist test track',
            'year': 2020,
            'bitrate_kbps': 320,
        })
        db.commit()

        # Get file IDs
        auto_file = db.get_library_file_by_path('/music/automatic.mp3')
        manual_file = db.get_library_file_by_path('/music/manual.mp3')

        # Add automatic match with higher score
        db.add_match(
            track_id='track123',
            file_id=auto_file.id,
            score=0.95,
            method='fuzzy:high',
            provider='spotify',
            confidence='HIGH'
        )

        # Add manual match with lower score but MANUAL confidence
        db.add_match(
            track_id='track123',
            file_id=manual_file.id,
            score=1.00,
            method='score:MANUAL:manual-selected',
            provider='spotify',
            confidence='MANUAL'
        )
        db.commit()

        # Query unified tracks - should return manual match
        from psm.db.queries_unified import list_unified_tracks_min
        tracks = list_unified_tracks_min(db.conn, provider='spotify')

        assert len(tracks) == 1
        track = tracks[0]
        assert track['matched'] is True
        # Should get manual match path, not automatic match path
        assert track['local_path'] == '/music/manual.mp3'

        db.close()

    def test_manual_match_confidence_in_diagnostics(self, tmp_path):
        """Test that diagnostics show 'Confidence: MANUAL' for manual matches."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)

        # Setup: Add a track
        db.upsert_track({
            'id': 'track123',
            'name': 'Test Track',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'duration_ms': 180000,
            'normalized': 'test artist test track',
        }, provider='spotify')

        # Add a library file
        db.add_library_file({
            'path': '/music/manual.mp3',
            'size': 1000,
            'mtime': 123456.0,
            'partial_hash': 'manual123',
            'title': 'Test Track',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'duration': 180.0,
            'normalized': 'test artist test track',
            'year': 2020,
            'bitrate_kbps': 320,
        })
        db.commit()

        manual_file = db.get_library_file_by_path('/music/manual.mp3')

        # Add manual match
        db.add_match(
            track_id='track123',
            file_id=manual_file.id,
            score=1.00,
            method='score:MANUAL:manual-selected',
            provider='spotify',
            confidence='MANUAL'
        )
        db.commit()

        # Diagnose track
        result = diagnose_track(db, 'track123', provider='spotify')

        assert result.track_found is True
        assert result.is_matched is True
        assert result.match_confidence == 'MANUAL'

        # Format output
        output = format_diagnostic_output(result)
        assert 'Confidence:  MANUAL - User-selected override' in output

        db.close()

    def test_get_match_for_track_includes_confidence(self, tmp_path):
        """Test that get_match_for_track returns confidence field."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)

        # Setup
        db.upsert_track({
            'id': 'track123',
            'name': 'Test Track',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'duration_ms': 180000,
            'normalized': 'test artist test track',
        }, provider='spotify')

        db.add_library_file({
            'path': '/music/test.mp3',
            'size': 1000,
            'mtime': 123456.0,
            'partial_hash': 'test123',
            'title': 'Test Track',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'duration': 180.0,
            'normalized': 'test artist test track',
            'year': 2020,
            'bitrate_kbps': 320,
        })
        db.commit()

        file = db.get_library_file_by_path('/music/test.mp3')

        db.add_match(
            track_id='track123',
            file_id=file.id,
            score=0.90,
            method='fuzzy:high',
            provider='spotify',
            confidence='HIGH'
        )
        db.commit()

        # Get match info
        match_info = db.get_match_for_track('track123', provider='spotify')

        assert match_info is not None
        assert 'confidence' in match_info
        assert match_info['confidence'] == 'HIGH'

        db.close()


class TestExportRanking:
    """Test that playlist/liked exports prioritize manual matches."""

    def test_playlist_export_uses_manual_match(self, tmp_path):
        """Test that get_playlist_tracks_with_local_paths returns manual match."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)

        # Setup playlist
        db.upsert_playlist('pl123', 'Test Playlist', 'snap1', provider='spotify')
        db.upsert_track({
            'id': 'track123',
            'name': 'Test Track',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'duration_ms': 180000,
            'normalized': 'test artist test track',
        }, provider='spotify')

        db.replace_playlist_tracks('pl123', [(0, 'track123', None)], provider='spotify')

        # Add two files
        db.add_library_file({
            'path': '/music/automatic.mp3',
            'size': 1000,
            'mtime': 123456.0,
            'partial_hash': 'auto123',
            'title': 'Test Track',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'duration': 180.0,
            'normalized': 'test artist test track',
            'year': 2020,
            'bitrate_kbps': 320,
        })

        db.add_library_file({
            'path': '/music/manual.mp3',
            'size': 1000,
            'mtime': 123456.0,
            'partial_hash': 'manual123',
            'title': 'Test Track',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'duration': 180.0,
            'normalized': 'test artist test track',
            'year': 2020,
            'bitrate_kbps': 320,
        })
        db.commit()

        auto_file = db.get_library_file_by_path('/music/automatic.mp3')
        manual_file = db.get_library_file_by_path('/music/manual.mp3')

        # Add automatic match
        db.add_match(
            track_id='track123',
            file_id=auto_file.id,
            score=0.95,
            method='fuzzy:high',
            provider='spotify',
            confidence='HIGH'
        )

        # Add manual match
        db.add_match(
            track_id='track123',
            file_id=manual_file.id,
            score=1.00,
            method='score:MANUAL:manual-selected',
            provider='spotify',
            confidence='MANUAL'
        )
        db.commit()

        # Export playlist
        tracks = db.get_playlist_tracks_with_local_paths('pl123', provider='spotify')

        assert len(tracks) == 1
        # Should use manual match
        assert tracks[0]['local_path'] == '/music/manual.mp3'

        db.close()

    def test_liked_export_uses_manual_match(self, tmp_path):
        """Test that get_liked_tracks_with_local_paths returns manual match."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)

        # Setup liked track
        db.upsert_track({
            'id': 'track123',
            'name': 'Test Track',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'duration_ms': 180000,
            'normalized': 'test artist test track',
        }, provider='spotify')

        db.upsert_liked('track123', '2025-10-01T00:00:00Z', provider='spotify')

        # Add two files
        db.add_library_file({
            'path': '/music/automatic.mp3',
            'size': 1000,
            'mtime': 123456.0,
            'partial_hash': 'auto123',
            'title': 'Test Track',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'duration': 180.0,
            'normalized': 'test artist test track',
            'year': 2020,
            'bitrate_kbps': 320,
        })

        db.add_library_file({
            'path': '/music/manual.mp3',
            'size': 1000,
            'mtime': 123456.0,
            'partial_hash': 'manual123',
            'title': 'Test Track',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'duration': 180.0,
            'normalized': 'test artist test track',
            'year': 2020,
            'bitrate_kbps': 320,
        })
        db.commit()

        auto_file = db.get_library_file_by_path('/music/automatic.mp3')
        manual_file = db.get_library_file_by_path('/music/manual.mp3')

        # Add automatic match
        db.add_match(
            track_id='track123',
            file_id=auto_file.id,
            score=0.95,
            method='fuzzy:high',
            provider='spotify',
            confidence='HIGH'
        )

        # Add manual match
        db.add_match(
            track_id='track123',
            file_id=manual_file.id,
            score=1.00,
            method='score:MANUAL:manual-selected',
            provider='spotify',
            confidence='MANUAL'
        )
        db.commit()

        # Export liked tracks
        tracks = db.get_liked_tracks_with_local_paths(provider='spotify')

        assert len(tracks) == 1
        # Should use manual match
        assert tracks[0]['local_path'] == '/music/manual.mp3'

        db.close()
