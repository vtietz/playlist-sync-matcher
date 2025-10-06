# Architecture

This document expands on the concise overview in the README.

## Layers

- CLI (psm/cli package): Argument parsing & command wiring only (thin). `psm/cli.py` is now removed; entry point logic lives under `psm/cli/` modules (`helpers.py`, `core.py`, `playlists.py`, `playlist_cmds.py`).
- Services (psm/services/*): Orchestrate workflows (pull, scan, match, export, reporting).
- Providers (psm/providers/*): Abstraction layer for streaming sources. Registry based.
- Match Engine (psm/match/*): Strategy pipeline; order configured via config.
- Persistence (psm/db.py): SQLite schema v1 (provider namespaced) + helper methods.
- Utilities (psm/utils/*): Normalization, hashing, filesystem helpers.

## Provider Abstraction

`ProviderClient` protocol defines minimum surface (user profile, playlists, playlist items). New providers register via `@register` decorator and appear through `available_providers()`.

`ProviderCapabilities` advertises optional features (future: search, batch add, isrc_lookup, extended audio features).

## Database Schema (v1)

Key design:
- Composite primary keys `(id, provider)` for `tracks` and `playlists` allow identical IDs from multiple providers.
- `playlist_tracks` keyed by `(playlist_id, provider, position)`; preserves order per provider.
- `library_files` stores extracted tags; includes `year` and `bitrate_kbps` for quality analysis.
- `matches` maps streaming tracks to local files by provider.
- `meta(schema_version=1)` recorded on init.

Indices: `tracks(isrc)`, `tracks(normalized)`, `library_files(normalized)`.

## Matching Pipeline

Strategies run sequentially until all matched or strategies exhausted:
1. `sql_exact` (fast normalized lookup)  
2. `album_match`  
3. `year_match`  
4. `duration_filter` (candidate pruning)  
5. `fuzzy` (RapidFuzz token similarity)

Each strategy can mark matches; unmatched set shrinks between steps.

## Performance Considerations

- LRU caching for normalization.
- Fast scan: skip unchanged library files by mtime+size.
- Batched DB commits (configurable).
- Indexed normalized fields to accelerate lookups & fuzzy candidate narrowing.

## Concurrency & Database Safety

The database uses SQLite's **Write-Ahead Logging (WAL)** mode, which provides safe concurrent access:

**Implementation**:
```python
# psm/db.py
SCHEMA = [
    "PRAGMA journal_mode=WAL;",  # Enable WAL mode
    # ... table definitions
]

# Connection with automatic retry on lock conflicts
self.conn = sqlite3.connect(path, timeout=30)
```

**Benefits**:
- Multiple processes can read simultaneously
- Readers don't block writers and vice versa
- Automatic retry on transient lock conflicts (30-second timeout)
- No custom locking code needed - SQLite handles it

**Safe concurrent patterns**:
- ✅ `pull` + `scan` in parallel (different tables)
- ✅ `scan` + `match` in parallel (match reads library_files, scan writes it)
- ✅ Multiple `scan` processes on different paths
- ✅ `pull` + `match` in parallel (pull writes tracks, match reads them)

**Isolation semantics**:
- Operations see a consistent snapshot of data at the time they start
- Changes from concurrent operations become visible after they commit
- No partial/torn reads or writes

**No explicit locking required**: Previous implementation used a custom `DatabaseLock` with polling, which has been removed in favor of relying entirely on SQLite's built-in WAL concurrency.

## Configuration Model

Environment-first loading:
1. Start with in-code defaults.
2. Optionally merge `.env` (only if `PSM_ENABLE_DOTENV=1`).
3. Deep‑merge any real environment variables with prefix `PSM__` (section/key separated by double underscores, e.g. `PSM__DATABASE__PATH`).
4. Parse JSON-ish scalar/list/dict strings into native types.

Immutability goal: Callers receive a plain nested dict; mutation by consumers is discouraged—prefer passing explicit overrides to loaders for tests.

## Future Evolution

- Cross‑provider canonical track table keyed by ISRC + variant metadata.
- Rate limiting middleware & unified error taxonomy.
- Playlist cloning between providers.
- Enriched audio feature matching (tempo/key) where supported.
