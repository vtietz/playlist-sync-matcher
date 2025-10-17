# Watch Mode Guide

**Status:** Production-ready as of v1.0  
**Last Updated:** October 8, 2025

---

## Overview

Watch mode enables automatic, real-time synchronization of your local music library database as files change on disk. Instead of manually running `scan` after adding or modifying music files, the tool monitors your library paths and updates the database automatically.

**Key Features:**
- 🔄 Automatic file detection (new, modified, deleted)
- ⏱️ Intelligent debouncing to avoid event storms
- 🚀 Incremental updates (only changed files processed)
- 💾 Low resource usage (< 50 MB RAM, < 5% CPU when idle)
- 🛡️ Graceful handling of interruptions (Ctrl+C)
- 🔧 Cross-platform (Windows, Linux, macOS)

---

## Quick Start

### Basic Watch Mode

Monitor your library and automatically update the database:

```bash
psm scan --watch
```

This will:
1. Start monitoring all configured library paths
2. Detect file changes (create, modify, delete)
3. Update the database after changes settle (2-second debounce)
4. Continue running until you press Ctrl+C

### Custom Debounce Time

Adjust the quiet period before processing changes:

```bash
# Wait 5 seconds after last change
psm scan --watch --debounce 5

# Immediate processing (1 second)
psm scan --watch --debounce 1
```

**When to adjust debounce:**
- **Increase** (5-10s): When frequently copying large batches of files
- **Decrease** (1s): When you want near-instant updates for single file changes

---

## Build Watch Mode 🆕

For automatic end-to-end synchronization, use `build --watch` to monitor your library and automatically run the full pipeline when files change:

```bash
psm build --watch                    # Monitor library, auto-rebuild on changes
psm build --watch --debounce 5       # Use 5-second debounce (default: 2)
```

**What it does:**
1. Monitors your music library for file changes (create, modify, delete)
2. When changes settle (debounce period), automatically runs:
   - `scan` (smart mode: only changed files by default)
   - `match` (smart mode: only unmatched tracks by default)
   - `export` (regenerate M3U playlists **for affected playlists only**)
   - `report` (update reports **for affected playlists only**)

**Key differences from `scan --watch`:**
- **Full pipeline**: Runs all steps (scan → match → export → report)
- **Incremental by default**: Uses smart modes for efficiency
- **Scoped exports**: Only regenerates M3U files for playlists affected by the changes (see "Affected Playlists" below)
- **No Spotify re-pull**: Does NOT re-fetch playlists from Spotify (run `pull` manually when playlists change)
- **End-to-end**: Your M3U playlists and reports stay in sync with library changes

### Affected Playlists Logic

When files change in your library, watch mode determines which playlists are affected by the changes:

1. **Scan changed files**: Identify new/modified/deleted library files
2. **Match changed files**: Find which Spotify tracks match the changed library files
3. **Determine affected playlists**: Query which playlists contain the matched tracks
4. **Check Liked Songs**: Also check if matched tracks are in your Liked Songs collection
5. **Scoped rebuild**: Export and report only for affected playlists (and Liked Songs if applicable)

**Example scenario:**

```bash
# You have 50 playlists in Spotify + Liked Songs
# You add 1 new Pink Floyd album to your library
# → Scan detects 10 new files
# → Match finds 8 of them match tracks in playlist "Classic Rock"
# → Export regenerates ONLY "Classic Rock.m3u" (not all 50 playlists)
# → Report updates ONLY the Classic Rock report
```

**Liked Songs handling:**
```bash
# You add a song that's in your Liked Songs but no playlists
# → Scan detects 1 new file
# → Match finds it matches a track in Liked Songs
# → Export regenerates "Liked Songs.m3u"
# → Report updates to include the new Liked Songs match
```

**Benefits:**
- **Fast rebuilds**: Only process playlists that actually changed
- **Reduced I/O**: Don't rewrite unchanged M3U files
- **Clearer feedback**: Logs show exactly which playlists were affected
- **Liked Songs support**: Tracks only in Liked Songs are still exported/reported

**Affected playlist determination:**
1. Query playlists: `SELECT DISTINCT playlist_id FROM playlist_tracks WHERE track_id IN (...) AND provider = ?`
2. Query Liked Songs: `SELECT track_id FROM liked_tracks WHERE track_id IN (...) AND provider = ?`
3. If both empty → skip export/report (logged as "No affected playlists or liked tracks, skipping...")
4. If only Liked Songs affected → full export/report (to include Liked Songs section)
5. If playlists affected → scoped export/report for those specific playlists

**Use cases:**
- **Live library maintenance**: Keep playlists updated while organizing your music collection
- **Download monitoring**: Automatically index and match new downloads
- **Content creation workflows**: Music library changes immediately reflected in exports

**Example workflow:**
```bash
# One-time: Pull latest playlists from Spotify
psm pull

# Start watching (runs in foreground)
psm build --watch

# In another window/session: Add/modify music files
# → Watch mode automatically rebuilds everything
# → Press Ctrl+C when done
```

**Performance notes:**
- Uses smart scan mode (only changed files), so scans are fast
- Scoped export/report means only affected playlists are processed
- Debouncing prevents excessive processing during batch operations
- Typical rebuild time: 2-10 seconds for small changes affecting 1-5 playlists

---

## Use Cases

### 1. Active Music Organization

You're tagging and organizing your music library:

```bash
# Terminal 1: Watch for changes
psm scan --watch

# Terminal 2: Edit tags, move files, etc.
# Changes are automatically detected and processed
```

### 2. Continuous Download Monitoring

Automatically index new downloads:

```bash
# Point library path to your Downloads/Music folder
psm scan --watch --debounce 10
```

The longer debounce prevents processing while large downloads are in progress.

### 3. Network Drive Monitoring

For NFS/SMB mounts, watch mode may be unreliable. Use polling instead:

```bash
# Run periodic scans every 5 minutes (smart mode is default)
while true; do psm scan; sleep 300; done

# Or force deep scan periodically
while true; do psm scan --deep; sleep 3600; done
```

---

## How It Works

### Event Detection

Watch mode uses the `watchdog` library, which leverages OS-native filesystem APIs:

| OS | Technology | Performance |
|----|------------|-------------|
| **Windows** | `ReadDirectoryChangesW` | Excellent |
| **Linux** | `inotify` | Excellent |
| **macOS** | `FSEvents` | Excellent |

These APIs are event-driven (not polling), so CPU usage is minimal.

### Debouncing

When files change rapidly (e.g., copying an album), watch mode collects events and waits for a quiet period before processing:

```
File 1 added  ─┐
File 2 added  ─┤
File 3 added  ─┤── 2s debounce ──> Process all 3 files together
File 4 added  ─┘
```

**Benefits:**
- Prevents excessive database writes
- Batches related changes for efficiency
- Avoids processing temporary files

### Event Filtering

Not all filesystem events trigger database updates:

**Processed:**
- `.mp3`, `.flac`, `.m4a`, `.wav`, `.ogg`, etc. (configured extensions)
- File creation, modification, deletion, rename

**Ignored:**
- Temporary files (`.tmp`, `.part`, `.download`)
- Directories
- Non-music files
- Files matching `ignore_patterns` in config

---

## Incremental Scan Options

In addition to watch mode, there are other incremental scan modes:

### Time-Based Scanning

Scan only files modified after a specific time:

```bash
# Last 2 hours
psm scan --since "2 hours ago"

# Last 30 minutes
psm scan --since "30 minutes ago"

# Specific date/time
psm scan --since "2025-10-08 10:00:00"

# Unix timestamp
psm scan --since "1728123456.789"
```

**Use case:** Periodic cron job that scans recent changes.

### Smart Scan (Default)

Automatically detect what changed since last scan:

```bash
psm scan               # Smart mode by default
psm scan --deep        # Force complete rescan
```

Smart mode reads `last_scan_time` from the database and scans only files modified since then.

**Use case:** Daily usage - fast incremental scans after adding/modifying files.

### Specific Paths

Scan only certain directories:

```bash
# Single directory
psm scan --paths ./Music/NewAlbum/

# Multiple directories
psm scan --paths ./Music/Artist1/ ./Music/Artist2/
```

**Use case:** You just downloaded one album and want to index only that.

---

## Configuration

### Library Settings

In your `config.yml` or `config.json`:

```yaml
library:
  paths:
    - "Z:/Music/Artists"
    - "Z:/Music/Compilations"
  
  extensions:
    - ".mp3"
    - ".flac"
    - ".m4a"
    - ".ogg"
    - ".wav"
  
  ignore_patterns:
    - ".stfolder"  # Syncthing metadata
    - ".git"
    - "*.tmp"
  
  skip_unchanged: true
  fast_scan: true
```

**Key options for watch mode:**
- `extensions`: Only these file types trigger events
- `ignore_patterns`: Patterns to exclude from watching

### Watch-Specific Config

Currently, debounce time is set via CLI flag. Future versions may add:

```yaml
library:
  watch:
    debounce_seconds: 2.0
    max_batch_size: 1000
    enable_auto_match: false  # Auto-run match after scan
```

---

## Troubleshooting

### Watch Mode Not Detecting Changes

**Symptoms:** Files change, but database doesn't update.

**Possible causes:**

1. **Network drives (NFS/SMB):**
   - Filesystem events may not propagate properly
   - **Solution:** Use smart scan mode with a cron job instead (e.g., `psm scan` every 5 minutes)

2. **File extension not monitored:**
   - Check `library.extensions` in config
   - **Solution:** Add extension to config

3. **Ignore pattern blocking files:**
   - Check `library.ignore_patterns`
   - **Solution:** Remove or adjust pattern

4. **Path not in library config:**
   - Files must be under a configured `library.paths`
   - **Solution:** Add path to config

### Path Normalization Issues

**Symptoms:** Watch mode scans files but doesn't find matches, or shows "path not found" errors.

**Possible causes:**

1. **Drive letter case mismatch (Windows):**
   - Library files stored as `c:\Music\file.mp3` but scanned as `C:\Music\file.mp3`
   - **Solution:** Path normalization automatically uppercases drive letters (e.g., `C:\`) for consistency

2. **UNC paths vs. mapped drives (Windows):**
   - Same file accessed via `Z:\Music\file.mp3` and `\\server\share\Music\file.mp3`
   - **Solution:** Stick to one format (mapped drives recommended for consistency)
   - **Note:** Path normalization resolves symlinks but can't unify UNC/mapped drive references

3. **Forward vs. backslashes (Windows):**
   - Paths like `C:/Music/file.mp3` vs `C:\Music\file.mp3`
   - **Solution:** Path normalization converts to backslashes on Windows

4. **Symlink resolution:**
   - Library path is a symlink to actual directory
   - **Solution:** Path normalization resolves symlinks automatically to canonical paths

**Debugging path issues:**

```bash
# Check what paths are in the database
psm db query "SELECT DISTINCT path FROM library_files LIMIT 10"

# Watch mode logs normalized paths during scan
psm build --watch  # Check log output for path format
```

### Matching Issues with Remaster Variants

**Symptoms:** New remastered versions of tracks don't match existing Spotify tracks, or duplicate matches appear.

**Common remaster patterns handled:**
- `Song Title - 2011 Remaster`
- `Song Title (2011 Remaster)`
- `Song Title (Remastered 2011)`
- `Song Title - Mono`
- `Song Title - Stereo Mix`
- `Song Title [Remastered]`

**Example:**
```
Library file: "Wish You Were Here - 2011 Remaster.mp3"
Spotify track: "Wish You Were Here"
→ Both normalized to "wish you were here" → HIGH confidence match
```

**If matches still fail:**

1. **Check normalization in database:**
   ```bash
   psm db query "SELECT title, normalized FROM library_files WHERE title LIKE '%Remaster%' LIMIT 5"
   ```

2. **Verify fuzzy matching threshold:**
   - Check `matching.fuzzy_threshold` in config (default: 0.70)
   - Lower threshold = more lenient matching
   - **Solution:** Adjust in config if too strict

3. **Review match reports:**
   ```bash
   # Generate detailed match report
   psm report
   
   # Check reports/playlists/<playlist>_matches.html
   # Look for "unmatched" tracks with high title similarity
   ```

### GUI Watch Mode Restrictions

**Symptoms:** Manual commands grayed out or show "Watch mode is active" message.

**Expected behavior:**
- When watch mode is active in the GUI, **write** commands are disabled to prevent conflicts
- GUI shows: ⌚ **Watch mode active** in status area
- Attempting to run write commands shows: _"⌚ Watch mode is active. Stop watch to run commands that modify data."_
- **Read-only commands ARE allowed** during watch mode (see below)

**Read-only commands allowed during watch mode:**
- `diagnose <track_id>` - Diagnose why a track isn't matching (reads DB only)
- `config get <key>` - View configuration settings
- `db query <sql>` - Query the database (SELECT statements)
- `--version` - Show version information
- `--help` - Show help text

**Commands blocked during watch mode:**
- `pull` - Fetches from Spotify (writes to DB)
- `scan` - Scans library (writes to DB)
- `match` - Creates matches (writes to DB)
- `set-match` - Creates manual match overrides (writes to DB)
- `export` - Writes M3U files
- `report` - Writes HTML reports
- `build` - Runs full pipeline (writes everything)

**Manual match overrides and watch mode:**
- Manual overrides created with `set-match` update the `last_write_epoch` and `last_write_source` metadata
- This triggers GUI refresh just like any other database change
- The GUI and exports will automatically reflect the manual match when the database monitor detects the change
- Manual matches are always prioritized over automatic matches (confidence='MANUAL')

**Why these restrictions exist:**
- **Database lock conflicts**: SQLite is single-writer; concurrent writes cause lock errors
- **Race conditions**: Watch mode's incremental state could be corrupted by concurrent full scans
- **Resource contention**: Running multiple heavy operations simultaneously degrades performance

**Solution:**
- Stop watch mode via GUI stop button or Ctrl+C (if running via CLI)
- Run the write command
- Restart watch mode if desired

**💡 Tip:** Use read-only commands like `diagnose` to troubleshoot matching issues while watch mode is running!

### High CPU Usage

**Symptoms:** Watch mode uses excessive CPU.

**Possible causes:**

1. **Event storm:**
   - Thousands of files changing simultaneously
   - **Solution:** Increase debounce time (`--debounce 10`)

2. **Recursive watching too deep:**
   - Very deep directory hierarchies (>20 levels)
   - **Solution:** Reorganize library or use periodic smart scans

3. **Antivirus interference:**
   - AV scanning new files triggers duplicate events
   - **Solution:** Exclude library paths from real-time scanning

### Watch Mode Crashes

**Symptoms:** Process exits unexpectedly.

**Possible causes:**

1. **OS file handle limits:**
   - Too many directories being watched (>10,000)
   - **Solution:** Split library into multiple watch sessions

2. **Database lock timeout:**
   - Another process holding DB lock
   - **Solution:** Ensure only one PSM instance accesses DB

3. **Memory exhaustion:**
   - Very large event queue (rare)
   - **Solution:** Restart with higher debounce

---

## Performance Considerations

### Resource Usage

Typical resource usage for watch mode:

| Library Size | Memory | CPU (idle) | CPU (active) |
|--------------|--------|------------|--------------|
| 1,000 files  | ~20 MB | <1%        | 5-10%        |
| 10,000 files | ~35 MB | 1-2%       | 10-15%       |
| 50,000 files | ~60 MB | 2-3%       | 15-25%       |

**"Active" = processing a batch of changes**

### Scaling Limits

Watch mode scales well up to:
- ✅ **50,000 files** across hundreds of directories
- ✅ **Batches of 1,000 simultaneous changes**
- ✅ **Deep hierarchies** (20+ levels)

Beyond this, consider:
- Splitting library into multiple instances
- Using periodic smart scans instead (default mode)

### Network Drives

**Reliability:**
- ✅ **Local drives** (SSD/HDD): Excellent
- ⚠️ **SMB/CIFS**: Unreliable (depends on OS/driver)
- ❌ **NFS**: Generally unreliable
- ❌ **Cloud sync** (Dropbox, OneDrive): Not recommended

**Alternative for network drives:**

```bash
# Cron job: every 5 minutes (smart scan is default)
*/5 * * * * cd /path/to/project && ./run.sh scan
```

---

## Advanced Usage

### Running as a Service

#### Linux (systemd)

Create `/etc/systemd/system/psm-watch.service`:

```ini
[Unit]
Description=Playlist Sync Matcher Watch Mode
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/home/youruser/playlist-sync-matcher
ExecStart=/home/youruser/playlist-sync-matcher/run.sh scan --watch
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable psm-watch
sudo systemctl start psm-watch
sudo systemctl status psm-watch
```

#### Windows (Task Scheduler)

1. Open Task Scheduler
2. Create Task → General:
   - Name: "PSM Watch Mode"
   - Run whether user is logged on or not
3. Triggers → New:
   - Begin: At startup
4. Actions → New:
   - Program: `C:\path\to\run.bat`
   - Arguments: `scan --watch`
   - Start in: `C:\path\to\project`
5. Conditions:
   - Uncheck "Start only if on AC power"

#### macOS (launchd)

Create `~/Library/LaunchAgents/com.psm.watch.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.psm.watch</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/run.sh</string>
        <string>scan</string>
        <string>--watch</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/project</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

Load:

```bash
launchctl load ~/Library/LaunchAgents/com.psm.watch.plist
launchctl start com.psm.watch
```

### Combining with Other Commands

**Option 1: Scan-only watch (manual downstream steps)**

Watch mode updates the database, but doesn't automatically run matching or export:

```bash
# Terminal 1: Watch for library changes
psm scan --watch

# Terminal 2: Manually trigger downstream steps when needed
psm match
psm export
psm report
```

**Option 2: Full pipeline watch (automatic everything) 🆕**

Use `build --watch` to automatically run the full pipeline when files change:

```bash
# One terminal: Watch and auto-rebuild everything
psm build --watch

# Changes to your music library automatically trigger:
# → scan (smart mode) → match (smart mode) → export → report
```

This is the recommended approach for most users who want "set it and forget it" synchronization.

---

## FAQ

**Q: Can I use `--watch` with `--since` or `--deep`?**  
A: No, `--watch` is a different mode and cannot be combined with other scan flags.

**Q: Does watch mode work on cloud-synced folders?**  
A: Generally no. Cloud sync tools (Dropbox, OneDrive) may not trigger filesystem events reliably. Use smart scan mode with cron instead.

**Q: What happens if I modify a file while watch mode is processing?**  
A: The debounce timer resets, and the file will be processed again after the quiet period.

**Q: Can I run multiple watch instances?**  
A: Not recommended. Multiple instances may conflict when accessing the SQLite database. Use one watcher for all paths.

**Q: Does watch mode detect file renames?**  
A: Yes, renames are treated as delete + create events. The old path is removed and the new path is added.

**Q: What if my library has 100,000+ files?**  
A: Watch mode may struggle with very large libraries. Consider:
- Split into multiple smaller libraries
- Use periodic smart scans instead (default mode)
- Increase `--debounce` time

---

## See Also

- [Configuration Guide](configuration.md) - Library path setup
- [Architecture](architecture.md) - Technical implementation details
- [Troubleshooting](troubleshooting.md) - Common issues and solutions
- [README.md](../README.md) - Main documentation

---

**Questions or issues?** Open a GitHub issue with the `watch-mode` label.
