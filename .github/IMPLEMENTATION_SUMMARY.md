# Parameter-Aware Action Naming Implementation Summary

## Problem Solved

**Before**: Clicking "Match Selected Track" incorrectly highlighted the toolbar "Match" button instead of the tracks panel button.

**After**: Each button gets highlighted correctly based on which specific action was triggered.

## Solution: Parameter-Aware Action Names

The system now generates unique action names based on command parameters:

| CLI Command | Action Name | Highlighted Button |
|-------------|-------------|-------------------|
| `['match']` | `'match'` | Toolbar "Match" |
| `['match', '--track-id', '123']` | `'match:track'` | Tracks panel "Match Selected Track" ✅ |
| `['diagnose', 'track_id']` | `'diagnose:track'` | Tracks panel "Diagnose Selected Track" ✅ |
| `['playlist', 'match', 'id']` | `'playlist:match'` | Left panel "Match Selected" ✅ |
| `['pull']` | `'pull'` | Toolbar "Pull" |
| `['playlist', 'pull', 'id']` | `'playlist:pull'` | Left panel "Pull Selected" ✅ |

## Changes Made

### 1. `psm/gui/services/command_service.py`

**Added**: `_extract_action_name()` method (35 lines)
```python
def _extract_action_name(self, args: list[str]) -> Optional[str]:
    """Extract semantic action name from CLI arguments.
    
    Creates unique action names to distinguish button contexts.
    """
    if not args:
        return None
    
    command = args[0]
    
    # Playlist-scoped (already working)
    if command == 'playlist' and len(args) >= 2:
        return f"playlist:{args[1]}"
    
    # Diagnose command (NEW - handles positional track_id argument!)
    if command == 'diagnose' and len(args) >= 2:
        return "diagnose:track"
    
    # Per-track (NEW - fixes the bug!)
    if '--track-id' in args:
        return f"{command}:track"
    
    # Per-playlist via flag (future-proof)
    if '--playlist-id' in args:
        return f"{command}:playlist"
    
    # Generic toolbar commands
    return command
```

**Updated**: `execute()` method
- Replaced inline action extraction with `_extract_action_name()` call
- Removed old 7-line if/elif/else logic
- Now uses clean, testable method

### 2. `psm/gui/controllers/main_orchestrator.py`

**Added**: `_set_track_button_state()` method (35 lines)
```python
def _set_track_button_state(self, action_name: str, state: str):
    """Set state styling for per-track action buttons in tracks panel."""
    base_action = action_name.split(':')[0]  # 'match:track' → 'match'
    
    tracks_panel = self.window.tracks_panel
    
    button_map = {
        'match': getattr(tracks_panel, 'btn_match_one', None),
        'diagnose': getattr(tracks_panel, 'btn_diagnose', None),
    }
    
    button = button_map.get(base_action)
    if button:
        # Apply orange/green/red styling based on state
        ...
```

**Updated**: `_on_action_state_change()` routing
```python
if action_name.startswith('build:'):
    # Build sub-steps
elif action_name.startswith('playlist:'):
    # Left panel buttons
elif action_name.endswith(':track'):  # ← NEW!
    self._set_track_button_state(action_name, state)
else:
    # Toolbar buttons
```

## How It Works

### Execution Flow (Example: Match Selected Track)

```
1. User clicks "Match Selected Track" button
2. tracks_panel.py emits signal with track_id
3. command_controller.py calls execute(['match', '--track-id', '123'])
4. command_service._extract_action_name() sees '--track-id' flag
5. Returns action_name = 'match:track'  ← Key differentiation!
6. ActionStateManager.set_action_running('match:track')
7. MainOrchestrator._on_action_state_change('match:track', 'running')
8. Routing logic: action_name.endswith(':track') → True
9. Calls _set_track_button_state('match:track', 'running')
10. Highlights tracks panel "Match Selected Track" button (orange)
11. On completion: button turns green, then resets
```

### Button State Lifecycle

```
Idle → Running → Success → Idle
  ↓       ↓         ↓
Default  Orange   Green
        (disabled) (flash)
```

All buttons are disabled during any running action (enforced by `enable_actions(False)`).

## Benefits

✅ **Correct Button Highlighting**: Each button highlights independently based on action context  
✅ **Clean Architecture**: Single responsibility - extraction logic in one method  
✅ **Scalable**: Easy to add new per-X actions (per-album, per-artist, etc.)  
✅ **Backward Compatible**: Existing toolbar buttons unchanged  
✅ **Testable**: _extract_action_name() is unit-testable  
✅ **Maintainable**: Clear naming convention (`:track`, `:playlist`)  

## Testing

✅ All 532 tests pass  
✅ No breaking changes  
✅ Works with existing playlist button routing  
✅ Gracefully handles unmapped actions (diagnose, config, etc.)  

## Future Enhancements

### Potential Extensions:
- **Per-Album Actions**: `'export:album'` for exporting album playlists
- **Per-Artist Actions**: `'pull:artist'` for artist-specific pulls
- **Batch Actions**: `'match:batch'` for multi-track operations
- **Filter Actions**: `'export:filtered'` for exporting filtered view

### CLI Enhancement (Optional):
Add structured action markers to CLI output:
```python
# In CLI commands
logger.info(f"🎵 ACTION:match:track track_id={args.track_id}")
```

This would make logs self-documenting and easier to parse.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         GUI Layer                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Toolbar    │  │  Left Panel  │  │ Tracks Panel │      │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤      │
│  │ Match (All)  │  │ Match Sel.   │  │ Match Sel.   │      │
│  │ Pull (All)   │  │ Pull Sel.    │  │ Track        │      │
│  │ Scan         │  │ Export Sel.  │  │ Diagnose     │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                 │                  │               │
│         └─────────────────┼──────────────────┘               │
│                           ▼                                  │
│              ┌────────────────────────┐                      │
│              │  CommandController     │                      │
│              └────────────┬───────────┘                      │
│                           ▼                                  │
│              ┌────────────────────────┐                      │
│              │   CommandService       │                      │
│              ├────────────────────────┤                      │
│              │ _extract_action_name() │ ← Parameter-aware    │
│              │   ['match']            │   extraction         │
│              │   → 'match'            │                      │
│              │   ['match','--track..']│                      │
│              │   → 'match:track' ✅   │                      │
│              └────────────┬───────────┘                      │
│                           ▼                                  │
│              ┌────────────────────────┐                      │
│              │ ActionStateManager     │                      │
│              │ set_action_running()   │                      │
│              └────────────┬───────────┘                      │
│                           ▼                                  │
│              ┌────────────────────────┐                      │
│              │  MainOrchestrator      │                      │
│              ├────────────────────────┤                      │
│              │ _on_action_state_      │                      │
│              │   change()             │ ← Smart routing      │
│              │   'match' → toolbar    │                      │
│              │   'match:track' →      │                      │
│              │     tracks_panel ✅    │                      │
│              │   'playlist:match' →   │                      │
│              │     left_panel ✅      │                      │
│              └────────────────────────┘                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Migration Notes

No migration needed! Changes are:
- Internal implementation only
- Existing action names still work ('match', 'pull', etc.)
- New suffixed names (':track', ':playlist') are additive
- All tests pass without modifications

---

**Implementation Date**: 2025-10-16  
**Files Modified**: 2 (command_service.py, main_orchestrator.py)  
**Lines Added**: ~75  
**Lines Removed**: ~10  
**Tests**: 532 passed ✅  
