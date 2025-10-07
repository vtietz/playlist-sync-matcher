Project assessment: lines of code, tasks, complexity, and effort estimate

Measured LOC so far (by inspected files)
- Core/platform:
  - [psm/providers/base.py](psm/providers/base.py) 251
  - [psm/providers/links.py](psm/providers/links.py) 42
  - [psm/providers/spotify/auth.py](psm/providers/spotify/auth.py) 303
  - [psm/providers/spotify/ingestion.py](psm/providers/spotify/ingestion.py) 273
  - [psm/providers/spotify/provider.py](psm/providers/spotify/provider.py) 151
  - [psm/ingest/library.py](psm/ingest/library.py) 329
  - [psm/export/playlists.py](psm/export/playlists.py) 139
  - [psm/db.py](psm/db.py) 285
  - [psm/db/interface.py](psm/db/interface.py) 84
  - [psm/db/sqlite_impl.py](psm/db/sqlite_impl.py) 267
  - [psm/utils/fs.py](psm/utils/fs.py) 27
  - [psm/utils/hashing.py](psm/utils/hashing.py) 32
  - [psm/utils/normalization.py](psm/utils/normalization.py) 48
  - [psm/utils/output.py](psm/utils/output.py) 154
  - [psm/utils/logging_helpers.py](psm/utils/logging_helpers.py) 89
  - [psm/config.py](psm/config.py) 267
  - [psm/config_types.py](psm/config_types.py) 206
  - [psm/version.py](psm/version.py) 9
  Subtotal core: 2,956 LOC

- Reporting (CSV/HTML reports and templates):
  - [psm/reporting/generator.py](psm/reporting/generator.py) 291
  - [psm/reporting/html_templates.py](psm/reporting/html_templates.py) 637
  - [psm/reporting/formatting.py](psm/reporting/formatting.py) 247
  - [psm/reporting/reports/base.py](psm/reporting/reports/base.py) 76
  - [psm/reporting/reports/matched_tracks.py](psm/reporting/reports/matched_tracks.py) 192
  - [psm/reporting/reports/unmatched_tracks.py](psm/reporting/reports/unmatched_tracks.py) 135
  - [psm/reporting/reports/unmatched_albums.py](psm/reporting/reports/unmatched_albums.py) 158
  - [psm/reporting/reports/playlist_coverage.py](psm/reporting/reports/playlist_coverage.py) 117
  - [psm/reporting/reports/playlist_detail.py](psm/reporting/reports/playlist_detail.py) 188
  - [psm/reporting/reports/album_completeness.py](psm/reporting/reports/album_completeness.py) 90
  - [psm/reporting/reports/metadata_quality.py](psm/reporting/reports/metadata_quality.py) 153
  - [psm/reporting/reports/__init__.py](psm/reporting/reports/__init__.py) 19
  Subtotal reporting: 2,303 LOC

- Tests and utilities used during assessment:
  - [tests/integration/test_report_command.py](tests/integration/test_report_command.py) 77
  - [tests/integration/test_cli_match_lock.py](tests/integration/test_cli_match_lock.py) 36
  - [tests/integration/test_year_and_diagnose.py](tests/integration/test_year_and_diagnose.py) 86
  - [tests/integration/test_playlist_popularity.py](tests/integration/test_playlist_popularity.py) 120
  - [tests/conftest.py](tests/conftest.py) 86
  - [test_db.py](test_db.py) 30
  Subtotal tests: 435 LOC

Measured total (36 files): ≈ 5,694 LOC

Additional modules present but not line-counted in this pass (estimated)
- CLI commands and helpers (core group, playlist subcommands, helpers): ≈ 650–850 LOC
  - Examples: psm/cli/core.py, psm/cli/helpers.py, psm/cli/playlist_cmds.py, psm/cli/playlists.py
- Service layer orchestration (pull, match, analysis, export, playlist ops, push): ≈ 1,200–1,600 LOC
  - Examples: psm/services/pull_service.py, psm/services/match_service.py, psm/services/analysis_service.py, psm/services/export_service.py, psm/services/playlist_service.py, psm/services/push_service.py
- Matching subsystem (scoring engine, legacy engine + strategies): ≈ 1,100–1,400 LOC
  - Examples: psm/match/scoring.py, psm/match/engine.py, psm/match/strategies/*.py
- Spotify API client: ≈ 300–450 LOC
  - Example: psm/providers/spotify/client.py

Estimated project size overall
- Code (Python): ≈ 9,500–10,500 LOC
- Tests (measured and assumed parity additions): ≈ 500–800 LOC
- Assets (HTML/CSS inside Python templates) are included above

System architecture overview (data flow)
- CLI: command group invokes services; commands include pull/login/scan/match/analyze/report/export/build/push. Example entry: psm/cli/core.py
- Services: orchestrate provider auth, ingestion, matching, reporting, export, and push. Example: psm/services/match_service.py
- Provider layer: abstracts auth/client; concrete Spotify provider implements OAuth PKCE and API client. Examples: [psm/providers/spotify/auth.py](psm/providers/spotify/auth.py), psm/providers/spotify/client.py, [psm/providers/spotify/provider.py](psm/providers/spotify/provider.py), [psm/providers/base.py](psm/providers/base.py)
- Database: SQLite with WAL and indices; explicit read/write APIs. Examples: [psm/db/sqlite_impl.py](psm/db/sqlite_impl.py), [psm/db/interface.py](psm/db/interface.py)
- Matching: token normalization, duration tolerance prefiltering, ISRC bonus, confidence tiers; legacy fuzzy strategies for single-playlist flows. Examples: psm/match/scoring.py, psm/match/engine.py
- Reporting: CSV + HTML reports (DataTables UI), playlist detail pages, dashboard index. Examples: [psm/reporting/generator.py](psm/reporting/generator.py), [psm/reporting/html_templates.py](psm/reporting/html_templates.py)
- Export/Push: M3U8 export modes (strict/mirrored/placeholders) and Spotify playlist replacement preview/apply. Examples: [psm/export/playlists.py](psm/export/playlists.py)

Mermaid diagram
```mermaid
flowchart LR
  CLI[CLI commands] --> Services[Service layer]
  Services --> DB[(SQLite DB)]
  Services --> Matching[Matching engines]
  Services --> Reporting[Report generators]
  Services --> Export[M3U8 Export]
  Services --> Push[Playlist Push]
  Services --> Provider[Provider (Spotify)]
  Provider --> Auth[OAuth PKCE]
  Provider --> API[Spotify API Client]
  Matching --> DB
  Reporting --> DB
  Export --> FS[Filesystem]
  Push --> API
```

Complexity and risk assessment
- OAuth and local callback server
  - Complexity: medium. Handling PKCE, local HTTP/HTTPS callback, token refresh, cache, timeouts, and optionally self-signed certificates for HTTPS.
  - Risk: dev environment variability (ports, firewalls, browsers), certificate generation and trust. Reference: [psm/providers/spotify/auth.py](psm/providers/spotify/auth.py)
- Spotify ingestion
  - Complexity: medium. Pagination, snapshot-based incremental playlist updates, liked tracks boundary conditions, normalization with optional year token, owner metadata, idempotency.
  - Risk: API rate limits/changes; consistent snapshot detection; partial data robustness. Reference: [psm/providers/spotify/ingestion.py](psm/providers/spotify/ingestion.py)
- Library scan
  - Complexity: medium. Fast vs full scan, metadata extraction via mutagen across formats, bitrate heuristics, path normalization and deletion detection, Windows vs POSIX paths, progress logging, batching commits.
  - Risk: performance on large libraries; edge-case tags; symlink/permission handling. Reference: [psm/ingest/library.py](psm/ingest/library.py)
- Matching engines
  - Complexity: high. Scoring engine (token normalization, version/feat/remaster stripping, duration-tier bonuses, ISRC boost, Jaccard pre-ranking) alongside legacy strategy pipeline (SQL exact, duration filter, fuzzy token_set_ratio, album/year exacts).
  - Risk: false positives/negatives, performance with many candidates, maintaining two pathways (global scoring vs single-playlist legacy) until convergence. References: psm/match/scoring.py, psm/match/engine.py
- Database design and concurrency
  - Complexity: medium. Provider-namespaced schema, composite keys, indices, WAL mode, lock handling diagnostics, incremental migrations for additive columns.
  - Risk: long-running transactions and external tools causing locks; backward compat of schema evolution. Reference: [psm/db/sqlite_impl.py](psm/db/sqlite_impl.py)
- Reporting and HTML templates
  - Complexity: medium. Multi-report generation, CSV/HTML parity, DataTables UX, cross-linking with provider URLs, playlist detail subpages, dashboard.
  - Risk: large datasets in browser tables; CSV/HTML consistency; encoding/path display. References: [psm/reporting/generator.py](psm/reporting/generator.py), [psm/reporting/html_templates.py](psm/reporting/html_templates.py)
- Export (M3U) and Push (write operations)
  - Complexity: medium. Export order fidelity, placeholder file management, sanitized filenames, owner-based organization; Push with diff/replace ordering, chunking, ownership and safety checks.
  - Risk: cross-platform path correctness; playlist ordering semantics; API change/error handling. Reference: [psm/export/playlists.py](psm/export/playlists.py)
- CLI UX and workflows
  - Complexity: low-medium. Many commands with shared config/db lifecycle and safety checks; printed diagnostics; selective report generation switch support.
  - Risk: cohesive UX, idempotence, clear error messages.

Development task breakdown (from scratch, without AI)
- Foundations and scaffolding (repo setup, configuration system, logging, packaging)
  - Define defaults, env/.env loader, typed config, logging levels. Reference: [psm/config.py](psm/config.py), [psm/config_types.py](psm/config_types.py)
  - Effort: 0.5–1.0 week
- Provider abstraction and Spotify implementation
  - Provider interfaces, link generators, OAuth PKCE, token cache/refresh, minimal client with retries/rate-limit handling.
  - Effort: 1.5–2.0 weeks
- Database schema and data access
  - Schema with indices, provider namespacing, migrations (additive), explicit DAOs, WAL and lock diagnostics.
  - Effort: 0.8–1.2 weeks
- Ingestion
  - Spotify playlists and liked tracks ingestion, snapshot detection, normalization/year token, owner fields, counts/progress.
  - Effort: 1.0–1.5 weeks
- Local library scan
  - Iteration, tag extraction, duration/bitrate, partial hash, skip-unchanged, deletion detection, progress, batch commits.
  - Effort: 1.0–1.5 weeks
- Matching subsystem
  - Normalization rules, scoring engine with confidence tiers; duration prefilter, Jaccard pre-ranking; legacy strategies for early correctness; diagnostics.
  - Effort: 2.0–3.0 weeks
- Services orchestration and CLI
  - End-to-end workflows: pull, scan, match, analyze, export, report, build, push; shared helpers; idempotence.
  - Effort: 1.0–1.5 weeks
- Reporting
  - CSV + HTML templates with DataTables; matched/unmatched tracks, unmatched albums, playlist coverage, playlist details, metadata quality; index dashboard.
  - Effort: 1.0–1.5 weeks
- Export and Push
  - M3U modes (strict/mirrored/placeholders), filename sanitize, owner org; push preview/apply with chunking and diffs.
  - Effort: 1.0–1.5 weeks
- Testing and QA
  - Unit tests for normalization, matching, ingestion; integration tests for CLI commands and reports; test fixtures and isolation.
  - Effort: 1.5–2.0 weeks
- Hardening and polish
  - Cross-platform path handling, error surfacing, retries/backoff, performance tuning (indices, batch sizes), docs and examples.
  - Effort: 0.8–1.2 weeks

Aggregate effort estimate (person-weeks)
- Sum (typical): 12–16 person-weeks
  - Lower bound assumes reuse of known patterns, minimal surprises, and steady scope
  - Upper bound includes time for debugging API edge cases, matching tuning, and HTML/report polish

Small-team calendar estimate (without AI)
- With 3 developers in parallel: 5–7 calendar weeks
  - Critical path overlaps: provider+DB+ingest can proceed in parallel with CLI skeleton; matching starts after scan/ingest shape known; reporting follows DB shape; push/export can parallelize late
- With 2 developers: 7–10 calendar weeks
- With 4 developers (1 part-time QA): 4–6 calendar weeks

Risk multipliers and contingencies
- Low risk context (clear requirements, stable API, experienced team): 0.8× (≈ 10–13 person-weeks)
- Moderate risk (typical): 1.0× (≈ 12–16 person-weeks)
- Higher risk (large libraries, cross-platform edge cases, stricter push semantics): 1.2–1.3× (≈ 14–21 person-weeks)

Primary complexity hotspots to watch
- Matching accuracy versus performance on large libraries (candidate pruning, indexing)
- OAuth HTTPS local callback and certificate handling on locked-down environments
- SQLite locking when multiple processes/tools open the DB; keep WAL, short transactions, and informative diagnostics (see [psm/db/sqlite_impl.py](psm/db/sqlite_impl.py))
- HTML DataTables scalability for very large outputs (consider CSV-first, paginated HTML, or summary-first drilldowns)
- Push safety (ownership, ordering guarantees, partial failure retries)

Scope reduction levers if needed
- Start with read-only features: ingest, scan, match, report, export; postpone push
- Use one matching engine (scoring) across both global and single-playlist paths from day one
- Simplify reports initially to CSV-only, add HTML after core correctness
- Restrict OAuth to HTTP-only for dev; defer HTTPS and cert automation to later

Summary
- The project is roughly 9.5–10.5k LOC of Python with moderate-to-high complexity in matching, robust ingestion, and reporting UX, plus a medium-complex OAuth/client layer.
- A small team without AI should plan for approximately 12–16 person-weeks, translating to 5–7 calendar weeks for 3 developers, with risks potentially expanding to 14–21 person-weeks depending on environment variability, matching quality targets, and write-path (push) robustness.