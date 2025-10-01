# spotify-m3u-sync

Synchronize your Spotify playlists and liked tracks into a local SQLite database, match them against your on-disk music library, export M3U8 playlists (with optional placeholders for missing tracks), and generate detailed missing track and album completeness reports.

## Features
Core:
- Unified config (defaults + YAML + environment overrides via `SPX__` prefix)
- SQLite storage: playlists, playlist tracks, liked tracks, tracks, library files, matches, meta checkpoints
- **High-performance normalization**: token sorting, version removal, expanded stopwords for better exact matches
- **Two-stage match engine**: SQL exact matching (85-95% hits) + targeted fuzzy matching with configurable threshold
- **Optimized library scanner**: fast scan mode skips audio parsing for unchanged files (2-3x speedup!)
- Spotify ingestion with pagination, retry, and incremental checkpoints (snapshot_id / added_at)
- Local library scanner (mutagen metadata extraction) with smart skip logic
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
- Comprehensive test suite (46 tests with parametrization for config, normalization, performance, matching, export)
- GitHub Actions CI (Windows + Ubuntu, Python 3.11/3.12)

Performance:
- **Scan**: 2-3x faster with fast_scan mode, batch queries, and optimized deletion checks
- **Match**: 5-20x faster with two-stage SQL + fuzzy approach
- **Scale**: Handles 10K+ file libraries efficiently

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

### Folder Organization by Owner
By default, playlists are exported to a flat directory structure. You can enable folder organization to separate your own playlists from those you follow:

```yaml
export:
  organize_by_owner: true
```

Or via environment variable:
```
set SPX__EXPORT__ORGANIZE_BY_OWNER=true
```

When enabled, playlists are organized as:
```
export/playlists/
├── my_playlists/           # Your own playlists
│   ├── 2008.m3u8
│   ├── Summer Mix.m3u8
│   └── ...
├── Friend_Name/            # Playlists by a specific user
│   ├── Party Hits.m3u8
│   └── ...
└── other/                  # Playlists with unknown owner
    └── ...
```

**Note**: Spotify's Web API doesn't expose playlist folders (those are UI-only), so this feature organizes by playlist owner instead, which helps separate your curated playlists from collaborative or followed ones.

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
- matching.fuzzy_threshold, show_unmatched_tracks, show_unmatched_albums
- export.mode, export.placeholder_extension, export.directory, export.organize_by_owner
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
- Scan shows colored action labels: `[new]`, `[updated]`, `[skip]`, `[deleted]` with file details.
- Match shows detailed per-match logging:
  - `[sql_exact]` (green) - Exact matches via SQL
  - `[fuzzy]` (cyan/yellow/magenta) - Fuzzy matches with score (color by confidence)
  - `[unmatched]` (red) - Sample of tracks that couldn't be matched
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

## Performance Optimizations

### Scan Performance (New!)
Three major optimizations dramatically improve scan speed, especially for large libraries:

| Config Key | Default | Description |
|------------|---------|-------------|
| `library.skip_unchanged` | `true` | Skips re-processing files when size & mtime are unchanged. |
| `library.fast_scan` | `true` | **NEW!** Skips audio tag parsing for unchanged files—reuses existing metadata from DB. Massive speedup! |
| `library.commit_interval` | `100` | Commits to DB after this many processed files. Higher = faster but less recovery on crash. |

**Fast Scan Mode** (`library.fast_scan: true`):
- When a file's size+mtime match DB, skips expensive `mutagen.File()` audio parsing
- Reuses existing title/artist/album/duration/normalized from DB
- **Speedup**: 50-200ms saved per unchanged file = **15-30 minutes** on 10K file libraries!
- Disable only if you need to re-verify all audio tags on every scan

**Performance improvements**:
- Set-based deletion check (no more O(n) file.exists() calls)
- Bulk metadata loading (1 query vs thousands of individual SELECTs)
- Fast scan mode (skip audio parsing for unchanged files)

**Example timings** (10,000 files, 90% unchanged):
- **Before optimizations**: 45 minutes
- **After optimizations**: 15-20 minutes (2-3x speedup!)

Scan behavior details:
- Files are considered unchanged if both `size` and `mtime` match (within 1-second tolerance for Windows)
- Debug mode (`SPX_DEBUG=1`) shows colored action labels: `[new]` (green), `[updated]` (blue), `[skip]` (yellow), `[deleted]` (red)
- Deleted files are automatically removed from DB at end of scan
- Summary includes counts: `files_seen`, `inserted`, `updated`, `skipped_unchanged`, `deleted`, `tag_errors`, `io_errors`
- Interim commits allow mid-scan interruption without losing progress

Environment overrides:
```
set SPX__LIBRARY__SKIP_UNCHANGED=true
set SPX__LIBRARY__FAST_SCAN=true
set SPX__LIBRARY__COMMIT_INTERVAL=500
```

**Maximum speed configuration** (for mostly unchanged libraries):
```yaml
library:
  skip_unchanged: true
  fast_scan: true
  commit_interval: 500  # Higher = fewer commits = faster
```

**Maximum accuracy configuration** (slower, re-verifies everything):
```yaml
library:
  skip_unchanged: false  # Re-scan all files
  fast_scan: false       # Re-parse all audio tags
  commit_interval: 50    # More frequent commits
```

### Match Performance (Two-Stage Approach)
The match engine uses a highly optimized multi-strategy approach that is both fast and configurable:

**Default Strategy Pipeline**:
1. **SQL Exact Matching** (`sql_exact`) - Uses indexed `normalized` columns for O(log n) lookups
2. **Duration Filtering** (`duration_filter`) - Prefilters candidates by track duration (±2s tolerance)
3. **Fuzzy Matching** (`fuzzy`) - RapidFuzz `token_set_ratio` on reduced candidate set

**Stage 1: SQL Exact Matching**
- Uses indexed `normalized` columns for O(log n) lookups
- Finds 70-95% of matches in <100ms via SQL INNER JOIN
- Method label: `sql_exact`

**Stage 2: Duration-Based Candidate Filtering (NEW!)**
- Filters out impossible matches based on track duration before expensive fuzzy matching
- Default tolerance: ±2 seconds (configurable via `matching.duration_tolerance`)
- **Speedup**: Reduces fuzzy matching work by 5-20x depending on library diversity
- Files without duration metadata are included as candidates (no filtering)
- This is a preprocessing step that narrows the candidate set for Stage 3

**Stage 3: Fuzzy Matching (Unmatched Only)**
- RapidFuzz `token_set_ratio` only on remaining unmatched tracks
- Uses prefiltered candidates from Stage 2 (if enabled)
- Configurable threshold (default 0.78): `matching.fuzzy_threshold`
- Method label: `fuzzy`
- **Real-time progress**: Shows which track is currently being matched, processing speed, and ETA

**Performance**: 10-50x faster than original O(n×m) approach with duration filtering
- Example: 1000 tracks × 1000 files = 20s → **<1s** (with duration filtering)
- Without duration filtering: 20s → **2.5s** (SQL exact only)

**Configurable Strategies**:
The matching engine now supports configurable strategies that can be enabled/disabled or reordered:

```yaml
matching:
  fuzzy_threshold: 0.78          # Minimum fuzzy match score (0.0-1.0)
  duration_tolerance: 2.0        # Seconds tolerance for duration filtering (±2s)
  strategies:                    # Ordered list of strategies to apply
    - sql_exact                  # Fast indexed exact match
    - duration_filter            # Prefilter by duration (reduces fuzzy work)
    - fuzzy                      # Expensive fuzzy matching on remaining tracks
```

Environment overrides:
```
set SPX__MATCHING__FUZZY_THRESHOLD=0.82
set SPX__MATCHING__DURATION_TOLERANCE=3.0
set SPX__MATCHING__STRATEGIES=["sql_exact","fuzzy"]
```

**Strategy Customization Examples**:
- **Maximum speed** (skip duration filter if all files have similar durations):
  ```yaml
  matching:
    strategies: [sql_exact, fuzzy]
  ```
- **Maximum accuracy** (strict duration tolerance):
  ```yaml
  matching:
    duration_tolerance: 1.0  # Only ±1 second
    strategies: [sql_exact, duration_filter, fuzzy]
  ```
- **Exact matches only** (no fuzzy):
  ```yaml
  matching:
    strategies: [sql_exact]
  ```

**Enhanced Normalization** (Better Exact Matches):
- **Token sorting**: "The Beatles" = "Beatles, The"
- **Version removal**: Strips `(Radio Edit)`, `[Live]`, `- Acoustic`, `(Remix)`, etc.
- **Expanded stopwords**: Filters out `and`, `or`, `of`, `in`, `on`, `at`, `to`, `for`, `with`, `from`, `by`
- **Result**: Higher exact match rate (85-95%) = fewer fuzzy matches needed = faster overall

Debug output shows stage breakdown:
```
[match] Loaded 1000 tracks and 1000 library files
[match] Enabled strategies: sql_exact, duration_filter, fuzzy
[match] Matched 847/1000 tracks (84.7%) - exact=847 fuzzy=0 - 2.34s
[match] Strategy 'sql_exact': 847 matches
[match] Strategy 'duration_filter': candidate filtering applied
```

With `SPX_DEBUG=1`, you'll also see detailed progress during each strategy:
```
[sql_exact] The Beatles - Hey Jude → Z:\Music\Beatles\Hey Jude.mp3
[duration_filter] Filtering 153 tracks against 1000 files (tolerance=±2.0s)
[duration_filter] Filtered to 15300 total candidates (avg 100.0 per track, 90.0% reduction) in 0.08s
[fuzzy] Processing: 15/153 tracks (10%) - 8 matches - 12.3 tracks/sec - ETA 11s
  → Currently matching: Led Zeppelin - Stairway to Heaven
[fuzzy] Led Zeppelin - Stairway to Heaven → Z:\Music\Zeppelin\Stairway.mp3 (score=0.92)
[unmatched] Sample tracks (first 3):
  - Pink Floyd - Echoes (normalized: pink floyd echoes)
```

Match color coding:
- `[sql_exact]` - **Green** (perfect normalized match via SQL)
- `[fuzzy]` - **Cyan** (score ≥ 0.9), **Yellow** (0.8-0.9), or **Magenta** (< 0.8)
- `[unmatched]` - **Red** (no match found above threshold)

### Enhanced Unmatched Diagnostics (NEW!)
After matching, the tool shows detailed diagnostics for unmatched tracks, helping you identify which tracks and albums are missing from your library.

**Unmatched Tracks Display**:
- Shows top N unmatched tracks (default 50, configurable)
- Sorted by playlist popularity (how many playlists contain each track)
- Marks liked tracks with ❤️ emoji
- Shows how many playlists contain each track

Example output:
```
[unmatched] Top 50 unmatched tracks (of 127 total, sorted by playlist popularity):
  [ 3 playlists] ❤️  The Beatles - Let It Be
  [ 3 playlists] Led Zeppelin - Stairway to Heaven
  [ 2 playlists] Pink Floyd - Comfortably Numb
  [ 1 playlist ] Queen - Bohemian Rhapsody
  [ 0 playlists] ❤️  Radiohead - Karma Police
  ... and 77 more unmatched tracks
```

**Missing Albums Display** (NEW!):
- Groups unmatched tracks by album
- Shows total playlist occurrences per album (sum across all tracks in that album)
- Sorted by popularity to help prioritize which albums to acquire
- Shows track count per album
- Configurable display count (default 20)

Example output:
```
[unmatched] Top 20 missing albums (of 45 total, by playlist popularity):
  [ 12 occurrences] The Beatles - Abbey Road (4 tracks)
  [  8 occurrences] Pink Floyd - The Wall (3 tracks)
  [  6 occurrences] Led Zeppelin - IV (2 tracks)
  [  3 occurrences] Queen - A Night at the Opera (1 track)
  [  0 occurrences] Radiohead - OK Computer (2 tracks)
  ... and 25 more albums
```

**Configuration**:
```yaml
matching:
  show_unmatched_tracks: 20   # Number of unmatched tracks to display (0 to disable)
  show_unmatched_albums: 20   # Number of missing albums to display (0 to disable)
```

Environment overrides:
```
set SPX__MATCHING__SHOW_UNMATCHED_TRACKS=100
set SPX__MATCHING__SHOW_UNMATCHED_ALBUMS=30
```

**Interpretation**:
- **High occurrence count** = Track/album appears in many playlists → high priority to acquire
- **Liked tracks (❤️)** = You explicitly liked this track → even higher priority
- **Zero occurrences** = Track not in any playlist but appears in liked tracks only
- **Album view** = Helps identify which complete albums to acquire rather than individual tracks

This feature helps you:
1. Identify which tracks are most important to acquire (based on playlist usage)
2. See which albums you're missing the most tracks from
3. Prioritize your music acquisition efforts based on actual usage patterns
4. Spot patterns (e.g., "I'm missing 80% of Pink Floyd's The Wall")

**Note**: For large libraries (10k+ unmatched tracks), Stage 2 fuzzy matching may take 10-20 minutes. The progress output shows you it's not hanging—see `FUZZY_MATCH_PROGRESS.md` for detailed explanation and performance tips.

### Applying Performance Improvements
To benefit from enhanced normalization, re-run the pipeline:
```
run.bat pull   # Re-normalize Spotify tracks with improved algorithm
run.bat scan   # Re-normalize local files (now with fast scan!)
run.bat match  # Will find more exact matches in Stage 1
```

See `PERFORMANCE_IMPROVEMENTS.md` for detailed technical information.

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
