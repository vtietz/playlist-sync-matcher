# Migration from Conda to python.org Python for PyInstaller

## ✅ MIGRATION COMPLETED SUCCESSFULLY!

**Date**: 2025-01-28  
**Python Version**: 3.12.10 (Microsoft Store)  
**PyInstaller Version**: 6.16.0  
**Build Mode**: --onefile ✅  
**Result**: Both CLI and GUI executables build and run successfully without DLL errors!

### What Was Changed
- ✅ Created `.venv_pyo` with python.org Python 3.12.10
- ✅ Installed all dependencies (PyInstaller 6.16.0)
- ✅ Simplified spec files (removed Conda DLL bundling)
- ✅ Switched from --onedir to --onefile mode
- ✅ Updated run.bat to use `.venv_pyo`
- ✅ Built and tested both executables successfully

### Build Results
- **CLI**: `dist/psm-cli.exe` (18.43 MB)
- **GUI**: `dist/psm-gui.exe` (57.54 MB)
- **Status**: Both launch without ImportError or DLL issues

---

## Migration History

### Original Status (Before Migration)
❌ Conda Python 3.12.4 caused PyInstaller --onefile failures  
❌ python312.dll had Windows API Set dependencies (api-ms-win-*.dll)  
✅ python.org Python 3.13.7 installed but too new for PyInstaller 6.3.0  
✅ Python 3.12.10 from Microsoft Store - SELECTED for migration

## Original Migration Steps (Reference)

### Step 1: Create Clean python.org venv
```powershell
# Navigate to project
cd C:\Users\live\.coding\python-scripts\spotify-m3u-sync

# Create new venv using python.org Python 3.13
py -3.13 -m venv .venv_pyo

# Activate it
.venv_pyo\Scripts\activate

# Upgrade pip and wheel
python -m pip install --upgrade pip wheel

# Install project dependencies
python -m pip install -r requirements.txt

# Install/upgrade PyInstaller to latest
python -m pip install "pyinstaller>=6.14"
```

### Step 2: Update run.bat to Use New venv
The run.bat script needs to activate `.venv_pyo` instead of `.venv`:

Change:
```batch
SET VENV_DIR=.venv
```
To:
```batch
SET VENV_DIR=.venv_pyo
```

### Step 3: Test with Source Code
```powershell
# Activate new venv
.venv_pyo\Scripts\activate

# Test CLI
python -m psm.cli --version
python -m psm.cli config

# Test GUI
python -m psm.gui
```

### Step 4: Update Spec Files for --onefile
Since we're using python.org Python, we can switch back to --onefile mode.

Changes needed in both `psm-cli.spec` and `psm-gui.spec`:
- Remove manual DLL bundling logic (python.org doesn't need it)
- Switch from --onedir to --onefile

### Step 5: Build with New Python
```powershell
# Clean previous builds
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

# Build CLI (onefile mode)
.venv_pyo\Scripts\python.exe -m PyInstaller psm-cli.spec --clean --noconfirm

# Build GUI (onefile mode)
.venv_pyo\Scripts\python.exe -m PyInstaller psm-gui.spec --clean --noconfirm

# Test executables
dist\psm-cli.exe --version
dist\psm-cli.exe config

# Test GUI
dist\psm-gui.exe
```

### Step 6: Validate Builds
```powershell
# Update validation script for onefile mode
.\validate_builds.bat
```

### Step 7: Update CI/CD (if applicable)
Update GitHub Actions or other CI to use python.org Python:
```yaml
- uses: actions/setup-python@v4
  with:
    python-version: '3.13'
    
- name: Create venv
  run: python -m venv .venv_pyo
  
- name: Install dependencies
  run: |
    .venv_pyo\Scripts\python.exe -m pip install --upgrade pip wheel
    .venv_pyo\Scripts\python.exe -m pip install -r requirements.txt
    .venv_pyo\Scripts\python.exe -m pip install "pyinstaller>=6.14"
    
- name: Build executables
  run: |
    .venv_pyo\Scripts\python.exe -m PyInstaller psm-cli.spec --clean --noconfirm
    .venv_pyo\Scripts\python.exe -m PyInstaller psm-gui.spec --clean --noconfirm
```

## Coexistence with Conda

### Keep Both Python Installations
- ✅ Conda stays installed for other projects
- ✅ python.org venv (.venv_pyo) used for PyInstaller builds
- ✅ No conflicts as long as you explicitly activate the correct environment

### Avoid Conda During Builds
```powershell
# If accidentally in Conda environment
conda deactivate

# Disable auto-activation (optional)
conda config --set auto_activate_base false

# Verify correct Python
where python
# Should show: <project>\.venv_pyo\Scripts\python.exe first
```

### VS Code Configuration
Update `.vscode/settings.json`:
```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/.venv_pyo/Scripts/python.exe"
}
```

## Expected Results

### Before (Conda + --onedir)
```
dist/
  psm-cli/           (folder ~30 MB)
    psm-cli.exe
    python312.dll
    ... (many DLLs)
  psm-gui/           (folder ~80 MB)
    psm-gui.exe
    ... (many DLLs)
```

### After (python.org + --onefile)
```
dist/
  psm-cli.exe        (single file ~20 MB)
  psm-gui.exe        (single file ~60 MB)
```

## Rollback Plan
If something goes wrong:
```powershell
# Switch back to old venv
.venv\Scripts\activate

# Old builds still work
# Can revert spec files to --onedir if needed
```

## Next Steps
1. Create `.venv_pyo` venv
2. Install dependencies
3. Test source code works
4. Update spec files for --onefile
5. Build and test executables
6. Validate on clean Windows VM (no Python installed)
