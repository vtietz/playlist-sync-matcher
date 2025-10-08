from pathlib import Path
from click.testing import CliRunner
from psm.cli import cli
from psm.version import __version__


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(cli, ['--version'])
    assert result.exit_code == 0
    assert 'playlist-sync-matcher' in result.output.lower()
    assert __version__ in result.output