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

block_cipher = None

# For python.org Python (not Conda), PyInstaller handles DLLs automatically
# No manual DLL bundling needed
binaries = []

a = Analysis(
    ['psm/gui/__main__.py'],
    pathex=[],
    binaries=binaries,
    datas=[],
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
    excludes=[],
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
    icon=None,  # Optional: add GUI icon (e.g., 'resources/icon.ico')
)
