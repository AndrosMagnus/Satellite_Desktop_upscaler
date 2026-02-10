# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

# PyInstaller executes .spec files without defining __file__, so rely on cwd.
project_root = Path.cwd().resolve()

block_cipher = None

a = Analysis(
    [str(project_root / "app" / "ui.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / "models" / "registry.json"), "models"),
        (str(project_root / "docs"), "docs"),
    ],
    hiddenimports=["PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets"],
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
    [],
    exclude_binaries=True,
    name="SatelliteUpscale",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SatelliteUpscale",
)
