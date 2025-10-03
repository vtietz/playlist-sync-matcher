# Architecture

This document expands on the concise overview in the README.

## Layers

- CLI (spx/cli package): Argument parsing & command wiring only (thin). `spx/cli.py` is now removed; entry point logic lives under `spx/cli/` modules (`helpers.py`, `core.py`, `playlists.py`, `playlist_cmds.py`).
- Services (spx/services/*): Orchestrate workflows (pull, scan, match, export, reporting).
- Providers (spx/providers/*): Abstraction layer for streaming sources. Registry based.
- Match Engine (spx/match/*): Strategy pipeline; order configured via config.
- Persistence (spx/db.py): SQLite schema v1 (provider namespaced) + helper methods.
- Utilities (spx/utils/*): Normalization, hashing, filesystem helpers.

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

## Future Evolution

- Cross‑provider canonical track table keyed by ISRC + variant metadata.
- Rate limiting middleware & unified error taxonomy.
- Playlist cloning between providers.
- Enriched audio feature matching (tempo/key) where supported.
