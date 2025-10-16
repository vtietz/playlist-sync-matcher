#!/usr/bin/env bash
# Cross-platform run script for playlist-sync-matcher

set -e  # Exit on error

VENV=".venv_pyo"

# Create venv if it doesn't exist
if [ ! -d "$VENV" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV"
fi

# Activate venv
if [ -f "$VENV/bin/activate" ]; then
    source "$VENV/bin/activate"
else
    echo "Error: Could not find venv activation script"
    exit 1
fi

# ============================================================================
# Handle commands
# ============================================================================
case "${1:-}" in
    # ------------------------------------------------------------------------
    # Dev Commands (only available via run.sh, not in built executables)
    # ------------------------------------------------------------------------
    install)
        echo "Installing dependencies from requirements.txt ..."
        pip install -r requirements.txt
        exit 0
        ;;
    test)
        shift
        echo "Running: python -m pytest $@"
        python -m pytest "$@"
        exit 0
        ;;
    analyze)
        shift
        echo "Running code quality analysis..."
        python scripts/analyze_code.py "$@"
        exit 0
        ;;
    cleanup)
        shift
        echo "Running code cleanup..."
        python scripts/cleanup_code.py "$@"
        exit 0
        ;;
    clear-cache)
        echo "Clearing Python cache files..."
        find . -type d -name "__pycache__" -exec echo "Removing {}" \; -exec rm -rf {} + 2>/dev/null || true
        find . -type f -name "*.pyc" -exec echo "Removing {}" \; -exec rm -f {} + 2>/dev/null || true
        find . -type f -name "*.pyo" -exec echo "Removing {}" \; -exec rm -f {} + 2>/dev/null || true
        echo "Cache cleared!"
        exit 0
        ;;
    validate)
        echo "Running build validation..."
        scripts/validate_builds.bat
        exit 0
        ;;
    py)
        # Run arbitrary python command inside the virtual environment
        shift
        python "$@"
        exit 0
        ;;
    build-cli)
        echo "Building CLI executable with PyInstaller..."
        pyinstaller psm-cli.spec
        if [ $? -eq 0 ]; then
            echo "CLI build successful: dist/psm-cli"
        else
            echo "Error: CLI build failed!"
            exit 1
        fi
        exit 0
        ;;
    build-gui)
        echo "Building GUI executable with PyInstaller..."
        pyinstaller psm-gui.spec
        if [ $? -eq 0 ]; then
            echo "GUI build successful: dist/psm-gui"
        else
            echo "Error: GUI build failed!"
            exit 1
        fi
        exit 0
        ;;
    build | build-all)
        echo "Building both CLI and GUI executables..."
        ./run.sh build-cli
        ./run.sh build-gui
        echo "All builds complete!"
        exit 0
        ;;
        
    # ------------------------------------------------------------------------
    # App Commands (delegate to psm CLI or GUI)
    # ------------------------------------------------------------------------
    psm)
        # Explicit: ./run.sh psm <command>
        shift
        python -m psm.cli "$@"
        exit 0
        ;;
    gui)
        python -m psm.gui
        exit 0
        ;;
    help|"")
        cat << 'EOF'
============================================================================
playlist-sync-matcher Development Runner
============================================================================

Usage: ./run.sh [command] [args]

Application Commands (run via psm CLI):
  ./run.sh psm [command]    Execute any psm CLI command
  ./run.sh gui              Launch desktop GUI

  Examples:
    ./run.sh psm pull       Pull Spotify playlists
    ./run.sh psm scan       Scan local music library
    ./run.sh psm match      Match tracks
    ./run.sh psm build      Full sync pipeline
    ./run.sh psm --help     Show all CLI commands
    ./run.sh gui            Launch GUI application

Development Commands (only available via run.sh):
  install                   Install or update dependencies
  test [args]               Run pytest (e.g. ./run.sh test -q tests/unit/)
  analyze [mode]            Code quality analysis (changed|all|files <paths>)
  cleanup [mode]            Code cleanup (whitespace, unused imports)
  clear-cache               Remove Python cache files (__pycache__, *.pyc)
  validate                  Validate built executables
  py <args>                 Run python with args inside venv

Build Commands (create standalone executables):
  build                     Build both CLI and GUI executables
  build-cli                 Build CLI executable only (dist/psm-cli)
  build-gui                 Build GUI executable only (dist/psm-gui)

============================================================================
For built executables (no venv needed):
  ./psm-cli [command]       Direct CLI execution (e.g. ./psm-cli build)
  ./psm-gui                 Direct GUI execution
============================================================================
EOF
        exit 0
        ;;
        
    # ------------------------------------------------------------------------
    # Default: treat as psm CLI command (backward compatibility)
    # ------------------------------------------------------------------------
    *)
        python -m psm.cli "$@"
        exit 0
        ;;
esac
