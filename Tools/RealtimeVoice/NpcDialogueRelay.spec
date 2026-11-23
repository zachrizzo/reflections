# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['relay.py'],
    pathex=[],
    binaries=[],
    datas=[('voices.json', '.')],
    hiddenimports=['pipeline', 'tts', 'actions', 'gemini', 'composing', 'api_keys'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'numpy', 'PIL', 'yaml', 'zstandard', 'matplotlib', 'pandas'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NpcDialogueRelay',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NpcDialogueRelay',
)
