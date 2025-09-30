import os
from spx.config import load_config


def test_env_override_export_mode(monkeypatch):
    # Ensure no dotenv auto-loading or prior env variable contamination
    monkeypatch.delenv('SPX_ENABLE_DOTENV', raising=False)
    monkeypatch.delenv('SPX__EXPORT__MODE', raising=False)
    cfg_default = load_config()
    assert cfg_default['export']['mode'] == 'strict'
    # Override via environment
    monkeypatch.setenv('SPX__EXPORT__MODE', 'mirrored')
    cfg = load_config()
    assert cfg['export']['mode'] == 'mirrored'
