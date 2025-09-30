from __future__ import annotations
import os
import yaml
from typing import Any, Dict
from pathlib import Path

_DEFAULTS: Dict[str, Any] = {
    "spotify": {
        "client_id": None,
        "redirect_port": 9876,
        "redirect_path": "/callback",  # can change to '/' if Spotify dashboard rejects
        "scope": "user-library-read playlist-read-private playlist-read-collaborative",
        "cache_file": "tokens.json",
    },
    "library": {
        "paths": ["music"],
        "extensions": [".mp3", ".flac", ".m4a", ".ogg"],
        "follow_symlinks": False,
        "ignore_patterns": [".*"],
    },
    "matching": {
        "fuzzy_threshold": 0.78,
        "exact_bonus": 0.05,
        "album_match_bonus": 0.04,
    },
    "export": {
        "directory": "export/playlists",
        "mode": "strict",  # strict | mirrored | placeholders
        "placeholder_extension": ".missing",
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


def load_yaml_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Config file {path} must contain a mapping at top level")
        return data  # type: ignore[return-value]


def load_config(explicit_file: str | None = None, overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Load configuration merging defaults <- file <- environment <- overrides.

    Environment variables are prefixed with SPX__ and use double underscores to
    traverse nesting, e.g. SPX__EXPORT__MODE=mirrored.
    """
    cfg: Dict[str, Any] = dict(_DEFAULTS)

    # File
    file_candidates = []
    if explicit_file:
        file_candidates.append(Path(explicit_file))
    else:
        file_candidates.extend([Path("config.yaml"), Path("config.yml")])

    for candidate in file_candidates:
        if candidate.exists():
            cfg = deep_merge(cfg, load_yaml_file(candidate))
            break

    # Environment overrides
    prefix = "SPX__"
    env_pairs = {k: v for k, v in os.environ.items() if k.startswith(prefix)}
    for raw_key, value in env_pairs.items():
        # Split on double underscore after prefix
        path_parts = raw_key[len(prefix):].split("__")
        cursor: Dict[str, Any] = cfg
        for part in path_parts[:-1]:
            cursor = cursor.setdefault(part.lower(), {})  # type: ignore[assignment]
        cursor[path_parts[-1].lower()] = coerce_scalar(value)

    # Explicit overrides (e.g., CLI)
    if overrides:
        cfg = deep_merge(cfg, overrides)

    return cfg


def coerce_scalar(value: str) -> Any:
    lower = value.lower()
    if lower in {"true", "yes", "1"}:
        return True
    if lower in {"false", "no", "0"}:
        return False
    # int
    try:
        if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
            return int(value)
    except Exception:
        pass
    # float
    try:
        return float(value)
    except Exception:
        return value

__all__ = ["load_config", "deep_merge"]
