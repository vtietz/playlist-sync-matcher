# Adding a New Streaming Provider

This guide explains how to integrate an additional streaming service (e.g. Deezer, Tidal) into the existing architecture.

## Overview
The application currently supports a single provider (`spotify`). The codebase has been prepared with a lightweight abstraction so new providers can be added with minimal churn.

Key components:
- `psm/providers/base.py` – Domain models & `ProviderClient` protocol
- `psm/providers/spotify_provider.py` – Example registration for Spotify
- `psm/services/pull_service.py` – Unified `pull_data()` ingestion entry point
- Configuration key: `provider` (defaults to `spotify`)

## High-Level Steps
1. Implement authentication flow for the new provider (OAuth / token exchange).
2. Implement a provider client exposing the required ingestion methods.
3. Register the provider with the registry (`@register`).
4. Map provider config in `.env` / environment variables.
5. Extend `pull_data()` to branch on the new provider and call its client & ingestion logic.
6. Add tests (unit + integration) behind environment guards if live API needed.
7. Update README and this guide with provider-specific notes.

## Data Model Expectations
At ingestion time you must supply (or be able to derive) for each track:
- Stable provider-specific track ID (string)
- Track name
- Artist names (comma-separated if multiple)
- Album name (optional but improves matching)
- ISRC if available (improves future cross-provider mapping)
- Duration in milliseconds
- Release year (optional; used if `matching.use_year=true`)

Playlists ingestion must provide:
- Playlist ID
- Name
- Snapshot / version identifier (if provider supports it) to enable incremental updates
- Owner ID / name (if available) for optional folder organization

## Authentication Strategy
You can mirror the structure of `SpotifyAuth` or implement a provider-specific auth class. Requirements:
- Persistent token cache JSON file (per provider) containing at least:
  - `access_token`
  - `expires_at` (epoch seconds) if expiring
  - `refresh_token` (if refresh flow supported)
- Graceful refresh attempt before full re-auth.

Token cache naming should be provider-scoped. The ingestion service already prefixes non-Spotify caches (`<provider>_tokens.json`) if not explicitly set.

## Implementing a Provider Client
Example skeleton (simplified):
```python
# psm/providers/deezer_provider.py
from __future__ import annotations
from .base import register, ProviderCapabilities, ProviderClient

@register
class DeezerProviderClient:  # does not need inheritance if you write fresh
    name = 'deezer'
    capabilities = ProviderCapabilities(
        search=True,
        create_playlist=False,
        batch_add=False,
        supports_isrc=True,
        max_batch_size=50,
    )

    def __init__(self, token: str):
        self.token = token
        # optionally build a requests.Session()

    def current_user_profile(self):
        # GET https://api.deezer.com/user/me?access_token=...
        ...

    def current_user_playlists(self, verbose: bool = False):
        # yield playlist dicts each containing id, name, creator info, etc.
        ...

    def playlist_items(self, playlist_id: str, verbose: bool = False):
        # return list of track item dicts (must include nested 'track' keys similar to Spotify ingestion expectations)
        ...
```

## Extending `pull_data()`
In `psm/services/pull_service.py` add a new branch:
```python
if provider == 'deezer':
    # 1. Acquire token (your DeezerAuth analog) => tok_dict
    # 2. client = DeezerProviderClient(tok_dict['access_token'])
    # 3. Implement ingest_deezer_playlists / ingest_deezer_liked mirroring Spotify patterns
    # 4. Reuse stats aggregation logic
```
Keep the rest of the function structure unchanged for consistency.

## Ingestion Helpers
Follow the existing Spotify ingestion pattern:
1. Fetch user profile (store current user id in meta table if relevant)
2. Enumerate playlists (check snapshot / updated version to skip unchanged)
3. For each playlist page through tracks (batch size per API limits)
4. Normalize artist/title combo using `normalize_title_artist()`
5. Upsert tracks then playlist then playlist-track relations
6. Commit after each playlist for durability
7. Ingest liked/favorites separately (if provider exposes them)

## Matching Considerations
No provider-specific code is currently in the matching engine because it operates on normalized track metadata already in the SQLite database. Ensure your ingestion writes the same columns (`tracks` table expected fields). If field names diverge, adapt ingestion to conform rather than changing matching.

## Configuration
Add a new top-level config section in the defaults (future change), e.g.:
```python
"deezer": {
    "client_id": None,
    "cache_file": "deezer_tokens.json",
    # other provider-specific settings
}
```
Users then set via environment:
```
PSM__PROVIDER=deezer
PSM__DEEZER__CLIENT_ID=...  # Example naming if future code maps this
```

## Testing Strategy
- Unit test ingestion parsing with recorded fixture JSON (store under `tests/fixtures/deezer/`).
- Mock network I/O (e.g., with `responses` or custom monkeypatch) to keep tests deterministic.
- Integration (optional) gated by env var (e.g., `PSM_DEEZER_LIVE_TEST=1`). Skip unless present.

## Error Handling
- Map provider-specific HTTP errors to `requests.HTTPError` (already raised) or custom exceptions (future enhancement).
- Respect rate-limit headers; implement retry/backoff similar to Spotify logic (tenacity decorators or custom).

## Performance Tips
- Use a shared `requests.Session`.
- Batch pagination requests only as needed; avoid fetching all playlists if only some changed (use snapshot/versioning).
- Cache normalization with existing utilities (already cheap, but consistent).

## Checklist Before Submitting PR
- [ ] New client class registered with `@register`
- [ ] Auth flow documented in README + this guide
- [ ] Config keys added with sensible defaults
- [ ] Ingestion functions mirror naming convention (`ingest_<provider>_playlists`)
- [ ] Tests added / updated (unit & optional live)
- [ ] README provider section updated with capabilities table
- [ ] No failing tests (`run.bat test -q` green)

---
Questions? Open an issue describing the provider and planned approach before large refactors.
