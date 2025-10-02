# spotify-m3u-sync

Sync your Spotify playlists to M3U8 files matched against your local music library, with detailed reporting on missing tracks and album completeness.

## Installation

### Option 1: Standalone Executable (Easiest)
No Python required! Download pre-built binaries from [Releases](https://github.com/YOUR_USERNAME/spotify-m3u-sync/releases):

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

### What if Python is not installed?
- Use **Option 1** (standalone executable) - works without Python
- Or install Python from [python.org](https://www.python.org/downloads/) for Option 2

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
run.bat test -q             # Run tests (Python source only)
```

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

**Matching**:
- `SPX__MATCHING__FUZZY_THRESHOLD` - Match sensitivity 0.0-1.0 (default: 0.78)
- `SPX__MATCHING__DURATION_TOLERANCE` - Duration match tolerance in seconds (default: 2.0)
- `SPX__MATCHING__SHOW_UNMATCHED_TRACKS` - Diagnostic output count (default: 20)
- `SPX__MATCHING__SHOW_UNMATCHED_ALBUMS` - Album diagnostic count (default: 20)
- `SPX__MATCHING__USE_YEAR` - Include year in matching (default: false)

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

1. **SQL Exact**: Indexed normalized columns (70-95% of matches in <100ms)
2. **Duration Filter**: Prefilter candidates by track duration (±2s tolerance)
3. **Fuzzy Match**: RapidFuzz token_set_ratio on reduced candidate set

Configure fuzzy threshold in `.env`:
```bash
SPX__MATCHING__FUZZY_THRESHOLD=0.82
SPX__MATCHING__DURATION_TOLERANCE=2.0
```

### Database Schema

**Tables**:
- `playlists`: Spotify playlists with owner info
- `playlist_tracks`: Track order and liked status
- `spotify_tracks`: Normalized Spotify metadata
- `library_files`: Local files with audio tags
- `matched_tracks`: Spotify ↔ local file mappings
- `meta`: Configuration and state

Schema updates automatically via `ALTER TABLE IF NOT EXISTS`.

### Match Customization

**Strategies** (configurable order in `.env`):
```bash
# Default: sql_exact, duration_filter, fuzzy
SPX__MATCHING__STRATEGIES=["sql_exact","duration_filter","fuzzy"]
```

Adjust for your library:
```bash
# Skip duration filter if all files similar length:
SPX__MATCHING__STRATEGIES=["sql_exact","fuzzy"]

# Stricter fuzzy matching:
SPX__MATCHING__FUZZY_THRESHOLD=0.85
```

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
