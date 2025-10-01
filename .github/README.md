# GitHub Actions Workflows

## release.yml

Automatically builds standalone executables for Windows, Linux, and macOS when you push a version tag.

### How to Create a Release

1. Update version in `spx/cli.py`
2. Commit your changes
3. Create and push a version tag:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
4. GitHub Actions will:
   - Build executables for Windows, Linux, and macOS
   - Run smoke tests on each platform
   - Create a GitHub Release with all binaries attached
   - Generate release notes automatically

### Manual Trigger

You can also trigger a build manually from the GitHub Actions tab without creating a release.

### Artifacts

The workflow produces:
- `spotify-m3u-sync-windows-amd64.exe` - Windows executable
- `spotify-m3u-sync-linux-amd64` - Linux executable
- `spotify-m3u-sync-macos-amd64` - macOS executable

All are standalone, single-file executables that don't require Python installation.
