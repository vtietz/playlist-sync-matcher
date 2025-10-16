# PyInstaller Build Issue - SOLUTION FOUND

## Problem
Executables built with `--onefile` mode fail with:
```
ImportError: DLL load failed while importing _ctypes
```

## Root Cause
Conda's `python312.dll` depends on Windows API Set DLLs (`api-ms-win-core-path-l1-1-0.dll`) that Windows cannot resolve when the DLL is extracted to PyInstaller's temporary folder in --onefile mode.

## Solution: Use --onedir Mode

### What Changes
- **Before**: Single .exe file (psm-cli.exe ~20MB)
- **After**: Folder with .exe + DLL files (psm-cli/ ~30MB extracted)

### Why This Works
In --onedir mode, all DLLs are extracted to a permanent folder alongside the .exe. Windows can then properly resolve API Set dependencies because the directory structure matches what the loader expects.

## Implementation

Change the EXE section in both spec files from:
```python
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,  # ← Bundles everything into single file
    a.zipfiles,
    a.datas,
    [],
    name='psm-cli',
    ...
)
```

To:
```python
exe = EXE(
    pyz,
    a.scripts,
    [],  # ← Empty, binaries go in COLLECT instead
    exclude_binaries=True,  # ← Key change
    name='psm-cli',
    ...
)

coll = COLLECT(
    exe,
    a.binaries,  # ← Binaries extracted to folder
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='psm-cli',
)
```

## Distribution Impact

### Before (--onefile)
```
dist/
  psm-cli.exe (19.9 MB)
  psm-gui.exe (59.4 MB)
```

### After (--onedir)
```
dist/
  psm-cli/
    psm-cli.exe
    python312.dll
    _ctypes.pyd
    ... (other DLLs)
  psm-gui/
    psm-gui.exe
    PySide6/ (Qt libraries)
    ... (other DLLs)
```

## User Experience
- Users run: `psm-cli\psm-cli.exe` instead of `psm-cli.exe`
- Distribution: ZIP the folder, not just the .exe
- Slightly larger download, but **it actually works**

## Testing
```cmd
REM Build with new spec
.\run.bat py -m PyInstaller psm-cli.spec --clean

REM Test
dist\psm-cli\psm-cli.exe --version
dist\psm-cli\psm-cli.exe config

REM Validate
.\validate_builds.bat
```

## Alternative: Python.org Instead of Conda
If you must have --onefile, switch from Conda Python to python.org Python:
1. Install Python from python.org  
2. Create venv: `python -m venv .venv`
3. Install requirements: `.venv\Scripts\pip install -r requirements.txt`
4. Build with PyInstaller

Python.org builds don't have the same API Set dependency issues.

## Recommendation
**Use --onedir mode** - it's the standard for professional PyInstaller distributions and avoids these compatibility issues entirely.
