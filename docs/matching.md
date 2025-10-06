# Matching Strategy

Detailed explanation of the scoring-based matching engine.

## Goals
- **High precision** (avoid wrong matches)
- **High recall** (maximize matched tracks)
- **Speed** (operate efficiently on 10K+ libraries)
- **Transparency** (provide diagnostic breakdowns for unmatched tracks)

## Architecture

The matching engine uses a **weighted scoring system** that evaluates multiple signals to determine match quality:

### Core Components

1. **Normalization** - All artist, title, album fields are normalized (case fold, punctuation strip, whitespace collapse, bracket variants) for fuzzy comparison.

2. **Scoring Engine** (`psm/match/scoring.py`)
   - Pure function-based design (no database access)
   - Weighted additive scoring with penalties
   - Confidence tier mapping (CERTAIN, HIGH, MEDIUM, LOW, REJECTED)
   - Transparent score breakdown for diagnostics

3. **Match Service** (`psm/services/match_service.py`)
   - Orchestrates matching workflow
   - Candidate prefiltering (duration + token overlap)
   - Batch processing with progress tracking
   - Unmatched track diagnostics

## Scoring Factors

### Positive Signals (Add Points)

| Signal | Weight | Description |
|--------|--------|-------------|
| Title exact match | 45 | Normalized title identical |
| Title fuzzy match | 0-30 | Token set ratio ≥88% (scaled by strength) |
| Artist exact match | 30 | Normalized artist identical |
| Artist fuzzy match | 20 | Token set ratio ≥92% |
| Album exact match | 18 | Normalized album identical |
| Album fuzzy match | 12 | Token set ratio ≥95% |
| Year match | 6 | Exact or ±1 year |
| Duration tight | 6 | ≤2 seconds difference |
| Duration loose | 3 | ≤4 seconds difference |
| ISRC match | 15 | International Standard Recording Code match |

### Penalties (Subtract Points)

| Penalty | Weight | Condition |
|---------|--------|-----------|
| Album missing (local) | 8 | Library file lacks album metadata |
| Album missing (remote) | 5 | Spotify track lacks album info |
| Year missing | 4 | Per missing year field (local or remote) |
| Variant mismatch | 6 | One version is Live/Remix/Acoustic/Edit, other is not |
| Complete metadata missing | 20 | Both album AND year missing on both sides |

## Confidence Tiers

Raw scores are mapped to confidence levels:

| Confidence | Score Range | Action |
|------------|-------------|--------|
| CERTAIN | ≥100 or all metadata matches | Auto-accept |
| HIGH | 90-99 | Auto-accept |
| MEDIUM | 78-89 | Auto-accept |
| LOW | 65-77 | Auto-accept (marginal) |
| REJECTED | <65 | Not matched |

## Optimization Strategies

### Duration Prefiltering
- Narrows candidate pool before fuzzy matching
- Default tolerance: ±4 seconds window
- Skips files missing duration metadata (can't exclude)

### Candidate Pruning
- Limits candidates per track to 500 (configurable)
- Uses Jaccard similarity on normalized tokens for fast pre-scoring
- Prioritizes tracks with overlapping words before fuzzy comparison

### Early Exit
- Stops on CERTAIN confidence (no need to check remaining candidates)
- Dramatically reduces processing time for high-quality libraries

## Configuration

```bash
# Matching behavior (via environment or config file)
PSM__MATCHING__DURATION_TOLERANCE=2.0
PSM__MATCHING__MAX_CANDIDATES_PER_TRACK=500
PSM__MATCHING__SHOW_UNMATCHED_TRACKS=50
PSM__MATCHING__SHOW_UNMATCHED_ALBUMS=20
```

Advanced tuning (requires code modification of `ScoringConfig` defaults):
- Fuzzy thresholds (`min_title_ratio`, `min_artist_ratio`)
- Score weights (all `weight_*` fields)
- Penalty values (all `penalty_*` fields)
- Confidence thresholds

## Diagnostics & Reporting

### Automatic Reports (Generated on Every Match)

The `match` command automatically generates comprehensive reports:

1. **matched_tracks.csv / .html**
   - All successfully matched tracks
   - Includes confidence levels (CERTAIN, HIGH, MEDIUM, LOW)
   - Shows match scores and both Spotify and local metadata
   - Sortable HTML table for easy exploration

2. **unmatched_tracks.csv / .html**
   - All Spotify tracks that couldn't be matched
   - Sorted by artist/album/name
   - Helps identify missing files in your library

3. **unmatched_albums.csv / .html**
   - Unmatched tracks grouped by album
   - Shows track count per album
   - Quickly identifies which albums to acquire

All reports saved to `export/reports/` (configurable via `reports.directory`).

### Console Diagnostics (INFO Mode)

After matching completes, the console shows:

1. **Top Unmatched Tracks** (default: 20) - Sorted by playlist popularity
   - Shows how many playlists contain each unmatched track
   - Includes ❤️ marker for liked tracks
   - Helps identify missing albums vs. obscure singles
   - Example: `[12 playlists] The Beatles - Come Together ❤️`

2. **Top Unmatched Albums** (default: 10) - Sorted by occurrence count
   - Groups unmatched tracks by album
   - Shows total playlist occurrences per album
   - Quickly identifies which albums to acquire
   - Example: `[45 occurrences] The Beatles - Abbey Road (17 tracks)`

**Customize diagnostic counts:**
```bash
run.bat match --top-tracks 50 --top-albums 20
```

## Expected Performance

### Match Rates (depends on metadata quality)

- **High-quality tags** (complete album/year/ISRC): 95-99%
- **Typical library** (some missing metadata): 85-95%
- **Poor tags** (many fields blank): 70-85%

### Speed
- **10,000 tracks**: ~5-15 seconds
- **50,000 tracks**: ~30-90 seconds
- **Dominated by**: Fuzzy matching (disabled for exact matches)

## Troubleshooting

### Low Match Rate?

1. **Check library metadata quality**
   ```bash
   run.bat analyze  # Generates detailed quality reports (CSV + HTML)
   run.bat scan     # Re-scan to pick up tag updates
   ```

2. **Enable DEBUG logging** to see scoring details
   ```bash
   PSM__LOG_LEVEL=DEBUG run.bat match
   ```

3. **Review unmatched diagnostics**
   - Check the auto-generated reports in `export/reports/`
   - Are albums consistently missing? (acquisition needed)
   - Are tracks low-occurrence? (may not be worth matching)

### Variant Confusion?

The engine detects and penalizes version mismatches (Live vs Studio, Remix vs Original). If you have multiple versions of tracks:

- Ensure library filenames clearly indicate variant type
- Consider separate playlists for live albums vs. studio albums

## Future Enhancements

- [ ] ISRC primary fast path when available
- [ ] Acoustic fingerprinting (advanced mode)
- [ ] Per-strategy precision/recall metrics
- [ ] Machine learning confidence calibration
- [ ] Album-aware batch matching

