import os
from spx.config import load_config


def test_env_override_export_mode(monkeypatch):
    # Ensure default is strict
    cfg_default = load_config()
    assert cfg_default['export']['mode'] == 'strict'
    # Override
    monkeypatch.setenv('SPX__EXPORT__MODE', 'mirrored')
    cfg = load_config()
    assert cfg['export']['mode'] == 'mirrored'
