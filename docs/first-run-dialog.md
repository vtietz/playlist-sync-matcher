# First-Run Dialog Architecture

## Overview

The first-run experience detects when no `.env` configuration file exists and guides users through creating one. Different interfaces are provided for CLI and GUI modes while sharing the same underlying logic.

## Implementations

### CLI Mode

**Entry Point**: `check_first_run_cli()` in `psm/utils/first_run.py`

**Flow**:
1. Check if `.env` exists → if yes, continue normally
2. Prompt user to create template (Y/n)
3. If yes:
   - Create `.env` file with template
   - Ask to open in editor (Y/n)
   - Exit with message to configure file
4. If no:
   - Show help about environment variables
   - Ask to continue anyway (y/N)
   - Exit or continue based on response

**Integration**: `check_first_run()` in `psm/cli/helpers.py` calls this during CLI command execution

### GUI Mode

**Entry Point**: `check_first_run_gui()` in `psm/utils/first_run.py`

**Flow**:
1. Check if `.env` exists → if yes, continue normally
2. Show `FirstRunDialog` (stateful QDialog)
3. **State A - Initial Prompt**:
   - Title: "Welcome to Playlist Sync Matcher!"
   - Message: Explains need for `.env` file
   - Buttons: "Create Template" | "Continue Anyway" | "Exit"
   - Default: "Create Template"
4. **State B - Post-Creation** (after successful creation):
   - Title: "Configuration Template Created!"
   - Message: Shows file location and next steps
   - Buttons: "Open File" | "Continue Anyway" | "Exit"
   - Default: "Open File"
5. User Actions:
   - "Create Template" → Creates file, transitions to State B
   - "Open File" → Opens `.env` in system editor (dialog remains open)
   - "Continue Anyway" → Accept dialog (returns True, app continues)
   - "Exit" → Reject dialog (returns False, app exits)

**Integration**: `main()` in `psm/gui/app.py` calls this before creating the main window

## FirstRunDialog Class

**Location**: `psm/utils/first_run.py`

**State Machine**:
```
┌─────────────────────┐
│   PROMPT STATE      │
│  "Create Template"  │  ──Create──┐
│  "Continue Anyway"  │            │
│  "Exit"             │            ▼
└─────────────────────┘   ┌─────────────────────┐
                          │ POST_CREATE STATE   │
                          │  "Open File"        │
                          │  "Continue Anyway"  │
                          │  "Exit"             │
                          └─────────────────────┘
```

**Key Methods**:
- `__init__(parent)` - Initialize dialog UI, set to PROMPT state
- `_init_prompt_state()` - Configure widgets for State A
- `_init_post_create_state()` - Configure widgets for State B
- `_on_create_clicked()` - Handle file creation, transition to State B
- `_on_open_file_clicked()` - Open file in editor (non-blocking)
- `_on_continue_clicked()` - Accept dialog (app continues)
- `_on_exit_clicked()` - Reject dialog (app exits)
- `exec()` - Show dialog, return True if accepted, False if rejected

**Error Handling**:
- File creation failure: Shows inline error message, stays in PROMPT state
- File already exists: Treats as success, transitions to POST_CREATE state
- Double-click prevention: Disables "Create Template" button during operation

## Design Decisions

### Single Dialog Instead of Multiple QMessageBoxes

**Previous Approach** (replaced):
- First QMessageBox: Prompt to create template
- Second QMessageBox: Show success, offer to open file
- Problem: Two separate dialogs, less cohesive UX

**New Approach**:
- Single stateful dialog that transitions between states
- More polished, professional feel
- User doesn't lose context between steps
- "Open File" button remains available (dialog stays open)

### State Transition Logic

**File Exists Check**:
- If `.env` already exists when "Create Template" is clicked
- Dialog treats this as success and transitions to POST_CREATE
- User can still click "Open File" to edit the existing file

**Non-Blocking "Open File"**:
- Opens file in system editor without closing dialog
- User can click "Open File" multiple times if needed
- Must explicitly choose "Continue Anyway" or "Exit"

**Inline Error Display**:
- Errors shown in red label within dialog (no popup)
- Dialog remains in PROMPT state
- "Create Template" button re-enabled
- User can retry or choose "Continue Anyway" / "Exit"

## Shared Components

### Template Generation

**Function**: `get_env_template()` in `psm/utils/first_run.py`

Returns a fully-commented `.env` template string with:
- Spotify API credentials section (required)
- Library paths configuration
- Export settings (mode, organization, path format)
- Matching settings (fuzzy threshold, duration tolerance)
- Database path
- Logging level

Used by both CLI and GUI modes when creating the template file.

### File Opening

**Function**: `open_file_in_editor(file_path)` in `psm/utils/first_run.py`

Platform-agnostic file opening:
- **Windows**: `os.startfile()` or fallback to `notepad.exe`
- **macOS**: `open` command
- **Linux**: `xdg-open` command

Returns `True` on success, `False` on failure (non-blocking).

## Integration Points

### GUI Entry Point

**File**: `psm/gui/app.py`
**Location**: `main()` function, lines 51-62

```python
# Check for first run before creating Qt application
from ..utils.first_run import check_env_exists
if not check_env_exists():
    # Need to show GUI dialog, so create minimal QApplication
    app = QApplication([])
    from ..utils.first_run import check_first_run_gui
    if not check_first_run_gui():
        logger.info("User needs to configure .env file. Exiting.")
        return 1
```

**Why Minimal QApplication First**:
- Qt dialogs require a QApplication instance
- Creates minimal app just to show dialog
- If user exits, app terminates without loading full UI
- If user continues, main QApplication is created normally

### CLI Entry Point

**File**: `psm/cli/helpers.py`
**Location**: `check_first_run()` function

```python
def check_first_run() -> bool:
    """Check if this is first run and handle .env creation.
    
    Skipped when PSM_SKIP_FIRST_RUN_CHECK is set (GUI-launched processes).
    """
    if os.environ.get('PSM_SKIP_FIRST_RUN_CHECK'):
        return True
    
    try:
        from ..utils.first_run import check_first_run_cli
        return check_first_run_cli()
    except KeyboardInterrupt:
        return False
```

**Skip Flag**: `PSM_SKIP_FIRST_RUN_CHECK`
- Set by `CliExecutor` in `psm/gui/runner.py`
- Prevents CLI commands launched from GUI from showing duplicate prompts
- GUI handles first-run check once at startup

## Testing Scenarios

### Manual Testing Matrix

| Scenario | Expected Behavior |
|----------|-------------------|
| **No .env, GUI launch** | FirstRunDialog shows in PROMPT state |
| **Click "Create Template"** | File created, dialog transitions to POST_CREATE |
| **Click "Open File"** | File opens in editor, dialog stays open |
| **Click "Continue Anyway" (PROMPT)** | App continues without `.env` |
| **Click "Continue Anyway" (POST_CREATE)** | App continues with created `.env` |
| **Click "Exit" (either state)** | App exits, logs message |
| **.env exists on "Create Template" click** | Transitions to POST_CREATE, shows existing file |
| **Creation fails (permissions)** | Inline error shown, stays in PROMPT state |
| **Double-click "Create Template"** | Button disabled during operation |
| **No .env, CLI launch** | CLI prompts shown (unchanged behavior) |
| **PSM_SKIP_FIRST_RUN_CHECK set** | No prompts, continues immediately |

### Edge Cases Covered

1. **Race condition**: `.env` created between check and dialog show
   - Dialog handles gracefully, treats as success

2. **Permissions error**: Read-only directory
   - Shows inline error, allows retry or exit

3. **Qt import failure**: PySide6 not available
   - Falls back to CLI mode automatically

4. **Multiple button clicks**: User spam-clicks buttons
   - "Create Template" disabled during operation
   - Other buttons accept/reject immediately (safe)

## Future Enhancements

Potential improvements (not currently implemented):

1. **Validation**: Check if Spotify Client ID is valid format
2. **Smart defaults**: Detect music folders (`C:\Users\<user>\Music`, etc.)
3. **In-dialog editing**: Simple text field for quick Client ID entry
4. **Progress indicator**: Show spinner during file operations
5. **Test connection**: Verify Spotify API credentials before closing

## Related Documentation

- [Configuration Guide](configuration.md) - Full `.env` reference
- [README Installation](../README.md#installation) - Download and setup instructions
- [Architecture Overview](architecture.md) - Overall system design
