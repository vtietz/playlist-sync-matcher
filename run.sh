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

# Optional dependency installer triggered explicitly via 'install' command

# Handle commands
case "${1:-}" in
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
    gui)
        python -m psm.gui
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
    build-all)
        echo "Building both CLI and GUI executables..."
        ./run.sh build-cli
        ./run.sh build-gui
        echo "All builds complete!"
        exit 0
        ;;
    help)
        echo "Usage: ./run.sh [command]"
        echo ""
        echo "Application Commands:"
        echo "  pull | scan | match | export | report | report-albums"
        echo "  build                 Build playlists (sync Spotify to M3U)"
        echo "  gui                   Launch desktop GUI"
        echo "  version               Show CLI version"
        echo ""
        echo "Development Commands:"
        echo "  install               Install or update dependencies"
        echo "  test [pytest args]    Run test suite (e.g. ./run.sh test -q tests/unit/)"
        echo "  analyze [mode]        Run code quality analysis (changed|all|files)"
        echo "                        Examples: ./run.sh analyze          (changed files only)"
        echo "                                 ./run.sh analyze all      (entire project)"
        echo "                                 ./run.sh analyze files psm/cli/core.py"
        echo "  cleanup [mode]        Clean code (whitespace, unused imports)"
        echo "                        Examples: ./run.sh cleanup          (changed files only)"
        echo "                                 ./run.sh cleanup all      (entire project)"
        echo "                                 ./run.sh cleanup --dry-run all  (preview)"
        echo "  clear-cache           Remove all Python cache files (__pycache__, *.pyc)"
        echo "  py <args>             Run python with args inside venv"
        echo ""
        echo "Build/Distribution Commands:"
        echo "  build-cli             Build CLI executable (dist/psm-cli)"
        echo "  build-gui             Build GUI executable (dist/psm-gui)"
        echo "  build-all             Build both CLI and GUI executables"
        exit 0
        ;;
    version)
        python -m psm.cli --version
        exit 0
        ;;
    py)
        # Run arbitrary python command inside the virtual environment
        shift
        python "$@"
        exit 0
        ;;
    *)
        python -m psm.cli "$@"
        exit 0
        ;;
esac
