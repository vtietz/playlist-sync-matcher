import os
from spx.config import load_config

def test_env_json_list_override(monkeypatch):
    # default single path
    cfg_default = load_config()
    assert isinstance(cfg_default['library']['paths'], list)
    assert cfg_default['library']['paths'][0] == 'music'
    # override with JSON array
    monkeypatch.setenv('SPX__LIBRARY__PATHS', '["X:/Music","Y:/Other","Z:/More"]')
    cfg = load_config()
    assert cfg['library']['paths'] == ["X:/Music", "Y:/Other", "Z:/More"]
