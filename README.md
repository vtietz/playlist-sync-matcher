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
Recent Spotify platform behavior increasingly prefers loopback IPs over the hostname `localhost` and allows HTTP for loopback. This tool now defaults to **`http://127.0.0.1:9876/callback`** (scheme `http`, host `127.0.0.1`, path `/callback`). HTTPS remains optional and can still be enabled for users who prefer it.

1. Go to https://developer.spotify.com/dashboard and log in.
2. Click "Create an app" (or "Create app").
3. App Name: anything (e.g., "Local Playlist Sync"). Description: optional.
4. Select only "Web API" for planned usage.
5. Add a Redirect URI: **`http://127.0.0.1:9876/callback`** (port must match `spotify.redirect_port`; default 9876). If you set `spotify.redirect_path` to `/`, register `http://127.0.0.1:9876/` instead.
6. Save and copy the Client ID (Client Secret not required for PKCE).
7. Set it via environment variable:
```
set SPX__SPOTIFY__CLIENT_ID=your_client_id_here
```
8. Trigger authentication:
```
run.bat pull
```
After approval a local token cache (`tokens.json`) is written.

### Redirect Configuration Overview
Config keys relevant to the redirect:
- `spotify.redirect_scheme` (default `http`)
- `spotify.redirect_host` (default `127.0.0.1`)
- `spotify.redirect_port` (default `9876`)
- `spotify.redirect_path` (default `/callback`)

The effective redirect URI is printed by:
```
run.bat redirect-uri
```
Or for just the spotify section of config:
```
run.bat config -s spotify
```

### Optional HTTPS Mode
If you prefer HTTPS (not required for loopback IP):
1. Register `https://localhost:9876/callback` (or `/` variant) in the Spotify dashboard.
2. Set overrides:
```
set SPX__SPOTIFY__REDIRECT_SCHEME=https
set SPX__SPOTIFY__REDIRECT_HOST=localhost
```
Self-signed certificate handling:
- If `cryptography` is installed or `openssl` exists, the tool will auto-create `cert.pem` / `key.pem` when starting the local listener.
- You can also supply existing files via `SPX__SPOTIFY__CERT_FILE` / `SPX__SPOTIFY__KEY_FILE`.

Manual generation (optional):
```
openssl req -x509 -newkey rsa:2048 -nodes -keyout key.pem -out cert.pem -days 365 -subj "/CN=localhost"
```

### Environment Overrides (HTTP / default)
```
set SPX__SPOTIFY__CLIENT_ID=your_client_id
set SPX__SPOTIFY__REDIRECT_SCHEME=http
set SPX__SPOTIFY__REDIRECT_HOST=127.0.0.1
set SPX__SPOTIFY__REDIRECT_PORT=9876
set SPX__SPOTIFY__REDIRECT_PATH=/callback
```

### Enabling Debug / Verbose Logging
There are two ways to turn on detailed logging:

1. One-off verbose ingestion:
```
run.bat pull -v
```
2. Persistent debug mode via config/environment (auto-enables all SPX_DEBUG checks):
```
set SPX__DEBUG=true
```
Or add `SPX__DEBUG=true` to your `.env` (with dotenv loading enabled outside tests). When `debug` is true the application sets `SPX_DEBUG=1` internally so any component gated on `os.environ['SPX_DEBUG']` becomes verbose (OAuth flow, ingestion, etc.).

Disable again by unsetting or setting `SPX__DEBUG=false`.

When debug mode is active:
- OAuth flow prints redirect, state, and token exchange milestones.
- Pull (ingestion) prints pagination, playlist skips/updates, liked-track boundary, and timing.
- Scan lists each discovered media file (`[scan] <path>`) plus a completion summary.
- Match / export logging may be expanded in future; for now they remain concise.
- Match: with debug shows total candidates, match count, duration + up to 5 sample matches.
- Export: with debug shows per-playlist summary (kept/missing/placeholders) and output file path.


### Login Command
Authenticate (or refresh token) without running ingestion:
```
run.bat login
```
Force a fresh OAuth flow ignoring cache:
```
run.bat login --force
```
Then run the pipeline pieces (pull/scan/match/export/report) or full sync.

Token cache file: `tokens.json` (path configurable by `spotify.cache_file`).

Browser trust warning: A self-signed cert will trigger a warning the first time—accept it only for `localhost`.

### Troubleshooting INVALID_CLIENT: Insecure redirect URI
If the browser shows `INVALID_CLIENT: Insecure redirect URI`:
1. The registered redirect URI does *not* exactly match the one the tool used. Compare with:
   ```
   run.bat redirect-uri
   ```
2. Confirm you registered exactly that value in the Spotify dashboard. (For default config: `http://127.0.0.1:9876/callback`)
3. Avoid mixing `localhost` and `127.0.0.1` unless you intentionally switched hosts.
4. If switching from previous HTTPS setup, remove old `https://localhost:9876/callback` entry if you now use HTTP/IP, or keep both registered if you intend to alternate.
5. Try a private window to eliminate cached redirect metadata.
6. For HTTPS mode specifically, ensure cert generation succeeded (delete `cert.pem`/`key.pem` to force regeneration if needed).
7. Change the path temporarily (`SPX__SPOTIFY__REDIRECT_PATH=/`) and register the matching variant to rule out a stale path mismatch.

Printing the exact active redirect URI (already available via command):
```
run.bat redirect-uri
```

## Tests
A `pytest.ini` is included so the project root is on the import path (enables `import spx` inside tests). The batch script bootstraps a virtual environment and installs runtime dependencies automatically each run.

Quick run (Windows):
```
run.bat test -q
```
Run a specific test file:
```
run.bat test tests\test_hashing.py -q
```
Run with verbose output and stop after first failure:
```
run.bat test -vv -x
```
Direct invocation (bypassing batch helper):
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q
```

If you add development-only tools (linters, type checkers), consider adding a `requirements-dev.txt` or migrating to a `pyproject.toml` with optional extras. For now, only runtime packages are required for the test suite.

## License
MIT (add actual license file later).

### Environment JSON Array Overrides
You can override list-valued settings via JSON arrays in environment variables. Example:
```
set SPX__LIBRARY__PATHS=["D:/Music","E:/MoreMusic"]
```
Objects are also supported:
```
set SPX__SPOTIFY__EXTRA={"foo":123}
```
Values starting with `[` or `{` are parsed as JSON; otherwise normal scalar coercion applies.
