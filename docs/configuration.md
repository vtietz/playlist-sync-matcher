# Configuration Reference

Configuration sources merge in order:
1. Built-in defaults (`psm/config.py`)
2. `.env` file
3. Environment variable overrides (highest precedence)

Environment variable naming: `PSM__SECTION__KEY` (double underscores as separators). Values starting with `[` or `{` are parsed as JSON.

## Core Keys

### Spotify
- `PSM__SPOTIFY__CLIENT_ID` (required) - Spotify app Client ID.
- `PSM__SPOTIFY__REDIRECT_PORT` (default 9876)
- `PSM__SPOTIFY__REDIRECT_SCHEME` (http|https, default http)
- `PSM__SPOTIFY__REDIRECT_HOST` (default 127.0.0.1)

### Provider
- `PSM__PROVIDER` - Active provider name (default `spotify`). Reserved for future multi-provider support.

### Library
- `PSM__LIBRARY__PATHS` - JSON array of directories.
- `PSM__LIBRARY__EXTENSIONS` - JSON array of file extensions.
- `PSM__LIBRARY__FOLLOW_SYMLINKS` - Traverse symlink targets (default false).
- `PSM__LIBRARY__IGNORE_PATTERNS` - JSON array of simple patterns to skip (default [".*"]).
- `PSM__LIBRARY__SKIP_UNCHANGED` - Skip unchanged files (size+mtime) (default true).
- `PSM__LIBRARY__FAST_SCAN` - Skip re-reading tags for unchanged files (default true).
- `PSM__LIBRARY__COMMIT_INTERVAL` - Batch size for DB commits (default 100).
- `PSM__LIBRARY__MIN_BITRATE_KBPS` - Threshold for quality analysis (default 320).

### Matching
- `PSM__MATCHING__STRATEGIES` - Ordered list (default [sql_exact, album_match, year_match, duration_filter, fuzzy]).
- `PSM__MATCHING__FUZZY_THRESHOLD` - 0.0–1.0 float (default 0.78).
- `PSM__MATCHING__DURATION_TOLERANCE` - Seconds tolerance for duration filter (default 2.0).
- `PSM__MATCHING__SHOW_UNMATCHED_TRACKS` - Diagnostic limit (default 20).
- `PSM__MATCHING__SHOW_UNMATCHED_ALBUMS` - Diagnostic limit (default 20).
- `PSM__MATCHING__USE_YEAR` - Include year token in normalization (default false).

### Export
- `PSM__EXPORT__MODE` - strict|mirrored|placeholders (default strict).
- `PSM__EXPORT__ORGANIZE_BY_OWNER` - Group playlists by owner (default false).
- `PSM__EXPORT__DIRECTORY` - Target folder (default data/export/playlists).
- `PSM__EXPORT__PLACEHOLDER_EXTENSION` - Extension for placeholder files (default .missing).

### Reports
- `PSM__REPORTS__DIRECTORY` - Report output directory (default data/export/reports).

### Database / Logging
- `PSM__DATABASE__PATH` - SQLite path (default data/db/spotify_sync.db).
- `PSM__DATABASE__PRAGMA_JOURNAL_MODE` - Journal mode (default WAL).
- `PSM__LOG_LEVEL` - DEBUG|INFO|WARNING.

## JSON Parsing Rules
- Leading `[` or `{` triggers JSON parse.
- Scalars auto-coerced: "true"/"false" → bool, numeric → int/float when safe.

## Example `.env`
```
PSM__SPOTIFY__CLIENT_ID=abc123
PSM__LIBRARY__PATHS=["C:/Music","D:/Archive"]
PSM__EXPORT__MODE=mirrored
PSM__EXPORT__ORGANIZE_BY_OWNER=true
PSM__MATCHING__FUZZY_THRESHOLD=0.82
PSM__MATCHING__STRATEGIES=["sql_exact","album_match","year_match","duration_filter","fuzzy"]
```

## Security Notes
Only the client ID (public) is stored; no client secret required (PKCE flow). Tokens cached locally (JSON) and auto-refreshed.
