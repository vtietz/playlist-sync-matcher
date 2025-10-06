## playlist-sync-matcher (PSM)

Have you ever wondered which tracks in your streaming playlists you already own, which ones are missing, and how to create working local playlists without manually rebuilding them? **playlist-sync-matcher (PSM)** is a small personal project designed to bridge the gap between streaming playlists (currently Spotify) and your local music library. It generates M3U/M3U8 playlists that point to real files and highlights what is missing, saving you time and effort.

GitHub: https://github.com/vtietz/playlist-sync-matcher

### What It Does
PSM automates the process of syncing streaming playlists with your local library:
- **Links to your local files** – Each playlist entry points to the real MP3/FLAC file on your drive.
- **Shows what's missing** – Clear reports of tracks and albums you don't have locally.
- **Creates standard M3U playlists** – Compatible with any music player.

This tool is perfect for music collectors who want to organize their collection around their streaming habits, sync playlists to devices, or enjoy offline listening.

### Key Features
- Spotify pull: playlists + liked tracks.
- Local library scan with fast-scan (mtime+size) shortcut.
- Layered match engine: exact → album → year → duration → fuzzy (RapidFuzz).
- Deterministic M3U8 export (collision-safe filenames with ID suffix).
- Three export modes: strict | mirrored (comments for missing) | placeholders.
- Optional folder organization by playlist owner.
- Reports: missing tracks CSV, album completeness, library quality (bitrate/tag gaps).
- Match diagnostics command for investigating tough cases.
- Provider abstraction + composite `(id, provider)` schema for future services.

### Typical Workflow
```bash
psm login      # OAuth (first time)
psm pull       # Fetch playlists
psm scan       # Index local files
psm match      # Run matching strategies
psm export     # Generate playlists
psm report     # Missing tracks summary
```
Or in one go:
```bash
psm build
```

### Technical Notes
- SQLite schema v1 with indices on normalized + ISRC fields.
- Service layer keeps CLI thin (separation of concerns).
- Environment/.env-based configuration (`PSM__SECTION__KEY` pattern).
- Caching + batching for performance (normalization cache, batched commits).
- Safe single-process DB access (simple locking).

### Why It Exists
PSM was created to simplify the process of syncing streaming playlists with local libraries. Instead of manually searching for tracks or rebuilding playlists, PSM automates the process—matching streaming tracks to local files, highlighting gaps, and exporting ready-to-use playlists. This saves time, reduces frustration, and helps you get the most out of both your streaming subscriptions and your own music collection.

### Contribute
I hope this project is useful to others! If you'd like to see support for additional streaming providers or have ideas for improvements, contributions are welcome. Check out the repository on GitHub: https://github.com/vtietz/playlist-sync-matcher.