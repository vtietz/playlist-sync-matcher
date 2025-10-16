# PyInstaller Build Issue - Expert Consultation Request

## Problem Statement
PyInstaller builds for a Python 3.12 application fail at runtime with `ImportError: DLL load failed while importing _ctypes` when using **--onefile mode**, but work correctly with **--onedir mode**. Need expert advice on whether we can fix --onefile mode or should stick with --onedir.

## Environment
- **Python Version**: 3.12.4 (conda)
- **Python Location**: `C:\Users\live\miniconda3\python.exe`
- **Project Setup**: Virtual environment (`.venv`) created from conda base
- **PyInstaller Version**: 6.3.0
- **OS**: Windows 11
- **Build Tool**: PyInstaller invoked via virtualenv: `.venv\Scripts\python.exe -m PyInstaller`

## Error Details

### Runtime Error (--onefile mode only)
```
Traceback (most recent call last):
  File "psm\cli\__main__.py", line 22, in <module>
    from psm.cli import cli
  File "click\__init__.py", line 10, in <module>
  ...
  File "click\_winconsole.py", line 16, in <module>
  File "ctypes\__init__.py", line 8, in <module>
ImportError: DLL load failed while importing _ctypes: Das angegebene Modul wurde nicht gefunden.
```
Translation: "The specified module was not found"

### Build Warning (Always present)
```
WARNING: Library not found: could not resolve 'api-ms-win-core-path-l1-1-0.dll', 
dependency of 'C:\\Users\\live\\miniconda3\\python312.dll'.
```

## Investigation Results

### What We Verified
1. ✅ **`python312.dll` IS bundled** in the executable
   - Verified with PyInstaller archive viewer
   - Shows in bundle: `python312.dll` (7.4 MB compressed)

2. ✅ **`_ctypes.pyd` IS bundled** in the executable
   - Verified with PyInstaller archive viewer  
   - Shows in bundle: `_ctypes.pyd` (60 KB compressed)

3. ✅ **Spec file correctly detects Python base**
   - Fixed to use `sys.base_prefix` instead of `sys.executable.parent`
   - Correctly finds: `C:\Users\live\miniconda3\` (not `.venv\Scripts\`)

4. ✅ **--onedir mode WORKS perfectly**
   - Same DLLs, same code
   - Runs without any import errors
   - All functionality works

## Root Cause Analysis

### The Windows API Set DLL Issue
`python312.dll` from Conda depends on Windows API Set virtual DLLs:
- `api-ms-win-core-path-l1-1-0.dll`
- `api-ms-win-core-winrt-string-l1-1-0.dll`
- `api-ms-win-shcore-scaling-l1-1-1.dll`
- `api-ms-win-core-winrt-l1-1-0.dll`

These are **not real files** - they're forwarding stubs that redirect to system DLLs (`kernel32.dll`, etc.). They're part of the Windows API Set architecture introduced in Windows 8+.

### Why --onefile Fails
1. PyInstaller extracts all files to a temporary directory (`_MEIxxxxxx`)
2. Windows loader tries to resolve `api-ms-win-*.dll` dependencies
3. **In temp directory context, Windows cannot resolve API Set forwarding**
4. DLL load fails even though `python312.dll` and `_ctypes.pyd` are present

### Why --onedir Works
1. All DLLs extracted to permanent directory structure
2. Windows loader can properly resolve API Set dependencies from stable location
3. Everything loads correctly

## Current Spec File Configuration

### DLL Bundling Logic (Working)
```python
# Get actual Python base (not venv wrapper)
if hasattr(sys, 'base_prefix'):
    python_base = Path(sys.base_prefix)  # C:\Users\live\miniconda3
else:
    python_base = Path(sys.prefix)

dll_dir = python_base / 'DLLs'

# Add python312.dll
python_dll = python_base / 'python312.dll'
if python_dll.exists():
    binaries.append((str(python_dll), '.'))

# Add all .pyd files including _ctypes.pyd
if dll_dir.exists():
    for pyd_file in dll_dir.glob('*.pyd'):
        binaries.append((str(pyd_file), '.'))
```

### Current Mode (--onedir - Working)
```python
exe = EXE(
    pyz,
    a.scripts,
    [],  # Empty - don't bundle binaries in exe
    exclude_binaries=True,  # Key for onedir mode
    name='psm-cli',
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,  # Binaries go in directory
    a.zipfiles,
    a.datas,
    name='psm-cli',
)
```

## Attempted Solutions

### ❌ Solution 1: Fix Path Detection
**Tried**: Changed spec file to use `sys.base_prefix` instead of `sys.executable.parent`
**Result**: DLLs now correctly found and bundled, but --onefile still fails at runtime
**Conclusion**: Path detection was issue, but not THE issue

### ❌ Solution 2: Manual DLL Bundling
**Tried**: Explicitly bundle `python312.dll` and all `.pyd` files from conda DLLs directory
**Result**: Files bundled correctly (verified with archive viewer), but --onefile still fails
**Conclusion**: DLLs are present, but Windows can't load them due to API Set dependencies

### ✅ Solution 3: Switch to --onedir Mode
**Tried**: Changed from --onefile to --onedir mode
**Result**: **WORKS PERFECTLY** - all tests pass, no import errors
**Conclusion**: This solves the problem but changes distribution format

## Questions for Expert

### Primary Question
**Is there a way to make --onefile mode work with Conda Python 3.12 on Windows?**

Specific sub-questions:
1. Can we bundle/embed the API Set DLLs somehow?
2. Can we configure PyInstaller to set different DLL search paths?
3. Is there a runtime hook that could help Windows resolve API Set dependencies?
4. Would embedding a manifest file help?

### Alternative Approaches
1. **Should we switch to python.org Python instead of Conda?**
   - Would python.org Python have fewer API Set dependencies?
   - What are the trade-offs?

2. **Is --onedir mode the "correct" solution?**
   - Is this a known limitation with Conda + PyInstaller + --onefile?
   - Do professional PyInstaller distributions typically use --onedir anyway?

3. **Could we use a different bundler?**
   - Would Nuitka, cx_Freeze, or py2exe handle this better?
   - What are the pros/cons vs PyInstaller?

## Current Working Solution (--onedir)

### Distribution Structure
```
dist/
  psm-cli/
    psm-cli.exe          (4.3 MB - launcher)
    python312.dll         (7.5 MB)
    _ctypes.pyd           (130 KB)
    ... (other dependencies)
  psm-gui/
    psm-gui.exe          (4.6 MB - launcher)
    python312.dll         (7.5 MB)
    PySide6/              (Qt libraries ~60 MB)
    ... (other dependencies)
```

### Validation Results
```
[1/6] Checking if executables exist... [PASS]
[2/6] Testing CLI --version... [PASS]
[3/6] Testing CLI config command... [PASS]
[4/6] Testing CLI emoji output... [PASS]
[5/6] Testing GUI launches without import errors... [PASS]
[6/6] Checking executable sizes... [PASS]

All validation tests passed!
```

### User Experience
- **Before**: Single `psm-cli.exe` file (would be ~20 MB if it worked)
- **After**: `psm-cli/` folder with `psm-cli.exe` + dependencies (~30 MB extracted)
- **Distribution**: ZIP the entire folder, not just the exe

## What We Need

### Ideal Outcome
Fix --onefile mode to work with Conda Python 3.12 on Windows

### Acceptable Outcome
Expert confirmation that --onedir is the correct/only solution for this configuration, so we can proceed with confidence

### Delivery Requirements
- Executables must be distributable to users without Python installed
- Must work on Windows 10/11 without requiring admin rights
- Should be simple for users: ideally double-click to run
- Build process should be reliable and reproducible in CI/CD

## Additional Context

### Why This Matters
- **User Experience**: --onefile is cleaner (single exe vs folder)
- **Distribution**: Easier to share single file vs ZIP
- **Professional Appearance**: Single exe feels more "finished"

### Why We Can Live with --onedir
- It works reliably
- Standard for many professional PyInstaller apps
- Total size is reasonable (~30 MB CLI, ~80 MB GUI)
- Can be easily zipped for distribution

## Files Available for Review

1. **psm-cli.spec** - PyInstaller spec file for CLI
2. **psm-gui.spec** - PyInstaller spec file for GUI
3. **validate_builds.bat** - Automated validation script
4. **Build output logs** - Full PyInstaller build logs available

## Request

Please advise:
1. Is --onefile fixable with Conda Python 3.12?
2. If yes, what approach should we try?
3. If no, is --onedir the recommended solution?
4. Should we consider switching away from Conda Python?

Thank you for your expertise!
