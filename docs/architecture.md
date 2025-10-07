# Architecture

This document expands on the concise overview in the README.

## Layers

- CLI (psm/cli package): Argument parsing & command wiring only (thin). Entry point logic lives under `psm/cli/` modules (`helpers.py`, `core.py`, `playlists.py`, `playlist_cmds.py`). Module execution via `psm/cli/__main__.py`.
- Services (psm/services/*): Orchestrate workflows (pull, scan, match, export, reporting, analysis, push).
- Providers (psm/providers/*): Abstraction layer for streaming sources. Registry based.
- Match Engine (psm/match/*): Scoring-based matching with strategy implementations.
- Reporting (psm/reporting/*): Generates CSV + HTML reports with interactive features.
- Persistence (psm/db.py): SQLite schema v1 (provider namespaced) + helper methods.
- Utilities (psm/utils/*): Normalization, hashing, filesystem helpers.
- Authentication (psm/auth/*): OAuth flows and token management.

## Provider Abstraction

`ProviderClient` protocol defines minimum surface (user profile, playlists, playlist items). New providers register via `@register` decorator and appear through `available_providers()`.

`ProviderCapabilities` advertises optional features (future: search, batch add, isrc_lookup, extended audio features).

## Database Schema (v1)

Key design:
- Composite primary keys `(id, provider)` for `tracks` and `playlists` allow identical IDs from multiple providers.
- `playlist_tracks` keyed by `(playlist_id, provider, position)`; preserves order per provider.
- `library_files` stores extracted tags; includes `year` and `bitrate_kbps` for quality analysis.
- `matches` maps streaming tracks to local files by provider.
- `meta(schema_version=1)` recorded on init.

Indices: `tracks(isrc)`, `tracks(normalized)`, `library_files(normalized)`.

## Matching Architecture

The matching system has evolved from a simple strategy pipeline to a sophisticated **scoring-based engine**:

### Current Implementation (Scoring Engine)

**Core Components**:
- `psm/match/scoring.py`: Pure scoring functions with confidence tiers (CERTAIN, HIGH, MEDIUM, LOW, REJECTED)
- `psm/services/match_service.py`: Orchestrates matching workflow with progress tracking
- Weighted additive scoring with multiple signals (exact/fuzzy text, album, year, duration, ISRC)
- Candidate prefiltering for performance (duration tolerance, token overlap)

**Scoring Factors** (see `docs/matching.md` for complete details):
- Title exact/fuzzy match (45/0-30 points)
- Artist exact/fuzzy match (30/20 points) 
- Album exact/fuzzy match (18/12 points)
- Year match (6 points), Duration match (3-6 points), ISRC match (15 points)
- Penalties for missing metadata, variant mismatches

**Confidence Mapping**:
- ≥100 points: CERTAIN (auto-accept)
- 90-99: HIGH, 78-89: MEDIUM, 65-77: LOW (all auto-accept)
- <65: REJECTED (no match)

### Legacy Strategy System (Deprecated)

The original pipeline approach is still present in `psm/match/engine.py` for backward compatibility:

1. `sql_exact` - Fast normalized lookup via SQL joins
2. `album_match` - Album-context matching strategy  
3. `year_match` - Year-enhanced matching
4. `duration_filter` - Candidate pruning by duration tolerance
5. `fuzzy` - RapidFuzz token similarity on remaining unmatched

**Migration Status**: New scoring engine is the primary path; legacy strategies are being phased out as they're superseded by the unified scoring approach.

## Reporting System

Comprehensive report generation with both CSV and interactive HTML outputs:

### Report Types

**Match Reports** (generated automatically by `match` command):
- `matched_tracks.csv/.html` - All successful matches with confidence scores and metadata
- `unmatched_tracks.csv/.html` - Spotify tracks without local matches
- `unmatched_albums.csv/.html` - Unmatched tracks grouped by album
- `playlist_coverage.csv/.html` - Coverage analysis per playlist

**Analysis Reports** (generated automatically by `analyze` command):  
- `metadata_quality.csv/.html` - Files with metadata issues (missing tags, low bitrate)
- Console output with intelligent album grouping for maximum impact

**Legacy Reports**:
- `missing_tracks.csv` - Simple missing track list
- `album_completeness.csv` - Album-level completion statistics

### Interactive Features

**HTML Reports** (`psm/reporting/html_templates.py`):
- Sortable tables with jQuery DataTables
- Search and pagination for large datasets
- Clickable Spotify links (tracks, playlists, albums)
- Navigation dashboard (`index.html`) linking all reports
- Responsive design for mobile/desktop viewing

**Report Generation** (`psm/reporting/generator.py`):
- Unified CSV + HTML generation from same data
- Link generation for Spotify URLs via `psm/providers/links.py`
- Progress tracking for large report sets
- Configurable output directory (`reports.directory`)

### Diagnostic Integration

**Console Diagnostics** (from match service):
- Top unmatched tracks by playlist popularity (configurable count)
- Top unmatched albums by occurrence frequency  
- Liked track indicators (❤️) for priority identification
- Album-grouped analysis results for efficient metadata fixing

**Report Command** (`psm/cli/core.py`):
- Standalone report generation: `psm report [--no-match-reports] [--no-analysis-reports]`
- Regenerates reports from existing database without re-running analysis

## Service Layer Architecture

The services orchestrate complex workflows while keeping CLI commands thin:

### Core Services (`psm/services/`)

**Pull Service** (`pull_service.py`):
- Unified provider data ingestion (currently Spotify-only)
- OAuth token management and refresh
- Playlist and track metadata extraction
- Incremental updates via snapshot detection

**Match Service** (`match_service.py`):  
- Orchestrates scoring-based matching engine
- Progress tracking with percentage completion
- Unmatched track diagnostics and console output
- Automatic report generation integration

**Export Service** (`export_service.py`):
- M3U playlist generation in multiple modes (strict/mirrored/placeholders)
- Owner-based organization (optional folder structure)
- Collision-safe filename generation with ID suffixes
- Spotify URL embedding in M3U comments

**Analysis Service** (`analysis_service.py`):
- Library quality analysis (missing metadata, low bitrate detection)  
- Album-grouped issue reporting for efficient fixing
- Configurable quality thresholds
- Integration with reporting system

**Push Service** (`push_service.py`):
- Experimental playlist ordering push-back to Spotify
- File mode (M3U parsing) and DB mode (stored order)
- Preview/apply workflow with ownership validation
- Full playlist replacement semantics

**Playlist Service** (`playlist_service.py`):
- Single-playlist operations (pull/match/export individual playlists)
- Playlist listing with metadata and Spotify URLs
- Integration point for playlist-specific workflows

### Service Design Principles

- **Return structured data**: Services return dataclass objects, not console output
- **No direct printing**: Console formatting handled by CLI layer
- **Stateless operations**: Services accept parameters, return results
- **Error propagation**: Exceptions bubble up to CLI for consistent handling
- **Configuration injection**: Services receive config dictionaries, don't load config directly

## Performance Considerations

- **LRU caching**: Normalization results cached to avoid recomputation
- **Fast scan mode**: Skip unchanged library files by mtime+size comparison
- **Batched DB commits**: Configurable commit intervals (default: 100 records)
- **Indexed lookups**: Normalized fields and ISRC indexed for fast matching
- **Candidate prefiltering**: Duration and token overlap reduce fuzzy matching work
- **Early exit**: CERTAIN confidence matches skip remaining candidates
- **WAL mode**: Enables safe concurrent operations without custom locking

The database uses SQLite's **Write-Ahead Logging (WAL)** mode, which provides safe concurrent access:

**Implementation**:
```python
# psm/db.py
SCHEMA = [
    "PRAGMA journal_mode=WAL;",  # Enable WAL mode
    # ... table definitions
]

# Connection with automatic retry on lock conflicts
self.conn = sqlite3.connect(path, timeout=30)
```

**Benefits**:
- Multiple processes can read simultaneously
- Readers don't block writers and vice versa
- Automatic retry on transient lock conflicts (30-second timeout)
- No custom locking code needed - SQLite handles it

**Safe concurrent patterns**:
- ✅ `pull` + `scan` in parallel (different tables)
- ✅ `scan` + `match` in parallel (match reads library_files, scan writes it)
- ✅ Multiple `scan` processes on different paths
- ✅ `pull` + `match` in parallel (pull writes tracks, match reads them)

**Isolation semantics**:
- Operations see a consistent snapshot of data at the time they start
- Changes from concurrent operations become visible after they commit
- No partial/torn reads or writes

**No explicit locking required**: Previous implementation used a custom `DatabaseLock` with polling, which has been removed in favor of relying entirely on SQLite's built-in WAL concurrency.

## Concurrency & Database Safety

Environment-first loading:
1. Start with in-code defaults.
2. Optionally merge `.env` (only if `PSM_ENABLE_DOTENV=1`).
3. Deep‑merge any real environment variables with prefix `PSM__` (section/key separated by double underscores, e.g. `PSM__DATABASE__PATH`).
4. Parse JSON-ish scalar/list/dict strings into native types.

Immutability goal: Callers receive a plain nested dict; mutation by consumers is discouraged—prefer passing explicit overrides to loaders for tests.

## Configuration Model

## Future Evolution

- **Multi-provider support**: Cross-provider canonical track table keyed by ISRC + variant metadata
- **Rate limiting**: Middleware for API throttling and unified error taxonomy  
- **Playlist cloning**: Copy playlists between providers with format conversion
- **Enhanced audio features**: Tempo/key matching where provider APIs support it
- **Advanced scoring**: Machine learning models for improved match confidence
- **Incremental sync**: Delta-based updates for large libraries and playlists
- **Distributed matching**: Parallel processing for very large libraries (>100K files)
