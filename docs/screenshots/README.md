# Screenshots

This directory contains screenshots for documentation.

## Planned Screenshots

### reports-overview.png
Dashboard view showing the index.html page with all report cards:
- Match Reports section (Matched Tracks, Unmatched Tracks, Unmatched Albums, Playlist Coverage)
- Analysis Reports section (Metadata Quality)
- Clean, modern card-based layout
- Navigation icons and descriptions visible

**How to capture:**
1. Run `run.bat build` to generate all reports
2. Open `data/export/reports/index.html` in browser
3. Take a clean screenshot showing the full dashboard
4. Save as `reports-overview.png` (1200-1600px width recommended)

### Optional Additional Screenshots

- **matched-tracks-detail.png** - Sortable table view with Spotify links
- **unmatched-albums-sorted.png** - Album grouping with track counts
- **playlist-coverage-drilldown.png** - Playlist coverage with detail links
- **metadata-quality-grouped.png** - Quality issues grouped by album

## Screenshot Guidelines

- Use a clean browser window (no extensions/toolbars visible)
- Ensure readable font sizes (at least 12-14px)
- Show real data (sanitize personal info if needed)
- Use consistent browser zoom level (100% recommended)
- PNG format preferred for crisp text rendering
- Optimize file size (TinyPNG or similar)

## Usage in README

Main screenshot referenced in README.md:
```markdown
![Reports Dashboard](docs/screenshots/reports-overview.png)
```

The image path will work correctly from the repository root.
