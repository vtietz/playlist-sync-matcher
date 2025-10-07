# Test Pyramid Migration Plan

Status: Draft (Ready for Execution)
Owner: Engineering
Last Updated: 2025-10-07
Related Files: `psm/db.py`, `psm/services/*`, `tests/`

## 1. Goals

Transform the current integration-heavy test suite into a proper test pyramid to improve:
- Feedback speed (fast unit tests without I/O)
- Test isolation and reliability
- Maintainability and refactor safety
- Clarity of responsibility between layers (DB vs Services vs Logic)

## 2. Target Distribution
| Layer | Target % | Purpose | Uses Real DB | External I/O |
|-------|----------|---------|--------------|--------------|
| Unit | ~70% | Pure logic & orchestration | No (mock DB) | No |
| Integration | ~20% | DB + service interactions | Yes | No (network stubbed) |
| E2E | ~10% | Full workflows via CLI | Yes | No (provider/network stubbed) |

Note: Real network calls remain forbidden in tests. Spotify API interactions must be stubbed/mocked.

## 3. Current State (Baseline)
- 117 tests, majority instantiate `Database` directly
- Very few pure unit tests (`normalization`, `scoring` helpers)
- No explicit E2E boundary (some CLI tests approximate partial flows)
- No standardized mocking layer for DB or provider clients
- Test runtime: ~7–8s (acceptable now, but unit isolation enables scale)

## 4. Strategy Overview
1. Introduce a `DatabaseInterface` abstraction
2. Provide an in-memory `MockDatabase` for unit tests
3. Refactor service layer function signatures to accept `DatabaseInterface`
4. Reclassify and relocate tests into `unit/`, `integration/`, `e2e/`
5. Add Pytest markers (`unit`, `integration`, `e2e`, `slow`)
6. Add provider/client stubs for ingestion and push flows
7. Introduce lightweight test data factories
8. Remove legacy direct DB coupling in logic where not required
9. Remove transitional compatibility code once migration complete

## 5. Scope of Change
| Area | Change Type | Notes |
|------|-------------|-------|
| `psm/db.py` | Add interface inheritance only | No behavior change |
| `psm/db/interface.py` | New | Abstract contract |
| `tests/mocks/mock_database.py` | New | In-memory mock |
| `services/*` | Type hint update only | No logic change expected |
| `tests/` | Restructure | Physical relocation + markers |
| `pytest.ini` | Marker declarations | Non-breaking |

## 6. Detailed Phases & Tasks

### Phase 1: Foundations (Interface + Mock)
- [x] Create `psm/db/interface.py` with `DatabaseInterface`
- [x] Make `Database` implement `DatabaseInterface` (converted `psm/db.py` to package, implementation in `psm/db/sqlite_impl.py`)
- [x] Implement `MockDatabase` (in-memory dict/list structures) at `tests/mocks/mock_database.py`
- [x] Provide method parity for all used service paths (playlist, tracks, library, matches, counters)
- [ ] Add `tests/mocks/fixtures.py` with reusable fixtures (pending)

### Phase 2: Service Layer DI (Dependency Injection)
- [ ] Update imports in: `pull_service.py`, `match_service.py`, `export_service.py`, `playlist_service.py`, `analysis_service.py`, `push_service.py`
- [ ] Replace `Database` type hints → `DatabaseInterface`
- [ ] Ensure `__all__` exports remain stable
- [ ] Add docstring note: "Accepts any DatabaseInterface implementation"
- [ ] Run full test suite (`run.bat py -m pytest`) to validate no regression

### Phase 3: Test Infrastructure
- [ ] Create directory tree:
  ```
  tests/unit/
  tests/integration/
  tests/e2e/
  tests/mocks/
  ```
- [ ] Add `pytest.ini` markers:
  ```ini
  markers =
      unit: Unit tests with mocked dependencies
      integration: Integration tests with real sqlite database
      e2e: Full workflow tests (CLI)
      slow: Longer-running tests
  ```
- [ ] Add root-level `tests/README.md` with execution guidance
- [ ] Introduce factory helpers (e.g., `make_track()`, `make_file()`, `make_playlist()`).

### Phase 4: Test Migration (Incremental)
- [ ] Identify pure logic candidates (matching, normalization, scoring filtering) → move to `tests/unit/`
- [ ] Rewrite service orchestration tests to use `MockDatabase`
- [ ] Keep schema + SQL validation inside `tests/integration/`
- [ ] Create initial 2 E2E tests:
  - `psm build` end-to-end with stubbed provider
  - `psm playlist build <id>` flow
- [ ] Add provider stubs (e.g., `MockSpotifyClient`) returning deterministic data
- [ ] Ensure no unit test imports the concrete `Database`

### Phase 5: Cleanup & Consolidation
- [ ] Remove any temporary adapter/shim functions introduced for migration
- [ ] Delete obsolete direct DB test code moved to unit level
- [ ] Validate no dead imports (run lint/check)
- [ ] Confirm service modules free of concrete DB-only assumptions

### Phase 6: Hardening & Documentation
- [ ] Measure layer distribution (# tests per marker)
- [ ] Add coverage report; ensure ≥90% logic coverage outside DB plumbing
- [ ] Document mocking patterns in `docs/development.md`
- [ ] Add CI matrix stages (fast unit vs full suite)
- [ ] Final removal of any conditional/backward-compat code

## 7. Success Criteria (Acceptance)
| Criterion | Target |
|-----------|--------|
| Unit Tests Share (%) | ≥ 65% (stretch 70%) |
| Integration Count | ≤ 25% total tests |
| E2E Coverage | Build + Single playlist + Reporting workflows |
| Avg Unit Runtime | < 0.5s per 100 tests |
| No Network Calls | Verified via stubbed clients |
| DB-Free Unit Tests | 100% pass without touching filesystem |
| Coverage (core logic) | ≥ 90% (excluding CLI, DB schema) |

## 8. Risk & Mitigation
| Risk | Impact | Mitigation |
|------|--------|------------|
| Interface drift (DB vs Mock) | Test flakiness | Add parity test asserting attribute/method set |
| Hidden coupling in services | Refactor delay | Start with read paths first, then write ops |
| Over-mocking reduces confidence | False positives | Balance with integration coverage for DB-specific behavior |
| CI config drift | Pipeline failures | Add staged jobs early |

## 9. Rollback Strategy
If instability arises:
1. Revert service signature changes (keep interface file for future).
2. Retain relocated tests but mark mock-based ones `xfail` temporarily.
3. Re-run full suite using original structure.
Rollback risk is low—changes are largely additive until Phase 5.

## 10. Execution Order (High-Level Checklist)
```
[x] Phase 1 complete (interface + mock + parity test)  
[ ] Phase 2 complete (services accept interface)
[ ] Phase 3 infra ready (markers + structure)
[ ] ≥20 tests migrated to unit
[ ] E2E baseline added
[ ] Integration tests curated
[ ] Legacy direct-DB unit tests removed
[ ] Coverage & distribution validated
[ ] Docs updated (development & architecture)
[ ] CI pipeline split (unit fast path)
[ ] Backward compatibility shims removed
```

## 11. Example Command Matrix
Run always through project wrapper (`run.bat`) to ensure venv + deps.
```cmd
:: Full suite
run.bat py -m pytest -q

:: Unit only (fast inner loop)
run.bat py -m pytest tests/unit -m unit -q

:: Integration only
run.bat py -m pytest tests/integration -m integration -q

:: E2E only (slower)
run.bat py -m pytest tests/e2e -m e2e -q

:: With coverage (future enhancement)
run.bat py -m pytest --cov=psm --cov-report=term-missing
```

## 12. Post-Migration Deletions (No Legacy Left Behind)
- Remove any transitional helper referencing old concrete DB patterns
- Ensure no lingering imports: `from psm.db import Database` inside unit test paths
- Remove any temporary stub duplication (centralize in `tests/mocks/`)

## 13. Future Enhancements (Optional)
- Property-based tests for fuzzy scoring heuristics
- Mutation testing on normalization logic
- Contract tests ensuring provider client stub fidelity
- Parallel test execution (pytest-xdist) once layering stabilized

## 14. Sign-off Checklist Before Declaring Done
| Item | Status |
|------|--------|
| Test layer distribution measured | Pending |
| Mock DB parity test added | Pending |
| Docs updated (`development.md`) | Pending |
| CI pipeline updated | Pending |
| Legacy code removal verified | Pending |
| Coverage threshold met | Pending |

---
This document is the authoritative reference for the test pyramid migration. Update sections in-place as phases complete (do not create duplicates).