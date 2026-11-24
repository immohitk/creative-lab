
# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

project_root = Path(SPECPATH).resolve().parent
icon_path = project_root / "assets" / "CL-SM.ico"
entry_point = project_root / "src" / "system_monitor" / "__main__.py"

a = Analysis(
    [str(entry_point)],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=[
        (str(icon_path), "assets"),
        (str(project_root / "docs" / "THIRD-PARTY-NOTICES.md"), "licenses"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CLSystemMonitor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(icon_path)],
)

# Exclude the unused Qt Virtual Keyboard components.
a.binaries = [
    entry
    for entry in a.binaries
    if not any(
        name in entry[0].replace("\\", "/").lower()
        for name in ("platforminputcontexts", "qt6virtualkeyboard.dll")
    )
]

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CLSystemMonitor",
)

# pyright: reportUndefinedVariable=false