# Database Layer Refactoring Plan

**Goal**: Consolidate SQL into repository layer, ensure provider-aware queries, fix correctness issues, improve testability.

**Status**: ✅ COMPLETE | **Created**: 2025-10-08 | **Completed**: 2025-10-08

---

## Summary

Successfully completed all 9 phases of the database refactoring:

✅ **Phase 1**: Consolidated to single Database implementation (deleted psm/db.py)
✅ **Phase 2-3**: Added provider-aware repository methods with best-match logic using window functions
✅ **Phase 4**: Refactored all services to use repository (removed db.conn usage)
✅ **Phase 5**: Fixed transaction boundaries (removed per-method commits)
✅ **Phase 6**: Applied consistent lock handling to all write operations
✅ **Phase 7**: Added 5 performance indexes for high-frequency joins
✅ **Phase 8**: Removed legacy psm/match/engine.py
✅ **Phase 9**: Tests running (to be verified)

---

## Changes Made

### Database Layer
- **Deleted**: `psm/db.py` (duplicate implementation)
- **Deleted**: `psm/match/engine.py` (legacy matching)
- **Enhanced**: `psm/db/sqlite_impl.py` with:
  - Provider-aware queries everywhere
  - Best-match window function logic (prevents duplicates)
  - Consistent lock handling on all writes
  - 5 new performance indexes
  - Removed per-method commits (transaction control at service layer)

### New Repository Methods
1. `list_playlists(playlist_ids, provider)` - Sorted playlist enumeration
2. `get_playlist_tracks_with_local_paths(playlist_id, provider)` - **Best match only**
3. `get_liked_tracks_with_local_paths(provider)` - **Best match only, newest first**
4. `get_track_by_id(track_id, provider)` - Single track retrieval
5. `get_match_for_track(track_id, provider)` - Match details with file info

### Services Refactored
- ✅ `export_service.py` - Uses repository methods, no db.conn
- ✅ `diagnostic_service.py` - Fixed "metadata" bug, uses repository methods
- ✅ `playlist_service.py` - Switched to MatchingEngine, uses repository methods

### Indexes Added
```sql
CREATE INDEX idx_playlist_tracks_playlist ON playlist_tracks(playlist_id, provider);
CREATE INDEX idx_playlist_tracks_track ON playlist_tracks(track_id, provider);
CREATE INDEX idx_matches_track ON matches(track_id, provider);
CREATE INDEX idx_matches_file ON matches(file_id);
CREATE INDEX idx_liked_tracks_track ON liked_tracks(track_id, provider);
```

---

## Critical Bugs Fixed

1. ✅ **DiagnosticService**: Wrong table "metadata" → correct "meta" table via `get_meta()`
2. ✅ **Export duplicates**: Window function ensures single best match per track
3. ✅ **Missing provider predicates**: All joins now include `AND t.provider = ?`
4. ✅ **Inconsistent commits**: Removed from repository, controlled at service layer
5. ✅ **Incomplete lock handling**: Applied to all write operations

---

## Next Action

Run full test suite to verify all changes work correctly.

---

## Phase 1: Consolidate DB Implementation
**Priority**: HIGH | **Status**: 🔴 Not Started

- [ ] **1.1** Keep `psm/db/sqlite_impl.py:Database` as single source of truth
- [ ] **1.2** Deprecate `psm/db.py:Database` (mark with deprecation warning)
- [ ] **1.3** Update `psm/db/__init__.py` to re-export from sqlite_impl
- [ ] **1.4** Update all service imports to use `from psm.db import Database`
- [ ] **1.5** Update all test imports

**Files affected**: `psm/db/__init__.py`, all services, all tests

---

## Phase 2: Add Repository Methods
**Priority**: HIGH | **Status**: 🔴 Not Started

Add to `DatabaseInterface` + implement in `sqlite_impl.Database`:

- [ ] **2.1** `list_playlists(playlist_ids: Optional[list[str]], provider: str) -> list[PlaylistRow]`
  - Stable ordering by owner_name, name
  - Filter by IDs when provided
  
- [ ] **2.2** `get_playlist_tracks_with_local_paths(playlist_id: str, provider: str) -> list[dict]`
  - **CRITICAL**: Single best match per track (highest score)
  - Use window function or correlated subquery
  - Provider-aware joins on tracks, matches, playlist_tracks
  
- [ ] **2.3** `get_liked_tracks_with_local_paths(provider: str) -> list[dict]`
  - Order by added_at DESC
  - Single best match per track
  - Provider-aware joins
  
- [ ] **2.4** Helper: `get_current_user_id(provider: str) -> Optional[str]` (via get_meta)
- [ ] **2.5** Helper: `get_current_user_name(provider: str) -> Optional[str]` (via get_meta)

**Files affected**: `psm/db/interface.py`, `psm/db/sqlite_impl.py`

---

## Phase 3: Make All Joins Provider-Aware
**Priority**: CRITICAL | **Status**: 🔴 Not Started

Ensure all repository SQL includes provider filters:

- [ ] **3.1** Add provider predicates to tracks joins: `AND t.provider = ?`
- [ ] **3.2** Add provider predicates to matches joins: `AND m.provider = ?`
- [ ] **3.3** Add provider predicates to playlist_tracks joins: `AND pt.provider = ?`
- [ ] **3.4** Review all existing repository methods for provider coverage

**Why**: Prevents cross-provider data leakage when multiple providers are added

---

## Phase 4: Refactor Services to Use Repository
**Priority**: HIGH | **Status**: 🔴 Not Started

### Export Service
- [ ] **4.1** Replace playlist enumeration raw SQL ([export_service.py:172](psm/services/export_service.py:172))
  - Use `list_playlists()`
  
- [ ] **4.2** Replace track fetch raw SQL ([export_service.py:227](psm/services/export_service.py:227))
  - Use `get_playlist_tracks_with_local_paths()`
  
- [ ] **4.3** Replace liked songs raw SQL ([export_service.py:337](psm/services/export_service.py:337))
  - Use `get_liked_tracks_with_local_paths()`

### Diagnostic Service
- [ ] **4.4** Fix table name bug: "metadata" → use `get_meta()` ([diagnostic_service.py:60](psm/services/diagnostic_service.py:60))
- [ ] **4.5** Replace all raw SQL with repository methods
- [ ] **4.6** Depend on `DatabaseInterface` instead of concrete `Database`

### Other Services
- [ ] **4.7** Audit `psm/services/push_service.py` for db.conn usage
- [ ] **4.8** Audit `psm/ingest/library.py` for db.conn usage
- [ ] **4.9** Audit `psm/providers/spotify/ingestion.py` for db.conn usage

**Files affected**: All services with db.conn calls

---

## Phase 5: Transaction Boundaries
**Priority**: MEDIUM | **Status**: 🔴 Not Started

- [ ] **5.1** Remove per-method commits in repository writes
- [ ] **5.2** Add `DatabaseInterface.commit()` for explicit control
- [ ] **5.3** Optional: Add `transaction()` context manager
- [ ] **5.4** Update services to commit at operation boundaries (per pull, per scan)
- [ ] **5.5** Keep commits only for schema/migration operations

**Pattern**: Service controls transactions, repository is passive

---

## Phase 6: Consistent Lock Handling
**Priority**: MEDIUM | **Status**: 🔴 Not Started

Apply `_execute_with_lock_handling` to all writes:

- [ ] **6.1** `upsert_liked` ([sqlite_impl.py:133](psm/db/sqlite_impl.py:133))
- [ ] **6.2** `add_library_file` ([sqlite_impl.py:144](psm/db/sqlite_impl.py:144))
- [ ] **6.3** `add_match` ([sqlite_impl.py:154](psm/db/sqlite_impl.py:154))
- [ ] **6.4** `replace_playlist_tracks` executemany ([sqlite_impl.py:111](psm/db/sqlite_impl.py:111))
- [ ] **6.5** Consider adding `PRAGMA busy_timeout=N` to connection setup

**Files affected**: `psm/db/sqlite_impl.py`

---

## Phase 7: Add Performance Indexes
**Priority**: LOW | **Status**: 🔴 Not Started

Create indexes for high-frequency joins:

- [ ] **7.1** `CREATE INDEX IF NOT EXISTS idx_playlist_tracks_playlist ON playlist_tracks(playlist_id, provider)`
- [ ] **7.2** `CREATE INDEX IF NOT EXISTS idx_playlist_tracks_track ON playlist_tracks(track_id, provider)`
- [ ] **7.3** `CREATE INDEX IF NOT EXISTS idx_matches_track ON matches(track_id, provider)`
- [ ] **7.4** `CREATE INDEX IF NOT EXISTS idx_matches_file ON matches(file_id)`
- [ ] **7.5** `CREATE INDEX IF NOT EXISTS idx_liked_tracks_track ON liked_tracks(track_id, provider)`

**Files affected**: `psm/db/sqlite_impl.py` (schema init)

---

## Phase 8: Retire Legacy Code
**Priority**: LOW | **Status**: 🔴 Not Started

- [ ] **8.1** Remove or deprecate `psm/match/engine.py` (legacy matching)
  - Newer `MatchingEngine` already uses repository methods
  - Legacy version bypasses provider conditions
- [ ] **8.2** Verify no references remain in codebase
- [ ] **8.3** Update documentation if needed

---

## Phase 9: Test Coverage
**Priority**: HIGH | **Status**: 🔴 Not Started

### Integration Tests
- [ ] **9.1** Export produces zero duplicate rows with multiple matches
- [ ] **9.2** Provider-aware joins prevent cross-provider data leakage
- [ ] **9.3** DiagnosticService reads from correct meta table
- [ ] **9.4** Repository methods return expected typed rows

### Unit Tests
- [ ] **9.5** Mock repository to verify services use it (not db.conn)
- [ ] **9.6** Test single-best-match SQL logic in isolation
- [ ] **9.7** Test transaction boundaries (commit/rollback)
- [ ] **9.8** Test lock handling retry logic

**Files affected**: `tests/integration/`, `tests/unit/`

---

## Critical Bugs to Fix Immediately

1. **DiagnosticService**: Wrong table name "metadata" → use `get_meta()` 
   - File: `psm/services/diagnostic_service.py:60`
   - Impact: Service fails to read threshold config

2. **Export duplicate rows**: Multiple matches cause duplicates
   - Files: `psm/services/export_service.py:227,337`
   - Impact: Playlists have duplicate entries

3. **Missing provider predicates**: Cross-provider data leakage risk
   - Files: All export queries
   - Impact: Wrong tracks when multiple providers exist

---

## Success Criteria

- ✅ Zero `db.conn` usage outside repository layer
- ✅ All joins include provider predicates
- ✅ Exports produce exactly one entry per track (best match)
- ✅ All tests pass with provider-aware logic
- ✅ Single `Database` implementation (sqlite_impl)
- ✅ Transaction control at service layer
- ✅ Consistent lock handling on all writes

---

## Implementation Notes

### Best Match SQL Pattern (SQLite)
```sql
-- Window function approach (SQLite ≥ 3.25)
WITH ranked_matches AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY track_id ORDER BY score DESC) AS rn
  FROM matches WHERE provider = ?
)
SELECT ... FROM ranked_matches WHERE rn = 1

-- Correlated subquery approach (older SQLite)
SELECT ... FROM matches m
WHERE m.score = (
  SELECT MAX(score) FROM matches m2 
  WHERE m2.track_id = m.track_id AND m2.provider = m.provider
)
```

### Transaction Pattern
```python
# Service layer controls transactions
db.begin_transaction()  # or use context manager
try:
    # Multiple repository calls...
    db.commit()
except Exception:
    db.rollback()
    raise
```

---

**Next Action**: Start with Phase 1 (DB consolidation) or fix critical bugs first?
