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
- Run `run.bat analyze` and fix missing tags.
- Lower fuzzy threshold slightly (e.g. 0.78).
- Enable year strategy if disabled.

## Wrong Matches
- Increase fuzzy threshold (>0.85).
- Add `year_match` earlier in strategy list.
- Inspect normalization collisions (enable DEBUG logging).

## Debug Logging
```
PSM__LOG_LEVEL=DEBUG
```
Shows match decisions and normalization outputs.

## Reset State
Delete database and token cache if needed:
```
rm data/spotify_sync.db
rm tokens.json
```
(Re-ingest will rebuild.)

## Windows Path Issues
Use double backslashes or forward slashes in `.env` paths: `C:/Music`.

## Placeholder Files
Ensure export mode `placeholders`; missing tracks create empty placeholder entries named after normalized title.

## Still Stuck?
Open an issue with:
- Command run
- DEBUG log excerpt
- Example unmatched track metadata
