# Provider Abstraction Refactoring Plan

**Status:** Planning  
**Date:** October 7, 2025  
**Goal:** Extract all Spotify-specific logic into `psm/providers/spotify/` with clean interfaces for future provider support.

## 1. Problem Analysis

### Current State
Spotify-specific code is scattered across the codebase:
- ✅ `psm/providers/spotify_provider.py` - Exists but thin wrapper
- ❌ `psm/auth/spotify_oauth.py` - Spotify OAuth logic
- ❌ `psm/ingest/spotify.py` - Spotify API client
- ❌ `psm/services/` - Services directly import SpotifyAuth & SpotifyClient
- ❌ `psm/cli/` - CLI commands check `cfg['spotify']` directly
- ❌ `psm/db/` - Default `provider='spotify'` hardcoded everywhere
- ❌ Comments/strings mentioning "Spotify" throughout

### Issues
1. **Tight Coupling:** Services directly instantiate `SpotifyAuth` and `SpotifyClient`
2. **No Abstraction:** No clean provider interface - just thin wrappers
3. **Scattered Logic:** Auth, API client, config validation spread across modules
4. **Testing Difficulty:** Spotify tests mixed with general logic tests
5. **Future Provider Support:** Adding Apple Music/Tidal/etc. would require touching many files

## 2. Target Architecture

### Proposed Structure
```
psm/
├── providers/
│   ├── __init__.py              # Provider registry & factory
│   ├── base.py                  # Abstract provider interfaces
│   ├── spotify/
│   │   ├── __init__.py         # Spotify provider package
│   │   ├── auth.py             # OAuth logic (moved from psm/auth/spotify_oauth.py)
│   │   ├── client.py           # API client (moved from psm/ingest/spotify.py)
│   │   ├── config.py           # Spotify config validation & defaults
│   │   ├── models.py           # Spotify-specific data models
│   │   └── provider.py         # SpotifyProvider implementation
│   └── links.py                # Keep link generators here
├── auth/
│   ├── __init__.py             # Generic auth interfaces (if needed)
│   └── certutil.py             # Keep cert utilities (provider-agnostic)
├── ingest/
│   ├── __init__.py             # Remove spotify.py
│   └── library.py              # Keep local library scanning
└── services/
    └── *.py                    # Use provider abstraction, not direct imports
```

### Provider Interface Design

```python
# psm/providers/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class AuthProvider(ABC):
    """Abstract authentication provider."""
    
    @abstractmethod
    def get_token(self, force: bool = False) -> Dict[str, Any]:
        """Get access token (may trigger OAuth flow)."""
        pass
    
    @abstractmethod
    def clear_cache(self) -> None:
        """Clear cached tokens."""
        pass


class StreamingProviderClient(ABC):
    """Abstract streaming provider API client."""
    
    @abstractmethod
    def get_user_playlists(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """Fetch user's playlists."""
        pass
    
    @abstractmethod
    def get_playlist(self, playlist_id: str) -> Dict[str, Any]:
        """Fetch playlist metadata."""
        pass
    
    @abstractmethod
    def get_playlist_tracks(self, playlist_id: str, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Fetch tracks from a playlist."""
        pass
    
    @abstractmethod
    def get_liked_tracks(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """Fetch user's liked/saved tracks."""
        pass
    
    @abstractmethod
    def replace_playlist_tracks(self, playlist_id: str, track_ids: List[str]) -> None:
        """Replace all tracks in a playlist."""
        pass


class Provider(ABC):
    """Complete provider abstraction."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'spotify', 'apple_music')."""
        pass
    
    @abstractmethod
    def create_auth(self, config: Dict[str, Any]) -> AuthProvider:
        """Create auth provider from config."""
        pass
    
    @abstractmethod
    def create_client(self, access_token: str) -> StreamingProviderClient:
        """Create API client with access token."""
        pass
    
    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> None:
        """Validate provider-specific configuration."""
        pass
    
    @abstractmethod
    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values."""
        pass
```

## 3. Detailed Migration Plan

### Phase 1: Create Provider Structure (Foundation)
**Goal:** Set up new directory structure and base interfaces

1. **Create directory structure:**
   ```cmd
   mkdir psm\providers\spotify
   ```

2. **Create base interfaces:**
   - `psm/providers/base.py` - Abstract interfaces (AuthProvider, StreamingProviderClient, Provider)
   - Define common methods all providers must implement
   - Add type hints and docstrings

3. **Update provider registry:**
   - `psm/providers/__init__.py` - Provider factory with registry pattern
   - `get_provider(name: str) -> Provider`
   - `register_provider(provider_class)`

**Deliverable:** Clean abstract interfaces, no implementation yet.

---

### Phase 2: Move Spotify Auth (psm/auth → psm/providers/spotify) ✅ COMPLETE
**Goal:** Encapsulate OAuth logic in Spotify provider

**Completed Actions:**
1. ✅ **Moved auth module:**
   - Copied `psm/auth/spotify_oauth.py` → `psm/providers/spotify/auth.py`
   - Renamed `SpotifyAuth` → `SpotifyAuthProvider` (implements `AuthProvider`)
   - Kept `certutil.py` in `psm/auth/` (provider-agnostic)
   - Added `clear_cache()` method implementation
   
2. ✅ **Maintained backward compatibility:**
   - Replaced `psm/auth/spotify_oauth.py` with deprecation shim
   - `SpotifyAuth` now aliases to `SpotifyAuthProvider`
   - Emits `DeprecationWarning` when old import path used
   - All existing code continues working without modifications

3. ✅ **Updated exports:**
   - `psm/providers/spotify/__init__.py` exports `SpotifyAuthProvider`
   - Old import path still works: `from psm.auth.spotify_oauth import SpotifyAuth`
   - New import path available: `from psm.providers.spotify import SpotifyAuthProvider`

4. ✅ **Tests verified:**
   - All 119 tests passing
   - Deprecation warning appears for old import usage
   - Backward compatibility confirmed

**Files Changed:**
- `psm/providers/spotify/auth.py` (created, 303 lines)
- `psm/providers/spotify/__init__.py` (updated to export SpotifyAuthProvider)
- `psm/auth/spotify_oauth.py` (replaced with 24-line compatibility shim)

**Note:** Old file NOT deleted yet - maintained as compatibility layer. Will be removed in later phase after all imports updated.

**Deliverable:** ✅ Spotify auth encapsulated, backward compatibility maintained, all tests passing.

---

### Phase 3: Move Spotify Client (psm/ingest → psm/providers/spotify) ✅ COMPLETE
**Goal:** Encapsulate Spotify API client logic

**Completed Actions:**
1. ✅ **Moved client module:**
   - Created `psm/providers/spotify/client.py` with `SpotifyAPIClient` class (246 lines)
   - Renamed `SpotifyClient` → `SpotifyAPIClient`
   - Preserved all API methods: current_user_profile, current_user_playlists, playlist_items, liked_tracks
   - Kept write operations: get_playlist, replace_playlist_tracks_remote
   - Maintained rate limiting, retry logic, and test mode support

2. ✅ **Moved helper functions:**
   - Created `psm/providers/spotify/ingestion.py` (290 lines)
   - Moved `extract_year()` function
   - Moved `ingest_playlists()` function
   - Moved `ingest_liked()` function
   - All functions preserve original behavior with incremental update logic

3. ✅ **Maintained backward compatibility:**
   - Replaced `psm/ingest/spotify.py` with 27-line deprecation shim
   - `SpotifyClient` aliases to `SpotifyAPIClient`
   - Re-exports `ingest_playlists` and `ingest_liked` from new location
   - Emits `DeprecationWarning` when old import path used

4. ✅ **Updated exports:**
   - `psm/providers/spotify/__init__.py` exports all new modules
   - Old import path still works: `from psm.ingest.spotify import SpotifyClient`
   - New import path available: `from psm.providers.spotify import SpotifyAPIClient`

5. ✅ **Tests verified:**
   - All 119 tests passing
   - 2 deprecation warnings (expected - from old imports in helpers.py and spotify_provider.py)
   - Zero regressions

**Files Changed:**
- `psm/providers/spotify/client.py` (created, 246 lines)
- `psm/providers/spotify/ingestion.py` (created, 290 lines)
- `psm/providers/spotify/__init__.py` (updated to export new modules)
- `psm/ingest/spotify.py` (replaced with 27-line compatibility shim)

**Note:** Old file NOT deleted yet - maintained as compatibility layer. `psm/ingest/library.py` remains untouched (provider-agnostic local file scanning).

**Deliverable:** ✅ Spotify client and ingestion logic encapsulated, backward compatibility maintained, all tests passing.

---

### Phase 4: Create SpotifyProvider Class
**Goal:** Unified Spotify provider implementation

1. **Create provider implementation:**
   ```python
   # psm/providers/spotify/provider.py
   from ..base import Provider, AuthProvider, StreamingProviderClient
   from .auth import SpotifyAuthProvider
   from .client import SpotifyAPIClient
   from .config import validate_spotify_config, get_spotify_defaults
   
   class SpotifyProvider(Provider):
       name = 'spotify'
       
       def create_auth(self, config: Dict[str, Any]) -> AuthProvider:
           self.validate_config(config)
           return SpotifyAuthProvider(
               client_id=config['client_id'],
               redirect_scheme=config.get('redirect_scheme', 'http'),
               # ... etc
           )
       
       def create_client(self, access_token: str) -> StreamingProviderClient:
           return SpotifyAPIClient(access_token)
       
       def validate_config(self, config: Dict[str, Any]) -> None:
           if not config.get('client_id'):
               raise ValueError('spotify.client_id required')
           # ... more validation
       
       def get_default_config(self) -> Dict[str, Any]:
           return get_spotify_defaults()
   ```

2. **Register provider:**
   ```python
   # psm/providers/spotify/__init__.py
   from .provider import SpotifyProvider
   from ..base import register_provider
   
   register_provider(SpotifyProvider())
   
   __all__ = ['SpotifyProvider']
   ```

**Deliverable:** Complete Spotify provider implementation.

---

### Phase 5: Update Services to Use Provider Abstraction
**Goal:** Decouple services from Spotify-specific code

1. **Update service signatures:**
   - Replace `spotify_config: Dict` → `provider_config: Dict, provider_name: str = 'spotify'`
   - Services get provider via `provider = get_provider(provider_name)`
   - Auth: `auth = provider.create_auth(provider_config)`
   - Client: `client = provider.create_client(token)`

2. **Files to update:**
   - `psm/services/pull_service.py`
   - `psm/services/playlist_service.py`
   - `psm/services/push_service.py`
   - `psm/services/match_service.py` (change variable names, not logic)

3. **Example transformation:**
   ```python
   # BEFORE:
   from ..auth.spotify_oauth import SpotifyAuth
   from ..ingest.spotify import SpotifyClient
   
   def pull_all(db, spotify_config, ...):
       auth = SpotifyAuth(
           client_id=spotify_config['client_id'],
           # ...10 more lines
       )
       tok = auth.get_token()
       client = SpotifyClient(tok['access_token'])
   
   # AFTER:
   from ..providers import get_provider
   
   def pull_all(db, provider_config, provider_name='spotify', ...):
       provider = get_provider(provider_name)
       auth = provider.create_auth(provider_config)
       tok = auth.get_token()
       client = provider.create_client(tok['access_token'])
   ```

**Deliverable:** Services decoupled from Spotify specifics.

---

### Phase 6: Update CLI Commands
**Goal:** CLI uses provider abstraction

1. **Update command handlers:**
   - `psm/cli/core.py` - Pull, auth commands
   - `psm/cli/playlist_cmds.py` - Playlist commands
   - `psm/cli/helpers.py` - Remove `_redact_spotify_config`, make generic

2. **Config access pattern:**
   ```python
   # BEFORE:
   if not cfg['spotify']['client_id']:
       raise click.UsageError('spotify.client_id not configured')
   
   # AFTER:
   provider_name = cfg.get('provider', 'spotify')
   provider_config = cfg.get(provider_name, {})
   provider = get_provider(provider_name)
   provider.validate_config(provider_config)  # Raises if invalid
   ```

3. **Update help text:**
   - Change "Spotify" → "streaming provider" in generic commands
   - Keep Spotify-specific commands clearly labeled

**Deliverable:** CLI provider-agnostic.

---

### Phase 7: Update Configuration
**Goal:** Provider-specific config sections

1. **Config structure:**
   ```python
   # psm/config.py _DEFAULTS
   _DEFAULTS = {
       'provider': 'spotify',  # Default provider
       'spotify': {
           # Spotify-specific config
           'client_id': '',
           'redirect_scheme': 'http',
           # ...
       },
       # Future providers:
       # 'apple_music': { ... },
       # 'tidal': { ... },
       # ...
   }
   ```

2. **Provider defaults:**
   - Move Spotify defaults → `psm/providers/spotify/config.py`
   - Provider interface `get_default_config()` returns them
   - Main config merges provider defaults dynamically

**Deliverable:** Extensible config structure.

---

### Phase 8: Update Database Defaults
**Goal:** Remove hardcoded 'spotify' defaults

1. **Current issue:**
   - All DB methods have `provider: str = 'spotify'` hardcoded
   - Should be explicit or config-driven

2. **Options:**
   **Option A (Preferred):** Make provider required (no default):
   ```python
   def upsert_playlist(self, pid: str, name: str, ..., provider: str) -> None:
       # Caller must specify provider explicitly
   ```
   
   **Option B:** Get default from config:
   ```python
   def upsert_playlist(self, pid: str, name: str, ..., provider: str | None = None) -> None:
       if provider is None:
           provider = config.get('provider', 'spotify')
   ```

3. **Update interface & implementation:**
   - `psm/db/interface.py` - Update signatures
   - `psm/db/sqlite_impl.py` - Update implementation
   - `tests/mocks/mock_database.py` - Update mock

**Deliverable:** DB layer provider-agnostic.

---

### Phase 9: Migrate Tests
**Goal:** Test organization mirrors code organization

1. **Create test structure:**
   ```
   tests/
   ├── unit/
   │   ├── providers/
   │   │   ├── test_provider_registry.py
   │   │   └── spotify/
   │   │       ├── test_spotify_auth.py
   │   │       ├── test_spotify_client.py
   │   │       └── test_spotify_provider.py
   │   └── ... (existing unit tests)
   ├── integration/
   │   ├── providers/
   │   │   └── spotify/
   │   │       ├── test_spotify_oauth_flow.py  (if safe to test)
   │   │       └── test_spotify_api_integration.py  (if safe to test)
   │   └── ... (existing integration tests)
   └── mocks/
       └── mock_provider.py  # Generic mock provider for testing
   ```

2. **Move existing Spotify tests:**
   - Find all Spotify-related tests in current structure
   - Move to `tests/unit/providers/spotify/` or `tests/integration/providers/spotify/`

3. **Create provider mocks:**
   - `MockAuthProvider` - Returns stub tokens
   - `MockStreamingClient` - Returns deterministic data
   - `MockProvider` - Combines above for service testing

**Deliverable:** Tests organized by provider, easy to add new providers.

---

### Phase 10: Documentation & Cleanup
**Goal:** Clean, documented provider system

1. **Documentation:**
   - `docs/providers.md` - Already exists, update with new architecture
   - Add "Adding a New Provider" guide
   - Document provider interface contracts
   - Update `docs/architecture.md`

2. **Code cleanup:**
   - Remove remaining Spotify-specific comments in generic code
   - Update variable names (`spotify_tracks` → `provider_tracks`)
   - Ensure no direct Spotify imports outside `psm/providers/spotify/`

3. **Verify isolation:**
   ```bash
   # Should find ZERO matches outside psm/providers/spotify/:
   grep -r "SpotifyAuth\|SpotifyClient" psm/ --exclude-dir=providers
   grep -r "from.*spotify" psm/ --exclude-dir=providers
   ```

**Deliverable:** Clean, well-documented provider abstraction.

---

## 4. Migration Checklist

### Phase 1: Foundation
- [x] Create `psm/providers/spotify/` directory
- [x] Create `psm/providers/base.py` with abstract interfaces (extended existing)
- [x] Update `psm/providers/__init__.py` with provider instance registry
- [x] All 119 tests passing ✅

**Status:** COMPLETE (2025-10-07)

### Phase 2: Auth Migration
- [ ] Move `spotify_oauth.py` → `providers/spotify/auth.py`
- [ ] Implement `AuthProvider` interface
- [ ] Update imports in services (use provider factory)
- [ ] Delete old `psm/auth/spotify_oauth.py`
- [ ] Tests pass

### Phase 3: Client Migration
- [ ] Move `spotify.py` → `providers/spotify/client.py`
- [ ] Implement `StreamingProviderClient` interface
- [ ] Move ingestion helpers → `providers/spotify/ingestion.py`
- [ ] Delete old `psm/ingest/spotify.py`
- [ ] Tests pass

### Phase 4: Provider Class
- [ ] Create `SpotifyProvider` implementation
- [ ] Register provider in `__init__.py`
- [ ] Create `providers/spotify/config.py` for defaults/validation
- [ ] Tests pass

### Phase 5: Services Update
- [ ] Update `pull_service.py`
- [ ] Update `playlist_service.py`
- [ ] Update `push_service.py`
- [ ] Update `match_service.py` (naming only)
- [ ] Tests pass

### Phase 6: CLI Update
- [ ] Update `cli/core.py`
- [ ] Update `cli/playlist_cmds.py`
- [ ] Update `cli/helpers.py`
- [ ] Tests pass

### Phase 7: Config Update
- [ ] Move Spotify defaults to provider
- [ ] Update main config loader
- [ ] Tests pass

### Phase 8: Database Update
- [ ] Remove `provider='spotify'` defaults from interface
- [ ] Update implementation
- [ ] Update MockDatabase
- [ ] Tests pass

### Phase 9: Test Migration
- [ ] Create `tests/unit/providers/spotify/`
- [ ] Create `tests/integration/providers/spotify/`
- [ ] Move Spotify tests to new locations
- [ ] Create `MockProvider` for testing
- [ ] All tests pass

### Phase 10: Documentation
- [ ] Update `docs/providers.md`
- [ ] Update `docs/architecture.md`
- [ ] Add "Adding a Provider" guide
- [ ] Verify no Spotify imports outside providers/
- [ ] Final test run

---

## 5. Testing Strategy

### During Migration
- **Run tests after each phase** - Ensure no regression
- **Use existing integration tests** - They validate behavior
- **Add provider interface tests** - Verify contracts

### After Migration
- **Verify isolation:**
  ```cmd
  # No Spotify imports outside providers/spotify
  run.bat py -c "import ast, pathlib; ..."
  ```
- **All 119 tests still pass**
- **Services work with provider abstraction**

---

## 6. Risk Mitigation

### Risks
1. **Breaking existing functionality** - Extensive Spotify imports everywhere
2. **Test failures** - Many tests may assume Spotify specifics
3. **Performance impact** - Extra abstraction layer

### Mitigation
1. **Incremental migration** - One phase at a time, tests after each
2. **Keep old code** - Don't delete until new code proven
3. **Backward compatibility** - Provider defaults to 'spotify'
4. **Comprehensive testing** - Run full suite after each phase

---

## 7. Success Criteria

✅ **Isolation:**
- No `SpotifyAuth`/`SpotifyClient` imports outside `psm/providers/spotify/`
- No hardcoded `'spotify'` strings outside config/providers
- Services use `Provider` interface only

✅ **Testing:**
- All 119 existing tests pass
- Spotify tests in `tests/*/providers/spotify/`
- MockProvider available for service testing

✅ **Documentation:**
- Provider architecture documented
- Guide for adding new providers
- Clean code with no Spotify-specific comments in generic modules

✅ **Extensibility:**
- Adding Apple Music/Tidal requires only:
  1. Create `psm/providers/apple_music/` (or tidal)
  2. Implement `Provider` interface
  3. Register provider
  4. Add config section
  5. No changes to services/CLI

---

## 8. Estimated Effort

| Phase | Complexity | Estimated Time | Risk |
|-------|------------|----------------|------|
| Phase 1 | Low | 1-2 hours | Low |
| Phase 2 | Medium | 2-3 hours | Medium |
| Phase 3 | Medium | 2-3 hours | Medium |
| Phase 4 | Low | 1 hour | Low |
| Phase 5 | High | 3-4 hours | High |
| Phase 6 | Medium | 2 hours | Medium |
| Phase 7 | Low | 1 hour | Low |
| Phase 8 | Medium | 2 hours | Medium |
| Phase 9 | Medium | 2-3 hours | Low |
| Phase 10 | Low | 1 hour | Low |
| **Total** | | **17-22 hours** | |

---

## 9. Next Steps

1. **Review this plan** - Get approval for approach
2. **Start Phase 1** - Create foundation (low risk)
3. **Iterate incrementally** - One phase at a time
4. **Test continuously** - After each phase
5. **Document as we go** - Update architecture docs

---

**This refactoring will result in a clean, extensible provider system where all Spotify logic is contained in one place, making future provider support straightforward.**
