# Requirements Split - Summary

## Problem
Previously, all dependencies (runtime + dev tools) were in a single `requirements.txt`:
- ❌ Dev tools (pytest, black, flake8, lizard, autoflake) bundled into executables
- ❌ PyInstaller installed even when not building
- ❌ Larger executable sizes unnecessarily
- ❌ No clear separation of concerns

## Solution
Split into two files:

### `requirements.txt` (Runtime Dependencies)
**Purpose**: Required for the application to run
**Used by**:
- Executable builds (PyInstaller bundles these)
- End users running from source
- Release workflow (builds executables)

**Contains**:
- click (CLI framework)
- requests (HTTP/API)
- mutagen (audio metadata)
- rapidfuzz (fuzzy matching)
- tenacity (retry logic)
- rich (terminal UI)
- cryptography (OAuth certs)
- watchdog (file watching)
- PySide6 (Qt GUI)

### `requirements-dev.txt` (Development Dependencies)
**Purpose**: Development, testing, and code quality
**Used by**:
- Developers (via `run.bat install`)
- CI workflow (testing, code quality checks)
- Local development environment

**Contains**:
- `-r requirements.txt` (includes runtime deps)
- pytest (testing)
- black (code formatting)
- flake8 (style checking)
- lizard (complexity analysis)
- autoflake (unused import removal)
- pyinstaller (executable building)

## Changes Made

### 1. Files Created/Modified
- ✅ Created `requirements-dev.txt`
- ✅ Updated `requirements.txt` (removed dev tools)
- ✅ Updated `run.bat` (install uses requirements-dev.txt)
- ✅ Updated `.github/workflows/ci.yml` (uses requirements-dev.txt)
- ✅ Updated `.github/workflows/release.yml` (uses requirements.txt + pyinstaller)
- ✅ Updated `psm-cli.spec` (excludes dev tools)
- ✅ Updated `psm-gui.spec` (excludes dev tools)

### 2. Workflow Changes

#### CI Workflow (Testing)
```yaml
pip install -r requirements-dev.txt  # Includes runtime + dev tools
```

#### Release Workflow (Building Executables)
```yaml
pip install -r requirements.txt      # Runtime only
pip install pyinstaller==6.3.0       # Build tool only
```

#### Local Development
```bat
run.bat install  # Installs requirements-dev.txt
```

### 3. PyInstaller Exclusions
Both `.spec` files now explicitly exclude:
- pytest, black, flake8, lizard, autoflake
- pycodestyle, pyflakes, mccabe

## Benefits

### 🎯 Smaller Executables
- Dev tools (pytest, black, etc.) no longer bundled
- Reduced executable size
- Faster builds

### 🔒 Clear Separation
- Runtime vs development dependencies clearly separated
- Easier to understand what's needed for what
- Better documentation

### ⚡ Faster CI
- CI only installs what it needs
- Release builds install minimal dependencies
- More efficient caching

### 📦 Better Maintenance
- Update dev tools without affecting executables
- Pin runtime versions independently
- Clearer dependency management

## Verification

### Test Locally
```bat
# Clean install
rmdir /s /q .venv_pyo
run.bat install
run.bat test
```

### Test Build
```bat
run.bat build
dist\psm-cli.exe --version
dist\psm-gui.exe
```

### Expected Results
- ✅ All tests pass
- ✅ Executables build successfully
- ✅ Executable sizes reduced (no pytest, black, etc.)
- ✅ CI passes

## Next Steps

1. ✅ Commit changes
2. ✅ Test locally
3. ✅ Push and verify CI passes
4. ✅ Test RC build (v0.1.2-rc.1)
5. ✅ Verify executable sizes reduced
