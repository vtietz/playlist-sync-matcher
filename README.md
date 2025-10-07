# playlist-sync-matcher

Turn your streaming playlists (e.g. from Spotify) into M3U playlist files that point to your actual local music files. The codebase has been prepared with a lightweight abstraction so new providers can be added with minimal churn.

## What it does
Instead of just getting a list of song names, you get working playlists that:
- **Link to your local files** – Each playlist entry points to the real MP3/FLAC file on your drive
- **Show what's missing** – Clear reports of tracks and albums you don't have locally
- **Work everywhere** – Standard M3U files that any music player can use

Perfect for syncing to devices, offline listening, or just organizing your collection around your streaming habits.

## How it works
1. **Reads your Spotify playlists** – Pulls all your playlist info  
2. **Scans your music folders** – Finds all the music files you own
3. **Matches them up** – Smart matching connects streaming tracks to local files
4. **Creates M3U playlists** – Generates playlist files pointing to your actual music
5. **Reports what's missing** – Shows you exactly what tracks and albums to download

No more manually recreating playlists or wondering what you're missing from your collection.

## Installation

### Option 1: Standalone Executable (Easiest)
No Python required! Download pre-built binaries from [Releases](https://github.com/vtietz/playlist-sync-matcher/releases):

**Windows**:
```bash
# Download playlist-sync-matcher-windows-amd64.exe
# Rename to psm.exe for convenience
psm.exe build
```

**Linux/Mac**:
```bash
# Download appropriate binary
chmod +x playlist-sync-matcher-linux-amd64
./playlist-sync-matcher-linux-amd64 build

# Or rename for convenience:
mv playlist-sync-matcher-linux-amd64 psm
./psm build
```

### Option 2: Python Source (Recommended for Development)
Requires **Python 3.9+**. The scripts will automatically set up a virtual environment:

**Windows**:
```bash
run.bat build
run.bat install   # (optional explicit dependency install)
```

**Linux/Mac**:
```bash
chmod +x run.sh
./run.sh build
./run.sh install  # (optional explicit dependency install)
```

> **First run**: The script creates a `.venv` directory and installs dependencies automatically.

## Quick Start

1. **Get a Spotify Client ID** (see [Setup](#spotify-setup) below)

2. **Create a `.env` file** for permanent configuration:
   ```bash
   # .env
   PSM__PROVIDERS__SPOTIFY__CLIENT_ID=your_client_id_here
   PSM__LIBRARY__PATHS=["C:/Music"]
   PSM__EXPORT__MODE=mirrored
   PSM__EXPORT__ORGANIZE_BY_OWNER=true
   ```
   
   > **Tip**: See `.env.example` for all available options. For one-time overrides, use `set` commands instead.
   
   > **Note**: Currently only **one provider** can be configured at a time. Multi-provider support is planned for a future release.

3. **Run the full build**:
   ```bash
   run.bat build     # Windows
   ./run.sh build    # Linux/Mac
   ```

This will authenticate with Spotify, scan your library, match tracks, export playlists, and generate reports.

## Features

| Capability | Value |
|------------|-------|
| Deterministic playlist exports | Stable M3U8 ordering, collision‑safe filenames |
| Multiple export modes | strict, mirrored, placeholders |
| Owner grouping (optional) | Organize playlists into folders by owner |
| Scoring-based matching | Weighted signals (exact/fuzzy/album/year/duration/ISRC) with confidence tiers |
| Rich reporting | Missing tracks, album completeness, unmatched diagnostics |
| Library quality analysis | Surface metadata gaps & low bitrate files |
| Fast scan mode | Skips unchanged files (mtime+size) to save minutes on large libraries |
| Provider‑ready architecture | Pluggable registry & namespaced schema |
| Clean schema v1 | Composite (id, provider) keys for future multi‑provider coexistence |

## Common Commands

> **Note**: Replace `run.bat` with `./run.sh` on Linux/Mac, or use `psm` if using standalone executable.

**Get workflow guidance**:
```bash
run.bat --help           # Shows typical workflow examples
./run.sh --help          # Linux/Mac Python
psm --help               # Standalone executable
```

**Full pipeline (recommended)**:
```bash
run.bat build         # Windows Python
./run.sh build        # Linux/Mac Python
psm build             # Standalone executable (all platforms)
```

**Individual steps**:
```bash
run.bat pull          # Fetch Spotify data
run.bat scan          # Scan local library → Shows directories + live progress
run.bat match         # Match tracks → Auto-generates match reports (CSV + HTML)
run.bat export        # Export playlists
```

**Analysis & Reports**:
```bash
run.bat analyze             # Analyze library quality → Auto-generates quality reports (CSV + HTML)
run.bat report              # Generate HTML/CSV reports from existing database
                            #   Options: --match-reports, --analysis-reports, --no-match-reports, --no-analysis-reports
```

**Other commands**:
```bash
run.bat version
run.bat install            # Install or update dependencies
run.bat config              # Show current configuration
run.bat test -q             # Run tests (Python source only)
```

### Library Scan

Builds a searchable database of your music files:

```bash
run.bat scan [--fast] [--paths PATH1 PATH2 ...]
```

**Features**:
- **Visual Progress**: Shows directories being scanned + live progress counter (every 100 files)
- **Fast Mode** (`--fast`): Skips files unchanged since last scan (compares mtime)
- **Cleanup**: Automatically removes deleted files from database
- **Debug Mode**: Set `LOG_LEVEL=DEBUG` to see current directory being scanned

**Example Output**:
```
Scanning 2 directories:
  • Z:\Artists\
  • Z:\Sampler\

100 files processed | 50 skipped | 38.3 files/s
200 files processed | 150 skipped | 40.4 files/s
...
✓ Library: 25 new 10 updated 1959 unchanged 6 deleted in 24.01s
```

### Automatic Reporting

**`match` command automatically generates:**
- `matched_tracks.csv` / `.html` - All matched tracks with confidence scores, clickable Spotify track links
- `unmatched_tracks.csv` / `.html` - All unmatched Spotify tracks, clickable Spotify track links
- `unmatched_albums.csv` / `.html` - Unmatched albums grouped by popularity
- `playlist_coverage.csv` / `.html` - Playlist coverage analysis with clickable Spotify playlist links
- Console: Top 20 unmatched tracks + top 10 unmatched albums (INFO mode)

**`analyze` command automatically generates:**
- `metadata_quality.csv` / `.html` - All files with quality issues (missing tags, low bitrate)
- Console: **Intelligent grouping by album** - Shows top albums with most files needing fixes
  - Example: "📁 The Beatles - Abbey Road (18 files missing year)"
  - Maximizes impact: Fix one album → fix many files at once

**`report` command (standalone):**
Generate reports from existing database without re-running match/analyze:
```bash
run.bat report                       # Generate all reports (default)
run.bat report --no-analysis-reports # Generate only match reports
run.bat report --no-match-reports    # Generate only analysis reports
```

All HTML reports include:
- **Sortable tables** - Click column headers to sort
- **Search & pagination** - Powered by jQuery DataTables
- **Clickable Spotify links** - Track IDs, playlist names link directly to Spotify
- **Navigation dashboard** - `index.html` provides quick access to all reports

Reports saved to `export/reports/` by default.

### Single Playlist Operations (Optional)

Work with individual playlists instead of syncing everything:

```bash
# List all playlists with IDs
run.bat playlists list

# List with Spotify URLs (clickable links)
run.bat playlists list --show-urls

# Pull a single playlist from Spotify
run.bat playlist pull <PLAYLIST_ID>

# Match a single playlist against your library
run.bat playlist match <PLAYLIST_ID>

# Export a single playlist to M3U
run.bat playlist export <PLAYLIST_ID>

# Build a single playlist (pull + match + export)
run.bat playlist build <PLAYLIST_ID>

# (Experimental) Push local order back to remote (preview then apply)
run.bat playlist push <PLAYLIST_ID>                # DB mode (uses DB ordering)
run.bat playlist push <PLAYLIST_ID> --file exported.m3u8   # File mode (derive from M3U)
run.bat playlist push <PLAYLIST_ID> --apply        # Apply changes (after preview)
```

**Example workflow**:
```bash
# 1. List all playlists to find the ID you want
run.bat playlists list

# Output example:
# ID                       Name                 Owner        Tracks
# -----------------------------------------------------------------------
# 37i9dQZF1DXcBWIGoYBM5M   Today's Top Hits     Spotify      50
# 3cEYpjA9oz9GiPac4AsH4n   My Workout Mix       YourName     127

# 2. Get URLs to open playlists in Spotify
run.bat playlists list --show-urls

# Output shows clickable links:
#   → https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M

# 3. Build just your workout playlist
run.bat playlist build 3cEYpjA9oz9GiPac4AsH4n
```

**Spotify URLs in M3U files**:
All exported M3U files now include the Spotify playlist URL as a comment in the header:
```m3u
#EXTM3U
# Spotify: https://open.spotify.com/playlist/3cEYpjA9oz9GiPac4AsH4n
#EXTINF:180,Artist - Song Title
C:\Music\Artist\Song.mp3
```

**M3U Filename Format**:
To prevent collisions when multiple playlists have the same name, exported M3U files include a unique identifier:
- Format: `<PlaylistName>_<First8CharsOfID>.m3u8`
- Example: `Workout Mix_3cEYpjA9.m3u8`
- The 8-character suffix is the first 8 characters of the Spotify playlist ID, ensuring each file is unique even if playlist names are identical

**Why use single-playlist commands?**
- **Faster**: Only process one playlist instead of all
- **Testing**: Try different settings on one playlist before full build
- **Selective updates**: Update frequently-changed playlists without re-processing everything
- **Debugging**: Isolate matching issues to a specific playlist
- **Easy sharing**: Copy Spotify URLs from list or M3U files to share with others

Additional detail & examples moved to: `docs/library_analysis.md`.

### Providers & Capabilities

List registered providers and key capability flags (e.g., whether push/replace is supported):
```bash
psm providers capabilities
run.bat providers capabilities
```
Currently only Spotify is registered; additional providers can be added following `docs/providers.md`.

### Experimental: Reverse Push (Playlist Replace)

You can now push a single playlist's ordering back to Spotify (full replace semantics). Two modes:

1. **DB Mode (no file)** – Omit `--file`; the ordering stored in the database (from last pull) becomes the desired ordering.
2. **File Mode** – Provide `--file path/to/playlist.m3u8`; the tool parses local file paths, maps them back to Spotify track IDs using existing matches, and constructs the desired list.

Safety & Behavior:
- Preview only by default – shows positional changes, additions, removals.
- Use `--apply` to perform the remote replace.
- Ownership enforced – refuses to modify playlists not owned by the current user.
- Full replace only – no incremental diff patching (simpler & deterministic).
- Unresolved file paths (not matched to a track ID) are skipped and counted.

Examples:
```bash
# Preview changes using DB ordering
run.bat playlist push 3cEYpjA9oz9GiPac4AsH4n

# Preview from exported M3U file
run.bat playlist push 3cEYpjA9oz9GiPac4AsH4n --file export/playlists/MyList_xxxxxxxx.m3u8

# Apply changes after reviewing preview output
run.bat playlist push 3cEYpjA9oz9GiPac4AsH4n --apply
```

This feature is experimental and currently implemented only for Spotify; provider abstraction keeps the path open for future services.

## Configuration (Summary)

### Using .env File

Create a `.env` file in the project root (or same directory as executable):

```bash
# .env - Simple key=value format
PSM__PROVIDERS__SPOTIFY__CLIENT_ID=your_client_id_here
PSM__LIBRARY__PATHS=["C:/Music","D:/Music"]
PSM__EXPORT__MODE=mirrored
PSM__EXPORT__ORGANIZE_BY_OWNER=true
PSM__MATCHING__FUZZY_THRESHOLD=0.82
PSM__MATCHING__DURATION_TOLERANCE=2.0
PSM__MATCHING__SHOW_UNMATCHED_TRACKS=50
PSM__MATCHING__SHOW_UNMATCHED_ALBUMS=20
```

> **Tip**: Copy `.env.example` to `.env` and edit your values. The tool automatically loads `.env` on startup.

### Temporary Overrides

Override any setting for a single command without editing `.env`:

**Windows**:
```bash
set PSM__EXPORT__MODE=strict
run.bat export
```

**Linux/Mac**:
```bash
export PSM__EXPORT__MODE=strict
./run.sh export
```

**Standalone executable**:
```bash
set PSM__EXPORT__MODE=strict    # Windows
export PSM__EXPORT__MODE=strict # Linux/Mac
psm export
```

### Priority Order

Settings are merged in this order (later overrides earlier):
1. **Built-in defaults** (in `psm/config.py`)
2. **`.env` file** (if exists)
3. **Shell environment variables** (`set`/`export` commands)

### Key Options (See docs/configuration.md for full list)

**Provider (Spotify)**:
- `PSM__PROVIDERS__SPOTIFY__CLIENT_ID` - Your Spotify app client ID (required)
- `PSM__PROVIDERS__SPOTIFY__REDIRECT_PORT` - OAuth redirect port (default: 9876)

**Library**:
- `PSM__LIBRARY__PATHS` - Folders to scan (JSON array, e.g., `["C:/Music"]`)
- `PSM__LIBRARY__EXTENSIONS` - File types (default: `[".mp3",".flac",".m4a",".ogg"]`)
- `PSM__LIBRARY__FAST_SCAN` - Skip re-parsing unchanged files (default: true)
- `PSM__LIBRARY__COMMIT_INTERVAL` - Batch size for DB commits (default: 100)
- `PSM__LIBRARY__MIN_BITRATE_KBPS` - Minimum bitrate for quality analysis (default: 320)

**Matching**:
- `PSM__MATCHING__FUZZY_THRESHOLD` - Match sensitivity 0.0-1.0 (default: 0.78)
- `PSM__MATCHING__DURATION_TOLERANCE` - Duration match tolerance in seconds (default: 2.0)
- `PSM__MATCHING__SHOW_UNMATCHED_TRACKS` - Diagnostic output count (default: 20)
- `PSM__MATCHING__SHOW_UNMATCHED_ALBUMS` - Album diagnostic count (default: 20)
- `PSM__MATCHING__USE_YEAR` - Include year in matching (default: false)
- `PSM__MATCHING__MAX_CANDIDATES_PER_TRACK` - Performance cap for candidates per track (default: 500)

**Export**:
- `PSM__EXPORT__MODE` - strict | mirrored | placeholders (default: strict)
- `PSM__EXPORT__ORGANIZE_BY_OWNER` - Group by owner (default: false)
- `PSM__EXPORT__DIRECTORY` - Output directory (default: export/playlists)

**Database**:
- `PSM__DATABASE__PATH` - SQLite file location (default: data/spotify_sync.db)

**Logging**:
- `PSM__LOG_LEVEL` - Control output verbosity: `DEBUG` (detailed diagnostics), `INFO` (normal progress, default), `WARNING` (quiet, errors only)

See `.env.example` for complete list with explanations.

### Export Modes

- **strict** (default): Only matched tracks
- **mirrored**: Full order with comments for missing tracks  
- **placeholders**: Like mirrored but creates placeholder files

### Folder Organization

Organize playlists by owner instead of flat structure. Set in `.env`:

```bash
PSM__EXPORT__ORGANIZE_BY_OWNER=true
```

Result:
```
export/playlists/
├── my_playlists/      # Your playlists
├── Friend_Name/       # Followed playlists
└── other/             # Unknown owner
```

**Note**: Spotify's API doesn't expose playlist folders (UI-only), so we organize by owner instead.

### Spotify Setup

This tool uses **HTTP loopback** (recommended by Spotify) with default redirect: `http://127.0.0.1:9876/callback`

**Steps**:
1. Go to https://developer.spotify.com/dashboard
2. Create an app (name: anything, e.g., "Playlist Build")
3. Add Redirect URI: `http://127.0.0.1:9876/callback`
4. Copy the Client ID
5. Add it to your `.env` file:
   ```bash
   PSM__PROVIDERS__SPOTIFY__CLIENT_ID=your_client_id_here
   ```
   Or set temporarily (Windows: `set`, Linux/Mac: `export`)
6. Authenticate:
   ```bash
   run.bat pull      # Windows
   ./run.sh pull     # Linux/Mac
   psm pull          # Standalone executable
   ```

Token cache is saved to `tokens.json` and refreshed automatically.

Detailed architecture & matching docs moved to: `docs/architecture.md` and `docs/matching.md`.

## Advanced (See docs for details)

### Diagnostics

When running `run.bat match`, the tool shows:
- Top 20 unmatched tracks (configurable via `matching.show_unmatched_tracks`)
- Top 20 unmatched albums (configurable via `matching.show_unmatched_albums`)

**Detailed Logging**:
Enable persistent detailed logging in `.env`:
```bash
PSM__LOG_LEVEL=DEBUG
```
Detailed logging provides diagnostic output for OAuth flow, ingestion, scanning, matching (with match scores), and export summaries. Use `INFO` (default) for normal operations or `WARNING` for quiet mode (errors only).

### Authentication

**Login without build**:
```bash
run.bat login         # Windows
./run.sh login        # Linux/Mac
psm login             # Standalone
```
Force fresh OAuth (ignore token cache):
```bash
run.bat login --force
./run.sh login --force
psm login --force
```

Token cache: `tokens.json` (auto-refreshed).

### Troubleshooting

**INVALID_CLIENT: Insecure redirect URI**
- Check your registered redirect URI exactly matches the tool's configuration:
  ```
  run.bat redirect-uri
  ```
- Default: `http://127.0.0.1:9876/callback`
- Don't mix `localhost` and `127.0.0.1` unless intentional

**Optional HTTPS Mode** (not required):
1. Register `https://localhost:9876/callback` in Spotify dashboard
2. Add to `.env`:
   ```bash
   PSM__PROVIDERS__SPOTIFY__REDIRECT_SCHEME=https
   PSM__PROVIDERS__SPOTIFY__REDIRECT_HOST=localhost
   ```
3. Auto-generates self-signed cert if `cryptography` or `openssl` available

## Tests

**Python source only** (not available for standalone executables):
```bash
run.bat test -q           # Windows
./run.sh test -q          # Linux/Mac
```

Run specific test:
```bash
run.bat test tests\test_hashing.py -q       # Windows
./run.sh test tests/test_hashing.py -q      # Linux/Mac
```

## Performance

**Fast Scan Mode** (enabled by default):
- Skips re-parsing audio tags for unchanged files (size + mtime match)
- Reuses metadata from database
- Saves 50-200ms per file = **15-30 minutes** on 10K files

Disable if you need to re-verify all tags in `.env`:
```bash
PSM__LIBRARY__FAST_SCAN=false
```

Other optimizations:
- `library.skip_unchanged: true` - Skip unchanged files
- `library.commit_interval: 100` - Batch database commits

## Technical Details

Condensed overview (see `docs/architecture.md` for full explanation):

- **Database**: SQLite, composite (id, provider) keys for tracks & playlists
- **Concurrency**: WAL mode enables safe parallel operations (see below)
- **Matching**: Weighted scoring system with confidence tiers (CERTAIN/HIGH/MEDIUM/LOW)
- **Performance**: LRU normalization cache, fast scan, bulk inserts, indexed normalized/isrc columns
- **Schema versioning**: `meta` table entry `schema_version=1` (clean baseline)

### Concurrent Operations

**You can safely run multiple commands simultaneously** thanks to SQLite's Write-Ahead Logging (WAL) mode:

```bash
# Example: Run all three in parallel (different terminals)
run.bat pull    # Terminal 1: Fetch Spotify data
run.bat scan    # Terminal 2: Scan local library  
run.bat match   # Terminal 3: Match tracks
```

**How it works**:
- WAL mode allows multiple readers + one writer concurrently
- 30-second timeout automatically retries brief lock conflicts
- No database corruption or "database is locked" errors
- Each operation is isolated and atomic

**What to expect**:
- ✅ **Safe**: Operations won't corrupt data or interfere with each other
- ✅ **Fast**: I/O-bound tasks (scan, pull) benefit from parallelization
- ⚠️ **Data visibility**: New data from concurrent operations appears on next run
  - Example: If `match` runs while `pull` is adding tracks, newly added tracks won't be matched until next `match` run
  - This is normal behavior, not a bug

**Performance tip**: Running compute-heavy operations simultaneously (e.g., 3+ concurrent scans) may slow down due to disk I/O contention, but won't cause errors.

## Multi-Provider Architecture

Implemented: provider column + composite keys, provider registry, config key `provider`.
Next steps (external contributions welcome):
- Additional provider client(s)
- Optional ISRC-centric canonical cross-provider table
- Playlist cloning between providers
- Rate limiting & unified error model

See: `docs/providers.md` for full integration guide.

## License

MIT License

---

## Developer Docs

Development, release process, and provider extension details live in the `docs/` directory:

- `docs/architecture.md`
- `docs/matching.md`
- `docs/configuration.md`
- `docs/library_analysis.md`
- `docs/troubleshooting.md`
- `docs/development.md`
- `docs/providers.md`

---

**Need Help?** Quick references:
- `run.bat config` - View current settings
- `run.bat redirect-uri` - Show OAuth redirect
- `.env.example` - All environment variables
- `PSM__LOG_LEVEL=DEBUG` - Enable detailed diagnostic logging
Values starting with `[` or `{` are parsed as JSON; objects are supported (see configuration docs).
