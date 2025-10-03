# spotify-m3u-sync

Build local playlist artifacts (currently Spotify) as M3U8 files matched against your local music library, with fast matching and rich reporting. The codebase is provider‑ready (namespaced schema, pluggable provider abstraction) so additional services (Deezer, Tidal, etc.) can be added without redesign. (Former command name 'sync' has been removed in favor of clearer 'build' semantics.)

## Installation

### Option 1: Standalone Executable (Easiest)
No Python required! Download pre-built binaries from [Releases](https://github.com/vtietz/spotify-m3u-sync/releases):

**Windows**:
```bash
# Download spotify-m3u-sync-windows-amd64.exe
# Rename to spx.exe for convenience
spx.exe build
```

**Linux/Mac**:
```bash
# Download appropriate binary
chmod +x spotify-m3u-sync-linux-amd64
./spotify-m3u-sync-linux-amd64 build

# Or rename for convenience:
mv spotify-m3u-sync-linux-amd64 spx
./spx build
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
   SPX__SPOTIFY__CLIENT_ID=your_client_id_here
   SPX__LIBRARY__PATHS=["C:/Music"]
   SPX__EXPORT__MODE=mirrored
   SPX__EXPORT__ORGANIZE_BY_OWNER=true
   ```
   
   > **Tip**: See `.env.example` for all available options. For one-time overrides, use `set` commands instead.

3. **Run the full build**:
   ```bash
   run.bat build     # Windows
   ./run.sh build    # Linux/Mac
   ```

This will authenticate with Spotify, scan your library, match tracks, export playlists, and generate reports.

## Features

Playlists → Deterministic M3U8 exports preserving order
Export modes → strict | mirrored | placeholders
Owner grouping → Organize playlists by owner folders
Matching pipeline → Multi‑stage (exact / album / year / duration / fuzzy) for high accuracy
Reporting → Missing tracks CSV + album completeness + unmatched diagnostics
Library quality analysis → Identify metadata gaps & low bitrate files
Fast scans → Skip unchanged file re‑parsing (size + mtime heuristic)
Provider abstraction → Schema + code prepared for additional streaming sources
Clean schema v1 → Composite (id, provider) keys; ready for multi‑provider coexistence

## Common Commands

> **Note**: Replace `run.bat` with `./run.sh` on Linux/Mac, or use `spx` if using standalone executable.

Full pipeline (recommended):
```bash
run.bat build         # Windows Python
./run.sh build        # Linux/Mac Python
spx build             # Standalone executable (all platforms)
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
run.bat install            # Install or update dependencies
run.bat config              # Show current configuration
run.bat report-albums       # Album completeness report
run.bat analyze             # Analyze library metadata quality
run.bat test -q             # Run tests (Python source only)
```

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
spx providers capabilities
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

### Temporary Overrides

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

### Priority Order

Settings are merged in this order (later overrides earlier):
1. **Built-in defaults** (in `spx/config.py`)
2. **`.env` file** (if exists)
3. **Shell environment variables** (`set`/`export` commands)

### Key Options (See docs/configuration.md for full list)

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
2. Create an app (name: anything, e.g., "Playlist Build")
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

Detailed architecture & matching docs moved to: `docs/architecture.md` and `docs/matching.md`.

## Advanced (See docs for details)

### Diagnostics

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

**Login without build**:
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

Condensed overview (see `docs/architecture.md` for full explanation):

- Database: SQLite, composite (id, provider) keys for tracks & playlists
- Matching: Ordered strategies (exact → album → year → duration → fuzzy)
- Performance: LRU normalization cache, fast scan, bulk inserts, indexed normalized/isrc columns
- Schema versioning: `meta` table entry `schema_version=1` (clean baseline)

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
- `SPX__LOG_LEVEL=DEBUG` - Enable detailed diagnostic logging
Values starting with `[` or `{` are parsed as JSON; objects are supported (see configuration docs).
