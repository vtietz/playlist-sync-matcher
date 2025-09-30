# spotify-m3u-sync

Synchronize your Spotify playlists and liked tracks into a local SQLite database, match them against your on-disk music library, export M3U8 playlists (with optional placeholders for missing tracks), and generate detailed missing track and album completeness reports.

## Features
Core:
- Unified config (defaults + YAML + environment overrides via `SPX__` prefix)
- SQLite storage: playlists, playlist tracks, liked tracks, tracks, library files, matches, meta checkpoints
- Normalization & partial hashing for robust file identity
- Match engine (exact + fuzzy with configurable threshold) storing persistent matches
- Spotify ingestion with pagination, retry, and incremental checkpoints (snapshot_id / added_at)
- Local library scanner (mutagen metadata extraction)
- Token cache with automatic refresh (PKCE OAuth)

Reporting & Export:
- Missing tracks CSV (Spotify tracks with no local match)
- Album completeness CSV (complete / partial / missing albums with percentages)
- Playlist export modes:
  - strict: only matched local file paths
  - mirrored: full order with EXTINF + commented missing markers
  - placeholders: mirrored plus placeholder files on disk preserving sequence

Tooling:
- Click CLI (`run.bat` convenience on Windows)
- Test suite (normalization, hashing, schema, env override, match integration, album completeness)
- GitHub Actions CI (Windows + Ubuntu, Python 3.11/3.12)

## Roadmap
- Duplicate detection & stats summary reporting
- Enhanced fuzzy ranking (ISRC, album-aware bonuses)
- Rich console output styling
- Packaging & distribution (PyPI)

## Usage (Windows examples)
Show version:
```
run.bat version
```

Authenticate & ingest Spotify playlists + liked tracks incrementally:
```
run.bat pull
```

Scan local library (configure paths in config or env):
```
run.bat scan
```

Run matching engine:
```
run.bat match
```

Export playlists (mode from config/env):
```
run.bat export
```

Generate missing tracks report:
```
run.bat report
```

Generate album completeness report:
```
run.bat report-albums
```

Full pipeline (pull -> scan -> match -> export -> report):
```
run.bat sync
```

## Export Modes
Configure via `export.mode` (default `strict`).
```
SPX__EXPORT__MODE=mirrored run.bat export
```
Placeholders mode creates a sibling directory with placeholder files (extension configurable by `export.placeholder_extension`).

## Configuration & Environment Overrides
Load order: defaults <- config.yaml (if present) <- environment <- (future CLI overrides).

Environment variables: prefix with `SPX__` and use double underscores for nesting.
Examples:
```
set SPX__SPOTIFY__CLIENT_ID=your_client_id
set SPX__EXPORT__MODE=placeholders
set SPX__MATCHING__FUZZY_THRESHOLD=0.82
```

Key sections:
- spotify.client_id, redirect_port, scope, cache_file
- library.paths, extensions, ignore_patterns
- matching.fuzzy_threshold
- export.mode, export.placeholder_extension, export.directory
- reports.directory
- database.path

### Obtaining a Spotify Client ID
1. Go to https://developer.spotify.com/dashboard and log in.
2. Click "Create an app" (or "Create app" if prompted for experience level; choose Basic/Intermediate as you like).
3. App Name: anything (e.g., "Local Playlist Sync"). Description: optional.
4. Which API/SDKs are you planning to use? Select only "Web API" (you do NOT need Ads API, Web Playback SDK, iOS, or Android for this tool).
5. Redirect URI: add `http://localhost:9876/callback` (port must match `spotify.redirect_port` config; default 9876). Even though there is no full webapp, the local auth flow spins up a tiny HTTP listener to capture the authorization code after you approve access in the browser.
  - If the Spotify dashboard flags this as "not secure" you can instead use the root path: `http://localhost:9876/` and set `SPX__SPOTIFY__REDIRECT_PATH=/` (or adjust in config). Both work with the embedded local server.
6. Save the app and copy the Client ID. (A Client Secret is not required for the PKCE flow used here.)
7. Set it via environment variable, e.g. on Windows CMD:
```
set SPX__SPOTIFY__CLIENT_ID=your_client_id_here
```
8. Run the initial pull to trigger authentication:
```
run.bat pull
```
You will be directed to a browser page to authorize; after approval the local redirect captures the code and a token cache (`tokens.json`) is written.

## Tests
Install dependencies then run:
```
python -m pytest -q
```
Included tests validate normalization, hashing, schema integrity, environment overrides, and basic match integration. Add more integration tests as logic expands.

## License
MIT (add actual license file later).
