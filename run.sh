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
esac

case "${1:-}" in
    test)
        shift
        echo "Running: python -m pytest $@"
        python -m pytest "$@"
        ;;
    help)
        echo "Usage: ./run.sh [command]"
        echo "Commands:"
        echo "  pull | scan | match | export | report | report-albums | build"
        echo "  install               Install or update dependencies"
        echo "  test [pytest args]    Run test suite (e.g. ./run.sh test -q tests/test_hashing.py)"
        echo "  version               Show CLI version"
        ;;
    version)
        python -m psm.cli --version
        ;;
    *)
        python -m psm.cli "$@"
        ;;
esac
