# Release Process Guide

## Release Strategy Overview

This project uses a single, basic tag-based GitHub Actions workflow to build and publish releases. Pushing a tag like v1.0.0 triggers builds for Windows, Linux, and macOS and creates a GitHub Release with auto-generated release notes.

## Current Workflows

- CI Workflow ([.github/workflows/ci.yml](../.github/workflows/ci.yml))
  - Triggers: every push to main, all PRs
  - Runs: tests on Python 3.11 & 3.12 for Windows & Linux
  - Purpose: quality gate before merge

- Release Workflow ([.github/workflows/release.yml](../.github/workflows/release.yml))
  - Triggers:
    - Git tags matching v* (e.g., v1.0.0) — builds and creates a release
    - workflow_dispatch (manual) — builds and uploads artifacts; does not create a release
  - Builds: 6 executables (CLI + GUI for Windows, Linux, macOS)
  - Outputs: GitHub Release with auto-generated release notes (generate_release_notes: true)

There is no enhanced release workflow; the project intentionally keeps release automation minimal.

## How to Create a Release

### Method 1: Tag-Based Automated Release (Recommended)

1. Update version number
   - Edit [psm/version.py](../psm/version.py) and bump the version string
2. Commit the version bump
   - git add psm/version.py; git commit -m "Bump version to X.Y.Z"; git push origin main
3. Create and push the tag
   - git tag vX.Y.Z && git push origin vX.Y.Z
4. Monitor the workflow
   - Check Actions → “Build and Release”; completion produces a GitHub Release

Output:
- 6 executables (CLI + GUI for Windows/Linux/macOS)
- Auto-generated release notes provided by GitHub

### Method 2: Manual Workflow Dispatch

Use this to test builds without creating a release.

Steps:
1. Go to GitHub → Actions → “Build and Release”
2. Click “Run workflow” and select a branch (usually main)
3. Wait for artifacts to build

Note: Manual runs of [release.yml](../.github/workflows/release.yml) upload artifacts but do not create a Release.

## Semantic Versioning Guidelines

Follow Semantic Versioning: MAJOR.MINOR.PATCH
- MAJOR: breaking changes
- MINOR: new features, backward-compatible
- PATCH: bug fixes, backward-compatible

Pre-release tags (optional):
- v0.2.0-alpha.1
- v0.2.0-beta.1
- v0.2.0-rc.1

## Release Checklist

Before tagging:
- [ ] All tests passing locally (`.\run.bat test tests\`)
- [ ] CI green on main ([.github/workflows/ci.yml](../.github/workflows/ci.yml))
- [ ] Update version in [psm/version.py](../psm/version.py)
- [ ] Test executables locally (`.\run.bat build`)

Create tag:
- [ ] Tag format: vX.Y.Z
- [ ] Push tag: `git push origin vX.Y.Z`

After build:
- [ ] Verify Release exists with 6 executables
- [ ] Download and test CLI/GUI binaries
- [ ] Update README if needed

## Troubleshooting

Version appears inconsistent between tag and version.py
- In the basic workflow, releases are created even if versions differ.
- Recommendation: keep tag and version.py aligned for clarity.
- To fix:
  1. Delete wrong tag locally and remotely:
     - `git tag -d v0.2.0`
     - `git push origin :refs/tags/v0.2.0`
  2. Update [psm/version.py](../psm/version.py)
  3. Commit, recreate tag, and push

Build fails on one platform
- Check the job logs in GitHub Actions
- Common issues:
  - Missing system libraries on Linux (e.g., libegl1, libgl1 for PySide6)
  - Code signing on macOS
  - Antivirus blocking on Windows

Release created but no executables
- Ensure “build-cli” and “build-gui” jobs succeeded
- Confirm artifacts were uploaded and downloaded into the release

Manual run doesn’t create a Release
- Expected: [release.yml](../.github/workflows/release.yml) only creates a Release for tag triggers.

## Release Workflow Diagram

Update version.py → Commit → Create tag → Push tag → GitHub Actions builds executables → Release published

## Recommended Release Cadence

- Patch releases: as needed for critical fixes
- Minor releases: every 2–4 weeks with new features
- Major releases: when API is stable and production-ready

## Quick Links

- Semantic Versioning: https://semver.org/
- GitHub Actions Documentation: https://docs.github.com/en/actions
- PyInstaller Docs: https://pyinstaller.org/
- GitHub Releases Guide: https://docs.github.com/en/repositories/releasing-projects-on-github
