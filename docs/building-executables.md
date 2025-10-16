# Building Separate CLI and GUI Executables

This project supports building two distinct executable distributions:

1. **CLI Executable** (`psm-cli`) - Command-line interface for automation and scripting
2. **GUI Executable** (`psm-gui`) - Graphical user interface for interactive use

## Why Separate Executables?

### Benefits:

- **Size Optimization**: CLI build excludes GUI frameworks (tkinter, etc.), resulting in smaller binaries
- **Dependency Isolation**: GUI dependencies not needed for server/automation environments
- **User Clarity**: Clear distinction between command-line and graphical tools
- **Distribution Flexibility**: Users can download only what they need

### Use Cases:

**CLI (`psm-cli`):**
- Server environments and automation
- CI/CD pipelines
- Shell scripting and cron jobs
- Headless systems

**GUI (`psm-gui`):**
- Desktop users preferring visual interaction
- Windows/Mac users unfamiliar with command line
- Interactive exploration and configuration
- Visual monitoring of matching progress

## Building Locally

### Prerequisites

```bash
pip install -r requirements.txt
```

### Build CLI Only

```bash
pyinstaller psm-cli.spec
```

Output: `dist/psm-cli.exe` (Windows) or `dist/psm-cli` (Linux/macOS)

### Build GUI Only

```bash
pyinstaller psm-gui.spec
```

Output: `dist/psm-gui.exe` (Windows) or `dist/psm-gui` (Linux/macOS)

### Build Both

```bash
pyinstaller psm-cli.spec
pyinstaller psm-gui.spec
```

Or use the helper script:

**Windows:**
```cmd
run.bat build
```

**Linux/macOS:**
```bash
./run.sh build
```

## Testing Executables

### CLI Smoke Test

```bash
# Windows
dist\psm-cli.exe --version
dist\psm-cli.exe --help

# Linux/macOS
dist/psm-cli --version
dist/psm-cli --help
```

### GUI Smoke Test

```bash
# Windows
dist\psm-gui.exe

# Linux/macOS
dist/psm-gui
```

The GUI should launch successfully without console output.

## PyInstaller Spec Files

### `psm-cli.spec`

- **Entry Point**: `psm/cli/__main__.py`
- **Mode**: Console application (`console=True`)
- **Excludes**: GUI packages (tkinter, PyQt, etc.)
- **Hidden Imports**: CLI, services, providers, matching engine

### `psm-gui.spec`

- **Entry Point**: `psm/gui/__main__.py`
- **Mode**: Windowed application (`console=False` on Windows)
- **Includes**: tkinter and all GUI dependencies
- **Hidden Imports**: GUI packages, adapters, panels, services

## GitHub Actions Workflow

The release workflow (`.github/workflows/release.yml`) automatically builds both executables:

### Jobs:

1. **`build-cli`**: Builds CLI for Windows, Linux, macOS
2. **`build-gui`**: Builds GUI for Windows, Linux, macOS
3. **`release`**: Creates GitHub release with all 6 artifacts

### Artifacts Produced (per release):

- `psm-cli-windows-amd64.exe`
- `psm-cli-linux-amd64`
- `psm-cli-macos-amd64`
- `psm-gui-windows-amd64.exe`
- `psm-gui-linux-amd64`
- `psm-gui-macos-amd64`

### Triggering a Release:

```bash
git tag v1.2.0
git push origin v1.2.0
```

GitHub Actions will automatically:
1. Build all 6 executables
2. Run smoke tests
3. Create a GitHub release
4. Attach all artifacts
5. Generate release notes

## File Size Comparison

Typical build sizes (approximate):

| Platform | CLI Size | GUI Size | Savings |
|----------|----------|----------|---------|
| Windows  | ~25 MB   | ~35 MB   | ~29%    |
| Linux    | ~20 MB   | ~30 MB   | ~33%    |
| macOS    | ~22 MB   | ~32 MB   | ~31%    |

*Actual sizes depend on Python version and dependencies*

## Distribution Recommendations

### For End Users:

**Recommended Downloads:**

- **Desktop Users**: Download GUI executable for your platform
- **Server/Automation**: Download CLI executable for your platform
- **Power Users**: Download both executables

### Package Naming Conventions:

- `psm-cli-{platform}-{arch}` - Command-line tool
- `psm-gui-{platform}-{arch}` - Graphical interface

### Installation Instructions (Include in Release Notes):

**CLI:**
```bash
# Download and make executable (Linux/macOS)
chmod +x psm-cli-linux-amd64
./psm-cli-linux-amd64 --version

# Windows - just double-click or run from cmd
psm-cli-windows-amd64.exe --version
```

**GUI:**
```bash
# Download and make executable (Linux/macOS)
chmod +x psm-gui-linux-amd64
./psm-gui-linux-amd64

# Windows - double-click the .exe file
```

## Advanced Configuration

### Custom Icons

Add application icons by updating the spec files:

```python
# psm-cli.spec
exe = EXE(
    ...
    icon='resources/cli-icon.ico',  # Windows
)

# psm-gui.spec
exe = EXE(
    ...
    icon='resources/gui-icon.ico',  # Windows
)
```

### Code Signing (Future)

For distribution on macOS/Windows, consider adding code signing:

```python
# In spec file
exe = EXE(
    ...
    codesign_identity='Developer ID Application: Your Name',  # macOS
)
```

## Troubleshooting

### CLI Build Fails

**Issue**: Missing hidden imports
**Solution**: Add to `hiddenimports` in `psm-cli.spec`

### GUI Build Fails

**Issue**: tkinter not found
**Solution**: Ensure Python installation includes tkinter:
```bash
# Ubuntu/Debian
sudo apt-get install python3-tk

# macOS (with Homebrew Python)
brew reinstall python-tk
```

### GUI Executable Shows Console (Windows)

**Issue**: `console=True` in spec file
**Solution**: Verify `psm-gui.spec` has `console=False`

### Large File Sizes

**Issue**: Build includes unnecessary packages
**Solution**: Add to `excludes` in spec file

## Migration from Old Build System

If upgrading from the old single-executable build:

1. Remove old `spx.spec` (if present)
2. Use new `psm-cli.spec` and `psm-gui.spec`
3. Update any build scripts to build both executables
4. Update documentation to reflect new naming

## See Also

- [PyInstaller Documentation](https://pyinstaller.org/)
- [GitHub Actions Workflow](.github/workflows/release.yml)
- [Project Architecture](docs/architecture.md)
