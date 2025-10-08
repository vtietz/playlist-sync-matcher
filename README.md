# Playlist Sync Matcher

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
psm.exe build     # Runs the sync pipeline (after setup below)
```

**Linux/Mac**:
```bash
# Download appropriate binary
chmod +x playlist-sync-matcher-linux-amd64
./playlist-sync-matcher-linux-amd64 build     # After setup

# Or rename for convenience:
mv playlist-sync-matcher-linux-amd64 psm
./psm build
```

### Option 2: Python Source (Recommended for Development)
Requires **Python 3.9+**. The scripts will automatically set up a virtual environment:

**Windows**:
```bash
run.bat install   # Install dependencies (first time)
run.bat build     # Run sync pipeline (after setup below)
```

**Linux/Mac**:
```bash
chmod +x run.sh
./run.sh install  # Install dependencies (first time)
./run.sh build    # Run sync pipeline (after setup)
```

> **First run**: The install script creates a `.venv` directory and installs all dependencies automatically.

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

### 4. Run the Complete Sync

Now run the complete data pipeline with a single command:

```bash
run.bat build     # Windows
./run.sh build    # Linux/Mac
psm build         # Standalone executable
```

> **What does "build" mean?** The `build` command runs the complete sync pipeline (not compiling code). It executes all steps in sequence.

This will:
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

**Complete sync pipeline** (recommended for first-time and regular use):
```bash
run.bat build         # Runs full pipeline: pull → scan → match → export
```
> The `build` command runs the data sync pipeline, not software compilation.

**Watch Mode** 🆕 (continuously monitor and rebuild):
```bash
run.bat build --watch             # Monitor library, auto-rebuild on changes
run.bat build --watch --debounce 5  # Use 5-second debounce (default: 2)
```
> Watch mode monitors your music library and automatically runs incremental rebuilds when files change. Uses quick scan (only changed files) for efficiency. Press Ctrl+C to stop. Does NOT re-pull from Spotify (run `pull` manually when playlists change).

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
run.bat scan                              # Full scan of all library paths
run.bat scan --quick                      # Scan only changed files since last run
run.bat scan --since "2 hours ago"        # Scan files modified in last 2 hours
run.bat scan --paths ./NewAlbum/          # Scan specific directory
run.bat scan --watch                      # Monitor filesystem and auto-update DB
```

**Features**:
- **Visual Progress**: Shows directories being scanned + live progress counter (every 100 files)
- **Smart Incremental**: `--quick` mode only scans new/modified files
- **Time-Based Filtering**: `--since` scans files modified after specified time
- **Watch Mode**: `--watch` monitors library and updates DB automatically
- **Cleanup**: Automatically removes deleted files from database
- **Debug Mode**: Set `LOG_LEVEL=DEBUG` to see current directory being scanned

**Watch Mode** 🆕:
```bash
# Continuously monitor library for changes
run.bat scan --watch --debounce 2

# Changes are detected and processed automatically
# Press Ctrl+C to stop
```

See [docs/watch-mode.md](docs/watch-mode.md) for comprehensive watch mode guide.

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
- **Includes "Liked Songs" (❤️) as a virtual playlist** - tracks you've liked in Spotify

**Console Output:**
- Top 20 unmatched tracks by popularity (configurable)
- Top 10 unmatched albums by occurrence frequency (configurable)
- Quick summary of match quality and coverage

### Liked Songs Support 🆕

Your Spotify "Liked Songs" (Lieblingssongs/❤️) are automatically included:

**✅ Automatic Pull**: `run.bat pull` fetches liked tracks alongside playlists  
**✅ Matching**: Liked tracks are matched just like playlist tracks  
**✅ Export**: A virtual "Liked Songs" playlist is created automatically (M3U file)  
**✅ Reports**: Liked Songs appear in all coverage and track reports  
**✅ Incremental**: Only new liked tracks are fetched on subsequent pulls

**Control via Config**:
```bash
# Disable Liked Songs export (still pulled and matched, just not exported)
PSM__EXPORT__INCLUDE_LIKED_SONGS=false
```

**Sorting**: Liked Songs M3U preserves Spotify's newest-first order (most recently liked at the top).

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

All HTML reports include sortable tables, live search, pagination, clickable Spotify links, and CSV export. Powered by jQuery DataTables.

**Reports Location:** `data/export/reports/` (configurable via `PSM__REPORTS__DIRECTORY`)

**Open Reports:**
```bash
start data\export\reports\index.html        # Windows
open data/export/reports/index.html         # Mac
xdg-open data/export/reports/index.html     # Linux
```

See `docs/matching.md` and `docs/library_analysis.md` for detailed report documentation.

### Single Playlist Operations

Work with individual playlists instead of syncing everything:

```bash
run.bat playlists list                      # List all playlists with IDs
run.bat playlists list --show-urls          # Include Spotify URLs

run.bat playlist pull <PLAYLIST_ID>         # Pull single playlist from Spotify
run.bat playlist match <PLAYLIST_ID>        # Match against library
run.bat playlist export <PLAYLIST_ID>       # Export to M3U
run.bat playlist build <PLAYLIST_ID>        # Pull + match + export

# Experimental: Push local order back to Spotify (preview first, then --apply)
run.bat playlist push <PLAYLIST_ID>         # Preview changes
run.bat playlist push <PLAYLIST_ID> --apply # Apply changes
```

**Use cases:** Testing settings, selective updates, debugging specific playlists, faster processing.

**M3U features:** Each exported playlist includes Spotify URL in header and collision-safe filenames (`PlaylistName_<8charID>.m3u8`).

See `docs/` for complete playlist command documentation.

## Configuration

All configuration via `.env` file or environment variables using the pattern `PSM__SECTION__KEY`.

**Minimal `.env` example:**
```bash
PSM__PROVIDERS__SPOTIFY__CLIENT_ID=your_client_id_here
PSM__LIBRARY__PATHS=["C:/Music"]
PSM__EXPORT__MODE=mirrored
PSM__EXPORT__ORGANIZE_BY_OWNER=true
```

**Common settings:**
- `PSM__MATCHING__FUZZY_THRESHOLD` - Match sensitivity 0.0-1.0 (default: 0.78)
- `PSM__MATCHING__DURATION_TOLERANCE` - Seconds (default: 2.0)
- `PSM__LIBRARY__FAST_SCAN` - Skip unchanged files (default: true)
- `PSM__LOG_LEVEL` - DEBUG|INFO|WARNING (default: INFO)

**Temporary override** (without editing `.env`):
```bash
set PSM__EXPORT__MODE=strict && run.bat export     # Windows
PSM__EXPORT__MODE=strict ./run.sh export           # Linux/Mac
```

See `docs/configuration.md` for complete list of all options and `.env.example` for examples.

## Advanced Usage

### Debug Mode
```bash
PSM__LOG_LEVEL=DEBUG run.bat match    # Detailed diagnostics
```

### Re-authenticate
```bash
run.bat login --force                  # Force fresh Spotify login
```

### Optional HTTPS Redirect
```bash
# In .env file:
PSM__PROVIDERS__SPOTIFY__REDIRECT_SCHEME=https
PSM__PROVIDERS__SPOTIFY__REDIRECT_HOST=localhost
```
Register `https://localhost:9876/callback` in Spotify Dashboard. Tool auto-generates cert if available.

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
