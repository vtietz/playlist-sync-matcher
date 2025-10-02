# spotify-m3u-sync

Sync your Spotify playlists to M3U8 files matched against your local music library, with detailed reporting on missing tracks and album completeness.

## Installation

### Option 1: Standalone Executable (Easiest)
No Python required! Download pre-built binaries from [Releases](https://github.com/vtietz/spotify-m3u-sync/releases):

**Windows**:
```bash
# Download spotify-m3u-sync-windows-amd64.exe
# Rename to spx.exe for convenience
spx.exe sync
```

**Linux/Mac**:
```bash
# Download appropriate binary
chmod +x spotify-m3u-sync-linux-amd64
./spotify-m3u-sync-linux-amd64 sync

# Or rename for convenience:
mv spotify-m3u-sync-linux-amd64 spx
./spx sync
```

### Option 2: Python Source (Recommended for Development)
Requires **Python 3.9+**. The scripts will automatically set up a virtual environment:

**Windows**:
```bash
run.bat sync
```

**Linux/Mac**:
```bash
chmod +x run.sh
./run.sh sync
```

> **First run**: The script creates a `.venv` directory and installs dependencies automatically.

## Quick Start

1. **Get a Spotify Client ID** (see [Setup](#spotify-setup) below)

2. **Create a `.env` file** for permanent configuration:
   ```bash
   # .env
   SPX__SPOTIFY__CLIENT_ID=your_client_id_here
   SPX__LIBRARY__PATHS=["C:/Music"]
   SPX__EXPORT__MODE=mirrored
   SPX__EXPORT__ORGANIZE_BY_OWNER=true
   ```
   
   > **Tip**: See `.env.example` for all available options. For one-time overrides, use `set` commands instead.

3. **Run the full sync**:
   ```bash
   run.bat sync      # Windows
   ./run.sh sync     # Linux/Mac
   ```

This will authenticate with Spotify, scan your library, match tracks, export playlists, and generate reports.

## What You Get

**Playlists**: M3U8 files matching Spotify playlist order
- **Strict mode**: Only matched tracks
- **Mirrored mode**: Full order with comments for missing tracks
- **Placeholders mode**: Creates placeholder files to preserve gaps
- **Folder organization**: Group playlists by owner (yours vs. others)

**Reports**:
- **Missing tracks**: CSV of unmatched Spotify tracks sorted by popularity
- **Album completeness**: Status of your albums (complete/partial/missing)
- **Diagnostic output**: Top unmatched tracks and albums with playlist counts

**Performance**: Handles 10K+ file libraries efficiently with smart caching and two-stage matching (SQL exact + fuzzy)

## Common Commands

> **Note**: Replace `run.bat` with `./run.sh` on Linux/Mac, or use `spx` if using standalone executable.

Full pipeline (recommended):
```bash
run.bat sync          # Windows Python
./run.sh sync         # Linux/Mac Python
spx sync              # Standalone executable (all platforms)
```

Individual steps:
```bash
run.bat pull          # Fetch Spotify data
run.bat scan          # Scan local library  
run.bat match         # Match tracks
run.bat export        # Export playlists
run.bat report        # Generate missing tracks CSV
```

Other commands:
```bash
run.bat version
run.bat config              # Show current configuration
run.bat report-albums       # Album completeness report
run.bat analyze             # Analyze library metadata quality
run.bat test -q             # Run tests (Python source only)
```

### Single Playlist Operations

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

# Sync a single playlist (pull + match + export)
run.bat playlist sync <PLAYLIST_ID>
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

# 3. Sync just your workout playlist
run.bat playlist sync 3cEYpjA9oz9GiPac4AsH4n
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
- **Testing**: Try different settings on one playlist before full sync
- **Selective updates**: Update frequently-changed playlists without re-processing everything
- **Debugging**: Isolate matching issues to a specific playlist
- **Easy sharing**: Copy Spotify URLs from list or M3U files to share with others

### Library Quality Analysis

Analyze your local music library's metadata quality to identify files with missing tags or low bitrate that might hurt matching accuracy:

```bash
# Basic analysis (shows summary + top 20 issues)
run.bat analyze

# Verbose mode (shows all issues)
run.bat analyze --verbose

# Custom bitrate threshold (default: 320 kbps)
run.bat analyze --min-bitrate 256

# Limit number of issues shown (default: 20)
run.bat analyze --max-issues 50

# Combine options
run.bat analyze --min-bitrate 256 --max-issues 100 --verbose
```

**What it checks**:
- **Missing metadata**: Files without artist, title, album, or year tags
- **Low bitrate**: Files below your quality threshold (default: 320 kbps)

**Example output**:
```
Library Quality Analysis
═══════════════════════════════════════════════════════════════

Summary Statistics:
  Total files:                        10,245
  Files with issues:                     387 (3.8%)
  
  Missing artist:                         12 (0.1%)
  Missing title:                          15 (0.1%)
  Missing album:                         124 (1.2%)
  Missing year:                          289 (2.8%)
  Low bitrate (< 320 kbps):               67 (0.7%)

Issues Found (showing 20 of 387):
  
  Missing: album, year
    → C:\Music\Downloads\Various - Track.mp3
    
  Missing: year | Bitrate: 128 kbps
    → C:\Music\Old\Artist - Song.mp3
```

**Configuration**:
```bash
# Set default bitrate threshold in .env
SPX__LIBRARY__MIN_BITRATE_KBPS=320
```

**Why this matters**:
- **Better matching**: Complete metadata helps album-based and year-based matching strategies
- **Quality control**: Identify low-bitrate files that should be replaced
- **Debugging**: Find files that won't match due to missing tags
- **Library maintenance**: Prioritize which files need tag cleanup

## Configuration

### Using .env File (Primary Configuration)

Create a `.env` file in the project root (or same directory as executable):

```bash
# .env - Simple key=value format
SPX__SPOTIFY__CLIENT_ID=your_client_id_here
SPX__LIBRARY__PATHS=["C:/Music","D:/Music"]
SPX__EXPORT__MODE=mirrored
SPX__EXPORT__ORGANIZE_BY_OWNER=true
SPX__MATCHING__FUZZY_THRESHOLD=0.82
SPX__MATCHING__DURATION_TOLERANCE=2.0
SPX__MATCHING__SHOW_UNMATCHED_TRACKS=50
SPX__MATCHING__SHOW_UNMATCHED_ALBUMS=20
```

> **Tip**: Copy `.env.example` to `.env` and edit your values. The tool automatically loads `.env` on startup.

### Temporary Overrides: Environment Variables

Override any setting for a single command without editing `.env`:

**Windows**:
```bash
set SPX__EXPORT__MODE=strict
run.bat export
```

**Linux/Mac**:
```bash
export SPX__EXPORT__MODE=strict
./run.sh export
```

**Standalone executable**:
```bash
set SPX__EXPORT__MODE=strict    # Windows
export SPX__EXPORT__MODE=strict # Linux/Mac
spx export
```

### Configuration Priority

Settings are merged in this order (later overrides earlier):
1. **Built-in defaults** (in `spx/config.py`)
2. **`.env` file** (if exists)
3. **Shell environment variables** (`set`/`export` commands)

### Key Configuration Options

**Spotify**:
- `SPX__SPOTIFY__CLIENT_ID` - Your Spotify app client ID (required)
- `SPX__SPOTIFY__REDIRECT_PORT` - OAuth redirect port (default: 9876)

**Library**:
- `SPX__LIBRARY__PATHS` - Folders to scan (JSON array, e.g., `["C:/Music"]`)
- `SPX__LIBRARY__EXTENSIONS` - File types (default: `[".mp3",".flac",".m4a",".ogg"]`)
- `SPX__LIBRARY__FAST_SCAN` - Skip re-parsing unchanged files (default: true)
- `SPX__LIBRARY__COMMIT_INTERVAL` - Batch size for DB commits (default: 100)
- `SPX__LIBRARY__MIN_BITRATE_KBPS` - Minimum bitrate for quality analysis (default: 320)

**Matching**:
- `SPX__MATCHING__FUZZY_THRESHOLD` - Match sensitivity 0.0-1.0 (default: 0.78)
- `SPX__MATCHING__DURATION_TOLERANCE` - Duration match tolerance in seconds (default: 2.0)
- `SPX__MATCHING__SHOW_UNMATCHED_TRACKS` - Diagnostic output count (default: 20)
- `SPX__MATCHING__SHOW_UNMATCHED_ALBUMS` - Album diagnostic count (default: 20)
- `SPX__MATCHING__USE_YEAR` - Include year in matching (default: false)
- `SPX__MATCHING__STRATEGIES` - Matching strategy order (default: `["sql_exact","album_match","year_match","duration_filter","fuzzy"]`)

**Export**:
- `SPX__EXPORT__MODE` - strict | mirrored | placeholders (default: strict)
- `SPX__EXPORT__ORGANIZE_BY_OWNER` - Group by owner (default: false)
- `SPX__EXPORT__DIRECTORY` - Output directory (default: export/playlists)

**Database**:
- `SPX__DATABASE__PATH` - SQLite file location (default: data/spotify_sync.db)

**Logging**:
- `SPX__LOG_LEVEL` - Control output verbosity: `DEBUG` (detailed diagnostics), `INFO` (normal progress, default), `WARNING` (quiet, errors only)

See `.env.example` for complete list with explanations.

### Export Modes

- **strict** (default): Only matched tracks
- **mirrored**: Full order with comments for missing tracks  
- **placeholders**: Like mirrored but creates placeholder files

### Folder Organization

Organize playlists by owner instead of flat structure. Set in `.env`:

```bash
SPX__EXPORT__ORGANIZE_BY_OWNER=true
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
2. Create an app (name: anything, e.g., "Playlist Sync")
3. Add Redirect URI: `http://127.0.0.1:9876/callback`
4. Copy the Client ID
5. Add it to your `.env` file:
   ```bash
   SPX__SPOTIFY__CLIENT_ID=your_client_id_here
   ```
   Or set temporarily (Windows: `set`, Linux/Mac: `export`)
6. Authenticate:
   ```bash
   run.bat pull      # Windows
   ./run.sh pull     # Linux/Mac
   spx pull          # Standalone executable
   ```

Token cache is saved to `tokens.json` and refreshed automatically.

## Performance & Architecture

### Recent Improvements (Phase 1 Refactoring - October 2025)

**Performance Enhancements**:
- **LRU Caching**: Normalization functions now use `@lru_cache(maxsize=2048)` to speed up repeated string processing during matching (especially beneficial with large libraries and backfill operations)
- **Connection Pooling**: OAuth token exchanges now use a shared `requests.Session` for better HTTP connection reuse and reduced latency during authentication
- **Optimized Queries**: Database count operations extracted into dedicated methods (`count_playlists()`, `count_tracks()`, etc.) for better encapsulation and potential query optimization

**Code Quality & Maintainability**:
- **Clean Separation**: Export directory resolution logic extracted into testable `_resolve_export_dir()` helper function
- **Better Encapsulation**: Database summary counts moved from raw SQL in CLI commands to proper `Database` class methods
- **Maintainable Config**: Config redaction now uses `copy.deepcopy` instead of JSON round-trip serialization (faster and cleaner)
- **Dict Dispatch Pattern**: Export mode handling uses dictionary dispatch reducing if/elif branching complexity

### Matching Strategy

The tool uses a multi-stage matching approach that runs strategies in sequence, with each strategy attempting to match unmatched tracks:

1. **SQL Exact Match**: Fast indexed lookups using normalized artist + title (catches 70-85% of matches in <100ms)
2. **Album Match**: Matches using normalized artist + title + album name (adds 5-10% more matches)
   - Distinguishes studio vs. live albums
   - Separates originals from compilations
   - Identifies different album editions
3. **Year Match**: Matches using normalized artist + title + year (adds 2-5% more matches)
   - Distinguishes remasters from originals
   - Separates live recordings by year
   - Identifies re-recordings
4. **Duration Filter**: Prefilters candidates by track duration (±2s tolerance by default)
5. **Fuzzy Match**: RapidFuzz token_set_ratio on remaining candidates (catches alternative versions, typos)

**Expected match rates**:
- Without album/year strategies: 75-85% match rate
- With album/year strategies: 88-92% match rate

**Configure matching strategies** in `.env`:
```bash
# Default order (recommended)
SPX__MATCHING__STRATEGIES=["sql_exact","album_match","year_match","duration_filter","fuzzy"]

# Skip album/year matching (faster, lower match rate)
SPX__MATCHING__STRATEGIES=["sql_exact","duration_filter","fuzzy"]

# Only exact + album (no fuzzy fallback)
SPX__MATCHING__STRATEGIES=["sql_exact","album_match"]

# Adjust fuzzy threshold (higher = stricter)
SPX__MATCHING__FUZZY_THRESHOLD=0.85

# Adjust duration tolerance (seconds)
SPX__MATCHING__DURATION_TOLERANCE=3.0
```

**Why album and year matching matter**:
- **Remasters**: "Abbey Road (2009 Remaster)" vs. "Abbey Road (Original)"
- **Live albums**: "Hotel California (Studio)" vs. "Hotel California (Live 1977)"
- **Compilations**: "Bohemian Rhapsody (Greatest Hits)" vs. "Bohemian Rhapsody (A Night at the Opera)"
- **Different years**: "Hurt (1994)" [Nine Inch Nails] vs. "Hurt (2002)" [Johnny Cash]

Without album/year matching, all these versions appear identical after normalization and might match incorrectly.

## Advanced

### Enhanced Diagnostics

When running `run.bat match`, the tool shows:
- Top 20 unmatched tracks (configurable via `matching.show_unmatched_tracks`)
- Top 20 unmatched albums (configurable via `matching.show_unmatched_albums`)

**Verbose Mode**:
```bash
run.bat pull -v       # Windows
./run.sh pull -v      # Linux/Mac
spx pull -v           # Standalone
```
Or enable persistent detailed logging in `.env`:
```bash
SPX__LOG_LEVEL=DEBUG
```
Detailed logging provides diagnostic output for OAuth flow, ingestion, scanning, matching (with match scores), and export summaries. Use `INFO` (default) for normal operations or `WARNING` for quiet mode (errors only).

### Authentication

**Login without sync**:
```bash
run.bat login         # Windows
./run.sh login        # Linux/Mac
spx login             # Standalone
```
Force fresh OAuth (ignore token cache):
```bash
run.bat login --force
./run.sh login --force
spx login --force
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
   SPX__SPOTIFY__REDIRECT_SCHEME=https
   SPX__SPOTIFY__REDIRECT_HOST=localhost
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
SPX__LIBRARY__FAST_SCAN=false
```

Other optimizations:
- `library.skip_unchanged: true` - Skip unchanged files
- `library.commit_interval: 100` - Batch database commits

## Technical Details

### Architecture

**Database**: SQLite with normalized metadata and automatic schema migration
**Matching**: Two-stage approach (SQL exact + fuzzy fallback with duration filtering)
**Performance**: Fast scan mode + bulk operations + set-based deletion checks

### Match Strategy

Multi-stage approach for optimal accuracy and performance:

1. **SQL Exact**: Indexed normalized columns (70-85% of matches in <100ms)
2. **Album Match**: Normalized artist + title + album (adds 5-10% more matches)
3. **Year Match**: Normalized artist + title + year (adds 2-5% more matches)
4. **Duration Filter**: Prefilter candidates by track duration (±2s tolerance)
5. **Fuzzy Match**: RapidFuzz token_set_ratio on reduced candidate set

Configure in `.env`:
```bash
SPX__MATCHING__STRATEGIES=["sql_exact","album_match","year_match","duration_filter","fuzzy"]
SPX__MATCHING__FUZZY_THRESHOLD=0.82
SPX__MATCHING__DURATION_TOLERANCE=2.0
```

See the [Matching Strategy](#matching-strategy) section for detailed explanation and customization examples.

### Database Schema

**Tables**:
- `playlists`: Spotify playlists with owner info
- `playlist_tracks`: Track order and liked status
- `spotify_tracks`: Normalized Spotify metadata
- `library_files`: Local files with audio tags (includes bitrate_kbps for quality analysis)
- `matched_tracks`: Spotify ↔ local file mappings
- `meta`: Configuration and state

Schema updates automatically via `ALTER TABLE IF NOT EXISTS`.

### Match Customization

**Strategies** (configurable order in `.env`):
```bash
# Default: sql_exact, album_match, year_match, duration_filter, fuzzy
SPX__MATCHING__STRATEGIES=["sql_exact","album_match","year_match","duration_filter","fuzzy"]
```

Adjust for your library:
```bash
# Skip album/year matching if not needed (faster):
SPX__MATCHING__STRATEGIES=["sql_exact","duration_filter","fuzzy"]

# Skip duration filter if all files similar length:
SPX__MATCHING__STRATEGIES=["sql_exact","album_match","year_match","fuzzy"]

# Stricter fuzzy matching:
SPX__MATCHING__FUZZY_THRESHOLD=0.85

# More lenient duration tolerance:
SPX__MATCHING__DURATION_TOLERANCE=3.0
```

**Tip**: Run `run.bat analyze` to identify metadata issues that might be hurting your match rates.

## License

MIT License

---

## For Developers

### Building Standalone Executables Locally

Install PyInstaller:
```bash
pip install pyinstaller
```

Build:
```bash
pyinstaller spx.spec
```

The executable will be in `dist/spx` (or `dist/spx.exe` on Windows).

### Creating Releases

The project uses GitHub Actions to automatically build executables for Windows, Linux, and macOS:

1. Update version in `spx/cli.py`
2. Commit and push
3. Create and push a version tag:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
4. GitHub Actions will build binaries and create a release automatically

### Running Tests

```bash
run.bat test -q              # Windows
./run.sh test -q             # Linux/Mac
python -m pytest -q          # Direct (with activated venv)
```

---

**Need Help?** Check:
- `run.bat config` - View current settings
- `run.bat redirect-uri` - Show OAuth redirect
- `.env.example` - All environment variables
- `SPX__LOG_LEVEL=DEBUG` - Enable detailed diagnostic logging
Objects are also supported:
```
set SPX__SPOTIFY__EXTRA={"foo":123}
```
Values starting with `[` or `{` are parsed as JSON; otherwise normal scalar coercion applies.
