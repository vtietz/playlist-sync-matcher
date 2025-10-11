#!/usr/bin/env bash
# Cross-platform run script for playlist-sync-matcher

set -e  # Exit on error

VENV=".venv"

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
        echo "Commands:"
        echo "  pull | scan | match | export | report | report-albums | build"
        echo "  gui                   Launch desktop GUI"
        echo "  build-cli             Build CLI executable (dist/psm-cli)"
        echo "  build-gui             Build GUI executable (dist/psm-gui)"
        echo "  build-all             Build both CLI and GUI executables"
        echo "  install               Install or update dependencies"
        echo "  test [pytest args]    Run test suite (e.g. ./run.sh test -q tests/test_hashing.py)"
        echo "  version               Show CLI version"
        echo "  py <args>             Run python with given args inside venv"
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
