# Liked Songs Virtual Playlist Feature

## Summary

Spotify's "Liked Songs" (Lieblingssongs/❤️) collection is now fully integrated as a virtual playlist throughout the application. This feature was implemented in response to user request for handling liked tracks separately from regular playlists.

## Implementation Details

### Architecture

**Virtual Playlist Pattern**: Liked Songs is treated as a special playlist without polluting the database with fake playlist records. Instead:
- Pull operations store liked tracks in the dedicated `liked_tracks` table
- Export and reporting dynamically generate a virtual playlist on-demand
- All three export modes (strict/mirrored/placeholders) are supported

### Changes Made

#### 1. Export Service (`psm/services/export_service.py`)
- Added `_export_liked_tracks()` helper function
- Modified `export_playlists()` to call liked songs export after regular playlists
- Respects `organize_by_owner` flag (places in user's folder)
- Preserves newest-first ordering (matching Spotify's UI)

#### 2. Playlist Coverage Report (`psm/reporting/reports/playlist_coverage.py`)
- Updated SQL query with UNION to include liked tracks as virtual playlist
- Uses parameterized query to safely inject owner name
- Graceful fallback when metadata table doesn't exist (test compatibility)
- Virtual playlist ID: `_liked_songs_virtual`

#### 3. Configuration (`psm/config.py` & `psm/config_types.py`)
- Added `export.include_liked_songs` setting (default: `true`)
- Users can disable liked songs export via config if needed

#### 4. Match Service (`psm/services/match_service.py`)
- Changed progress logging terminology from "skipped" to "unmatched" for clarity
- Avoids confusion between scan skipping (unchanged files) and match skipping (no match found)

## User-Facing Changes

### Default Behavior
- `run.bat pull` - Fetches liked tracks automatically
- `run.bat match` - Matches liked tracks alongside playlist tracks
- `run.bat export` - Creates "Liked Songs_xxxxxxxx.m3u8" file automatically
- `run.bat report` - Includes Liked Songs in all coverage reports

### Configuration
Users can disable liked songs export in `.env`:
```bash
PSM__EXPORT__INCLUDE_LIKED_SONGS=false
```

### File Naming
Exported file follows existing convention:
- Regular playlists: `Playlist Name_playlis.m3u8`
- Liked Songs: `Liked Songs__liked_s.m3u8`

### Ordering
Liked Songs M3U preserves Spotify's newest-first order (most recently liked tracks appear first in the playlist).

### Owner Organization
When using `--organize-by-owner` flag:
- Liked Songs are placed in the current user's folder
- Falls back to root export directory if user name unavailable

## Testing

Added comprehensive test suite (`tests/integration/test_liked_songs_export.py`):
- ✅ Default export behavior
- ✅ Config-based disabling
- ✅ Playlist coverage report inclusion
- ✅ Owner organization respect
- ✅ Newest-first ordering preservation

All 175 tests pass (170 existing + 5 new).

## Documentation Updates

- **README.md**: Added "Liked Songs Support 🆕" section
- **This document**: Complete implementation reference

## Database Schema

No changes required! Existing schema already supported liked tracks:
```sql
CREATE TABLE liked_tracks (
    track_id TEXT NOT NULL, 
    provider TEXT NOT NULL DEFAULT 'spotify', 
    added_at TEXT, 
    PRIMARY KEY(track_id, provider)
);
```

## Backward Compatibility

✅ Fully backward compatible:
- Existing configurations work without changes
- Users who don't use liked songs see no impact
- Default behavior is sensible (enabled)
- Can be disabled via config if unwanted

## Technical Decisions

### Why Virtual Playlist?
Alternative approaches considered:
1. ❌ **Inject fake playlist record**: Pollutes database, complicates queries
2. ❌ **Separate export command**: Inconsistent UX, users must remember two commands
3. ✅ **Virtual playlist**: Clean separation, consistent UX, no DB pollution

### Why Default Enabled?
- Most users with liked tracks want them exported
- Consistent with "everything just works" philosophy
- Easy to disable if unwanted

### Why SQL UNION Instead of Code Merge?
- Single query more efficient than multiple queries + code merge
- Report generation stays declarative (SQL-based)
- Easier to maintain and debug

## Future Enhancements

Potential improvements (not implemented):
- [ ] CLI flag `--skip-liked` to temporarily skip export
- [ ] Separate liked songs stats in pull command output
- [ ] Per-playlist detail report for liked songs
- [ ] Push support (sync liked tracks back to Spotify)

## Files Changed

**Core Implementation**:
- `psm/services/export_service.py` - Virtual playlist export logic
- `psm/reporting/reports/playlist_coverage.py` - Include in coverage reports
- `psm/config.py` - Default configuration
- `psm/config_types.py` - Typed configuration
- `psm/services/match_service.py` - Terminology fix (skipped→unmatched)

**Tests**:
- `tests/integration/test_liked_songs_export.py` - New comprehensive test suite

**Documentation**:
- `README.md` - User-facing documentation
- `docs/LIKED_SONGS_FEATURE.md` - This file

## Terminology Improvement (Bonus)

While implementing this feature, we also improved match command clarity:
- **Before**: "310 skipped" (confusing - sounds ignored)
- **After**: "310 unmatched" (clear - these tracks couldn't be matched)

This prevents confusion with scan's "skipped" (unchanged files optimization).

## Conclusion

Liked Songs are now first-class citizens in the playlist ecosystem, with:
- Zero database schema changes
- Full feature parity with regular playlists
- Clean, maintainable implementation
- Comprehensive test coverage
- Clear user documentation
