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
- Push feature introduced new modules: psm/push/m3u_parser.py, psm/services/push_service.py
- Add license file later
- Future: caching tokens.json, efficient batch upserts, improved scoring thresholds
