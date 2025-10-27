from psm.services.match_service import run_matching
from tests.mocks.mock_database import MockDatabase  # noqa
from tests.mocks.fixtures import mock_db  # noqa: F401 (fixture import)


def test_run_matching_no_tracks(mock_db):
    config = {"matching": {"fuzzy_threshold": 0.78}}
    # No tracks or library files -> zero matches
    result = run_matching(mock_db, config)
    assert result.library_files == 0
    assert result.matched == 0
