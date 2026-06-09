# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


local_hiddenimports = [
    'money',
    'purchase_extractor',
    'summary',
    'tag_store',
    'ui_state',
    'version',
    'views',
    'views.tags',
]
customtkinter_datas = collect_data_files('customtkinter')
customtkinter_hiddenimports = collect_submodules('customtkinter')

a = Analysis(
    ['purchase_tagger_app.py'],
    pathex=[],
    binaries=[],
    datas=[('tags.json', '.'), ('assets/app_icon.ico', 'assets')] + customtkinter_datas,
    hiddenimports=local_hiddenimports + customtkinter_hiddenimports,
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
    a.binaries,
    a.datas,
    [],
    name='purchase_tagger_app',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/app_icon.ico',
)
