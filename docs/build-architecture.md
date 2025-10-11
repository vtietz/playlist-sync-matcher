# Build Architecture: Separate CLI and GUI Executables

## Overview Diagram

```
playlist-sync-matcher/
│
├── psm/
│   ├── cli/
│   │   ├── __main__.py  ◄──── Entry point for CLI
│   │   ├── core.py
│   │   ├── helpers.py
│   │   └── *_cmds.py
│   │
│   ├── gui/
│   │   ├── __main__.py  ◄──── Entry point for GUI
│   │   ├── app.py
│   │   ├── main_window.py
│   │   └── [panels, tabs, services, ...]
│   │
│   └── [shared modules]
│       ├── db/
│       ├── services/
│       ├── providers/
│       ├── match/
│       └── export/
│
├── psm-cli.spec  ◄──── PyInstaller config for CLI
├── psm-gui.spec  ◄──── PyInstaller config for GUI
│
└── .github/workflows/
    └── release.yml  ◄──── CI/CD pipeline
```

## Build Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     GitHub Release Workflow                  │
│                    (Triggered by version tag)                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ├─────────────┬─────────────┐
                              ▼             ▼             ▼
                         ┌─────────┐  ┌─────────┐  ┌─────────┐
                         │ Windows │  │  Linux  │  │  macOS  │
                         └─────────┘  └─────────┘  └─────────┘
                              │             │             │
                    ┌─────────┴─────┬───────┴─────┬───────┴─────┐
                    ▼               ▼             ▼             ▼
            ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
            │  build-cli   │ │  build-gui   │ │   (repeat    │
            │     job      │ │     job      │ │  for each    │
            └──────────────┘ └──────────────┘ │  platform)   │
                    │               │         └──────────────┘
                    ▼               ▼
            ┌──────────────┐ ┌──────────────┐
            │ psm-cli.spec │ │ psm-gui.spec │
            └──────────────┘ └──────────────┘
                    │               │
                    ▼               ▼
            ┌──────────────┐ ┌──────────────┐
            │ PyInstaller  │ │ PyInstaller  │
            │   (build)    │ │   (build)    │
            └──────────────┘ └──────────────┘
                    │               │
                    ▼               ▼
            ┌──────────────┐ ┌──────────────┐
            │  dist/       │ │  dist/       │
            │  psm-cli     │ │  psm-gui     │
            └──────────────┘ └──────────────┘
                    │               │
                    └───────┬───────┘
                            ▼
                    ┌──────────────┐
                    │   Upload to  │
                    │GitHub Release│
                    └──────────────┘
                            │
                            ▼
            ┌────────────────────────────────┐
            │  6 Artifacts per Release:      │
            │  - psm-cli-windows-amd64.exe   │
            │  - psm-cli-linux-amd64         │
            │  - psm-cli-macos-amd64         │
            │  - psm-gui-windows-amd64.exe   │
            │  - psm-gui-linux-amd64         │
            │  - psm-gui-macos-amd64         │
            └────────────────────────────────┘
```

## Dependency Separation

```
┌─────────────────────────┐      ┌─────────────────────────┐
│      psm-cli.spec       │      │      psm-gui.spec       │
│  (Console Application)  │      │  (Windowed Application) │
└─────────────────────────┘      └─────────────────────────┘
            │                                  │
            │                                  │
            ├──► Entry: psm/cli/__main__.py   ├──► Entry: psm/gui/__main__.py
            │                                  │
            ├──► Mode: console=True            ├──► Mode: console=False
            │                                  │
            ├──► Excludes:                     ├──► Includes:
            │    • tkinter                     │    • tkinter
            │    • PyQt5/6                     │    • PySide6 (if used)
            │    • PySide2/6                   │    • All GUI deps
            │    • psm.gui.*                   │
            │                                  │
            └──► Includes:                     └──► Includes:
                 • psm.cli.*                        • psm.gui.*
                 • psm.services.*                   • psm.cli.* (optional)
                 • psm.db.*                         • psm.services.*
                 • psm.match.*                      • psm.db.*
                 • psm.providers.*                  • psm.match.*
                 • psm.export.*                     • psm.providers.*
                 • psm.utils.*                      • psm.export.*
                                                    • psm.utils.*
```

## Local Build Commands

```
┌──────────────────────────────────────────────────────────┐
│                   Development Builds                      │
└──────────────────────────────────────────────────────────┘

Windows:                     Linux/macOS:
┌─────────────────────┐     ┌─────────────────────┐
│ run.bat build-cli   │     │ ./run.sh build-cli  │
└─────────────────────┘     └─────────────────────┘
          │                            │
          ▼                            ▼
    pyinstaller psm-cli.spec
          │
          ▼
    dist/psm-cli.exe (Windows)
    dist/psm-cli (Linux/macOS)

┌─────────────────────┐     ┌─────────────────────┐
│ run.bat build-gui   │     │ ./run.sh build-gui  │
└─────────────────────┘     └─────────────────────┘
          │                            │
          ▼                            ▼
    pyinstaller psm-gui.spec
          │
          ▼
    dist/psm-gui.exe (Windows)
    dist/psm-gui (Linux/macOS)

┌─────────────────────┐     ┌─────────────────────┐
│ run.bat build-all   │     │ ./run.sh build-all  │
└─────────────────────┘     └─────────────────────┘
          │                            │
          ▼                            ▼
    Builds both CLI and GUI
```

## Shared Codebase Benefits

```
┌───────────────────────────────────────────────┐
│          Shared Core Modules                  │
│  (Single source of truth, no duplication)     │
└───────────────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
┌──────────────┐        ┌──────────────┐
│   CLI Build  │        │   GUI Build  │
│              │        │              │
│ Uses:        │        │ Uses:        │
│ • Services   │        │ • Services   │
│ • Matching   │        │ • Matching   │
│ • Database   │        │ • Database   │
│ • Providers  │        │ • Providers  │
│ • Export     │        │ • Export     │
│              │        │ + GUI Layer  │
└──────────────┘        └──────────────┘

Benefits:
✓ Single API for all operations
✓ Bug fixes apply to both
✓ No code duplication
✓ Consistent behavior
✓ Easier maintenance
```

## Size Analysis

```
┌────────────────────────────────────────────────┐
│         Executable Size Breakdown              │
└────────────────────────────────────────────────┘

CLI Build (~25 MB Windows):
├── Python runtime      ~12 MB
├── Core modules       ~8 MB
│   ├── psm.services
│   ├── psm.db
│   ├── psm.match
│   ├── psm.providers
│   └── psm.export
├── Dependencies       ~4 MB
│   ├── click
│   ├── requests
│   ├── fuzzywuzzy
│   └── sqlite3
└── CLI interface      ~1 MB

GUI Build (~35 MB Windows):
├── Python runtime      ~12 MB
├── Core modules       ~8 MB (same as CLI)
├── GUI framework      ~10 MB
│   └── tkinter (or PySide6)
├── Dependencies       ~4 MB (same as CLI)
└── GUI modules        ~1 MB
    ├── psm.gui.panels
    ├── psm.gui.tabs
    ├── psm.gui.services
    └── psm.gui.state

Savings from separation: ~29-33%
```

## File Structure After Build

```
dist/
├── psm-cli.exe         (Windows CLI)
├── psm-cli             (Linux/macOS CLI)
├── psm-gui.exe         (Windows GUI)
└── psm-gui             (Linux/macOS GUI)

Each executable is:
✓ Self-contained (no Python installation needed)
✓ Single file (all dependencies bundled)
✓ Portable (copy to any system)
✓ Optimized (UPX compressed)
```

## Key Design Decisions

1. **Separate spec files**: Allows independent build configuration
2. **Shared codebase**: No code duplication, single source of truth
3. **Clear naming**: `psm-cli` vs `psm-gui` removes ambiguity
4. **Parallel builds**: GitHub Actions builds both simultaneously
5. **Exclude strategy**: CLI excludes GUI deps, GUI includes everything
6. **Entry points**: Different `__main__.py` files for each interface

## Future Extensibility

```
Current:
psm-cli.spec ─► CLI executable
psm-gui.spec ─► GUI executable

Potential Future Additions:
psm-api.spec      ─► REST API server
psm-spotify.spec  ─► Spotify-only variant
psm-minimal.spec  ─► Minimal core (no matching)
```

## See Also

- [Building Executables Guide](building-executables.md)
- [Implementation Summary](separate-executables-summary.md)
- [Quick Start](quick-start-executables.md)
