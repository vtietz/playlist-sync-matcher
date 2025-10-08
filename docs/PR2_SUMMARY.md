# PR2: ExportResult Path Correctness - Summary

**Completed**: October 8, 2025  
**Duration**: ~15 minutes  
**Test Results**: ✅ 179/179 tests pass

## Overview

Fixed a bug where `export_playlists()` was recording constructed file paths instead of the actual paths returned by export helper functions. This caused a mismatch between what was recorded in `ExportResult.exported_files` and the actual filenames on disk.

## Problem

### Before (Incorrect)
```python
# In export_playlists() - line 127-138
if mode == 'strict':
    export_strict(playlist_meta, tracks, target_dir)
elif mode == 'mirrored':
    export_mirrored(playlist_meta, tracks, target_dir)
# ...

# WRONG: Constructs path manually, doesn't match actual file
result.exported_files.append(str(target_dir / f"{pl['name']}.m3u"))
```

**Issues**:
1. ❌ Assumes filename is `{name}.m3u` but actual is `{sanitized_name}_{id}.m3u8`
2. ❌ Doesn't account for name sanitization (special characters replaced with `_`)
3. ❌ Wrong extension (`.m3u` vs `.m3u8`)
4. ❌ Missing playlist ID suffix that export functions add

**Example Mismatch**:
- **Recorded**: `data/export/playlists/My Awesome: Playlist.m3u`
- **Actual File**: `data/export/playlists/My_Awesome__Playlist_abc12345.m3u8`

### After (Correct)
```python
# In export_playlists() - line 127-138
if mode == 'strict':
    actual_path = export_strict(playlist_meta, tracks, target_dir)
elif mode == 'mirrored':
    actual_path = export_mirrored(playlist_meta, tracks, target_dir)
# ...

# CORRECT: Uses the path returned by the export function
result.exported_files.append(str(actual_path))
```

## Implementation

### Change Summary

**File**: `psm/services/export_service.py`

**Modified**: Lines 127-138 in the playlist export loop

**Diff**:
```diff
         # Dispatch to export function based on mode
         if mode == 'strict':
-            export_strict(playlist_meta, tracks, target_dir)
+            actual_path = export_strict(playlist_meta, tracks, target_dir)
         elif mode == 'mirrored':
-            export_mirrored(playlist_meta, tracks, target_dir)
+            actual_path = export_mirrored(playlist_meta, tracks, target_dir)
         elif mode == 'placeholders':
-            export_placeholders(playlist_meta, tracks, target_dir, placeholder_extension=placeholder_ext)
+            actual_path = export_placeholders(playlist_meta, tracks, target_dir, placeholder_extension=placeholder_ext)
         else:
             logger.warning(f"Unknown export mode '{mode}', defaulting to strict")
-            export_strict(playlist_meta, tracks, target_dir)
+            actual_path = export_strict(playlist_meta, tracks, target_dir)
         
-        result.exported_files.append(str(target_dir / f"{pl['name']}.m3u"))
+        result.exported_files.append(str(actual_path))
```

### Verification

**Already Correct**: `_export_liked_tracks()` (lines 220-244)
- ✅ Already captured `actual_path` from export functions
- ✅ Already appended `str(actual_path)` to `result.exported_files`
- ✅ Served as the reference implementation for this fix

## Benefits

1. **Accuracy**: `ExportResult.exported_files` now contains real file paths that exist on disk
2. **Consistency**: Normal playlists and Liked Songs handled identically
3. **Robustness**: Works correctly regardless of sanitization rules or filename format changes
4. **Testability**: Integration tests can verify actual file existence using paths from result

## Test Results

### Integration Tests
```
✅ test_export_modes.py              3/3 passed
✅ test_liked_songs_export.py        5/5 passed
✅ test_organize_by_owner.py         2/2 passed
```

### Full Suite
```
✅ 179/179 tests passed in 4.37s
```

## Impact

### Users
- **No visible changes** - This is an internal bug fix
- Exported files continue to work identically

### Developers
- `ExportResult.exported_files` now trustworthy for automation/reporting
- Can verify file existence using paths from result object
- Aligns with expected behavior documented in tests

## Adherence to Plan

✅ **Scope**: Exactly as planned in REFACTORING_PLAN.md  
✅ **Files**: Only `export_service.py` modified (1 file)  
✅ **Tests**: All integration tests pass  
✅ **Duration**: Under 1 day estimate (15 minutes actual)  
✅ **Risk**: Low - simple path capture fix

## Files Changed

```
Modified (1 file):
  psm/services/export_service.py (lines 127-138)

Updated (2 files):
  docs/REFACTORING_PLAN.md
  docs/PR2_SUMMARY.md (this file)
```

## Next Steps

✅ **PR2 Complete** - Ready for commit

**PR3: CandidateSelector Utility** (next)
- Extract duration prefilter logic
- Extract Jaccard token prescore logic
- Reduce duplication in `match_changed_tracks()` and `match_changed_files()`
