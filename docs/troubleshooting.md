# Troubleshooting

## OAuth Errors
`INVALID_CLIENT` or redirect mismatch:
- Verify redirect shown by `run.bat redirect-uri` is registered in Spotify dashboard.
- Default: `http://127.0.0.1:9876/callback`.

## HTTPS Redirect (Optional)
Add to `.env`:
```
PSM__SPOTIFY__REDIRECT_SCHEME=https
PSM__SPOTIFY__REDIRECT_HOST=localhost
```
Register `https://localhost:9876/callback`.

## Slow Matching
- Ensure fast scan enabled: `PSM__LIBRARY__FAST_SCAN=true`.
- Reduce strategy list (e.g. remove `year_match` / `album_match`).
- Increase commit interval for large initial scans.

## Low Match Rate

**Quick diagnostic workflow:**

1. **Check automatic reports** (generated during match):
   ```bash
   run.bat match  # Generates reports automatically
   start data\export\reports\index.html  # Open report dashboard
   ```

2. **Review unmatched tracks/albums reports**:
   - Look for patterns: Are specific albums consistently missing?
   - Check Spotify metadata vs. what you expected
   - Use search/sort to find problem areas

3. **Run library quality analysis**:
   ```bash
   run.bat analyze  # Generates metadata_quality report
   ```
   - Check for missing artist/title/album/year tags
   - Fix metadata using your preferred tag editor
   - Sort HTML report by album to batch-edit efficiently

4. **Re-scan and re-match after fixing tags**:
   ```bash
   run.bat scan   # Pick up updated tags
   run.bat match  # Re-match with better metadata
   ```

**Configuration adjustments:**
- Lower fuzzy threshold slightly: `PSM__MATCHING__FUZZY_THRESHOLD=0.75`
- Enable year strategy if disabled: `PSM__MATCHING__USE_YEAR=true`
- Check duration tolerance if many duration mismatches: `PSM__MATCHING__DURATION_TOLERANCE=3.0`

## Wrong Matches

**Diagnosis:**
1. **Review matched_tracks report**:
   ```bash
   start data\export\reports\matched_tracks.html
   ```
   - Sort by confidence score (look for LOW/MEDIUM matches)
   - Compare Spotify vs. Local metadata columns
   - Check which match strategy was used

2. **Look for normalization collisions**:
   ```bash
   PSM__LOG_LEVEL=DEBUG run.bat match
   ```
   - Shows exact normalization results
   - Reveals when different songs normalize to same text

**Solutions:**
- Increase fuzzy threshold: `PSM__MATCHING__FUZZY_THRESHOLD=0.85` (stricter)
- Add `year_match` earlier in strategy list for better disambiguation
- Enable year in normalization: `PSM__MATCHING__USE_YEAR=true`
- Check duration tolerance isn't too permissive: `PSM__MATCHING__DURATION_TOLERANCE=2.0`

## Debug Logging
```
PSM__LOG_LEVEL=DEBUG
```
Shows match decisions and normalization outputs.

## Reset State
Delete database and token cache if needed:
```bash
# Windows
del data\db\spotify_sync.db
del tokens.json

# Linux/Mac
rm data/db/spotify_sync.db
rm tokens.json
```
(Re-ingest will rebuild.)

## Windows Path Issues
Use double backslashes or forward slashes in `.env` paths: `C:/Music`.

## Placeholder Files
Ensure export mode `placeholders`; missing tracks create empty placeholder entries named after normalized title.

## PowerShell Error with run.bat test

**Error**: `"." kann syntaktisch an dieser Stelle nicht verarbeitet werden.` (German: "The '.' cannot be processed at this position")

**Cause**: PowerShell tries to parse pytest's output (which contains `.` progress indicators) as PowerShell commands, causing a parser error.

**Solutions**:
1. **Use cmd.exe instead** (recommended):
   ```cmd
   cmd /c "run.bat test -q"
   ```

2. **Use the Python command directly**:
   ```powershell
   .\run.bat py -m pytest -q
   ```

3. **Switch to Command Prompt**: Open `cmd.exe` and run `run.bat test -q` there

**Note**: This is a PowerShell quirk when running batch files with console output. The tests still run successfully - the error appears after completion and can be safely ignored.

## Concurrent Operations

**Q: Can I run multiple commands at the same time?**

Yes! The database uses SQLite WAL mode which supports safe concurrent operations:

```bash
# Safe to run in parallel (different terminals/processes)
run.bat pull    # Terminal 1
run.bat scan    # Terminal 2
run.bat match   # Terminal 3
```

**Expected behavior**:
- No errors or corruption
- Each operation works with its own snapshot of data
- New data from concurrent operations appears on next run

**Performance notes**:
- I/O-bound operations (scan, pull) benefit from parallelization
- Too many simultaneous operations may compete for disk I/O
- Database handles locking automatically with 30-second timeout

## Database Locked Errors

If you see "database is locked" errors:
- Usually resolves automatically within 30 seconds (automatic retry)
- If persistent, check for stuck processes: `tasklist | find "python"` (Windows) or `ps aux | grep python` (Linux/Mac)
- Last resort: restart terminal and try again

The WAL mode implementation makes lock errors very rare in normal usage.

## Still Stuck?
Open an issue with:
- Command run
- DEBUG log excerpt
- Example unmatched track metadata
