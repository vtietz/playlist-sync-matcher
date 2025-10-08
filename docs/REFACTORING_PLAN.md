# Refactoring Plan: Architecture Improvements

**Status**: In Progress  
**Started**: October 8, 2025  
**Target Completion**: October 22, 2025

## Overview

This refactoring addresses five core architectural issues while maintaining 100% backward compatibility:

1. **Presentation Separation**: Remove CLI styling from services/library modules
2. **Matching Logic Consolidation**: Eliminate duplication via MatchingEngine abstraction
3. **Export Path Correctness**: Record actual exported file paths, not constructed ones
4. **SQL Encapsulation**: Minimize raw SQL via repository layer
5. **Watch Loop Testability**: Extract loop logic and improve ignore pattern semantics

## Guiding Principles

- **Zero Functional Changes**: Users see identical behavior (except bug fixes)
- **All Tests Pass**: No PR merges with failing tests
- **Incremental Migration**: New modules coexist with old; migrate call sites gradually
- **Type Safety**: Add typed configs where beneficial, use adapters for backward compat

## Progress Tracking

### PR1: Presentation Separation ✅ Complete
**Status**: Complete (October 8, 2025)  
**Duration**: ~1 hour

**Scope**:
- [x] Remove `click.style`/`print()` from services
- [x] Remove `click.style`/`print()` from export helpers
- [x] Add styled banners in CLI commands
- [x] Verify no tests assert service-level styling

**Files Modified**:
- `psm/services/match_service.py` - Removed styled prints, using logger.info()
- `psm/services/export_service.py` - Removed styled prints, using logger.info()
- `psm/services/watch_build_service.py` - Removed styled prints, using logger.info()
- `psm/export/playlists.py` - Removed click dependency, using logger.debug()
- `psm/cli/core.py` - Added styled headers before service calls (match, export, build --watch)

**Test Results**:
- ✅ All 179 tests pass
- ✅ No functional changes to output
- ✅ Services now free of presentation logic

**Acceptance Criteria**:
- [x] No `click.style()` calls in `psm/services/` or `psm/export/`
- [x] CLI commands render banners before calling services
- [x] All existing tests pass (179/179)
- [x] Manual verification: terminal output formatting preserved

---

### PR2: ExportResult Path Correctness ⏸️ Not Started
**Status**: Blocked by PR1  
**Estimated Duration**: 1 day

**Scope**:
- [ ] Capture actual paths returned by export functions
- [ ] Update `export_playlists()` to record real `.m3u8` paths with IDs
- [ ] Verify consistency with `_export_liked_tracks()` handling

**Files to Modify**:
- `psm/services/export_service.py` - Fix `result.exported_files` recording

**Acceptance Criteria**:
- [ ] `result.exported_files` contains actual sanitized filenames with playlist IDs
- [ ] Integration tests in `tests/integration/test_export_modes.py` pass
- [ ] Integration tests in `tests/integration/test_liked_songs_export.py` pass

---

### PR3: CandidateSelector Utility ⏸️ Not Started
**Status**: Blocked by PR2  
**Estimated Duration**: 2 days

**Scope**:
- [ ] Create `psm/match/candidate_selector.py`
- [ ] Implement `duration_prefilter()` method
- [ ] Implement `token_prescore()` method (Jaccard similarity)
- [ ] Add unit tests for edge cases (duration window, cap ordering)
- [ ] Refactor `match_changed_tracks()` to use selector
- [ ] Refactor `match_changed_files()` to use selector

**Files to Create**:
- `psm/match/candidate_selector.py`
- `tests/unit/match/test_candidate_selector.py`

**Files to Modify**:
- `psm/services/match_service.py` - Use CandidateSelector in incremental methods

**Acceptance Criteria**:
- [ ] `CandidateSelector` unit tests pass (100% coverage on new code)
- [ ] `match_changed_tracks()` behavior unchanged (verified via integration tests)
- [ ] `match_changed_files()` behavior unchanged (verified via integration tests)
- [ ] Duration prefilter maintains ±4s minimum window logic

---

### PR4: MatchingEngine Class ⏸️ Not Started
**Status**: Blocked by PR3  
**Estimated Duration**: 3 days (split into 2 PRs if needed)

**Scope**:
- [ ] Create `psm/match/engine_service.py` or extend `psm/match/engine.py`
- [ ] Implement `MatchingEngine` class with `match_all()` method
- [ ] Implement `match_changed_tracks()` method on engine
- [ ] Implement `match_changed_files()` method on engine
- [ ] Extract confidence summary helper
- [ ] Add unit tests for engine methods
- [ ] Refactor `run_matching()` to delegate to engine
- [ ] Refactor incremental match services to delegate to engine

**Files to Create**:
- `psm/match/engine_service.py` (or extend existing `engine.py`)
- `tests/unit/match/test_matching_engine.py`

**Files to Modify**:
- `psm/services/match_service.py` - Delegate to MatchingEngine

**Acceptance Criteria**:
- [ ] MatchingEngine unit tests pass
- [ ] Full matching produces identical results (verify via integration tests)
- [ ] Incremental matching produces identical results
- [ ] Progress logging cadence unchanged
- [ ] Confidence summary display unchanged

**Note**: Consider splitting into:
- **PR4a**: Basic engine with `match_all()`
- **PR4b**: Incremental methods (`match_changed_tracks/files`)

---

### PR5: Typed Configs ⏸️ Not Started
**Status**: Blocked by PR4  
**Estimated Duration**: 2 days

**Scope**:
- [ ] Define `MatchingConfig` dataclass in `psm/config_types.py`
- [ ] Define `ExportConfig` dataclass in `psm/config_types.py`
- [ ] Implement `from_dict_matching(cfg_dict) -> MatchingConfig`
- [ ] Implement `from_dict_export(cfg_dict) -> ExportConfig`
- [ ] Update MatchingEngine to accept typed config (optional)
- [ ] Add type hints to service functions (gradual)
- [ ] Document adapter pattern for future configs

**Files to Modify**:
- `psm/config_types.py` - Add dataclasses and adapters
- `psm/services/match_service.py` - Optionally use typed config
- `psm/services/export_service.py` - Optionally use typed config

**Acceptance Criteria**:
- [ ] Dataclasses defined with correct types and defaults
- [ ] Adapter functions convert existing dict configs correctly
- [ ] No breaking changes to existing service signatures
- [ ] Documentation updated in `docs/configuration.md`

---

### PR6: Repository Layer (Read Queries) ⏸️ Not Started
**Status**: Blocked by PR4  
**Estimated Duration**: 3-4 days

**Scope**:
- [ ] Create `psm/db/repositories/` directory
- [ ] Implement `tracks_repository.py` (list_all_tracks, list_by_ids, list_unmatched)
- [ ] Implement `files_repository.py` (list_all_files, list_by_ids, find_by_path)
- [ ] Implement `matches_repository.py` (delete_for_tracks, delete_for_files, count_tiers)
- [ ] Implement `playlists_repository.py` (list_playlists_meta, list_playlist_tracks)
- [ ] Migrate read queries in `match_service.py`
- [ ] Migrate read queries in `export_service.py`
- [ ] (Optional) Migrate queries in `reporting/generator.py`

**Files to Create**:
- `psm/db/repositories/__init__.py`
- `psm/db/repositories/tracks_repository.py`
- `psm/db/repositories/files_repository.py`
- `psm/db/repositories/matches_repository.py`
- `psm/db/repositories/playlists_repository.py`
- `tests/unit/db/test_repositories.py`

**Files to Modify**:
- `psm/services/match_service.py` - Use repositories
- `psm/services/export_service.py` - Use repositories
- `psm/reporting/generator.py` - (Optional) Use repositories

**Acceptance Criteria**:
- [ ] Repository unit tests pass
- [ ] All services using repositories produce identical results
- [ ] No raw SQL in services (except writes via DatabaseInterface)
- [ ] DatabaseInterface remains unchanged

**Note**: Coordinate with PR4 changes to MatchingEngine

---

### PR7: Watch Loop Testability ⏸️ Not Started
**Status**: Blocked by PR6  
**Estimated Duration**: 2 days

**Scope**:
- [ ] Extract `WatchLoop` class to `psm/services/watch_loop.py`
- [ ] Implement `start()`, `stop()`, `run_once()` methods
- [ ] Replace substring ignore with `fnmatch` in `watch_service.py`
- [ ] Add unit tests for ignore pattern matching
- [ ] Add unit tests for WatchLoop with mocked handlers
- [ ] Narrow exception handling in handlers (specific exceptions only)
- [ ] Refactor `run_watch_build()` to use WatchLoop

**Files to Create**:
- `psm/services/watch_loop.py`
- `tests/unit/services/test_watch_loop.py`
- `tests/unit/services/test_watch_ignore_patterns.py`

**Files to Modify**:
- `psm/services/watch_service.py` - Use fnmatch for ignore patterns
- `psm/services/watch_build_service.py` - Use WatchLoop class
- `docs/configuration.md` - Document fnmatch pattern syntax

**Acceptance Criteria**:
- [ ] Ignore pattern tests verify fnmatch behavior: `*.tmp`, `**/temp/*`, `**/.DS_Store`
- [ ] WatchLoop unit tests cover mtime changes and handler invocations
- [ ] Integration tests for watch mode pass unchanged
- [ ] Exception handling specific to `sqlite3.OperationalError`, `OSError`

---

## Rollback Plan

Each PR is atomic and can be reverted independently:

1. **PR1**: Revert removes logger calls, restores click.style in services
2. **PR2**: Revert restores constructed path strings
3. **PR3-4**: Revert removes CandidateSelector/MatchingEngine, restores inline logic
4. **PR5**: Revert removes typed configs, services use dict lookups
5. **PR6**: Revert removes repositories, restores inline SQL
6. **PR7**: Revert removes WatchLoop, restores inline loop logic

## Testing Strategy

### Unit Tests
- CandidateSelector: duration window, Jaccard ordering
- MatchingEngine: match_all, incremental methods
- Repositories: query result correctness
- WatchLoop: mtime detection, handler invocations
- Ignore patterns: fnmatch edge cases

### Integration Tests
- All existing integration tests must pass for each PR
- Key test suites:
  - `tests/integration/test_export_modes.py`
  - `tests/integration/test_liked_songs_export.py`
  - `tests/integration/test_organize_by_owner.py`
  - Matching behavior tests (if any exist)

### Manual Smoke Tests
- Run full `build` workflow after each PR
- Verify terminal output formatting matches expectations
- Verify exported file paths are correct
- Test watch mode with file changes

## Success Metrics

- **Code Duplication**: Reduce matching logic duplication by ~60% (3 copies → 1 engine)
- **Raw SQL**: Reduce inline SQL in services by ~70%
- **Test Coverage**: Maintain >85% coverage (add tests for new modules)
- **Performance**: Zero regression (matching speed unchanged)
- **Behavioral Changes**: Zero user-visible changes (except bug fixes)

## Risk Mitigation

1. **Keep Public APIs Stable**: Service function signatures unchanged
2. **Coexistence**: New modules alongside old during transition
3. **Adapters**: Typed configs via `from_dict_*` prevent sweeping changes
4. **Incremental Commits**: Each commit in a PR should be buildable/testable
5. **Early Validation**: Run test suite after every logical change

## Timeline Estimate

- **Week 1 (Oct 8-14)**: PR1, PR2
- **Week 2 (Oct 15-21)**: PR3, PR4a, PR4b
- **Week 3 (Oct 22-28)**: PR5, PR6 (start)
- **Week 4 (Oct 29-Nov 4)**: PR6 (finish), PR7

**Total Effort**: ~10-14 days (staggered over 3-4 weeks for review cycles)

## Notes

- PRs should be reviewed individually - no stacking
- Each PR must pass CI before merge
- Update this document as we discover new issues/opportunities
- Document any deviations from plan with rationale

---

**Last Updated**: October 8, 2025  
**Next Review**: After PR1 completion
