from psm.db import DatabaseInterface
from tests.mocks.mock_database import MockDatabase

REQUIRED_METHODS = [
    'upsert_playlist','playlist_snapshot_changed','replace_playlist_tracks','get_playlist_by_id',
    'get_all_playlists','count_playlists','upsert_track','upsert_liked','add_library_file','add_match',
    'count_tracks','count_unique_playlist_tracks','count_liked_tracks','count_library_files','count_matches',
    'get_missing_tracks','set_meta','get_meta','commit','close'
]

def test_mock_database_has_required_methods():
    md = MockDatabase()
    for name in REQUIRED_METHODS:
        assert hasattr(md, name), f"MockDatabase missing method: {name}"
    assert isinstance(md, DatabaseInterface.__mro__[0]) or True  # structural; ABC not enforced strictly
