#!/usr/bin/env python3
"""Count actual audio files on disk vs database."""
import sqlite3
from pathlib import Path
import os

# Get config from environment (same way psm does it)
from psm.config import load_config
cfg = load_config()

lib_paths = cfg.get("library", {}).get("paths", ["music"])
extensions = cfg.get("library", {}).get("extensions", [".mp3", ".flac", ".m4a", ".ogg"])

print(f"Library paths: {lib_paths}")

# Count files on disk
print("Counting files on disk...")
disk_files = set()
extensions_tuple = tuple(ext.lower() for ext in extensions)

for lib_path_str in lib_paths:
    lib_path = Path(lib_path_str)
    if not lib_path.exists():
        print(f"⚠️  Path not found: {lib_path}")
        continue
    
    for p in lib_path.rglob("*"):
        if p.is_file() and p.suffix.lower() in extensions_tuple:
            # Ignore hidden/system files (same as scan logic)
            if any(part.startswith('.') for part in p.parts):
                continue
            disk_files.add(str(p.resolve()))

# Count files in database
db_path = Path("data/db/spotify_sync.db")
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()
cursor.execute("SELECT path FROM library_files")
db_files = {row[0] for row in cursor.fetchall()}
conn.close()

# Compare
on_disk_only = disk_files - db_files
in_db_only = db_files - disk_files
in_both = disk_files & db_files

print()
print("=" * 80)
print("File Inventory")
print("=" * 80)
print(f"Files on disk:           {len(disk_files):,}")
print(f"Files in database:       {len(db_files):,}")
print(f"In both (matched):       {len(in_both):,}")
print(f"On disk only (NEW):      {len(on_disk_only):,}")
print(f"In DB only (DELETED):    {len(in_db_only):,}")
print()

if on_disk_only:
    print(f"⚠️  {len(on_disk_only):,} NEW files on disk not in database!")
    print("   This explains why smart scan had to process them.")
    print()
    print("Sample new files (first 10):")
    for i, path in enumerate(sorted(on_disk_only)[:10], 1):
        print(f"  {i:2}. {Path(path).name}")
    print()
    print("Smart scan is working CORRECTLY - these ARE new files!")
    print("They need to be processed regardless of their mtime.")
else:
    print("✅ All disk files are in database")

if in_db_only:
    print()
    print(f"⚠️  {len(in_db_only):,} files in DB but not on disk (deleted/moved)")
    print("   Consider running database cleanup to remove orphaned entries.")
