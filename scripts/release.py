#!/usr/bin/env python3
"""Release helper script for Playlist Sync Matcher.

Automates version bumping and tag creation to reduce errors.

Usage:
    python scripts/release.py patch    # 0.1.0 -> 0.1.1
    python scripts/release.py minor    # 0.1.0 -> 0.2.0
    python scripts/release.py major    # 0.1.0 -> 1.0.0
    python scripts/release.py 1.2.3    # Set specific version

After running, manually push: git push origin main && git push origin v1.2.3
"""
import sys
import re
from pathlib import Path
import subprocess

PROJECT_ROOT = Path(__file__).parent.parent
VERSION_FILE = PROJECT_ROOT / "psm" / "version.py"


def get_current_version():
    """Read current version from version.py."""
    content = VERSION_FILE.read_text()
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
    if not match:
        print("❌ Could not find __version__ in version.py")
        sys.exit(1)
    return match.group(1)


def parse_version(version_str):
    """Parse semantic version string."""
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$", version_str)
    if not match:
        print(f"❌ Invalid version format: {version_str}")
        print("   Expected: X.Y.Z or X.Y.Z-suffix")
        sys.exit(1)
    major, minor, patch, suffix = match.groups()
    return int(major), int(minor), int(patch), suffix or ""


def bump_version(current, bump_type):
    """Calculate new version based on bump type."""
    major, minor, patch, suffix = parse_version(current)

    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        # Assume it's a specific version
        parse_version(bump_type)  # Validate format
        return bump_type


def update_version_file(new_version):
    """Update version.py with new version."""
    content = VERSION_FILE.read_text()
    new_content = re.sub(r'(__version__\s*=\s*["\'])[^"\']+(["\'])', rf"\g<1>{new_version}\g<2>", content)
    VERSION_FILE.write_text(new_content)


def run_command(cmd, check=True):
    """Run shell command and return output."""
    try:
        result = subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True, cwd=PROJECT_ROOT)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {cmd}")
        print(f"   Error: {e.stderr}")
        if check:
            sys.exit(1)
        return None


def check_git_status():
    """Verify git is clean before releasing."""
    status = run_command("git status --porcelain")
    if status:
        print("⚠️  Warning: Uncommitted changes detected:")
        print(status)
        response = input("\nContinue anyway? [y/N]: ").strip().lower()
        if response not in ("y", "yes"):
            print("❌ Aborted")
            sys.exit(1)


def check_on_main():
    """Verify we're on main branch."""
    branch = run_command("git branch --show-current")
    if branch != "main":
        print(f"⚠️  Warning: Not on main branch (current: {branch})")
        response = input("\nContinue anyway? [y/N]: ").strip().lower()
        if response not in ("y", "yes"):
            print("❌ Aborted")
            sys.exit(1)


def main():
    """Main release workflow."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    bump_type = sys.argv[1].lower()

    # Get current version
    current = get_current_version()
    print(f"📌 Current version: {current}")

    # Calculate new version
    new_version = bump_version(current, bump_type)
    print(f"🎯 New version: {new_version}")

    # Confirm
    response = input("\nProceed with release? [Y/n]: ").strip().lower()
    if response in ("n", "no"):
        print("❌ Aborted")
        sys.exit(0)

    # Pre-flight checks
    print("\n🔍 Running pre-flight checks...")
    check_git_status()
    check_on_main()

    # Update version file
    print(f"\n📝 Updating {VERSION_FILE.name}...")
    update_version_file(new_version)

    # Git operations
    print("\n📦 Creating git commit and tag...")
    run_command(f"git add {VERSION_FILE}")
    run_command(f'git commit -m "Bump version to {new_version}"')
    run_command(f"git tag v{new_version}")

    print("\n✅ Release prepared successfully!")
    print("\n📋 Next steps:")
    print(f"   1. Review the commit: git show HEAD")
    print(f"   2. Push to trigger release:")
    print(f"      git push origin main")
    print(f"      git push origin v{new_version}")
    print(f"\n   Or to undo:")
    print(f"      git reset --hard HEAD~1")
    print(f"      git tag -d v{new_version}")
    print(f"\n🔗 Monitor release: https://github.com/vtietz/playlist-sync-matcher/actions")


if __name__ == "__main__":
    main()
