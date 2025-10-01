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

### Export Modes
Three modes available via `export.mode`:
- **strict** (default): Only matched tracks
- **mirrored**: Full order with markers for missing tracks  
- **placeholders**: Like mirrored but creates placeholder files

```
set SPX__EXPORT__MODE=mirrored
```

### Folder Organization
Organize playlists by owner instead of flat structure:

```yaml
export:
  organize_by_owner: true
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

### Environment Variables

**Using .env file** (recommended for permanent configuration):
```bash
# Create .env file in project root (see .env.example)
SPX__SPOTIFY__CLIENT_ID=your_client_id_here
SPX__LIBRARY__PATHS=["C:/Music","D:/Music"]
SPX__EXPORT__MODE=mirrored
SPX__EXPORT__ORGANIZE_BY_OWNER=true
SPX__MATCHING__FUZZY_THRESHOLD=0.82
```

**Using shell environment** (for one-time overrides):
```bash
# Windows
set SPX__SPOTIFY__CLIENT_ID=your_client_id
set SPX__EXPORT__MODE=mirrored

# Linux/Mac
export SPX__SPOTIFY__CLIENT_ID=your_client_id
export SPX__EXPORT__MODE=mirrored
```

**Format**: Prefix with `SPX__` and use double underscores for nesting.

Key options:
- `library.paths` - Folders to scan (JSON array)
- `library.extensions` - File types (default: mp3, flac, m4a, ogg)
- `matching.fuzzy_threshold` - Match sensitivity (0.78 default)
- `matching.show_unmatched_tracks` - Debug output count (20 default)
- `matching.show_unmatched_albums` - Album diagnostic count (20 default)
- `export.mode` - strict | mirrored | placeholders
- `export.organize_by_owner` - Group by owner (false default)
- `database.path` - SQLite file location

Create a `config.yaml` file for permanent settings or use `.env` (see `.env.example`).

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
Or enable persistent debug logging in `.env`:
```bash
SPX__DEBUG=true
```
Debug mode provides detailed output for OAuth flow, ingestion, scanning, matching (with match scores), and export summaries.

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

Configure fuzzy threshold in `.env` or `config.yaml`:
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

**Strategies** (configurable order):
```yaml
matching:
  strategies:
    - sql_exact          # Default: fast indexed match
    - duration_filter    # Default: prefilter by duration
    - fuzzy              # Default: fuzzy fallback
```

Adjust for your library in `.env`:
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
- `SPX__DEBUG=true` - Enable verbose logging
Objects are also supported:
```
set SPX__SPOTIFY__EXTRA={"foo":123}
```
Values starting with `[` or `{` are parsed as JSON; otherwise normal scalar coercion applies.
