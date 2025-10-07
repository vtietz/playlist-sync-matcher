# Library Quality Analysis

Command: `run.bat analyze` (or `./run.sh analyze` / `psm analyze`).

## Purpose
Identify metadata or quality issues that reduce match accuracy:
- Missing artist / title / album / year
- Low bitrate below configured threshold

Automatically generates both **console diagnostics** and **comprehensive reports** (CSV + HTML) for detailed exploration.

## Output

### Console Diagnostics

**Summary Statistics:**
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
```

**Intelligent Album Grouping:**
Shows top albums with the most files needing fixes (maximizes impact):
```
Top Albums with Issues:
📁 The Beatles - Abbey Road (18 files missing year)
📁 Pink Floyd - The Wall (12 files missing year)
📁 Queen - Greatest Hits (8 files low bitrate)
```

**Why Album Grouping?**
- Fix one album's metadata → improve many files at once
- More efficient than fixing scattered individual files
- Clear action items: "Tag all tracks from Abbey Road with year 1969"

### Generated Reports

**Metadata Quality Report** (`metadata_quality.csv` / `.html`):
- Complete list of all files with issues
- Grouped by issue type (missing artist, missing title, etc.)
- Full file paths for batch editing
- Bitrate and duration information
- Sortable/searchable HTML table with pagination
- CSV export for spreadsheet analysis

**Interactive Features:**
- Click column headers to sort by any field
- Search to filter specific artists/albums/issues
- Filter by issue type or bitrate threshold
- Download CSV for batch processing scripts

Reports saved to `data/export/reports/` (configurable via `PSM__REPORTS__DIRECTORY`).

## Configuration

```bash
# Quality threshold
PSM__LIBRARY__MIN_BITRATE_KBPS=320

# Console output limits
PSM__ANALYSIS__MAX_ISSUES=20      # Max issues shown in console
PSM__ANALYSIS__SHOW_ALL=false     # Set true to show all issues
```

## Command Options

```bash
# Basic analysis
run.bat analyze

# Show all issues (no limit)
run.bat analyze --verbose

# Custom bitrate threshold
run.bat analyze --min-bitrate 256

# Limit console output
run.bat analyze --max-issues 50
```

## Why It Matters
- **Improves Match Accuracy** – Complete metadata enables better matching strategies
- **Quality Control** – Identify low-bitrate files for replacement
- **Batch Efficiency** – Album grouping guides efficient tag cleanup
- **Completeness Tracking** – See which albums need metadata updates

## Workflow Integration

**Recommended Workflow:**
```bash
# 1. Run analysis to identify issues
run.bat analyze

# 2. Open HTML report for detailed exploration
start data\export\reports\metadata_quality.html

# 3. Fix metadata using your preferred tag editor
#    (Sort by album to batch-edit all tracks from same album)

# 4. Re-scan library to update database
run.bat scan

# 5. Re-run analysis to verify improvements
run.bat analyze

# 6. Re-match to benefit from improved metadata
run.bat match
```

## Report Details

The HTML report includes:

| Column | Description |
|--------|-------------|
| **File Path** | Full path to the file (shortened for display) |
| **Artist** | Artist metadata (or "Missing") |
| **Title** | Track title (or "Missing") |
| **Album** | Album name (or "Missing") |
| **Year** | Release year (or "Missing") |
| **Bitrate** | Audio bitrate in kbps (flagged if below threshold) |
| **Duration** | Track duration in MM:SS format |
| **Issues** | Comma-separated list of detected problems |

**Issue Types:**
- `Missing: artist` – No artist tag
- `Missing: title` – No title tag  
- `Missing: album` – No album tag
- `Missing: year` – No year/date tag
- `Low bitrate (< 320 kbps)` – Below quality threshold

## Future Enhancements
- Optional acoustic fingerprinting for metadata reconstruction
- Batch tag suggestion heuristics
- Integration with MusicBrainz/Discogs for automatic tagging
- Album art quality analysis
