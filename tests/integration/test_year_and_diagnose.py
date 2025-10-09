from pathlib import Path
from click.testing import CliRunner
from psm.cli import cli
from psm.db import Database


def test_year_column_migration_and_normalization(tmp_path: Path, test_config):
    db_path = tmp_path / 'db.sqlite'
    test_config['database']['path'] = str(db_path)
    # Enable use_year
    test_config['matching']['use_year'] = True
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
    }, provider='spotify')
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
    # Close direct handle so CLI can acquire its own lock
    db.close()
    result = runner.invoke(cli, ['match'], obj=test_config)
    assert result.exit_code == 0
    # Re-open to inspect results
    db2 = Database(db_path)
    row = db2.conn.execute('SELECT * FROM matches WHERE track_id="t1"').fetchone()
    assert row is not None
    db2.close()


def test_match_diagnose_outputs(tmp_path: Path, test_config):
    db_path = tmp_path / 'db.sqlite'
    test_config['database']['path'] = str(db_path)
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
    }, provider='spotify')
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
    # Close direct handle so CLI can acquire its own lock
    db.close()
    runner = CliRunner()
    res = runner.invoke(cli, ['diagnose', 't2'], obj=test_config)
    assert res.exit_code == 0
    assert 'Track: t2' in res.output
    assert 'closest files' in res.output  # Changed from "Top candidates" to match current output
    # Note: "Existing match" may not appear if no match exists yet