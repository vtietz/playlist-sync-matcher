# MainWindow Refactoring Proposal

## Context

### Current Situation
- **File**: `psm/gui/main_window.py`
- **Current Size**: 829 lines
- **Growth Trend**: Adding bidirectional filtering will add ~100-150 more lines
- **Problem**: File is becoming difficult to maintain and navigate

### What the File Does
`MainWindow` is the main GUI window that:
1. **Creates UI Structure**: Builds a tabbed interface with:
   - **Left Panel Tabs**: Playlists, Albums, Artists (for browsing music library)
   - **Right Panel Tabs**: Tracks (main data view with filtering)
   - **Bottom Panel**: Logs and status information
2. **Manages Models**: Owns all data models (PlaylistsModel, AlbumsModel, ArtistsModel, TracksModel)
3. **Coordinates Signals**: Connects user actions (button clicks, selections) to controller actions
4. **Handles Updates**: Receives data from controllers and updates all views

### Current Implementation in Progress
We're implementing **bidirectional filtering**:
- **User Requirement**: When user selects a playlist/album/artist in the left panel, the tracks view should filter automatically
- **Reverse Direction**: When user changes a filter dropdown in tracks view, the corresponding item should be selected in the left panel
- **Complexity**: Requires careful signal coordination to avoid infinite loops (selection triggers filter, filter triggers selection, etc.)

### Code Structure Breakdown
```
MainWindow (829 lines total)
├── Initialization & Setup (90 lines)
│   ├── __init__ (signals, models, settings)
│   └── _create_ui (main layout assembly)
│
├── Widget Creation Methods (310 lines) ← **BLOAT AREA**
│   ├── _create_toolbar (40 lines)
│   ├── _create_playlists_widget (20 lines - tab container)
│   ├── _create_playlists_tab (110 lines) ← **BIG**
│   ├── _create_albums_tab (6 lines - wrapper)
│   ├── _create_artists_tab (6 lines - wrapper)
│   ├── _create_right_panel (12 lines - tab container)
│   ├── _create_tracks_tab (70 lines) ← **BIG**
│   ├── _create_playlist_detail_widget (32 lines)
│   └── _create_bottom_panel (14 lines)
│
├── Event Handlers (150 lines)
│   ├── Playlist filter handlers (_apply_playlist_filters, _populate_playlist_filter_options)
│   ├── Selection handlers (_on_playlist_selection_changed)
│   ├── Button handlers (enable_playlist_actions, _get_selected_playlist)
│   └── Window state handlers (closeEvent, _save_window_state, _restore_window_state)
│
├── Data Update Methods (100 lines)
│   ├── update_playlists, update_playlist_detail
│   ├── update_tracks, update_albums, update_artists
│   ├── update_unmatched_tracks, update_liked_tracks
│   └── update_status_counts, populate_filter_options
│
├── Utility Methods (80 lines)
│   ├── append_log, clear_log
│   ├── show_error, show_info
│   └── Various getters/setters
│
└── Bidirectional Filtering Logic (NOT YET IMPLEMENTED - will add ~100-150 lines)
    ├── Coordinate selection → filter updates
    ├── Coordinate filter → selection updates
    ├── Prevent circular signal loops
    └── Handle clear button actions
```

---

## Refactoring Options

### **Option 1: Extract Tab Builders** ⭐ Simple, Structural

**What**: Move tab creation logic to separate builder classes

**New Files to Create**:
```
psm/gui/tabs/
├── __init__.py
├── playlists_tab.py (~150 lines)
│   └── PlaylistsTabBuilder
│       ├── build() -> QWidget
│       ├── _create_filter_bar()
│       ├── _create_table()
│       ├── _create_buttons()
│       └── signals: playlist_selected, playlist_cleared
│
├── tracks_tab.py (~100 lines)
│   └── TracksTabBuilder
│       ├── build() -> QWidget
│       ├── _create_unified_tracks_view()
│       └── signals: filter_changed
│
├── albums_tab.py (~20 lines)
│   └── AlbumsTabBuilder (thin wrapper around AlbumsView)
│
└── artists_tab.py (~20 lines)
    └── ArtistsTabBuilder (thin wrapper around ArtistsView)
```

**MainWindow Changes**:
```python
# BEFORE (in MainWindow)
def _create_playlists_tab(self) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    # ... 110 lines of UI construction
    return widget

# AFTER (in MainWindow)
def _create_playlists_tab(self) -> QWidget:
    builder = PlaylistsTabBuilder(self.playlists_model, self.playlist_proxy_model)
    builder.playlist_selected.connect(self._on_playlist_selected)
    builder.playlist_cleared.connect(self._on_playlist_cleared)
    return builder.build()
```

**Benefits**:
- ✅ Reduces main_window.py by ~250-300 lines (down to ~530 lines)
- ✅ Each tab is self-contained and testable
- ✅ Easy to understand - clear file-per-tab structure
- ✅ Minimal changes to MainWindow class structure

**Drawbacks**:
- ❌ Doesn't reduce complexity of signal coordination
- ❌ Still need to wire signals in MainWindow
- ❌ Creates more files to navigate

---

### **Option 2: Extract Filter Coordinator** ⭐⭐ Logic-focused

**What**: Create a dedicated coordinator class to handle all bidirectional filtering logic

**New File to Create**:
```
psm/gui/coordinators/
└── filter_coordinator.py (~150-200 lines)
    └── FilterCoordinator
        ├── __init__(playlists_view, albums_view, artists_view, tracks_view)
        ├── connect_signals()  # Wire all bidirectional signals
        ├── _on_playlist_selected(playlist_name)
        ├── _on_album_selected(album_name, artist_name)
        ├── _on_artist_selected(artist_name)
        ├── _on_playlist_filter_changed(playlist_name)
        ├── _on_artist_filter_changed(artist_name)
        ├── _on_album_filter_changed(album_name)
        ├── _block_signals context manager  # Prevent loops
        └── clear_all_filters()
```

**How It Works**:
```python
# BEFORE (all in MainWindow - will be ~150 lines)
def _on_playlist_selected(self, playlist_name):
    # Block signals to prevent loop
    self.unified_tracks_view.blockSignals(True)
    # Set filter
    track_ids = self._get_track_ids_for_playlist(playlist_name)
    self.filter_bar.set_playlist_filter(playlist_name)
    # Update tracks
    self.proxy.set_playlist_filter(playlist_name, track_ids)
    self.unified_tracks_view.blockSignals(False)

def _on_album_selected(self, album_name, artist_name):
    # Similar complexity...
    
# ... 8-10 more handler methods with similar patterns

# AFTER (in MainWindow - just 10 lines)
def __init__(self):
    # ... existing init code
    self.filter_coordinator = FilterCoordinator(
        playlists_view=self.playlists_table_view,
        albums_view=self.albums_view,
        artists_view=self.artists_view,
        tracks_view=self.unified_tracks_view,
        data_facade=self.data_facade  # For fetching track IDs
    )
    self.filter_coordinator.connect_signals()
```

**Key Responsibility**: 
The coordinator becomes the "traffic cop" for all filter-related events:
1. Listens to selection changes in all left panel tabs
2. Updates track filters when selections change
3. Listens to filter changes in track view
4. Updates left panel selections when filters change
5. Prevents infinite loops using signal blocking

**Benefits**:
- ✅ Isolates complex bidirectional logic from MainWindow
- ✅ Single Responsibility Principle - one class for filter coordination
- ✅ Easier to test filtering logic in isolation
- ✅ Reduces main_window.py by ~100-150 lines (prevents growth, down to ~680 lines)
- ✅ Makes signal flow explicit and documented

**Drawbacks**:
- ❌ Adds another abstraction layer
- ❌ Coordinator needs references to multiple views
- ❌ MainWindow still large (~680 lines)

---

### **Option 3: Both (Tab Builders + Coordinator)** ⭐⭐⭐ Most Comprehensive

**What**: Combine both approaches for maximum benefit

**File Structure**:
```
psm/gui/
├── main_window.py (~350-400 lines) ← **50% reduction**
├── tabs/
│   ├── playlists_tab.py
│   ├── tracks_tab.py
│   ├── albums_tab.py
│   └── artists_tab.py
└── coordinators/
    └── filter_coordinator.py
```

**Benefits**:
- ✅ Maximum size reduction (829 → ~400 lines)
- ✅ Clear separation of concerns
- ✅ Each component highly testable
- ✅ MainWindow becomes pure orchestration

**Drawbacks**:
- ❌ Most files to create/maintain
- ❌ Highest upfront effort
- ❌ More navigation between files during development

---

### **Option 4: Continue As-Is** ⭐ No Changes

**What**: Accept the file size and add bidirectional filtering directly to MainWindow

**Result**: ~980 lines total (829 current + ~150 for filtering)

**Benefits**:
- ✅ No refactoring needed
- ✅ All code in one place
- ✅ Fastest to implement filtering feature

**Drawbacks**:
- ❌ File approaching 1000 lines
- ❌ Difficult to navigate and maintain
- ❌ Hard to test individual components
- ❌ Future features will make it worse

---

## Recommendation Matrix

| Criteria | Option 1 (Tabs) | Option 2 (Coordinator) | Option 3 (Both) | Option 4 (As-Is) |
|----------|----------------|------------------------|-----------------|------------------|
| **Line Reduction** | ~300 lines | ~150 lines | ~450 lines | 0 lines |
| **Implementation Effort** | Medium | Low-Medium | High | None |
| **Testing Improvement** | High | High | Very High | None |
| **Maintainability** | Good | Very Good | Excellent | Poor |
| **Immediate Value** | Low | High | Medium | High |
| **Long-term Value** | Medium | High | Very High | Low |

---

## My Recommendation: **Option 2 (FilterCoordinator)** 🎯

**Why**:
1. **Addresses immediate need**: We're about to add complex bidirectional filtering - perfect time to extract it
2. **Prevents file from growing to 1000+ lines**: Keeps growth in check
3. **Isolates the most complex logic**: Filtering coordination is the hardest part to understand
4. **Lower effort than Option 3**: Can be done in ~1 hour vs ~3 hours for full extraction
5. **Can do Option 1 later**: Tab extraction is independent and can happen anytime

**Implementation Plan**:
1. Create `psm/gui/coordinators/filter_coordinator.py` with FilterCoordinator class
2. Move all bidirectional filtering logic there (~150 lines)
3. Update MainWindow to use coordinator (~10 line change)
4. Test thoroughly
5. **Result**: MainWindow stays at ~680 lines instead of growing to ~980

**Future**: If file continues to grow, do Option 1 (tab extraction) in a separate PR.

---

## Questions for Expert Review

1. **Architecture**: Is FilterCoordinator the right pattern, or would you suggest a different approach (mediator, observer, etc.)?

2. **Signal Management**: Should the coordinator use Qt's signal blocking, or implement a custom "dirty flag" system to prevent loops?

3. **Testing Strategy**: How would you structure tests for bidirectional filtering? Mock all views, or integration tests?

4. **Alternative**: Would you recommend a completely different pattern (e.g., central state manager, Redux-like architecture)?

5. **Timing**: Should we refactor now (before adding filtering), or implement filtering first then refactor?

6. **Tab Extraction Priority**: Is reducing file size urgent enough to warrant Option 3 (both refactorings)?

---

## Code Examples

### Current State (Without Refactoring)
```python
# main_window.py - Will grow to ~980 lines
class MainWindow(QMainWindow):
    def _on_playlist_selected(self, selection):
        # 20 lines of coordination logic
        
    def _on_album_selected(self, album, artist):
        # 25 lines of coordination logic
        
    def _on_artist_selected(self, artist):
        # 20 lines of coordination logic
        
    def _on_track_filter_changed(self):
        # 30 lines of reverse coordination logic
        
    # ... 6 more similar handlers
    # Total: ~150 lines just for filtering coordination
```

### With FilterCoordinator (Option 2)
```python
# main_window.py - Stays at ~680 lines
class MainWindow(QMainWindow):
    def __init__(self):
        # ... existing init
        self.filter_coordinator = FilterCoordinator(
            playlists_view=self.playlists_table_view,
            albums_view=self.albums_view,
            artists_view=self.artists_view,
            tracks_view=self.unified_tracks_view,
            data_facade=self.data_facade
        )
        self.filter_coordinator.connect_signals()

# coordinators/filter_coordinator.py - New 150-line file
class FilterCoordinator:
    """Coordinates bidirectional filtering between left panel and tracks view."""
    
    def __init__(self, playlists_view, albums_view, artists_view, tracks_view, data_facade):
        self._playlists_view = playlists_view
        self._albums_view = albums_view
        self._artists_view = artists_view
        self._tracks_view = tracks_view
        self._data_facade = data_facade
        self._updating = False  # Prevent loops
    
    def connect_signals(self):
        """Wire all bidirectional signals."""
        # Left panel → tracks filter
        self._playlists_view.selectionModel().selectionChanged.connect(self._on_playlist_selected)
        self._albums_view.album_selected.connect(self._on_album_selected)
        self._artists_view.artist_selected.connect(self._on_artist_selected)
        
        # Tracks filter → left panel selection
        self._tracks_view.filter_bar.playlist_combo.currentTextChanged.connect(self._on_playlist_filter_changed)
        # ... etc
    
    def _on_playlist_selected(self, selected, deselected):
        """Handle playlist selection - update tracks filter."""
        if self._updating:
            return
        self._updating = True
        try:
            # Get selected playlist
            indexes = selected.indexes()
            if indexes:
                playlist_name = indexes[0].data()
                track_ids = self._data_facade.get_track_ids_for_playlist(playlist_name)
                self._tracks_view.set_playlist_filter(playlist_name, track_ids)
            else:
                self._tracks_view.clear_playlist_filter()
        finally:
            self._updating = False
    
    # ... similar handlers for other directions
```

---

## File Size Projection

| Scenario | main_window.py Size | New Files | Total Lines |
|----------|---------------------|-----------|-------------|
| **Current** | 829 | 0 | 829 |
| **Option 4 (As-Is + filtering)** | ~980 | 0 | 980 |
| **Option 2 (Coordinator)** | ~680 | 150 | 830 |
| **Option 1 (Tabs)** | ~530 | 290 | 820 |
| **Option 3 (Both)** | ~400 | 440 | 840 |

*Note: Total lines stay similar, but organized into logical units*

---

## Timeline Estimate

| Option | Implementation Time | Testing Time | Total |
|--------|-------------------|--------------|-------|
| Option 1 | 2-3 hours | 1 hour | 3-4 hours |
| Option 2 | 1 hour | 30 min | 1.5 hours |
| Option 3 | 3-4 hours | 1.5 hours | 4.5-5.5 hours |
| Option 4 | 30 min | 30 min | 1 hour |

---

**Current Status**: Ready to implement filtering. Awaiting decision on refactoring approach.
