#!/usr/bin/env python3
"""Diagnose why smart scan is finding files as 'new' when they exist in DB."""
import sqlite3
from pathlib import Path
import json

# Load config to get library paths
try:
    with open("config.json") as f:
        cfg = json.load(f)
        lib_paths = cfg.get("library", {}).get("paths", ["music"])
except FileNotFoundError:
    lib_paths = ["music"]  # default

# Connect to database
db_path = Path("data/db/spotify_sync.db")
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get 5 sample paths from database
cursor.execute("SELECT path FROM library_files LIMIT 5")
db_paths = [row['path'] for row in cursor.fetchall()]

print("=" * 80)
print("Path Format Diagnostic")
print("=" * 80)
print()
print(f"Library paths from config: {lib_paths}")
print()
print("Sample paths from database:")
for i, db_path_str in enumerate(db_paths, 1):
    print(f"{i}. {db_path_str}")
    
    # Check if this path exists on filesystem
    p = Path(db_path_str)
    exists = p.exists()
    
    # What does resolve() give us?
    try:
        resolved = str(p.resolve())
    except Exception as e:
        resolved = f"ERROR: {e}"
    
    print(f"   exists={exists} | resolve()={resolved}")
    print(f"   match={db_path_str == resolved}")
    print()

# Check for path separator differences
cursor.execute("SELECT COUNT(*) as count, CASE WHEN path LIKE '%\\%' THEN 'backslash' WHEN path LIKE '%/%' THEN 'forward' ELSE 'unknown' END as sep_type FROM library_files GROUP BY sep_type")
sep_counts = cursor.fetchall()

print("Path separator usage in database:")
for row in sep_counts:
    print(f"  {row['sep_type']:12} : {row['count']:,} files")
print()

# Check for case differences
cursor.execute("SELECT path FROM library_files WHERE path != LOWER(path) LIMIT 3")
mixed_case = cursor.fetchall()
if mixed_case:
    print("Sample paths with mixed case:")
    for row in mixed_case:
        print(f"  DB:    {row['path']}")
        print(f"  lower: {row['path'].lower()}")
        print()

conn.close()

print("=" * 80)
print("DIAGNOSIS:")
print("=" * 80)
print("If 'match=False' above, the issue is:")
print("  - Database stores paths in one format (e.g., 'C:\\Music\\file.mp3')")
print("  - scan_library resolves to different format (e.g., 'C:/Music/file.mp3')")
print("  - Dict lookup fails because strings don't match exactly")
print()
print("Solution: Normalize paths to same format when:")
print("  1. Storing in database (insertion)")
print("  2. Loading from database (dict keys)")
print("  3. Comparing during scan (lookup)")
