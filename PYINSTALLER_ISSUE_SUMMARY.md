# PyInstaller Build Issue - Summary for Expert Review

## Problem Description
PyInstaller builds **consistently fail** with a DLL import error when executables are run:

```
ImportError: DLL load failed while importing _ctypes: Das angegebene Modul wurde nicht gefunden.
(Translation: "The specified module was not found")
```

## Error Trace
```
File "click\_winconsole.py", line 16, in <module>
File "ctypes\__init__.py", line 8, in <module>
ImportError: DLL load failed while importing _ctypes
```

## Root Cause Analysis

### What We Know
1. ✅ `python312.dll` IS bundled in the executable (verified with PyInstaller archive viewer)
2. ✅ `_ctypes.pyd` IS bundled in the executable  
3. ✅ Build process finds and includes all required DLLs
4. ❌ Runtime fails with "module not found" despite DLLs being present

### The Real Problem
**Conda's `python312.dll` depends on Windows API Set DLLs that don't exist on the target system:**

```
WARNING: Library not found: could not resolve 'api-ms-win-core-path-l1-1-0.dll', 
dependency of 'C:\\Users\\live\\miniconda3\\python312.dll'
```

These `api-ms-win-*.dll` files are **API Set virtual DLLs** introduced in Windows 8+. They redirect to actual system DLLs (`kernel32.dll`, etc.). The problem is:
- Conda's Python was compiled against newer Windows SDK
- These API Sets don't exist on older Windows versions OR the runtime loader can't resolve them from within PyInstaller's extracted environment

### Why PyInstaller Can't Fix This Automatically
PyInstaller cannot bundle Windows API Set DLLs because they're not real files - they're forwarding stubs managed by the OS. When `python312.dll` is extracted to a temp directory and loaded, Windows can't resolve the API Set dependencies properly.

## Original Path Detection Issue (FIXED)
The spec files HAD incorrect path detection logic (now fixed with `sys.base_prefix`):

### Current Logic (BROKEN)
```python
# Get conda base path (where python.exe is)
conda_base = Path(sys.executable).parent
dll_dir = conda_base / 'DLLs'

# Add python312.dll from conda base
python_dll = conda_base / 'python312.dll'
```

### Why It Fails
- When running via `run.bat py -m PyInstaller`, Python is executed from **virtualenv**: `.venv\Scripts\python.exe`
- `sys.executable.parent` resolves to: `.venv\Scripts\` (NOT conda base)
- `python312.dll` is actually located in: `C:\Users\live\miniconda3\python312.dll`
- Result: **DLL is not found and not bundled** → runtime import error

### Why It's Flaky
The build might work if:
1. PyInstaller's analysis happens to find the DLL through some other path
2. DLLs are cached from a previous successful build
3. Windows DLL search paths happen to include the conda base directory

But it fails when:
- Build directories are cleaned (`--clean`)
- PyInstaller can't auto-detect the DLL location
- The DLL search order doesn't include conda base

## Environment Details
- **Python Location**: `c:\Users\live\.coding\python-scripts\spotify-m3u-sync\.venv\Scripts\python.exe`
- **Actual python312.dll Location**: `C:\Users\live\miniconda3\python312.dll`
- **Actual _ctypes.pyd Location**: `C:\Users\live\miniconda3\DLLs\_ctypes.pyd`
- **Python Version**: 3.12.4 (conda)
- **PyInstaller Version**: 6.3.0
- **OS**: Windows 11

## Solution Options

###  Option 1: Use python.org Python Instead of Conda (RECOMMENDED)
Download and install standard Python from python.org instead of Conda:
- python.org builds are linked against older Windows SDKs
- More compatible with PyInstaller
- Don't have conda-specific dependencies

### Option 2: Use PyInstaller --onedir Mode
Instead of --onefile, use --onedir to extract DLLs to a folder:
- Allows Windows to find API Set dependencies properly
- Downside: Distribution is a folder, not a single .exe

### Option 3: Downgrade Python or Rebuild with Compatible SDK
- Use Python 3.11 instead of 3.12 (older API Set requirements)
- Or rebuild conda Python with older Windows SDK target

### Option 4: Add Universal CRT Redistributable
Ensure target systems have Visual C++ Redistributable installed:
- Includes API Set forwarding DLLs
- Download from Microsoft: vc_redist.x64.exe

## Immediate Workaround
For testing, use --onedir mode in spec files temporarily:

1. **Detects the actual Python base** (not the venv wrapper):
   ```python
   import sys
   from pathlib import Path
   
   # Get real Python base (handles venv properly)
   if hasattr(sys, 'base_prefix'):
       python_base = Path(sys.base_prefix)  # Works with venv
   else:
       python_base = Path(sys.prefix)
   ```

2. **Verifies DLL exists before adding**:
   ```python
   python_dll = python_base / 'python312.dll'
   if python_dll.exists():
       binaries.append((str(python_dll), '.'))
   else:
       print(f"WARNING: python312.dll not found at {python_dll}")
   ```

3. **Uses correct DLLs directory**:
   ```python
   dll_dir = python_base / 'DLLs'  # Not venv/Scripts/DLLs
   ```

## Affected Files
- `psm-cli.spec` (lines 20-55)
- `psm-gui.spec` (lines 20-55)

Both have identical broken path detection logic.

## Test Case to Verify Fix
After fixing the spec files, verify with:

```bash
# Clean build
.\run.bat py -m PyInstaller psm-cli.spec --clean

# Test executable
dist\psm-cli.exe --version

# Should succeed without ImportError
```

## Current Workaround
Sometimes rebuilding works if PyInstaller happens to find the DLLs. But this is unreliable and wastes time.

## Priority
**HIGH** - Blocks reliable executable distribution. Users cannot depend on builds working consistently.
