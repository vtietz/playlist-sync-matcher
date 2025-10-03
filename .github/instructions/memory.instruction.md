---
applyTo: '**'
---

# User Memory

## User Preferences
- Programming languages: Python
- Code style preferences: Minimal changes to existing files, service layer orchestration, dataclasses for structured returns
- Development environment: VS Code, Windows (cmd shell)
- Communication style: Concise, focused on actionable implementation

## Project Context
- Current project type: CLI tool for building local artifacts from Spotify playlists and local library (export/import prototype)
- Tech stack: Python (click, requests, sqlite3, rapidfuzz, mutagen)
- Architecture patterns: Service layer, provider abstraction, DB access encapsulation
- Key requirements: Multi-provider readiness, provider namespacing in DB, config hygiene, experimental push (single playlist) feature

## Coding Patterns
- Preferred patterns and practices: Thin CLI, services return structured objects, minimal speculative abstraction
- Code organization preferences: New features isolated in new modules to limit edits
- Testing approaches: Pytest with focused unit/integration tests; avoid network in tests (use stubs)
- Documentation style: High-level README + detailed docs in docs/ directory

## Context7 Research History
- (None performed – internal codebase changes only for push feature MVP)

## Conversation History
- Completed: Multi-provider scaffolding, DB refactor, configuration cleanup, export modes
- Pending (now implemented): Experimental push feature (preview + apply) supporting file and DB modes
- Safety constraints: Ownership enforcement, preview default, full replace only

## Notes
- Push feature introduced new modules: spx/push/m3u_parser.py, spx/services/push_service.py
- SpotifyClient extended with write methods (replace & add in batches) for future provider parity reference.---
applyTo: '**'
---
# User Memory

## User Preferences
- Programming languages: Python focus
- Code style preferences: Modular small files, test-driven increments
- Development environment: Windows (run.bat convenience), virtualenv
- Communication style: Concise, actionable, progress updates

## Project Context
- Current project type: CLI tool for building local playlist artifacts & playlist export
- Tech stack: Python 3.11+, sqlite3, click, requests, mutagen, rapidfuzz, tenacity, PyYAML, rich
- Architecture patterns: Modular packages (auth, ingest, match, export, reporting, utils)
- Key requirements: Missing tracks report, mirrored playlists (future), efficient build pipeline (pull/scan/match/export/report), config layering

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
