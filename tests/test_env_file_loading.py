from pathlib import Path
import os
from spx.config import load_config

def test_env_file_loading(tmp_path, monkeypatch):
    # create temporary .env
    env_file = tmp_path / '.env'
    env_file.write_text('SPX__EXPORT__MODE=placeholders\n', encoding='utf-8')
    # chdir into tmp_path to simulate project root where .env resides
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('SPX_ENABLE_DOTENV', '1')
    cfg = load_config()
    assert cfg['export']['mode'] == 'placeholders'
    # explicit OS environment should override .env
    monkeypatch.setenv('SPX__EXPORT__MODE', 'mirrored')
    cfg2 = load_config()
    assert cfg2['export']['mode'] == 'mirrored'