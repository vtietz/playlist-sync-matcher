from __future__ import annotations
import re
import subprocess
import sys

import psm.version as v

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.]+)?$")


def test_version_constant_format():
    assert SEMVER_RE.match(v.__version__), f"Version '{v.__version__}' is not valid semantic version"


def test_cli_global_version_option():
    # Invoke the CLI using current interpreter to ensure we are in the venv
    proc = subprocess.run([
        sys.executable,
        '-m', 'psm.cli',
        '--version'
    ], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr or proc.stdout
    out = (proc.stdout + proc.stderr).strip()
    # Expected pattern: 'playlist-sync-matcher, version X.Y.Z'
    assert 'playlist-sync-matcher' in out.lower()
    assert v.__version__ in out, f"CLI output did not contain version: {out}"
