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

## Rich Interactive Reports

Get comprehensive insights into your music collection with beautiful, interactive HTML reports:

![Reports Dashboard](docs/screenshots/reports-overview.png)

**What You Get:**
- 📊 **Sortable & Searchable Tables** – Click column headers to sort, use search to filter thousands of tracks instantly
- 🔗 **Clickable Spotify Links** – Track names, playlists, and albums link directly to Spotify for easy reference
- 📈 **Match Quality Insights** – Confidence scores, match strategies, and metadata comparison side-by-side
- 🎵 **Missing Content Analysis** – See exactly which albums to download for maximum playlist coverage
- 🔍 **Library Quality Reports** – Find metadata gaps, low-bitrate files grouped by album for efficient fixing
- 📱 **Responsive Design** – Works beautifully on desktop and mobile

**Report Types:**
- **Matched Tracks** – All successful matches with confidence scores and match strategies
- **Unmatched Tracks** – What you're missing from Spotify, sorted by popularity
- **Unmatched Albums** – Missing content grouped by album for smart downloading decisions
- **Playlist Coverage** – Track completion percentage for each playlist with drill-down details
- **Metadata Quality** – Library files with missing tags or quality issues, grouped by album

![Report Example](docs/screenshots/report.png)

All reports export as both CSV (for spreadsheets) and interactive HTML (for exploration).

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

## Getting Started

### 1. Get a Spotify Client ID

You'll need a Spotify Developer app to access your playlists:

1. Go to https://developer.spotify.com/dashboard
2. Click **Create App**
3. Fill in any name (e.g., "My Playlist Sync")
4. Add Redirect URI: `http://127.0.0.1:9876/callback`
5. Copy your **Client ID** (you don't need the Client Secret)

### 2. Configure the Tool

Create a `.env` file in the same directory as the executable (or project root):

```bash
# .env - Minimum required configuration
PSM__PROVIDERS__SPOTIFY__CLIENT_ID=your_client_id_here
PSM__LIBRARY__PATHS=["C:/Music"]
```

**Optional settings** for better results:
```bash
PSM__EXPORT__MODE=mirrored                # Show missing tracks as comments
PSM__EXPORT__ORGANIZE_BY_OWNER=true      # Group playlists by owner
```

> **Tip**: See `.env.example` for all available options.

### 3. Authenticate with Spotify

Run the login command to connect your Spotify account:

```bash
run.bat login     # Windows
./run.sh login    # Linux/Mac
psm login         # Standalone executable
```

A browser window will open for Spotify authorization. After you approve, the tool saves your credentials to `tokens.json` (auto-refreshed).

### 4. Run Your First Build

Now run the complete pipeline:

```bash
run.bat build     # Windows
./run.sh build    # Linux/Mac
psm build         # Standalone executable
```

This single command will:
1. **Pull** your Spotify playlists and tracks
2. **Scan** your local music library
3. **Match** streaming tracks to local files
4. **Export** M3U playlists pointing to your files
5. **Generate** interactive HTML reports

**Find your results**:
- M3U playlists: `data/export/playlists/`
- Interactive reports: `data/export/reports/index.html`

**Open the report dashboard**:
```bash
start data\export\reports\index.html        # Windows
open data/export/reports/index.html         # Mac
xdg-open data/export/reports/index.html     # Linux
```

> **Note**: Currently only **one provider** (Spotify) can be configured. Multi-provider support is planned for a future release.

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

**Full pipeline** (recommended for first-time and regular use):
```bash
run.bat build         # Runs: pull → scan → match → export
```

**Individual steps** (for selective updates):
```bash
run.bat pull          # Fetch Spotify playlists and tracks
run.bat scan          # Scan local music library
run.bat match         # Match tracks (auto-generates reports)
run.bat export        # Generate M3U playlists
run.bat analyze       # Analyze library quality (auto-generates quality reports)
```

**Reports**:
```bash
run.bat report        # Regenerate all reports from database
                      # Options: --match-reports, --analysis-reports, 
                      #          --no-match-reports, --no-analysis-reports
```

**Other**:
```bash
run.bat --help        # Show workflow examples
run.bat config        # Show current configuration
run.bat version       # Show version info
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

Every workflow step automatically generates comprehensive reports to help you understand your collection.

#### Match Reports (`run.bat match`)

When matching tracks, you get:

**📊 Matched Tracks Report**
- Every successfully matched track with confidence score (CERTAIN/HIGH/MEDIUM/LOW)
- Match strategy used (ISRC, exact match, fuzzy match, album context, etc.)
- Side-by-side comparison: Spotify metadata ↔ Local file metadata
- Clickable Spotify track links to verify matches
- Duration comparison and match quality indicators

**❌ Unmatched Tracks Report**  
- All Spotify tracks without local matches
- Sorted by playlist popularity (tracks in multiple playlists shown first)
- Artist, album, duration, and release year for easy identification
- Clickable Spotify links to preview/purchase missing tracks
- Liked tracks marked with ❤️ for priority downloading

**💿 Unmatched Albums Report**
- Missing tracks grouped by album for efficient bulk downloading
- Shows track count per album to prioritize complete album acquisitions
- Sorted by frequency (albums appearing in multiple playlists listed first)
- Perfect for identifying "which albums should I buy next?"

**📈 Playlist Coverage Report**
- Coverage percentage for each of your playlists
- Track counts: Total, Matched, Missing for every playlist
- Clickable playlist names link to Spotify
- Drill-down links to detailed per-playlist track reports
- Owner information and playlist URLs

**Console Output:**
- Top 20 unmatched tracks by popularity (configurable)
- Top 10 unmatched albums by occurrence frequency (configurable)
- Quick summary of match quality and coverage

#### Analysis Reports (`run.bat analyze`)

Library quality analysis helps you improve match accuracy:

**🔍 Metadata Quality Report**
- Files with missing tags (artist, title, album, year)
- Files below bitrate threshold (default: 320 kbps)
- Grouped by issue type for targeted fixing
- Full file paths for easy batch editing
- Bitrate and duration information

**Console Output with Intelligent Grouping:**
- Top albums with most files needing fixes
- Example: "📁 The Beatles - Abbey Road (18 files missing year)"
- Maximizes impact: Fix one album's metadata → improve many files at once
- Prioritizes albums over scattered individual files

#### Standalone Report Generation

Regenerate all reports from existing database without re-running analysis:

```bash
run.bat report                       # Generate all reports (default)
run.bat report --no-analysis-reports # Generate only match reports
run.bat report --no-match-reports    # Generate only analysis reports
```

Perfect for tweaking report formats or sharing results without re-processing.

#### Interactive HTML Features

All HTML reports include:

✅ **Sortable Tables** – Click any column header to sort ascending/descending  
✅ **Live Search** – Filter thousands of tracks instantly as you type  
✅ **Pagination** – Navigate large datasets with configurable page sizes (10/25/50/100 entries)  
✅ **Clickable Spotify Links** – Track IDs, playlist names, album names link directly to Spotify  
✅ **Navigation Dashboard** – Beautiful `index.html` homepage with quick access to all reports  
✅ **CSV Export** – Download button on every report for spreadsheet analysis  
✅ **Responsive Design** – Works on desktop, tablet, and mobile  
✅ **Dark/Light Friendly** – Clean, professional styling that works in any environment

Powered by jQuery DataTables for enterprise-grade table functionality.

**Reports Location:**  
Default: `data/export/reports/` (configurable via `PSM__REPORTS__DIRECTORY`)

**Open Reports:**
```bash
# Windows
start data\export\reports\index.html

# Linux/Mac  
open data/export/reports/index.html
xdg-open data/export/reports/index.html  # Linux alternative
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
run.bat playlist push 3cEYpjA9oz9GiPac4AsH4n --file data/export/playlists/MyList_xxxxxxxx.m3u8

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
- `PSM__EXPORT__DIRECTORY` - Output directory (default: data/export/playlists)

**Reports**:
- `PSM__REPORTS__DIRECTORY` - Report output directory (default: data/export/reports)

**Database**:
- `PSM__DATABASE__PATH` - SQLite file location (default: data/db/spotify_sync.db)

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
data/export/playlists/
├── randomdj/           # Your playlists (uses your Spotify username)
├── Radio_FM4/          # Followed playlists from Radio FM4
├── radioeins/          # Followed playlists from radioeins
└── other/              # Unknown owner
```

**Note**: Spotify's API doesn't expose playlist folders (UI-only), so we organize by owner instead.

## Advanced Usage

### Re-authenticate

Force fresh login (ignores cached tokens):
```bash
run.bat login --force
```

### Debug Mode

Enable detailed logging for diagnostics:
```bash
PSM__LOG_LEVEL=DEBUG run.bat match
```

Shows: OAuth flow, match scores, normalization, file scanning progress, and more.

### Optional HTTPS Redirect

By default, Spotify redirect uses HTTP (`http://127.0.0.1:9876/callback`). For HTTPS:

1. Register `https://localhost:9876/callback` in Spotify Dashboard
2. Add to `.env`:
   ```bash
   PSM__PROVIDERS__SPOTIFY__REDIRECT_SCHEME=https
   PSM__PROVIDERS__SPOTIFY__REDIRECT_HOST=localhost
   ```
3. Tool auto-generates self-signed cert if `cryptography` or `openssl` available

## Configuration

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

## Technical Details

Brief overview (see `docs/architecture.md` for comprehensive details):

- **Database**: SQLite with composite (id, provider) keys for multi-provider support
- **Matching**: Weighted scoring system with confidence tiers (CERTAIN/HIGH/MEDIUM/LOW)
- **Performance**: LRU caching, fast scan mode, bulk inserts, indexed columns
- **Concurrency**: WAL mode enables safe parallel operations (pull + scan + match simultaneously)
- **Schema**: Clean v1 baseline with provider namespacing

For technical deep-dives, see `docs/architecture.md` and `docs/matching.md`.

## Troubleshooting

**INVALID_CLIENT error?**
- Check redirect URI: `run.bat redirect-uri`
- Default is `http://127.0.0.1:9876/callback`
- Must match exactly in Spotify Developer Dashboard

**Low match rate?**
- Run `run.bat analyze` to find metadata issues
- Check reports: `data/export/reports/index.html`
- See `docs/troubleshooting.md` for detailed solutions

**Need detailed logs?**
```bash
PSM__LOG_LEVEL=DEBUG run.bat match
```

See `docs/troubleshooting.md` for complete troubleshooting guide.

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
