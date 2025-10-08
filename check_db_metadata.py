#!/usr/bin/env python3
"""Quick script to check if database has mtime/size metadata."""
import sqlite3
from pathlib import Path

# Try both possible database locations
db_paths = [Path("data/db/spotify_sync.db"), Path("data/spotify_sync.db")]
db_path = None
for p in db_paths:
    if p.exists():
        db_path = p
        break

if not db_path:
    print(f"❌ Database not found in: {', '.join(str(p) for p in db_paths)}")
    exit(1)

print(f"Using database: {db_path}")

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Count total files
cursor.execute("SELECT COUNT(*) FROM library_files")
total = cursor.fetchone()[0]

if total == 0:
    print(f"📊 Database is empty (0 files)")
    print(f"   This is expected for a new database.")
    conn.close()
    exit(0)

# Count files with mtime
cursor.execute("SELECT COUNT(*) FROM library_files WHERE mtime IS NOT NULL")
with_mtime = cursor.fetchone()[0]

# Count files with size
cursor.execute("SELECT COUNT(*) FROM library_files WHERE size IS NOT NULL")
with_size = cursor.fetchone()[0]

# Sample a few rows
cursor.execute("SELECT path, size, mtime FROM library_files LIMIT 5")
samples = cursor.fetchall()

conn.close()

print(f"📊 Database Metadata Status")
print(f"=" * 60)
print(f"Total files:       {total:,}")
print(f"With mtime:        {with_mtime:,} ({with_mtime/total*100:.1f}%)")
print(f"With size:         {with_size:,} ({with_size/total*100:.1f}%)")
print(f"Missing metadata:  {total - with_mtime:,} files")
print()
print(f"Sample rows:")
for path, size, mtime in samples:
    print(f"  {Path(path).name[:40]:40} | size={size} | mtime={mtime}")
print()

if with_mtime < total:
    print(f"⚠️  {total - with_mtime:,} files are missing mtime/size metadata!")
    print(f"   This means smart scan MUST process them (can't skip based on time).")
    print(f"   Solution: Run 'psm scan --deep' ONCE to populate metadata.")
else:
    print(f"✅ All files have metadata - smart scan should be fast!")
