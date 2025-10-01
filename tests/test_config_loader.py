from pathlib import Path
import os
import textwrap
from spx.config import load_config, deep_merge, coerce_scalar


def test_deep_merge_simple():
    a = {'a': 1, 'b': {'x': 1, 'y': 2}}
    b = {'b': {'y': 99, 'z': 5}, 'c': 3}
    merged = deep_merge(a, b)
    assert merged['a'] == 1
    assert merged['b']['x'] == 1
    assert merged['b']['y'] == 99
    assert merged['b']['z'] == 5
    assert merged['c'] == 3


def test_coerce_scalar():
    assert coerce_scalar('true') is True
    assert coerce_scalar('False') is False
    assert coerce_scalar('10') == 10
    assert isinstance(coerce_scalar('10.5'), float)
    assert coerce_scalar('foo') == 'foo'


def test_load_config_dotenv_and_env(tmp_path: Path, monkeypatch):
    """Test that .env file is loaded and environment variables override it."""
    env_file = tmp_path / '.env'
    env_file.write_text(textwrap.dedent('''\
    SPX__EXPORT__MODE=mirrored
    SPX__EXPORT__DIRECTORY=custom/export
    SPX__MATCHING__FUZZY_THRESHOLD=0.9
    '''), encoding='utf-8')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('SPX_ENABLE_DOTENV', '1')
    # env override
    monkeypatch.setenv('SPX__EXPORT__MODE', 'placeholders')
    monkeypatch.setenv('SPX__MATCHING__FUZZY_THRESHOLD', '0.85')
    cfg = load_config()
    # .env applied
    assert cfg['export']['directory'] == 'custom/export'
    # env override applied after .env
    assert cfg['export']['mode'] == 'placeholders'
    # numeric coercion
    assert abs(cfg['matching']['fuzzy_threshold'] - 0.85) < 1e-9


def test_explicit_file_parameter_ignored(tmp_path: Path):
    """Test that explicit_file parameter is kept for backward compatibility but ignored."""
    cfg_file = tmp_path / 'alt.yml'
    cfg_file.write_text('export:\n  mode: mirrored\n', encoding='utf-8')
    # explicit_file parameter is ignored now - always uses .env
    cfg = load_config(explicit_file=str(cfg_file))
    # Should use default, not the YAML file
    assert cfg['export']['mode'] == 'strict'
