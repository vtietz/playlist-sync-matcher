---
applyTo: '**'
---
# User Memory

## User Preferences
- Programming languages: Python focus
- Code style preferences: Modular small files, test-driven increments
- Development environment: Windows (run.bat convenience), virtualenv
- Communication style: Concise, actionable, progress updates

## Project Context
- Current project type: CLI tool for Spotify to local library sync & playlist export
- Tech stack: Python 3.11+, sqlite3, click, requests, mutagen, rapidfuzz, tenacity, PyYAML, rich
- Architecture patterns: Modular packages (auth, ingest, match, export, reporting, utils)
- Key requirements: Missing tracks report, mirrored playlists (future), incremental sync, config layering

## Coding Patterns
- Prefer explicit helper functions (deep_merge, partial_hash, normalization)
- Use dataless simple dicts initially; may evolve to dataclasses
- Tests for each utility before broad integration
- CLI with click grouping

## Context7 Research History
- Libraries researched: click, requests, mutagen, rapidfuzz (token_set_ratio), tenacity (retry/backoff), PyYAML (safe_load), rich (console logging)
- Best practices: safe YAML loading, explicit normalization, retry with exponential backoff on 429, separate normalization before fuzzy scoring
- Implementation patterns: token_set_ratio/100 for 0-1 score; environment variable deep overrides using double underscore

## Conversation History
- Phase 1 scaffold implemented (config, db, utils, match engine, ingest skeleton, export strict, reporting, CLI, tests)
- Pending enhancements: advanced export modes, incremental snapshots, extended reports, token refresh

## Notes
- Add license file later
- Future: caching tokens.json, efficient batch upserts, improved scoring thresholds
