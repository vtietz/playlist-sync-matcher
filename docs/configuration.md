# Configuration Reference

Configuration sources merge in order:
1. Built-in defaults (`spx/config.py`)
2. `.env` file
3. Environment variable overrides (highest precedence)

Environment variable naming: `SPX__SECTION__KEY` (double underscores as separators). Values starting with `[` or `{` are parsed as JSON.

## Core Keys

### Spotify
- `SPX__SPOTIFY__CLIENT_ID` (required) - Spotify app Client ID.
- `SPX__SPOTIFY__REDIRECT_PORT` (default 9876)
- `SPX__SPOTIFY__REDIRECT_SCHEME` (http|https, default http)
- `SPX__SPOTIFY__REDIRECT_HOST` (default 127.0.0.1)

### Provider
- `SPX__PROVIDER` - Active provider name (default `spotify`). Reserved for future multi-provider support.

### Library
- `SPX__LIBRARY__PATHS` - JSON array of directories.
- `SPX__LIBRARY__EXTENSIONS` - JSON array of file extensions.
- `SPX__LIBRARY__FOLLOW_SYMLINKS` - Traverse symlink targets (default false).
- `SPX__LIBRARY__IGNORE_PATTERNS` - JSON array of simple patterns to skip (default [".*"]).
- `SPX__LIBRARY__SKIP_UNCHANGED` - Skip unchanged files (size+mtime) (default true).
- `SPX__LIBRARY__FAST_SCAN` - Skip re-reading tags for unchanged files (default true).
- `SPX__LIBRARY__COMMIT_INTERVAL` - Batch size for DB commits (default 100).
- `SPX__LIBRARY__MIN_BITRATE_KBPS` - Threshold for quality analysis (default 320).

### Matching
- `SPX__MATCHING__STRATEGIES` - Ordered list (default [sql_exact, album_match, year_match, duration_filter, fuzzy]).
- `SPX__MATCHING__FUZZY_THRESHOLD` - 0.0–1.0 float (default 0.78).
- `SPX__MATCHING__DURATION_TOLERANCE` - Seconds tolerance for duration filter (default 2.0).
- `SPX__MATCHING__SHOW_UNMATCHED_TRACKS` - Diagnostic limit (default 20).
- `SPX__MATCHING__SHOW_UNMATCHED_ALBUMS` - Diagnostic limit (default 20).
- `SPX__MATCHING__USE_YEAR` - Include year token in normalization (default false).

### Export
- `SPX__EXPORT__MODE` - strict|mirrored|placeholders (default strict).
- `SPX__EXPORT__ORGANIZE_BY_OWNER` - Group playlists by owner (default false).
- `SPX__EXPORT__DIRECTORY` - Target folder.
- `SPX__EXPORT__PLACEHOLDER_EXTENSION` - Extension for placeholder files (default .missing).

### Reports
- `SPX__REPORTS__DIRECTORY` - Report output directory.

### Database / Logging
- `SPX__DATABASE__PATH` - SQLite path.
- `SPX__DATABASE__PRAGMA_JOURNAL_MODE` - Journal mode (default WAL).
- `SPX__LOG_LEVEL` - DEBUG|INFO|WARNING.

## JSON Parsing Rules
- Leading `[` or `{` triggers JSON parse.
- Scalars auto-coerced: "true"/"false" → bool, numeric → int/float when safe.

## Example `.env`
```
SPX__SPOTIFY__CLIENT_ID=abc123
SPX__LIBRARY__PATHS=["C:/Music","D:/Archive"]
SPX__EXPORT__MODE=mirrored
SPX__EXPORT__ORGANIZE_BY_OWNER=true
SPX__MATCHING__FUZZY_THRESHOLD=0.82
SPX__MATCHING__STRATEGIES=["sql_exact","album_match","year_match","duration_filter","fuzzy"]
```

## Security Notes
Only the client ID (public) is stored; no client secret required (PKCE flow). Tokens cached locally (JSON) and auto-refreshed.
