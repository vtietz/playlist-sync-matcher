# Playlist Sync Matcher

Turn your streaming playlists (e.g. from Spotify) into M3U playlist files that point to your actual local music files. The codebase has been prepared with a lightweight abstraction so new providers can be added with minimal churn.

## What it does
Instead of just getting a list of song names, you get working playlists that:
- **Link to your local files** – Each playlist entry points to the real MP3/FLAC file on your drive
- **Show what's missing** – Missing tracks marked with ❌ emoji in mirrored mode, plus detailed reports
- **Preserve your path format** – Network drives (Z:\) vs UNC paths (\\server\share) maintained automatically
- **Keep playlists in sync** – Detects previously exported playlists that were deleted in Spotify and prompts you to remove obsolete files ([Smart Playlist Cleanup](#smart-playlist-cleanup); optional full clean before export)
- **Work everywhere** – Standard M3U files that any music player can use (VLC, Foobar2000, etc.)

Perfect for syncing to devices, offline listening, or just organizing your collection around your streaming habits.

## Features

| Capability | Value |
|------------|-------|
| **M3U Export Modes** | strict (matched only), mirrored (all tracks with ❌ indicators), placeholders (dummy files) |
| **Smart Path Handling** | Preserves Z:\ vs \\server\share network paths, absolute/relative path support |
| **Playlist Cleanup** | Detects obsolete playlists with interactive deletion, optional full clean before export |
| **Owner Grouping** | Optional: organize playlists into folders by owner |
| **Liked Songs Support** | Automatic virtual playlist export for your Spotify ❤️ Liked Songs |
| **Progress Indicators** | Live progress during export ([1/302] Exporting: Playlist Name) |
| **Scoring-based Matching** | Weighted signals (exact/fuzzy/album/year/duration/ISRC) with confidence tiers |
| **Rich Reporting** | Interactive HTML + CSV: missing tracks, album completeness, coverage analysis |
| **Library Quality Analysis** | Surface metadata gaps & low bitrate files grouped by album |
| **Fast Scan Mode** | Skips unchanged files (mtime+size) to save minutes on large libraries |
| **Watch Mode** | Continuous monitoring of library and database with incremental updates |
| **Provider-Ready Architecture** | Pluggable registry with namespaced schema; multi-provider support planned (see [docs/providers.md](docs/providers.md:1)) |

## Command-Line Interface (CLI)

The CLI is the core engine that powers everything. Perfect for automation, scripting, and power users.

**Quick Example:**
```bash
psm-cli login         # Authenticate with Spotify
psm-cli build         # Pull → Scan → Match → Export (complete pipeline)
psm-cli build --watch # Continuous monitoring mode
```

**Common Commands:**
```bash
psm-cli pull          # Fetch Spotify playlists and tracks
psm-cli scan          # Scan local music library
psm-cli match         # Match tracks (generates reports automatically)
psm-cli export        # Generate M3U playlists
psm-cli analyze       # Analyze library quality
psm-cli report        # Regenerate all reports
```

**Use Cases:**
- ✅ Server/headless systems
- ✅ Automated scheduled tasks (cron/Task Scheduler)
- ✅ CI/CD pipelines
- ✅ Scripting and batch operations
- ✅ Power users who prefer command-line

📖 **[Complete CLI Reference](docs/cli-reference.md)** - All commands, options, and workflow examples


## Graphical Desktop App (GUI)

![GUI](docs/screenshots/gui.png)

Visual interface for interactive exploration. Runs the same CLI engine under the hood.

**Launch:**
```bash
psm-gui              # Standalone executable
run.bat gui          # Windows (via run script)
./run.sh gui         # Linux/Mac (via run script)
python -m psm.cli gui   # Direct Python invocation
```

**Features:**
- 📊 **Master–Detail Playlists** – Browse playlists on the left, view tracks on the right
- 🔎 **Powerful Filters** – Quick filters for Playlist, Artist, Album, Year, Matched, Confidence, Quality + search boxes
- ⚡ **All CLI Actions** – Pull, Scan, Match, Export, Report, Build, Open Reports, Refresh via toolbar buttons
- 🔄 **Watch Mode Toggle** – Enable continuous monitoring with one click
- 📝 **Live Logs** – Real-time CLI output streaming to a log panel
- 🧭 **Status Bar Metrics** – Total tracks, matched count/percentage, and playlist count
- 🎨 **Professional UI** – Dark-themed Qt interface (system theme aware)

**Use Cases:**
- ✅ Desktop users (Windows/macOS/Linux)
- ✅ Visual playlist exploration
- ✅ Real-time progress monitoring
- ✅ Interactive filtering and searching
- ✅ New users learning the tool

**Architecture:**
- Zero changes to existing CLI/service code (isolated `psm/gui/` module)
- Read-only data layer using `DatabaseInterface` only (no raw SQL)
- All actions execute actual CLI commands as subprocesses (CLI parity)
- Live log parsing from CLI stdout

📖 **Detailed Documentation:**
- [`psm/gui/README.md`](psm/gui/README.md) - Usage, keyboard shortcuts, and architecture
- [`docs/gui-performance.md`](docs/gui-performance.md) - Performance optimization patterns


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

**Highlights:**
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

### Option 1: Prebuilt Bundles (Easiest)
No Python required! Download a platform bundle from [Releases](https://github.com/vtietz/playlist-sync-matcher/releases). Each bundle contains both the GUI and the CLI:

- Windows: `psm-windows-amd64.zip` → contains `psm-gui.exe` and `psm-cli.exe`
- macOS: `psm-macos-amd64.tar.gz` → contains `psm-gui` and `psm-cli`
- Linux: `psm-linux-amd64.tar.gz` → contains `psm-gui` and `psm-cli`

Why bundles?
- Ensures the GUI and CLI versions match
- Clear names inside the archive (no OS/arch suffix on the internal binary)
- GitHub displays SHA-256 hashes for verification

You can still download individual binaries if you prefer (backward-compatible assets remain available):
- Windows: `psm-gui-windows-amd64.exe`, `psm-cli-windows-amd64.exe`
- macOS: `psm-gui-macos-amd64`, `psm-cli-macos-amd64`
- Linux: `psm-gui-linux-amd64`, `psm-cli-linux-amd64`

Notes:
- On Linux/macOS, executables typically don’t have a file extension – that’s normal. Make them executable with `chmod +x`.
- The `amd64` suffix denotes CPU architecture (x86_64). It helps avoid confusion if ARM builds are added later.

**Windows**:
```bash
# GUI version (recommended for interactive use)
# Download and extract psm-windows-amd64.zip (contains psm-gui.exe and psm-cli.exe)
psm-gui.exe           # Launches desktop application

# CLI version (for automation/scripting)
# Or download individual: psm-cli-windows-amd64.exe
psm-cli.exe --version
psm-cli.exe build     # Runs the sync pipeline (after setup below)
```

**Linux/Mac**:
```bash
# GUI version (recommended for interactive use)
# Download and extract the bundle (psm-linux-amd64.tar.gz or psm-macos-amd64.tar.gz)
# Then run the internal binaries:
chmod +x psm-gui
./psm-gui

# CLI version (for automation/scripting)
# Or download individual binaries (then chmod +x): psm-cli-linux-amd64 or psm-cli-macos-amd64
chmod +x psm-cli
./psm-cli --version
./psm-cli build
```

> **💡 Tip**: Rename executables for convenience (e.g., `mv psm-cli-linux-amd64 psm-cli`)

### Option 2: Python Source (Recommended for Development)
Requires **Python 3.10+** (CI builds on 3.12). The scripts will automatically set up a virtual environment:

**Windows**:
```bash
run.bat install      # Install dependencies (first time)
run.bat psm build    # Run sync pipeline (after setup below)
run.bat build        # Build both CLI and GUI executables
run.bat build-cli    # Build CLI executable only
run.bat build-gui    # Build GUI executable only
```

**Linux/Mac**:
```bash
chmod +x run.sh
./run.sh install     # Install dependencies (first time)
./run.sh psm build   # Run sync pipeline (after setup)
./run.sh build       # Build both CLI and GUI executables
./run.sh build-cli   # Build CLI executable only
./run.sh build-gui   # Build GUI executable only
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

**First Run Experience**:

- **CLI**: When you run any command for the first time without a `.env` file, the CLI will prompt you to create a template with all necessary settings. If you choose to create it, the template will automatically open in your default text editor so you can immediately start configuring.

- **GUI**: When you launch the GUI for the first time without a `.env` file, a dialog will guide you through the setup:
  1. **Initial Prompt**: Offers to create a template `.env` file, continue anyway (using environment variables), or exit
  2. **After Creation**: If you create the template, the dialog updates to show the file location and offers to open it in your editor
  3. **Continue or Exit**: After opening the file (or choosing not to), you can continue with the application or exit to configure the file first

**Manual Setup**: Alternatively, create a `.env` file manually in the same directory as the executable (or project root):

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
run.bat psm login     # Windows
./run.sh psm login    # Linux/Mac
psm-cli login         # Standalone executable
```

A browser window will open for Spotify authorization. After you approve, the tool saves your credentials to `tokens.json` (auto-refreshed).

### 4. Run the Complete Sync

Now run the complete data pipeline with a single command:

```bash
run.bat psm build     # Windows
./run.sh psm build    # Linux/Mac
psm-cli build         # Standalone executable
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

## Common Commands

> **Note**: Replace `run.bat` with `./run.sh` on Linux/Mac, or use `psm-cli` if using standalone CLI executable, or launch `psm-gui` for the graphical interface.
> 
> **📖 For complete CLI reference**: See [docs/cli-reference.md](docs/cli-reference.md) for detailed command documentation, all options, and workflow examples.

**Complete sync pipeline** (recommended for first-time and regular use):
```bash
run.bat build         # Runs full pipeline: pull → scan → match → export
```
> The `build` command runs the data sync pipeline, not software compilation.

**Watch Mode** (continuously monitor and rebuild):
```bash
run.bat build --watch             # Monitor library + database for changes
run.bat build --watch --debounce 5  # Use 5-second debounce (default: 2)
run.bat build --watch --no-report  # Skip report regeneration
run.bat build --watch --no-export  # Skip playlist export
```
> **Watch mode** monitors both your **music library files** AND **database** for changes.
> 
> **Important**: Does **NOT** run initial full build - run `run.bat build` first without `--watch`.
> Then start watch mode for continuous monitoring.
>
> **How it works**:
> 
> **Library file changes** (incremental):
> - Detects file changes in library paths (add, modify, delete)
> - Scans only changed files (not entire library)
> - Matches only changed files against all tracks
> - Updates affected playlists in M3U export
> - Regenerates reports
> 
> **Database changes** (e.g., after `run.bat pull` in another terminal):
> - Detects database modification (new/changed tracks from Spotify)
> - **Incremental match**: matches all library files against only changed tracks
> - Updates affected playlists
> - Regenerates reports
> 
> **Performance**: Both library and database changes use incremental matching for fast updates (typically 3-6 seconds vs 45+ seconds for full rebuild).
> 
> **Workflow**:
> ```bash
> # Terminal 1: Start watch mode
> run.bat build --watch
> 
> # Terminal 2: Pull new Spotify data when needed
> run.bat pull
> # Watch mode will automatically detect and re-match!
> ```
> 
> Press Ctrl+C to stop.

**Individual steps** (for selective updates):
```bash
run.bat pull          # Fetch Spotify playlists and tracks
run.bat scan          # Scan local music library (smart: only new/modified files)
run.bat scan --deep   # Force complete rescan of all library paths
run.bat match         # Match tracks (smart: skips already-matched, auto-generates reports)
run.bat match --full  # Force complete re-match of all tracks
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
run.bat scan                              # Smart scan: only new/modified files (default)
run.bat scan --deep                       # Force complete rescan of all library paths
run.bat scan --since "2 hours ago"        # Scan files modified in last 2 hours
run.bat scan --paths ./NewAlbum/          # Scan specific directory
run.bat scan --watch                      # Monitor filesystem and auto-update DB
```

**Features**:
- **Visual Progress**: Shows directories being scanned + live progress counter (every 100 files)
- **Smart by Default**: Only scans new/modified files (use `--deep` for complete rescan)
- **Time-Based Filtering**: `--since` scans files modified after specified time
- **Watch Mode**: `--watch` monitors library and updates DB automatically
- **Cleanup**: Automatically removes deleted files from database
- **Debug Mode**: Set `LOG_LEVEL=DEBUG` to see current directory being scanned

**Watch Mode**:
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

### Liked Songs Support 

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

### Troubleshooting Unmatched Tracks 🔍

When tracks don't match, use the `diagnose` command to understand why:

**Workflow:**
1. Check `unmatched_tracks` report (CSV or HTML)
2. Copy the Track ID from the first column
3. Run diagnose command:

```bash
run.bat diagnose <track_id>
```

**What you'll see:**
- **Track metadata**: Artist, title, album, duration, normalized string
- **Match status**: Already matched, or why not
- **Top 5 closest files**: With fuzzy match scores and duration comparison
- **Recommendations**: Specific fixes (tag corrections, threshold adjustments)

**Example:**
```bash
# Diagnose a specific unmatched track
run.bat diagnose 3n3Ppam7vgaVa1iaRUc9Lp

# Show top 10 closest files instead of 5
run.bat diagnose --top-n 10 3n3Ppam7vgaVa1iaRUc9Lp
```

**Common issues revealed:**
- File tags don't match Spotify metadata (artist/title spelling)
- Match score just below threshold (→ lower threshold slightly)
- File not in library (→ download and scan)
- Duration mismatch too large (→ check if correct version)

See [docs/troubleshooting.md](docs/troubleshooting.md) for more details.

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

### Export Modes & Features 🎵

The tool offers flexible M3U playlist export with smart features for managing your playlists:

#### **Export Modes**

**Strict Mode** (default for reliability)
- Only includes tracks with local file matches
- Cleanest playlists for guaranteed playback
- Missing tracks silently omitted

**Mirrored Mode** (recommended for completeness)
- Preserves ALL tracks from Spotify playlist
- Missing tracks marked with ❌ emoji in title (visible in player UI)
- Placeholder entries: `!MISSING - Artist - Title`
- Perfect for tracking what you need to download

**Placeholders Mode** (for advanced workflows)
- Creates dummy `.missing` files for unmatched tracks
- Maintains playlist order with physical files
- Useful for scripting batch downloads

#### **Smart Playlist Cleanup**

Keep your export directory synchronized:

**Obsolete Detection** (enabled by default)
- Automatically finds playlists that were deleted from Spotify
- Interactive prompt lists obsolete files with option to delete
- Example output:
  ```
  ⚠ Found 3 obsolete playlist(s):
    • Old_Deleted_Playlist_abc123.m3u
    • Temp_Test_List_def456.m3u
  
  Delete obsolete playlists? [y/N]:
  ```

**Clean Before Export** (optional, disabled by default)
- `PSM__EXPORT__CLEAN_BEFORE_EXPORT=true` deletes ALL .m3u files before export
- Safest option but removes any manual additions
- Use for "fresh start" after major library reorganization

**Configuration:**
```bash
PSM__EXPORT__DETECT_OBSOLETE=true       # Default: detect and prompt
PSM__EXPORT__CLEAN_BEFORE_EXPORT=false  # Default: keep existing files
```

#### **Network Path Preservation**

Automatically preserves your configured path format:

- **Z:\Artists\Album\Song.mp3** → Stays as drive letter if configured that way
- **\\\\server\share\Artists\Album\Song.mp3** → Stays as UNC if configured that way
- **Works by**: Matching database absolute paths against your `PSM__LIBRARY__PATHS` config
- **Cross-platform**: Pure Python, no Windows-specific commands

**Configuration:**
```bash
PSM__LIBRARY__PATHS=["Z:/Artists","Z:/Sampler"]  # Your mount points
PSM__EXPORT__USE_LIBRARY_ROOTS=true              # Enable path reconstruction (default)
PSM__EXPORT__PATH_FORMAT=absolute                # absolute or relative (default: absolute)
```

#### **Live Progress Indicators**

See export progress in real-time:
```
▶ Exporting playlists to M3U
[1/302] Exporting: Chill Vibes
[2/302] Exporting: Workout Mix
[3/302] Exporting: Road Trip
...
[302/302] Exporting: Late Night Jazz
Exporting Liked Songs as virtual playlist (1624 tracks)
✓ Exported 302 playlists to Z:\Playlists\Spotify
✓ Export complete
```

#### **Visual Missing Track Indicators**

Mirrored mode makes missing tracks obvious in any player:

**In M3U file:**
```m3u
#EXTM3U
#EXTINF:180,Artist - Song Title
Z:\Artists\Artist\Song.mp3
#EXTINF:215,❌ Artist - Missing Song
!MISSING - Artist - Missing Song
```

**In your media player:**
- ✅ **Artist - Song Title** (plays normally)
- ❌ **Artist - Missing Song** (visible as missing, shows download priority)

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

**Export options:**
- `PSM__EXPORT__MODE` - strict|mirrored|placeholders (default: strict)
- `PSM__EXPORT__ORGANIZE_BY_OWNER` - Group by owner (default: true)
- `PSM__EXPORT__INCLUDE_LIKED_SONGS` - Export Liked Songs playlist (default: true)
- `PSM__EXPORT__PATH_FORMAT` - absolute|relative paths (default: absolute)
- `PSM__EXPORT__USE_LIBRARY_ROOTS` - Preserve Z:\ vs \\server\share (default: true)
- `PSM__EXPORT__CLEAN_BEFORE_EXPORT` - Delete all .m3u before export (default: false)
- `PSM__EXPORT__DETECT_OBSOLETE` - Prompt to delete obsolete playlists (default: true)

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

Multi-provider support is planned; see [docs/providers.md](docs/providers.md:1).

## License

MIT License

---

## Developer Docs

Development, release process, and provider extension details live in the `docs/` directory:

**User Guides:**
- `docs/cli-reference.md` - Complete CLI command reference
- `docs/architecture.md` - System design and components
- `docs/matching.md` - Match algorithm and strategies
- `docs/configuration.md` - All configuration options
- `docs/library_analysis.md` - Report generation details
- `docs/troubleshooting.md` - Common issues and solutions
- `docs/watch-mode.md` - Watch mode guide

**Development:**
- `docs/development.md` - Development setup and workflow
- `docs/providers.md` - Adding new streaming providers

---

**Need Help?** Quick references:
- `run.bat config` - View current settings
- `run.bat redirect-uri` - Show OAuth redirect
- `.env.example` - All environment variables
- `PSM__LOG_LEVEL=DEBUG` - Enable detailed diagnostic logging
Values starting with `[` or `{` are parsed as JSON; objects are supported (see configuration docs).
