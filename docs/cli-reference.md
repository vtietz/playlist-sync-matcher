# CLI Reference Guide

Complete command-line reference for Playlist Sync Matcher.

## Table of Contents

- [Global Options](#global-options)
- [Main Commands](#main-commands)
  - [build](#build) - Complete sync pipeline
  - [login](#login) - Spotify authentication
  - [pull](#pull) - Fetch playlists
  - [scan](#scan) - Index local library
  - [match](#match) - Match tracks
  - [export](#export) - Generate M3U files
  - [analyze](#analyze) - Library quality check
  - [report](#report) - Generate reports
  - [gui](#gui) - Launch desktop GUI
- [Diagnostic Commands](#diagnostic-commands)
  - [diagnose](#diagnose) - Debug match failures
  - [config](#config) - Show configuration
  - [token-info](#token-info) - OAuth token status
  - [redirect-uri](#redirect-uri) - Show OAuth redirect
- [Playlist Commands](#playlist-commands)
  - [playlist pull](#playlist-pull)
  - [playlist match](#playlist-match)
  - [playlist export](#playlist-export)
  - [playlist build](#playlist-build)
  - [playlist push](#playlist-push)
  - [playlists list](#playlists-list)
- [Provider Commands](#provider-commands)
- [Common Workflows](#common-workflows)

---

## Global Options

Available for all commands:

```bash
--version                     Show version and exit
--config-file PATH            [Deprecated] Config file (ignored, use .env)
--progress / --no-progress    Enable/disable progress logging (overrides config)
--progress-interval INTEGER   Log progress every N items (overrides config)
--help                        Show help message
```

**Examples:**
```bash
psm --version                        # Show version
psm build --no-progress              # Run without progress output
psm match --progress-interval 50     # Show progress every 50 items
```

---

## Main Commands

### build

Run the complete one-way sync pipeline.

**Usage:**
```bash
psm build [OPTIONS]
```

**What it does:**
1. **Pull** playlists and liked tracks from Spotify
2. **Scan** local music library (smart mode: only changed files)
3. **Match** streaming tracks to local files
4. **Export** M3U playlists
5. **Generate** reports (matched, unmatched, coverage, albums)

**Options:**
```bash
--watch                       Monitor library and database, rebuild on changes
--debounce INTEGER            Seconds to wait after change before rebuild (default: 2)
--no-export                   Skip M3U playlist export
--no-report                   Skip report generation
```

**Examples:**
```bash
psm build                             # Complete sync (recommended)
psm build --watch                     # Continuous monitoring mode
psm build --watch --debounce 5        # 5-second debounce in watch mode
psm build --watch --no-report         # Skip reports during watch
```

**Watch Mode Details:**
- Monitors **library files** (add, modify, delete) AND **database changes**
- Incremental updates: only processes changed files/tracks (fast: 3-6 seconds)
- Does NOT run initial build - run `psm build` first, then start watch mode
- Press Ctrl+C to stop

**Workflow Tips:**
```bash
# Terminal 1: Start watch mode
psm build --watch

# Terminal 2: Pull new Spotify data when needed
psm pull
# Watch mode auto-detects and re-matches!
```

---

### login

Authenticate with Spotify using OAuth PKCE flow.

**Usage:**
```bash
psm login [OPTIONS]
```

**Options:**
```bash
--force    Force re-authentication (ignore cached tokens)
```

**What happens:**
1. Opens browser to Spotify authorization page
2. You approve the app
3. Tool receives callback and saves tokens to `tokens.json`
4. Tokens auto-refresh when expired (no need to re-login)

**Examples:**
```bash
psm login              # First-time authentication
psm login --force      # Force fresh login (if tokens corrupted)
```

**Troubleshooting:**
- **INVALID_CLIENT error?** → Check redirect URI matches Spotify Dashboard
- Run `psm redirect-uri` to see expected URI
- Default: `http://127.0.0.1:9876/callback`

---

### pull

Fetch playlists and liked tracks from Spotify.

**Usage:**
```bash
psm pull [OPTIONS]
```

**Options:**
```bash
--force-refresh    Force refresh even if no changes detected
```

**What it fetches:**
- All your playlists (owned and followed)
- All tracks in each playlist
- Your Liked Songs (❤️)
- Playlist metadata (name, owner, description, URL)

**Incremental Updates:**
- Only fetches playlists modified since last pull
- Only fetches new liked tracks
- Fast for regular syncs (seconds vs minutes for full refresh)

**Examples:**
```bash
psm pull                    # Smart incremental update (default)
psm pull --force-refresh    # Force complete re-fetch
```

**Performance:**
- First run: ~30-60 seconds for 100 playlists
- Subsequent runs: ~5-10 seconds (incremental)

---

### scan

Scan local music library and index track metadata.

**Usage:**
```bash
psm scan [OPTIONS]
```

**Options:**
```bash
--deep                       Force complete rescan of all library paths
--since TEXT                 Scan files modified after time (e.g., "2 hours ago")
--paths PATH                 Scan specific directory (repeatable)
--watch                      Monitor filesystem and auto-update database
--debounce INTEGER           Watch mode debounce seconds (default: 2)
```

**Smart Scanning (default):**
- Only scans new/modified files (checks mtime + size)
- Automatically removes deleted files from database
- Skips unchanged files for fast updates

**Examples:**
```bash
psm scan                              # Smart scan (default)
psm scan --deep                       # Force complete rescan
psm scan --since "2 hours ago"        # Scan recent changes
psm scan --paths ./NewAlbum/          # Scan specific directory
psm scan --watch                      # Continuous monitoring
psm scan --watch --debounce 5         # 5-second debounce
```

**Watch Mode:**
- Monitors `PSM__LIBRARY__PATHS` for file changes
- Automatically indexes new/modified files
- Removes deleted files from database
- Press Ctrl+C to stop

**Performance:**
- Smart scan: ~5-10 seconds for typical changes
- Deep scan: ~30-60 seconds for 10,000 files
- Shows live progress: directories scanned, files processed, files/second

**Output Example:**
```
Scanning 2 directories:
  • /Music/Artists/
  • /Music/Sampler/

100 files processed | 50 skipped | 38.3 files/s
200 files processed | 150 skipped | 40.4 files/s
...
✓ Library: 25 new 10 updated 1959 unchanged 6 deleted in 24.01s
```

---

### match

Match streaming tracks to local library files using scoring algorithm.

**Usage:**
```bash
psm match [OPTIONS]
```

**Options:**
```bash
--full              Force complete re-match of all tracks (ignores existing matches)
--min-confidence    Minimum confidence level (CERTAIN|HIGH|MEDIUM|LOW)
```

**What it does:**
1. Compares Spotify tracks against local library files
2. Uses weighted scoring: ISRC, exact match, fuzzy match, album context, duration
3. Assigns confidence tiers: CERTAIN (100%) → LOW (78%+)
4. Generates match reports automatically

**Incremental Matching (default):**
- Only matches unmatched tracks
- Skips tracks with existing matches
- Fast for regular updates (seconds vs minutes)

**Scoring Signals:**
- **ISRC match** (100%) - International Standard Recording Code
- **Exact match** (95%) - Perfect artist + title
- **Fuzzy match** (78%+) - Handles typos, punctuation
- **Album context** (+5%) - Matching album strengthens confidence
- **Year match** (+3%) - Release year agreement
- **Duration** (±2 seconds tolerance) - Must match within window

**Examples:**
```bash
psm match                         # Smart incremental (default)
psm match --full                  # Force complete re-match
psm match --min-confidence HIGH   # Only HIGH and CERTAIN matches
```

**Performance:**
- Incremental: ~10-20 seconds for 500 new tracks
- Full re-match: ~30-60 seconds for 5,000 tracks

**See Also:**
- [docs/matching.md](matching.md) - Match algorithm deep-dive
- `psm diagnose TRACK_ID` - Debug specific match failures
- `psm set-match` - Manually override matches
- `psm remove-match` - Remove matches

---

### set-match

Manually override the automatic match for a track.

**Usage:**
```bash
psm set-match --track-id TRACK_ID [--file-path PATH | --file-id ID]
```

**Arguments:**
```
--track-id TEXT      Spotify track ID to manually match  [required]
--file-path PATH     Absolute path to the local file to match to
--file-id INTEGER    Library file ID to match to (alternative to --file-path)
```

**What it does:**
1. Validates track exists in database
2. Resolves file (by path or ID)
3. Adds file to library if not present
4. Deletes any existing matches for the track
5. Creates manual match with confidence=MANUAL
6. Updates metadata to trigger GUI refresh

**Manual Match Priority:**
Manual matches are ALWAYS preferred over automatic matches in:
- Unified tracks view (SQL ranking)
- Playlist exports (.m3u files)
- Liked songs exports
- Diagnostics display

**Examples:**
```bash
# Manual match using file path
psm set-match --track-id 3n3Ppam7vgaVa1iaRUc9Lp --file-path "C:\Music\song.mp3"

# Manual match using file ID from library
psm set-match --track-id 3n3Ppam7vgaVa1iaRUc9Lp --file-id 12345

# Verify manual match
psm diagnose 3n3Ppam7vgaVa1iaRUc9Lp
```

**Use cases:**
- Automatic matcher picked wrong version (live vs studio, remaster, etc.)
- Better quality file at different location
- Metadata doesn't match but you know it's correct
- Override fuzzy matching when certain

**See Also:**
- `psm remove-match` - Remove manual or automatic matches
- `psm diagnose TRACK_ID` - Verify match confidence

---

### remove-match

Remove the match for a track (manual or automatic).

**Usage:**
```bash
psm remove-match --track-id TRACK_ID
```

**Arguments:**
```
--track-id TEXT    Track ID to remove match for  [required]
```

**What it does:**
1. Validates track exists in database
2. Checks if track has existing match
3. Displays current match details (file, confidence, score)
4. Deletes all matches for the track
5. Updates metadata to trigger GUI refresh

**After Removal:**
Track will appear as unmatched until you:
- Run `psm match --track-id <id>` for new automatic match
- Run `psm set-match --track-id <id> --file-path <path>` for manual match

**Examples:**
```bash
# Remove match (shows current match details)
psm remove-match --track-id 3n3Ppam7vgaVa1iaRUc9Lp

# Verify track is unmatched
psm diagnose 3n3Ppam7vgaVa1iaRUc9Lp

# Re-match automatically
psm match --track-id 3n3Ppam7vgaVa1iaRUc9Lp
```

**Use cases:**
- Removing incorrect manual matches
- Clearing matches before setting new manual ones
- Resetting tracks to allow re-matching with updated rules
- Troubleshooting matching issues

**See Also:**
- `psm set-match` - Create manual match override
- `psm match --track-id <id>` - Create new automatic match

---

### export

Generate M3U playlist files pointing to local music files.

**Usage:**
```bash
psm export [OPTIONS]
```

**Options:**
```bash
--mode [strict|mirrored|placeholders]    Export mode (overrides config)
--clean                                   Delete all .m3u files before export
```

**Export Modes:**

**Strict (default for reliability):**
- Only includes successfully matched tracks
- Cleanest playlists for guaranteed playback
- Missing tracks silently omitted

**Mirrored (recommended for completeness):**
- Preserves ALL tracks from Spotify
- Missing tracks marked with ❌ emoji
- Example: `❌ Artist - Missing Song`
- Perfect for tracking what to download

**Placeholders:**
- Creates dummy `.missing` files for unmatched tracks
- Maintains playlist order with physical files
- Useful for scripting batch downloads

**Smart Features:**
- **Obsolete Detection**: Prompts to delete playlists removed from Spotify
- **Network Path Preservation**: Maintains Z:\ vs \\server\share format
- **Collision-Safe Names**: `PlaylistName_abc12345.m3u`
- **Liked Songs**: Automatic virtual playlist for ❤️ tracks

**Examples:**
```bash
psm export                        # Use configured mode (default: strict)
psm export --mode mirrored        # Show all tracks with ❌ for missing
psm export --mode placeholders    # Create .missing files
psm export --clean                # Delete all .m3u files first
```

**Configuration:**
```bash
# .env settings
PSM__EXPORT__MODE=mirrored                  # strict|mirrored|placeholders
PSM__EXPORT__ORGANIZE_BY_OWNER=true        # Group by owner folders
PSM__EXPORT__INCLUDE_LIKED_SONGS=true      # Export Liked Songs playlist
PSM__EXPORT__PATH_FORMAT=absolute          # absolute|relative
PSM__EXPORT__USE_LIBRARY_ROOTS=true        # Preserve Z:\ vs \\server\share
PSM__EXPORT__DETECT_OBSOLETE=true          # Prompt to delete obsolete
PSM__EXPORT__CLEAN_BEFORE_EXPORT=false     # Auto-clean before export
```

**Output:**
```
▶ Exporting playlists to M3U
[1/302] Exporting: Chill Vibes
[2/302] Exporting: Workout Mix
...
[302/302] Exporting: Late Night Jazz
Exporting Liked Songs as virtual playlist (1624 tracks)
✓ Exported 302 playlists to /Music/Playlists/Spotify
```

---

### analyze

Analyze local library quality (missing tags, low bitrate).

**Usage:**
```bash
psm analyze [OPTIONS]
```

**What it checks:**
- Missing metadata (artist, title, album, year)
- Low bitrate files (below threshold)
- Grouped by album for efficient bulk fixing

**Auto-Generated Reports:**
- **Metadata Quality Report** (CSV + HTML)
- **Console Output** with top albums needing fixes

**Options:**
```bash
--bitrate-threshold INTEGER    Minimum bitrate in kbps (default: 320)
```

**Examples:**
```bash
psm analyze                     # Check quality (320 kbps threshold)
psm analyze --bitrate-threshold 256   # Lower threshold
```

**Output Location:**
- `data/export/reports/metadata_quality.html`
- `data/export/reports/metadata_quality.csv`

**Console Example:**
```
🔍 Library Quality Analysis

Top Albums with Issues:
📁 The Beatles - Abbey Road (18 files missing year)
📁 Pink Floyd - The Wall (12 files missing album)
📁 Various Artists - Greatest Hits (8 files low bitrate)
...
```

**See Also:**
- [docs/library_analysis.md](library_analysis.md) - Analysis details

---

### report

Generate all available reports from existing database.

**Usage:**
```bash
psm report [OPTIONS]
```

**Options:**
```bash
--match-reports / --no-match-reports            Include/exclude match reports
--analysis-reports / --no-analysis-reports      Include/exclude quality reports
```

**Generated Reports:**

**Match Reports** (from `psm match`):
- `matched_tracks.html` - All matches with confidence scores
- `unmatched_tracks.html` - Missing tracks, sorted by popularity
- `unmatched_albums.html` - Missing content grouped by album
- `playlist_coverage.html` - Coverage % per playlist

**Analysis Reports** (from `psm analyze`):
- `metadata_quality.html` - Files with missing/poor metadata

**Examples:**
```bash
psm report                         # Generate all reports (default)
psm report --no-analysis-reports   # Only match reports
psm report --no-match-reports      # Only analysis reports
```

**Use Cases:**
- Regenerate reports after manual database edits
- Share results without re-processing
- Tweak report formats/thresholds

**Output Location:**
- `data/export/reports/index.html` (dashboard)
- Individual report files in same directory

**Open Reports:**
```bash
# Windows
start data\export\reports\index.html

# Mac
open data/export/reports/index.html

# Linux
xdg-open data/export/reports/index.html
```

---

### gui

Launch the desktop GUI application.

**Usage:**
```bash
psm gui
```

**Features:**
- 📊 Master-detail playlists view
- 🎯 Actionable tabs (Unmatched, Matched, Coverage, Albums, Liked Songs)
- ⚡ All CLI actions via toolbar buttons
- 🔄 Watch mode toggle
- 📝 Live logs and progress tracking
- 🎨 Professional Qt interface

**No Options** - GUI is fully interactive.

**See Also:**
- `psm/gui/README.md` - Detailed GUI documentation
- `docs/gui-performance.md` - Performance patterns

---

## Diagnostic Commands

### diagnose

Diagnose why a specific track isn't matching.

**Usage:**
```bash
psm diagnose [OPTIONS] TRACK_ID
```

**Arguments:**
```
TRACK_ID    Spotify track ID (from unmatched_tracks report)
```

**Options:**
```bash
--top-n INTEGER    Number of closest files to show (default: 5)
```

**What it shows:**
- Track metadata from Spotify
- Current match status
- Top N closest library files with scores
- Duration comparison
- Specific recommendations for fixes

**Workflow:**
1. Check `unmatched_tracks` report
2. Copy Track ID from first column
3. Run diagnose command
4. Follow recommendations

**Examples:**
```bash
psm diagnose 3n3Ppam7vgaVa1iaRUc9Lp                  # Show top 5 matches
psm diagnose --top-n 10 3n3Ppam7vgaVa1iaRUc9Lp       # Show top 10
```

**Output Example:**
```
🔍 Diagnosing Track: Artist - Song Title

Track Info:
  ID: 3n3Ppam7vgaVa1iaRUc9Lp
  Artist: Artist Name
  Title: Song Title
  Album: Album Name
  Duration: 3:45
  Normalized: artist name song title

Match Status: ❌ Not matched

Top 5 Closest Files:
  1. Score: 0.85 | Duration: 3:47 | Artist - Song Title (Alt Mix).mp3
     → Almost matches! Duration off by 2s. Check if correct version.
  
  2. Score: 0.76 | Duration: 3:45 | Artiste - Song Title.mp3
     → Fuzzy match failed. Artist tag has typo. Fix: 'Artiste' → 'Artist Name'
  
Recommendations:
  • Lower PSM__MATCHING__FUZZY_THRESHOLD from 0.78 to 0.75
  • Fix artist tag in file #2
  • Check if file #1 is correct version (different mix?)
```

**See Also:**
- [docs/troubleshooting.md](troubleshooting.md) - Complete troubleshooting guide

---

### config

Show current configuration settings.

**Usage:**
```bash
psm config show
```

**What it displays:**
- All configuration values (defaults + overrides)
- Source of each value (default, .env, environment variable)
- Validation status

**Example Output:**
```
Configuration:
  PSM__PROVIDERS__SPOTIFY__CLIENT_ID = "abc123..." (from .env)
  PSM__LIBRARY__PATHS = ["C:/Music"] (from .env)
  PSM__EXPORT__MODE = "mirrored" (from .env)
  PSM__MATCHING__FUZZY_THRESHOLD = 0.78 (default)
  ...
```

**See Also:**
- [docs/configuration.md](configuration.md) - All config options
- `.env.example` - Example configuration file

---

### token-info

Show OAuth token cache status and expiration info.

**Usage:**
```bash
psm token-info
```

**What it shows:**
- Token file location
- Whether tokens exist
- Expiration time (if available)
- Whether tokens need refresh

**Example Output:**
```
OAuth Token Info:
  File: tokens.json
  Status: ✓ Valid tokens found
  Expires: 2025-10-13 15:30:42 UTC (in 47 minutes)
  Auto-refresh: Enabled
```

---

### redirect-uri

Show OAuth redirect URI for Spotify app configuration.

**Usage:**
```bash
psm redirect-uri
```

**What it shows:**
- Current redirect URI from configuration
- Instructions for Spotify Dashboard setup

**Example Output:**
```
Current OAuth Redirect URI:
  http://127.0.0.1:9876/callback

Setup Instructions:
1. Go to https://developer.spotify.com/dashboard
2. Open your app settings
3. Add this exact URI to "Redirect URIs"
4. Click "Save"

Note: URI must match exactly (including http:// and port)
```

**Configuration:**
```bash
# .env - Use HTTPS with custom domain (optional)
PSM__PROVIDERS__SPOTIFY__REDIRECT_SCHEME=https
PSM__PROVIDERS__SPOTIFY__REDIRECT_HOST=localhost
PSM__PROVIDERS__SPOTIFY__REDIRECT_PORT=9876
```

---

## Playlist Commands

Work with individual playlists instead of syncing all.

### playlist pull

Pull a single playlist from Spotify.

**Usage:**
```bash
psm playlist pull PLAYLIST_ID
```

**Arguments:**
```
PLAYLIST_ID    Spotify playlist ID (from URL or `playlists list`)
```

**Examples:**
```bash
psm playlist pull 37i9dQZF1DXcBWIGoYBM5M      # Pull specific playlist
```

---

### playlist match

Match a single playlist's tracks against library.

**Usage:**
```bash
psm playlist match PLAYLIST_ID
```

**Arguments:**
```
PLAYLIST_ID    Spotify playlist ID
```

**Examples:**
```bash
psm playlist match 37i9dQZF1DXcBWIGoYBM5M     # Match one playlist
```

---

### playlist export

Export a single playlist to M3U file.

**Usage:**
```bash
psm playlist export PLAYLIST_ID
```

**Arguments:**
```
PLAYLIST_ID    Spotify playlist ID
```

**Examples:**
```bash
psm playlist export 37i9dQZF1DXcBWIGoYBM5M    # Export one playlist
```

---

### playlist build

Pull + match + export a single playlist (complete workflow).

**Usage:**
```bash
psm playlist build PLAYLIST_ID
```

**Arguments:**
```
PLAYLIST_ID    Spotify playlist ID
```

**What it does:**
1. Pull playlist from Spotify
2. Match tracks against library
3. Export to M3U file

**Examples:**
```bash
psm playlist build 37i9dQZF1DXcBWIGoYBM5M     # Complete single-playlist sync
```

**Use Cases:**
- Testing settings on one playlist before full sync
- Selective updates for specific playlists
- Faster processing for large collections

---

### playlist push

**⚠️ Experimental:** Push local M3U track order back to Spotify.

**Usage:**
```bash
psm playlist push [OPTIONS] PLAYLIST_ID
```

**Arguments:**
```
PLAYLIST_ID    Spotify playlist ID
```

**Options:**
```bash
--apply    Actually apply changes (default: preview only)
```

**What it does:**
1. Reads local M3U file
2. Compares track order with Spotify
3. Shows differences (preview mode)
4. Optionally updates Spotify playlist order

**Examples:**
```bash
psm playlist push 37i9dQZF1DXcBWIGoYBM5M           # Preview changes
psm playlist push --apply 37i9dQZF1DXcBWIGoYBM5M   # Apply changes
```

**⚠️ Warning:** This modifies your Spotify playlist! Always preview first.

---

### playlists list

List all playlists with IDs.

**Usage:**
```bash
psm playlists list [OPTIONS]
```

**Options:**
```bash
--show-urls    Include Spotify URLs
```

**Examples:**
```bash
psm playlists list              # Show IDs and names
psm playlists list --show-urls  # Include Spotify links
```

**Output Example:**
```
Your Playlists:
  ID: 37i9dQZF1DXcBWIGoYBM5M | Name: Chill Vibes | Owner: spotify
  ID: 1A2B3C4D5E6F7G8H9I0J   | Name: Workout Mix | Owner: yourusername
  ...
```

---

## Provider Commands

### providers list

List available streaming providers.

**Usage:**
```bash
psm providers list
```

**Current Support:**
- Spotify (full implementation)

**Future:**
- Additional providers welcome (see `docs/providers.md`)

---

## Common Workflows

### First-Time Setup
```bash
# 1. Configure (automatic first-run prompt)
psm config show

# 2. Authenticate
psm login

# 3. Initial sync
psm build
```

### Regular Sync
```bash
# Complete sync (recommended)
psm build

# OR individual steps
psm pull          # Get latest playlists
psm scan          # Update library index
psm match         # Re-match tracks
psm export        # Update M3U files
```

### Continuous Monitoring
```bash
# Terminal 1: Watch mode
psm build --watch

# Terminal 2: Manual operations
psm pull          # Watch auto-detects and rebuilds
```

### Quality Improvement
```bash
# Check library quality
psm analyze

# View unmatched tracks
open data/export/reports/unmatched_tracks.html

# Debug specific track
psm diagnose TRACK_ID

# Fix tags, then re-scan and match
psm scan --deep
psm match --full
```

### Single Playlist Testing
```bash
# Get playlist IDs
psm playlists list

# Test one playlist
psm playlist build PLAYLIST_ID

# If successful, sync all
psm build
```

### Regenerate Reports
```bash
# After manual database edits
psm report

# Match reports only
psm report --no-analysis-reports

# Quality reports only
psm report --no-match-reports
```

### Debug Authentication
```bash
# Check current token status
psm token-info

# Show redirect URI for Spotify setup
psm redirect-uri

# Force fresh login
psm login --force
```

---

## Environment Variables

All configuration can be set via `.env` file or environment variables using the pattern `PSM__SECTION__KEY`.

**Quick Reference:**

```bash
# Required
PSM__PROVIDERS__SPOTIFY__CLIENT_ID=your_client_id_here
PSM__LIBRARY__PATHS=["C:/Music", "D:/Archive"]

# Export
PSM__EXPORT__MODE=mirrored                  # strict|mirrored|placeholders
PSM__EXPORT__ORGANIZE_BY_OWNER=true        # Group by owner folders
PSM__EXPORT__INCLUDE_LIKED_SONGS=true      # Export Liked Songs

# Matching
PSM__MATCHING__FUZZY_THRESHOLD=0.78         # 0.0-1.0
PSM__MATCHING__DURATION_TOLERANCE=2.0       # Seconds

# Performance
PSM__LIBRARY__FAST_SCAN=true                # Skip unchanged files

# Logging
PSM__LOG_LEVEL=INFO                         # DEBUG|INFO|WARNING
```

**Temporary Override:**
```bash
# Windows
set PSM__EXPORT__MODE=strict && psm export

# Linux/Mac
PSM__EXPORT__MODE=strict psm export
```

**See Also:**
- [docs/configuration.md](configuration.md) - Complete configuration reference
- `.env.example` - Example configuration with all options

---

## Exit Codes

- **0** - Success
- **1** - General error (configuration, authentication, etc.)
- **2** - Database error
- **3** - Network/API error

---

## Debug Mode

Enable detailed diagnostic logging:

```bash
# Temporary
PSM__LOG_LEVEL=DEBUG psm match

# Or in .env
PSM__LOG_LEVEL=DEBUG
```

**What you'll see:**
- API request/response details
- Match scoring calculations
- File processing steps
- Configuration resolution

---

## Related Documentation

- [README.md](../README.md) - Quick start and overview
- [docs/configuration.md](configuration.md) - All configuration options
- [docs/matching.md](matching.md) - Match algorithm details
- [docs/troubleshooting.md](troubleshooting.md) - Common issues
- [docs/watch-mode.md](watch-mode.md) - Watch mode deep-dive
- [docs/library_analysis.md](library_analysis.md) - Report generation
- [docs/providers.md](providers.md) - Adding new providers
- [docs/development.md](development.md) - Development guide
