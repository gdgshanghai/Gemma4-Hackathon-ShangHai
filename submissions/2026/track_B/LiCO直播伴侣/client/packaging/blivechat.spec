# -*- mode: python ; coding: utf-8 -*-
import os
import sys

from PyInstaller.utils.hooks import collect_submodules

project_root = os.path.abspath(os.path.join(SPECPATH, '..'))

hiddenimports = [
    'tornado.platform.asyncio',
    'sqlalchemy.dialects.sqlite',
    'openai',
    'aiohttp',
    'cachetools',
    'circuitbreaker',
    'Crypto',
]
hiddenimports += collect_submodules('blivedm')
hiddenimports += collect_submodules('blcsdk')
hiddenimports += ['pyttsx3', 'pyttsx3.drivers']
if sys.platform == 'win32':
    hiddenimports += ['pyttsx3.drivers.sapi5']
elif sys.platform == 'darwin':
    hiddenimports += ['pyttsx3.drivers.nsss']

datas = [
    (os.path.join(project_root, 'frontend', 'dist'), os.path.join('frontend', 'dist')),
    (os.path.join(project_root, 'data', 'config.example.ini'), 'data'),
    (os.path.join(project_root, 'data', 'loader.html'), 'data'),
    (os.path.join(project_root, 'plugins'), 'plugins'),
]

a = Analysis(
    [os.path.join(SPECPATH, 'launcher_entry.py')],
    pathex=[project_root],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='blivechat',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
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
    upx=False,
    upx_exclude=[],
    name='blivechat',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='blivechat.app',
        icon=None,
        bundle_identifier='com.blivechat.app',
        info_plist={
            'NSHighResolutionCapable': 'True',
            'CFBundleDisplayName': 'blivechat',
        },
    )
