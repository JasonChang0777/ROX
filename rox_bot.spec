# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_dir = Path(SPECPATH)
gardening_dir = project_dir / "rox_gardening"
fishing_dir = project_dir / "rox_fishing"

launcher_analysis = Analysis(
    [str(gardening_dir / "rox_bot_launcher.pyw")],
    pathex=[str(gardening_dir)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
gardening_analysis = Analysis(
    [str(gardening_dir / "gardening_bot.py")],
    pathex=[str(gardening_dir)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
fishing_analysis = Analysis(
    [str(fishing_dir / "fishing_bot.py")],
    pathex=[str(fishing_dir)],
    binaries=[],
    datas=[
        (str(fishing_dir / "templates" / "empty_bait.png"), "templates"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

launcher_pyz = PYZ(launcher_analysis.pure)
gardening_pyz = PYZ(gardening_analysis.pure)
fishing_pyz = PYZ(fishing_analysis.pure)

launcher_exe = EXE(
    launcher_pyz,
    launcher_analysis.scripts,
    [],
    exclude_binaries=True,
    name="ROX Bot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)
gardening_exe = EXE(
    gardening_pyz,
    gardening_analysis.scripts,
    [],
    exclude_binaries=True,
    name="ROX Gardening Bot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
)
fishing_exe = EXE(
    fishing_pyz,
    fishing_analysis.scripts,
    [],
    exclude_binaries=True,
    name="ROX Fishing Bot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
)

release = COLLECT(
    launcher_exe,
    gardening_exe,
    fishing_exe,
    launcher_analysis.binaries,
    launcher_analysis.datas,
    gardening_analysis.binaries,
    gardening_analysis.datas,
    fishing_analysis.binaries,
    fishing_analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ROX Bot",
)
