# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for building the CLI executable.

This builds a standalone command-line executable without GUI dependencies.

Build command:
    pyinstaller psm-cli.spec

Output:
    dist/psm-cli.exe (Windows)
    dist/psm-cli (Linux/macOS)
"""
import sys
import os

block_cipher = None

# For python.org Python (not Conda), PyInstaller handles DLLs automatically
# No manual DLL bundling needed
binaries = []

resource_dir = 'psm/gui/resources'
data_files = []
for rel in (
    'ps-icon.ico',
    'psm-icon.ico',
):
    p = os.path.join(resource_dir, rel)
    if os.path.exists(p):
        data_files.append((p, resource_dir))

a = Analysis(
    ['psm/cli/__main__.py'],
    pathex=['.'],  # Add current directory to Python path
    binaries=binaries,
    datas=data_files,
    hiddenimports=[
        'psm',
        'psm.cli',
        'psm.cli.helpers',
        'psm.cli.core',
        'psm.cli.__init__',
        'psm.cli.analyze_cmds',
        'psm.cli.config_cmds',
        'psm.cli.diagnose_cmds',
        'psm.cli.export_cmds',
        'psm.cli.match_cmds',
        'psm.cli.oauth_cmds',
        'psm.cli.playlist_cmds',
        'psm.cli.playlists',
        'psm.cli.provider_cmds',
        'psm.cli.report_cmds',
        'psm.cli.scan_cmds',
        'psm.auth',
        'psm.db',
        'psm.export',
        'psm.ingest',
        'psm.match',
        'psm.providers',
        'psm.push',
        'psm.reporting',
        'psm.services',
        'psm.utils',
        'psm.utils.first_run',
        '_ctypes',
        'ctypes',
        'ctypes.wintypes',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'psm.gui',  # Exclude GUI package
        'tkinter',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,  # Bundle everything into single exe
    a.zipfiles,
    a.datas,
    [],
    name='psm-cli',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # CLI requires console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=(os.path.join(resource_dir, 'ps-icon.ico') if os.path.exists(os.path.join(resource_dir, 'ps-icon.ico')
          else (os.path.join(resource_dir, 'psm-icon.ico') if os.path.exists(os.path.join(resource_dir, 'psm-icon.ico')
                else None)),
)
