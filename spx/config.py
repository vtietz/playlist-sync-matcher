from __future__ import annotations
import os
import yaml
import json
from typing import Any, Dict
from pathlib import Path
import copy

_DEFAULTS: Dict[str, Any] = {
    "debug": False,  # top-level debug flag (enables verbose logging when true)
    "spotify": {
        "client_id": None,
        "redirect_scheme": "http",  # default to loopback HTTP per updated Spotify guidance
        "redirect_host": "127.0.0.1",  # explicit loopback host (use 127.0.0.1 instead of 'localhost')
        "redirect_port": 9876,
        "redirect_path": "/callback",  # can change to '/' if Spotify dashboard rejects
        "scope": "user-library-read playlist-read-private playlist-read-collaborative",
        "cache_file": "tokens.json",
        "cert_file": "cert.pem",  # self-signed cert path (generated on demand)
        "key_file": "key.pem",   # self-signed key path (generated on demand)
    },
    "library": {
        "paths": ["music"],
        "extensions": [".mp3", ".flac", ".m4a", ".ogg"],
        "follow_symlinks": False,
        "ignore_patterns": [".*"],
        "skip_unchanged": True,           # skip files whose size+mtime unchanged (fast path)
        "fast_scan": True,                # skip audio parsing for unchanged files (massive speedup)
        "commit_interval": 100,           # commit after N processed (new/updated) files
    },
    "matching": {
        "fuzzy_threshold": 0.78,
        "exact_bonus": 0.05,
        "album_match_bonus": 0.04,
        "use_year": False,  # when true include year token (if available) in normalization / scoring
        "duration_tolerance": 2.0,  # seconds tolerance for duration-based filtering (±2s default)
        "strategies": ["sql_exact", "duration_filter", "fuzzy"],  # ordered list of matching strategies to apply
        "show_unmatched_tracks": 20,  # number of unmatched tracks to show in debug output
        "show_unmatched_albums": 20,  # number of unmatched albums to show in debug output
    },
    "export": {
        "directory": "export/playlists",
        "mode": "strict",  # strict | mirrored | placeholders
        "placeholder_extension": ".missing",
        "organize_by_owner": False,  # when true, organize playlists into folders by owner
    },
    "reports": {
        "directory": "export/reports",
    },
    "database": {
        "path": "data/spotify_sync.db",
        "pragma_journal_mode": "WAL",
    },
}


def deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Merge dict b into a (shallow copies) returning new dict.
    Nested dicts are merged recursively; other values override.
    """
    result = dict(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = deep_merge(result[k], v)  # type: ignore[arg-type]
        else:
            result[k] = v
    return result


def _load_dotenv(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, val = line.split('=', 1)
        key = key.strip()
        val = val.strip()
        # Strip inline comments starting with # unless inside quotes
        if '#' in val:
            in_single = False
            in_double = False
            result_chars = []
            for ch in val:
                if ch == "'" and not in_double:
                    in_single = not in_single
                elif ch == '"' and not in_single:
                    in_double = not in_double
                if ch == '#' and not in_single and not in_double:
                    break
                result_chars.append(ch)
            val = ''.join(result_chars).rstrip()
        # Remove wrapping quotes if present
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            if len(val) >= 2:
                val = val[1:-1]
        if key:
            values[key] = val
    return values


def load_yaml_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Config file {path} must contain a mapping at top level")
        return data  # type: ignore[return-value]


def load_config(explicit_file: str | None = None, overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Load configuration merging defaults <- file <- .env <- environment <- overrides.

    During test runs (detected via PYTEST_CURRENT_TEST) .env loading is skipped
    unless SPX_ENABLE_DOTENV=1 is set to allow deterministic defaults.
    """
    dotenv_values: Dict[str, str] = {}
    if os.environ.get('SPX_ENABLE_DOTENV') or not os.environ.get('PYTEST_CURRENT_TEST'):
        dotenv_values = _load_dotenv(Path('.env'))
    # Deep copy defaults to avoid cross-call mutation of nested dicts
    cfg: Dict[str, Any] = copy.deepcopy(_DEFAULTS)
    file_candidates = []
    if explicit_file:
        file_candidates.append(Path(explicit_file))
    else:
        file_candidates.extend([Path("config.yaml"), Path("config.yml")])
    for candidate in file_candidates:
        if candidate.exists():
            cfg = deep_merge(cfg, load_yaml_file(candidate))
            break
    prefix = "SPX__"
    # Merge .env and real environment (real env wins)
    combined = {**{k: v for k, v in dotenv_values.items() if k.startswith(prefix)},
                **{k: v for k, v in os.environ.items() if k.startswith(prefix)}}
    for raw_key, value in combined.items():
        path_parts = raw_key[len(prefix):].split("__")
        cursor: Dict[str, Any] = cfg
        for part in path_parts[:-1]:
            cursor = cursor.setdefault(part.lower(), {})  # type: ignore[assignment]
        cursor[path_parts[-1].lower()] = coerce_scalar(value)
    if overrides:
        cfg = deep_merge(cfg, overrides)
    # If top-level debug true, also reflect into process env SPX_DEBUG for modules using it directly
    if cfg.get('debug') and not os.environ.get('SPX_DEBUG'):
        os.environ['SPX_DEBUG'] = '1'
    return cfg


def coerce_scalar(value: str) -> Any:
    txt = value.strip()
    # JSON object or array
    if (txt.startswith('[') and txt.endswith(']')) or (txt.startswith('{') and txt.endswith('}')):
        try:
            return json.loads(txt)
        except Exception:
            pass  # fall through to scalar heuristics
    lower = txt.lower()
    if lower in {"true", "yes", "1"}:
        return True
    if lower in {"false", "no", "0"}:
        return False
    # int
    try:
        if txt.isdigit() or (txt.startswith("-") and txt[1:].isdigit()):
            return int(txt)
    except Exception:
        pass
    # float
    try:
        return float(txt)
    except Exception:
        return txt

__all__ = ["load_config", "deep_merge"]
