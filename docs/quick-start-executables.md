# Quick Start: Separate CLI and GUI Executables

## TL;DR

**You now have two separate executables:**
- **`psm-cli`** - Command-line tool (smaller, for automation)
- **`psm-gui`** - Desktop app (larger, with visual interface)

## Download Links

Go to [Releases](https://github.com/vtietz/playlist-sync-matcher/releases) and download:

### For Automation/Scripting
- Windows: `psm-cli-windows-amd64.exe`
- Linux: `psm-cli-linux-amd64`
- macOS: `psm-cli-macos-amd64`

### For Desktop Use
- Windows: `psm-gui-windows-amd64.exe`
- Linux: `psm-gui-linux-amd64`
- macOS: `psm-gui-macos-amd64`

## Quick Commands

### Windows

**CLI**:
```cmd
psm-cli.exe --version
psm-cli.exe login
psm-cli.exe build
```

**GUI**:
```cmd
psm-gui.exe
```
(Just double-click the .exe)

### Linux/macOS

**CLI**:
```bash
chmod +x psm-cli-linux-amd64
./psm-cli-linux-amd64 --version
./psm-cli-linux-amd64 login
./psm-cli-linux-amd64 build
```

**GUI**:
```bash
chmod +x psm-gui-linux-amd64
./psm-gui-linux-amd64
```

## Build Your Own

### Prerequisites
```bash
pip install -r requirements.txt
```

### Build Commands

**Windows**:
```cmd
run.bat build-cli    REM CLI only
run.bat build-gui    REM GUI only
run.bat build-all    REM Both
```

**Linux/macOS**:
```bash
./run.sh build-cli   # CLI only
./run.sh build-gui   # GUI only
./run.sh build-all   # Both
```

## Which One Do I Need?

### Choose CLI if you:
- ✅ Use Linux servers or headless systems
- ✅ Want to automate playlist syncing
- ✅ Run scheduled tasks (cron/Task Scheduler)
- ✅ Prefer command-line tools
- ✅ Need smaller file size (~20-25 MB)

### Choose GUI if you:
- ✅ Use Windows or macOS desktop
- ✅ Prefer visual interfaces
- ✅ Want to see real-time progress
- ✅ Like exploring playlists visually
- ✅ Are new to the tool

### Download Both if you:
- ✅ Use both desktop and server
- ✅ Want GUI for setup, CLI for automation
- ✅ Are a power user

## Size Comparison

| Platform | CLI      | GUI      | Difference |
|----------|----------|----------|------------|
| Windows  | ~25 MB   | ~35 MB   | 29% smaller|
| Linux    | ~20 MB   | ~30 MB   | 33% smaller|
| macOS    | ~22 MB   | ~32 MB   | 31% smaller|

## What Changed?

**Before**: One executable (`psm` or `playlist-sync-matcher`)

**Now**: Two executables:
- `psm-cli` - Command-line only (no GUI dependencies)
- `psm-gui` - Full desktop application

**Benefits**:
- Smaller downloads for automation use
- Clear naming (no confusion)
- Optimized for each use case

## Need Help?

- 📚 [Full Building Guide](building-executables.md)
- 📖 [README](../README.md)
- 🐛 [Report Issues](https://github.com/vtietz/playlist-sync-matcher/issues)
