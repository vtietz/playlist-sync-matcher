from pathlib import Path
from click.testing import CliRunner
from psm.cli import cli
from psm.db import Database


def test_year_column_migration_and_normalization(tmp_path: Path, monkeypatch):
    db_path = tmp_path / 'db.sqlite'
    monkeypatch.setenv('PSM__DATABASE__PATH', str(db_path))
    # Enable use_year
    monkeypatch.setenv('PSM__MATCHING__USE_YEAR', 'true')
    db = Database(db_path)
    # Insert a track without normalized (simulate pre-change) and with year
    db.upsert_track({
        'id': 't1',
        'name': 'Der Wal',
        'album': 'Authentic Trip',
        'artist': 'Funny Van Dannen',
        'isrc': None,
        'duration_ms': 123000,
        'normalized': None,
        'year': 2005,
    })
    # Insert a library file normalized using year token
    db.add_library_file({
        'path': 'Der Wal.mp3',
        'size': 1000,
        'mtime': 0.0,
        'partial_hash': 'abc',
        'title': 'Der Wal',
        'album': 'Authentic Trip',
        'artist': 'Funny Van Dannen',
        'duration': 123.0,
        'normalized': 'funny van dannen der wal 2005',
        'year': 2005,
    })
    db.commit()
    # Run match (should backfill normalization adding year and then match)
    runner = CliRunner()
    result = runner.invoke(cli, ['match'])
    assert result.exit_code == 0
    row = db.conn.execute('SELECT * FROM matches WHERE track_id="t1"').fetchone()
    assert row is not None


def test_match_diagnose_outputs(tmp_path: Path, monkeypatch):
    db_path = tmp_path / 'db.sqlite'
    monkeypatch.setenv('PSM__DATABASE__PATH', str(db_path))
    db = Database(db_path)
    # Prepare data
    db.upsert_track({
        'id': 't2',
        'name': 'Song Title',
        'album': 'Album',
        'artist': 'Artist',
        'isrc': None,
        'duration_ms': 111000,
        'normalized': 'artist song title',
        'year': None,
    })
    db.add_library_file({
        'path': 'Song Title.mp3',
        'size': 1000,
        'mtime': 0.0,
        'partial_hash': 'abc',
        'title': 'Song Title',
        'album': 'Album',
        'artist': 'Artist',
        'duration': 111.0,
        'normalized': 'artist song title',
        'year': None,
    })
    db.commit()
    runner = CliRunner()
    res = runner.invoke(cli, ['match-diagnose', 't2'])
    assert res.exit_code == 0
    assert 'Track: t2' in res.output
    assert 'Top candidates' in res.output
    assert 'Existing match' in res.output  # may be none before running match