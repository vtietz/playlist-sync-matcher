#!/usr/bin/env bash
# Cross-platform run script for spotify-m3u-sync

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

# Install requirements quietly
pip install -q -r requirements.txt

# Handle commands
case "${1:-}" in
    test)
        shift
        echo "Running: python -m pytest $@"
        python -m pytest "$@"
        ;;
    help)
        echo "Usage: ./run.sh [command]"
        echo "Commands:"
        echo "  pull | scan | match | export | report | report-albums | sync"
        echo "  test [pytest args]    Run test suite (e.g. ./run.sh test -q tests/test_hashing.py)"
        echo "  version               Show CLI version"
        ;;
    version)
        python -m spx.cli --version
        ;;
    *)
        python -m spx.cli "$@"
        ;;
esac
