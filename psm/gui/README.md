# PSM GUI Module

Desktop GUI for Spotify M3U Sync built with PySide6 (Qt for Python).

## Architecture

### Design Principles
- **Zero Impact**: GUI module is completely isolated - no changes to existing CLI/service code
- **Read-Only Data Layer**: `DataFacade` uses only `DatabaseInterface` methods, no raw SQL
- **CLI Parity**: All actions execute actual CLI commands as subprocesses
- **Live Progress**: Real-time log streaming and progress bar updates from CLI output

### Module Structure

```
psm/gui/
├── __init__.py              # Package initialization
├── __main__.py              # Entry point for `python -m psm.gui`
├── app.py                   # QApplication bootstrap, config/DB loading
├── data_facade.py           # Read-only data access layer (no SQL)
├── models.py                # Qt table models (7 models for different views)
├── main_window.py           # Main UI layout and components
├── controllers.py           # Event handling and action execution
├── runner.py                # CLI subprocess execution with streaming
├── progress_parser.py       # Parse CLI output for progress updates
└── resources/
    └── style.qss            # Qt stylesheet
```

### Component Responsibilities

**app.py**
- Loads configuration via `load_typed_config()`
- Initializes database via `get_db()`
- Creates and shows `MainWindow`

**data_facade.py** (DataFacade)
- Wraps `DatabaseInterface` methods for GUI consumption
- Returns structured data (lists of dicts/dataclasses)
- Methods:
  - `list_playlists()` - All playlists with track counts
  - `get_playlist_detail(playlist_id)` - Tracks with local paths
  - `list_unmatched_tracks()` - Tracks without local matches
  - `list_matched_tracks()` - Tracks with local matches
  - `list_playlist_coverage()` - Coverage stats per playlist
  - `list_unmatched_albums()` - Albums with unmatched tracks
  - `get_liked_tracks()` - Liked songs

**models.py** (Qt Table Models)
- `PlaylistsTableModel` - Master playlist view
- `PlaylistDetailTableModel` - Tracks in selected playlist
- `UnmatchedTracksTableModel` - Tracks needing matches
- `MatchedTracksTableModel` - Successfully matched tracks
- `PlaylistCoverageTableModel` - Coverage statistics
- `UnmatchedAlbumsTableModel` - Albums with missing tracks
- `LikedTracksTableModel` - Liked songs

**main_window.py** (MainWindow)
- **Toolbar**: 11 action buttons
  - Pull | Scan | Match | Export | Report | Build | Watch | Refresh
  - Export Playlist | Report Playlist | Build Playlist
- **Left Panel**: Playlists master table
- **Right Panel**: Tabbed detail views
  - Playlist Detail
  - Unmatched Tracks
  - Matched Tracks
  - Coverage
  - Unmatched Albums
  - Liked Tracks
- **Bottom Panel**: Log window + Progress bar + Status bar

**controllers.py** (MainController)
- Connects UI signals to actions
- Handles playlist selection → detail loading
- Executes CLI commands via `CliExecutor`
- Updates progress bar from CLI output

**runner.py** (CliRunner + CliExecutor)
- `CliRunner` (QThread): Subprocess execution with stdout streaming
- `CliExecutor`: High-level action interface with progress callbacks

**progress_parser.py**
- Regex patterns for parsing CLI output
- Standardized formats from `psm.utils.progress`:
  - `[1/4] Step name` → step progress  
  - `Progress: 123/456 items (27%)` → item progress
  - `✓ Operation completed in 1.2s` → completion
  - `→ Status message` → status updates
- Backward compatible with legacy formats

## Installation

```bash
# Install dependencies
run.bat install

# Or manually
pip install -r requirements.txt
```

## Usage

### Launch GUI

```bash
# Via run scripts (recommended)
run.bat gui              # Windows
./run.sh gui             # Linux/macOS

# Via CLI command
psm gui                  # If installed globally
python -m psm.cli gui    # Direct CLI invocation

# Direct module execution
python -m psm.gui        # Bypasses CLI
```

**All methods work identically** - use whichever fits your workflow.

### Actions

**Pull Playlists**
- Fetches latest playlists from Spotify
- Updates database with new tracks
- Progress: Shows playlist count and track count

**Scan Library**
- Scans local music library for audio files
- Updates file metadata (mtime, size)
- Progress: Shows files processed

**Match Tracks**
- Matches Spotify tracks to local files
- Uses fuzzy matching with configurable threshold
- Progress: Shows tracks matched

**Export Playlists**
- Exports all playlists to M3U files
- Uses configured export directory
- Progress: Shows playlists exported

**Generate Report**
- Creates HTML report for all playlists
- Shows coverage, unmatched tracks, statistics
- Opens report in browser when complete

**Build Playlists**
- Full workflow: Pull → Scan → Match → Export → Report
- Can be toggled to watch mode (continuous)
- Progress: Shows current step [N/M]

**Per-Playlist Actions**
- **Export Playlist**: Export single playlist to M3U
- **Report Playlist**: Generate HTML report for one playlist
- **Build Playlist**: Full workflow for single playlist

### Tabs

**Playlist Detail**
- Shows tracks in selected playlist
- Columns: Title | Artist | Album | Local Path | Matched

**Unmatched Tracks**
- All tracks without local matches across all playlists
- Sortable by playlist, artist, album, title

**Matched Tracks**
- All successfully matched tracks
- Shows local file paths

**Coverage**
- Per-playlist statistics
- Total tracks | Matched | Coverage % | Unmatched

**Unmatched Albums**
- Albums with at least one unmatched track
- Groups by (Artist, Album)
- Shows total tracks vs unmatched count

**Liked Tracks**
- Tracks from "Liked Songs" playlist
- Same format as Playlist Detail

### Log Window

- **Live Updates**: Real-time output from CLI commands
- **Auto-Scroll**: Follows latest output
- **Styled**: Adapts to system dark/light theme
- **Copyable**: Select and copy log text

### Theme Support

The GUI automatically adapts to your system's theme (dark/light mode):
- **Windows**: Respects Windows dark mode settings
- **macOS**: Follows macOS appearance settings  
- **Linux**: Adapts to GTK/Qt theme

The stylesheet uses Qt palette colors (`palette(base)`, `palette(text)`, etc.) which automatically change based on system theme. The log window uses inverted colors for a terminal-like appearance in any theme.

### Progress Bar

- **Percentage**: Shows 0-100% progress
- **Label**: Current action description
- **Live Updates**: Parsed from CLI output

## Keyboard Shortcuts

- `Ctrl+R` - Refresh data
- `Ctrl+P` - Pull playlists
- `Ctrl+S` - Scan library
- `Ctrl+M` - Match tracks
- `Ctrl+E` - Export playlists
- `Ctrl+G` - Generate report
- `Ctrl+B` - Build playlists
- `Ctrl+W` - Toggle watch mode

## Configuration

GUI uses the same configuration file as CLI (`config.ini`).

Key settings:
- `local_music_dir` - Path to scan for audio files
- `export_dir` - Where to write M3U playlists
- `fuzzy_threshold` - Matching sensitivity (0.0-1.0)
- `watch_debounce_seconds` - Delay before watch mode triggers rebuild

## Troubleshooting

### GUI doesn't start

```bash
# Check PySide6 installation
python -c "from PySide6.QtWidgets import QApplication; print('OK')"

# Reinstall
run.bat install
```

### Database locked errors

- Close other instances of the app
- GUI uses read-only access to database
- Only writes happen via CLI subprocesses

### Actions fail silently

- Check log window for error messages
- CLI commands may require authentication (first run)
- Ensure `config.ini` is properly configured

### Progress bar stuck

- Some operations don't report progress (e.g., OAuth)
- Check log window for "waiting for auth" messages
- Complete auth in browser, GUI will resume

## Development

### Running from source

```bash
# Activate virtualenv
.venv\Scripts\activate

# Run GUI
python -m psm.gui
```

### Testing changes

```bash
# Run all tests
run.bat test

# Run GUI tests (when added)
pytest tests/unit/gui/
```

### Adding new actions

1. Add method to `CliExecutor` in `runner.py`
2. Wire button to method in `controllers.py`
3. Add progress patterns to `progress_parser.py` if needed
4. Update this README

### Styling

Edit `resources/style.qss` - standard Qt stylesheet syntax.

**Theme-Aware Design**:
- Uses Qt palette colors that automatically adapt to system theme
- `palette(base)` - background color
- `palette(text)` - text color
- `palette(highlight)` - accent color
- Works seamlessly in both light and dark modes

Key selectors:
- `QTableView` - Table styling
- `QPushButton` - Button colors (uses palette(highlight))
- `QTabWidget` - Tab appearance
- `#logWindow` - Log window specific styles (terminal-like)

## Architecture Notes

### Why subprocess execution?

- **CLI Parity**: GUI actions behave exactly like CLI commands
- **No Code Duplication**: Services run once via CLI, not reimplemented for GUI
- **Process Isolation**: Long-running operations don't freeze GUI
- **Live Output**: Stream stdout/stderr to log window
- **Easy Debugging**: Same code path as CLI

### Why DataFacade?

- **Abstraction**: GUI doesn't depend on database schema
- **Type Safety**: Returns structured data, not raw sqlite3.Row
- **Performance**: Can add caching without touching DatabaseInterface
- **Testing**: Easy to mock for GUI tests

### Why no direct service calls?

- **Separation of Concerns**: GUI module has zero business logic
- **Maintainability**: Service layer changes don't affect GUI
- **Consistency**: CLI and GUI always in sync

### Button State Management Pattern

**Problem**: Buttons should be disabled during command execution AND when their prerequisites aren't met (e.g., "Diagnose Selected Track" requires both: no command running AND a track selected).

**Solution**: Centralized state flags with dedicated update methods.

**Implementation** (see `main_window.py`):

```python
# 1. Define state flags in __init__
self._is_running: bool = False          # True when CLI command executing
self._has_track_selection: bool = False # True when track selected

# 2. Create centralized update method
def _update_track_actions_state(self):
    """Single source of truth for track action button states."""
    should_enable = not self._is_running and self._has_track_selection
    self.btn_diagnose.setEnabled(should_enable)

# 3. Update state flags and trigger update
def enable_actions(self, enabled: bool):
    self._is_running = not enabled
    self._update_track_actions_state()  # Recalculate button states

def _on_track_selection_changed(self, selected, deselected):
    self._has_track_selection = has_selection
    self.enable_track_actions(has_selection)  # Delegates to _update_track_actions_state
```

**Benefits**:
- Single source of truth for button state logic
- No race conditions (both flags checked in one place)
- Easy to add new conditions (e.g., `_is_connected`)
- Self-documenting (method name explains when buttons are enabled)

**When adding new conditional buttons**:
1. Add state flag(s) to `__init__`
2. Create `_update_<feature>_actions_state()` method with combined logic
3. Call update method whenever any flag changes
4. Document prerequisites in method docstring

## Future Enhancements

- [ ] PyInstaller spec for standalone executables
- [ ] Settings dialog (edit config.ini from GUI)
- [ ] Drag-and-drop M3U import
- [ ] Context menu on playlist table (right-click actions)
- [ ] Playlist search/filter
- [ ] Track search across all playlists
- [ ] Export selected playlists (multi-select)
- [ ] Dark mode toggle
- [ ] Playlist statistics graphs (matplotlib)
- [ ] Notifications (system tray on Windows/macOS)
- [ ] Undo/redo for database operations
- [ ] Export to multiple formats (M3U8, PLS, XSPF)

## Performance Optimization

For developers working with large datasets (50k+ tracks), see [`docs/gui-performance.md`](../../docs/gui-performance.md) which documents the performance optimization patterns used in this GUI:
- Fast-path filter optimization (90% CPU reduction)
- Direct data access patterns (avoiding Qt overhead)
- Chunked async loading (60fps UI responsiveness)
- Reusable patterns for any Qt table application

## License

Same as parent project (MIT).
