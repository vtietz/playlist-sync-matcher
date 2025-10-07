from psm.db import Database
from psm.config import load_config
from pathlib import Path

cfg = load_config()
db_path = Path(cfg['database']['path'])
print(f'DB Path: {db_path}')
print(f'DB Exists: {db_path.exists()}')

db = Database(db_path)
rows = db.conn.execute('SELECT p.id, p.name FROM playlists p LIMIT 5').fetchall()
print(f'\nFound {len(rows)} playlists:')
for r in rows:
    print(f'  - {r["name"]}')

# Test the full query from playlist_coverage
coverage_rows = db.conn.execute("""
    SELECT 
        p.id as playlist_id,
        p.name as playlist_name,
        p.owner_name,
        COUNT(DISTINCT pt.track_id) as total_tracks
    FROM playlists p
    JOIN playlist_tracks pt ON p.id = pt.playlist_id
    GROUP BY p.id, p.name, p.owner_name
    LIMIT 3
""").fetchall()
print(f'\nCoverage query returned {len(coverage_rows)} rows:')
for r in coverage_rows:
    print(f'  - {r["playlist_name"]}: {r["total_tracks"]} tracks')
