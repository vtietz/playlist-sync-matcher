# Library Quality Analysis

Command: `run.bat analyze` (or `./run.sh analyze` / `psm analyze`).

## Purpose
Identify metadata or quality issues that reduce match accuracy:
- Missing artist / title / album / year
- Low bitrate below configured threshold

## Options
```
--verbose            Show all issues (otherwise limited)
--min-bitrate <int>  Override threshold (default from config or 320)
--max-issues <int>   Limit displayed issues (default 20)
```

## Configuration
`PSM__LIBRARY__MIN_BITRATE_KBPS=320`

## Sample Output (abbreviated)
```
Library Quality Analysis
========================
Total files:              10,245
Files with issues:           387 (3.8%)
  Missing artist:              12
  Missing title:               15
  Missing album:              124
  Missing year:               289
  Low bitrate (<320):          67

Issues (showing 20):
  Missing: album, year
    → C:/Music/Downloads/Various - Track.mp3
  Missing: year | Bitrate: 128 kbps
    → C:/Music/Old/Artist - Song.mp3
```

## Why It Matters
- Improves match precision (album/year based disambiguation)
- Surfaces candidates for tag cleanup or higher quality replacement
- Helps tune strategy ordering and thresholds

## Future Enhancements
- Optional acoustic fingerprinting for metadata reconstruction
- Batch tag suggestion heuristics
