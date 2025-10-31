# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for building the GUI executable.

This builds a standalone GUI application with all necessary dependencies.

Build command:
    pyinstaller psm-gui.spec

Output:
    dist/psm-gui.exe (Windows)
    dist/psm-gui (Linux/macOS)
"""
import sys
import os

block_cipher = None

# For python.org Python (not Conda), PyInstaller handles DLLs automatically
# No manual DLL bundling needed
binaries = []

resource_dir = 'psm/gui/resources'

# Collect only existing resources to avoid build failures
data_files = []
for rel in (
    'style.qss',
    'psm-icon.png',
    'psm-icon.ico',
    'ps-icon.ico',
    'icon.png',
    'icon.ico',
):
    p = os.path.join(resource_dir, rel)
    if os.path.exists(p):
        data_files.append((p, resource_dir))

# Choose an executable icon if available (Windows only)
icon_candidates = (
    os.path.join(resource_dir, 'ps-icon.ico'),
    os.path.join(resource_dir, 'psm-icon.ico'),
    os.path.join(resource_dir, 'icon.ico'),
)
exe_icon = None
for cand in icon_candidates:
    if os.path.exists(cand):
        exe_icon = cand
        break

a = Analysis(
    ['psm/gui/__main__.py'],
    pathex=['.'],
    binaries=binaries,
    datas=data_files,
    hiddenimports=[
        'psm',
        'psm.gui',
        'psm.gui.adapters',
        'psm.gui.components',
        'psm.gui.panels',
        'psm.gui.services',
        'psm.gui.shell',
        'psm.gui.state',
        'psm.gui.tabs',
        'psm.gui.utils',
        'psm.gui.views',
        'psm.gui.controllers',
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
        'tkinter',
        'tkinter.ttk',
        '_ctypes',
        'ctypes',
        'ctypes.wintypes',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude dev/test tools (not needed in runtime)
        'pytest',
        'black',
        'flake8',
        'lizard',
        'autoflake',
        'pycodestyle',
        'pyflakes',
        'mccabe',
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
    name='psm-gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI doesn't need console window on Windows
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=exe_icon,
)
