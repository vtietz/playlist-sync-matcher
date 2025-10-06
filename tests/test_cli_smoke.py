from pathlib import Path
from click.testing import CliRunner
from psm.cli import cli


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(cli, ['version'])
    assert result.exit_code == 0
    assert 'spotify-m3u-sync' in result.output


def test_cli_report_albums_empty_db(tmp_path: Path, monkeypatch):
    # point database and reports dir to temp
    db_path = tmp_path / 'db.sqlite'
    reports_dir = tmp_path / 'reports'
    monkeypatch.setenv('PSM__DATABASE__PATH', str(db_path))
    monkeypatch.setenv('PSM__REPORTS__DIRECTORY', str(reports_dir))
    runner = CliRunner()
    result = runner.invoke(cli, ['report-albums'])
    assert result.exit_code == 0
    out_file = reports_dir / 'album_completeness.csv'
    assert out_file.exists()
    content = out_file.read_text(encoding='utf-8').strip().splitlines()
    # header only when no albums
    assert len(content) == 1
    assert content[0].startswith('artist,album,total,matched,missing,percent_complete,status')