# Matching Strategy

Detailed explanation of the multi-stage matching pipeline.

## Goals
- High precision (avoid wrong matches).
- High recall (maximize matched tracks).
- Speed (operate efficiently on 10K+ libraries).

## Normalization
All artist, title, album fields normalized (case fold, punctuation strip, whitespace collapse, bracket variants) before indexing & comparison.

## Strategies
1. SQL Exact: normalized artist+title (and optional album/year where present). Uses indexed `normalized` text.
2. Album Match: Adds album dimension to disambiguate compilations / live / remasters.
3. Year Match: Adds year dimension (if tags present) to separate remasters or re‑recordings.
4. Duration Filter: Candidate pruning by ± tolerance (default 2s).
5. Fuzzy: RapidFuzz token_set_ratio on narrowed candidate pool.

## Configuration
```bash
SPX__MATCHING__STRATEGIES=["sql_exact","album_match","year_match","duration_filter","fuzzy"]
SPX__MATCHING__FUZZY_THRESHOLD=0.82
SPX__MATCHING__DURATION_TOLERANCE=2.0
SPX__MATCHING__USE_YEAR=true # optionally enable year influence earlier
```

## Tuning Tips
- Increase fuzzy threshold (0.85+) to reduce false positives if library has many alternate versions.
- Remove `year_match` if year tags are sparse (reduces extra lookups).
- Skip `album_match` for performance if you primarily care about singles playlists.

## Expected Impact
Approximate cumulative match rate improvements (varies by metadata quality):
- sql_exact: 70–85%
- + album: +5–10%
- + year: +2–5%
- + fuzzy: Remaining plausible matches (2–8%).

## Diagnostics
`run.bat match` prints top unmatched tracks/albums counts (configurable via:
`SPX__MATCHING__SHOW_UNMATCHED_TRACKS` / `SPX__MATCHING__SHOW_UNMATCHED_ALBUMS`).

## Future Enhancements
- ISRC primary fast path (when available from provider & tags).
- Acoustic fingerprint / audio duration clustering (optional advanced mode).
- Strategy-specific precision/recall instrumentation.
