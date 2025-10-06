from __future__ import annotations
import os
import json
import logging
from typing import Any, Dict
from pathlib import Path
import copy

try:
    from .config_types import TypedConfigDict
except ImportError:
    # Fallback for tests or when types not yet available
    TypedConfigDict = dict  # type: ignore

_DEFAULTS: Dict[str, Any] = {
    "log_level": "INFO",
    "provider": "spotify",
    "spotify": {
        "client_id": None,
        "redirect_scheme": "http",
        "redirect_host": "127.0.0.1",
        "redirect_port": 9876,
        "redirect_path": "/callback",
        "scope": "user-library-read playlist-read-private playlist-read-collaborative",
        "cache_file": "tokens.json",
        "cert_file": "cert.pem",
        "key_file": "key.pem",
    },
    "library": {
        "paths": ["music"],
        "extensions": [".mp3", ".flac", ".m4a", ".ogg"],
        "follow_symlinks": False,
        "ignore_patterns": [".*"],
        "skip_unchanged": True,
        "fast_scan": True,
        "commit_interval": 100,
        "min_bitrate_kbps": 320,
    },
    "matching": {
        "fuzzy_threshold": 0.78,
        "use_year": False,
        "duration_tolerance": 2.0,
        "strategies": ["sql_exact", "album_match", "year_match", "duration_filter", "fuzzy"],
        "show_unmatched_tracks": 20,
        "show_unmatched_albums": 20,
    },
    "export": {
        "directory": "export/playlists",
        "mode": "strict",
        "placeholder_extension": ".missing",
        "organize_by_owner": False,
    },
    "reports": {"directory": "export/reports"},
    "database": {"path": "data/spotify_sync.db", "pragma_journal_mode": "WAL"},
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


def load_config(explicit_file: str | None = None, overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Load configuration merging defaults <- .env <- environment <- overrides.

    During test runs (detected via PYTEST_CURRENT_TEST) .env loading is skipped
    unless PSM_ENABLE_DOTENV=1 is set to allow deterministic defaults.

    Args:
        explicit_file: Ignored; retained only for backward compatibility with older call sites.
        overrides: Dict of values to deep-merge last (primarily for tests).

    Returns:
        dict: Configuration dictionary (for typed access use load_typed_config()).
    """
    dotenv_values: Dict[str, str] = {}
    if os.environ.get('PSM_ENABLE_DOTENV') or not os.environ.get('PYTEST_CURRENT_TEST'):
        dotenv_values = _load_dotenv(Path('.env'))
    # Deep copy defaults to avoid cross-call mutation of nested dicts
    cfg: Dict[str, Any] = copy.deepcopy(_DEFAULTS)
    
    # explicit_file parameter intentionally ignored (legacy signature retained)
    
    # Environment variable prefix (legacy project prefix was different; now standardized on PSM__)
    prefix = "PSM__"
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
    
    # Configure logging based on log_level
    _configure_logging(cfg.get('log_level', 'INFO'))
    
    return cfg


def load_typed_config(explicit_file: str | None = None, overrides: Dict[str, Any] | None = None):
    """Load configuration as typed AppConfig object.
    
    This provides type-safe access to configuration with IDE autocomplete support.
    For backward compatibility, use load_config() which returns a dict.
    
    Args:
        explicit_file: Kept for compatibility, not used
        overrides: Dictionary of override values
        
    Returns:
        AppConfig: Typed configuration object with .to_dict() for dict conversion
    """
    from .config_types import AppConfig
    dict_config = load_config(explicit_file, overrides)
    return AppConfig.from_dict(dict_config)


def _configure_logging(level_str: str) -> None:
    """Configure Python logging based on configured level."""
    level_str = level_str.upper()
    level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL,
    }
    level = level_map.get(level_str, logging.INFO)
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        format='%(message)s',  # Simple format - just the message
        force=True  # Reconfigure even if already configured
    )


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

__all__ = ["load_config", "deep_merge", "load_typed_config"]
