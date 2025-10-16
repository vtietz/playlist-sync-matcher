# Documentation Cleanup Needed

## Files with Hardcoded/Outdated Sizes

### Priority: HIGH (User-Facing Documentation)

#### 1. `docs/quick-start-executables.md`
**Current:** Shows ~20-25 MB CLI, ~30-35 MB GUI (onedir mode estimates)  
**Actual:** 18.43 MB CLI, 60.33 MB GUI (onefile mode, python.org build)  
**Action:** Make sizes generic, note they vary by platform/Python version
**Lines:** 86, 104-106

**Suggested Change:**
```markdown
- ✅ Need smaller file size (CLI is ~30-40% smaller than GUI)

## Approximate Sizes

| Platform | CLI        | GUI        | Note |
|----------|------------|------------|------|
| Windows  | ~15-20 MB  | ~55-65 MB  | GUI includes PySide6 |
| Linux    | ~15-20 MB  | ~50-60 MB  | Varies by dependencies |
| macOS    | ~15-20 MB  | ~50-60 MB  | Universal2 binaries larger |

**Note:** Sizes vary depending on Python version, PyInstaller version, and build configuration.
```

#### 2. `docs/building-executables.md`
**Current:** Shows ~20-25 MB CLI, ~30-35 MB GUI  
**Action:** Same as above
**Lines:** 155-157

#### 3. `docs/build-architecture.md`
**Current:** Detailed breakdown with specific MB values  
**Actual:** Now single-file --onefile mode, structure changed  
**Action:** Update entire section for --onefile architecture
**Lines:** 197-218

**Suggested Change:**
```markdown
## Build Size Breakdown

### Single-File (--onefile) Architecture

Both executables bundle everything into a single .exe/.app file:

**CLI Build (Windows ~18 MB, varies by platform):**
- Python runtime + standard library
- Application code (psm package)
- Dependencies (click, requests, mutagen, rapidfuzz, etc.)
- Compressed into single bootloader-wrapped executable

**GUI Build (Windows ~58 MB, varies by platform):**
- Everything from CLI build
- PySide6 Qt framework (~40 MB compressed)
- GUI modules (panels, components, controllers)
- Qt platform plugins and resources

**Advantages:**
- Single file distribution (no folders)
- No DLL dependencies to manage
- Simpler deployment
- Slightly slower startup (extraction to temp)

**Note:** Sizes vary by platform, Python version, and dependency versions.
```

### Priority: MEDIUM (Technical Documentation)

#### 4. `docs/performance-optimization.md`
**Current:** "~500KB additional memory for 6,000 extra cached strings"  
**Action:** Keep specific numbers for technical benchmarks (this is OK)
**Status:** ✅ Fine as-is (performance metrics need specifics)

#### 5. `docs/watch-mode.md`
**Current:** Resource usage tables with specific MB values  
**Action:** Keep as benchmark data (this is OK for performance docs)
**Status:** ✅ Fine as-is (performance benchmarks need actual measurements)

#### 6. `docs/cli-reference.md`
**Current:** "320 kbps threshold" mention  
**Action:** Keep (this is a configuration value, not a build artifact)
**Status:** ✅ Fine as-is (refers to config setting)

#### 7. `docs/library_analysis.md`
**Current:** "Low bitrate (< 320 kbps)"  
**Action:** Keep (configuration threshold)
**Status:** ✅ Fine as-is

## Obsolete/Redundant Documentation

### Consider Removing:
- ❓ `PYINSTALLER_ISSUE_SUMMARY.md` - Older summary, superseded by EXPERT_SUMMARY
- ❓ `PYINSTALLER_SOLUTION.md` - Redundant with MIGRATION doc
- ❓ `docs/ai-assessment.md` - AI-generated assessment, may be outdated

### Keep (Valuable References):
- ✅ `MIGRATION_TO_PYTHON_ORG.md` - Migration guide for future reference
- ✅ `PYINSTALLER_ISSUE_EXPERT_SUMMARY.md` - Comprehensive problem analysis

## Summary

**Immediate Actions:**
1. ✅ **Delete debug scripts** (test_db.py, check_db_metadata.py, count_files.py, diagnose_paths.py)
2. ⚠️ **Update 3 docs** with generic sizes (quick-start, building, build-architecture)
3. ⚠️ **Review PyInstaller docs** (keep 1-2, delete redundant)

**Keep As-Is:**
- Performance docs with specific measurements (watch-mode.md, performance-optimization.md)
- Configuration thresholds (320 kbps bitrate)
- README.md (well-balanced)
- run.bat/run.sh help (complete)
