# -*- mode: python ; coding: utf-8 -*-
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata
from importlib.resources import files

icon_path = str(files("aTrain.static").joinpath("favicon.ico"))

datas = []
datas += collect_data_files('aTrain')
datas += collect_data_files('torch')
datas += collect_data_files('nicegui')
datas += collect_data_files('lightning')
datas += collect_data_files('lightning_fabric')
datas += collect_data_files('lightning_utilities')
datas += collect_data_files('pyannote')
datas += collect_data_files('pyannote.audio.models')
datas += collect_data_files('pyannote.audio.models.segmentation')
datas += collect_data_files('pyannote.audio.models.embedding')
datas += collect_data_files('pytorch_lightning')
datas += collect_data_files('faster_whisper')
datas += collect_data_files('aTrain_core')
datas += copy_metadata('lightning')
datas += copy_metadata('lightning_utilities')
datas += copy_metadata('torch')
datas += copy_metadata('tqdm')
datas += copy_metadata('requests')
datas += copy_metadata('packaging')
datas += copy_metadata('filelock')
datas += copy_metadata('numpy')
datas += copy_metadata('tokenizers')
datas += copy_metadata('pyannote.audio')
datas += copy_metadata('huggingface-hub')
datas += copy_metadata('pyyaml')
datas += copy_metadata('pytorch_lightning')
# aTrain_core is not a separate distribution under the single-pyproject layout
# (it ships inside the aTrain wheel), so copy_metadata('aTrain_core') would raise
# PackageNotFoundError. Its data files are still bundled via collect_data_files
# above; nothing reads aTrain_core's dist metadata at runtime.

hiddenimports = ['pytorch_lightning','pyyaml','huggingface-hub','pyannote','pytorch','lightning']
hiddenimports += collect_submodules('wakepy')
hiddenimports += collect_submodules('pyannote')
hiddenimports += collect_submodules('sklearn')

a = Analysis(
    ['freeze.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)
# scikit-learn's wheel ships msvcp140.dll 14.16 (VS 2017) in sklearn/.libs.
# PyInstaller collects it into the app root, where it shadows the system's
# newer copy for every DLL loaded afterwards - including torch's c10.dll,
# whose DllMain then fails with WinError 1114 and takes the app down before
# the UI appears. Drop it so the system runtime is used, as in aTrain <=1.4.1.
# Matched on the source path, not just the file name: no dependency ships a
# runtime we need today (torch's Windows wheel carries none), but one that
# started to would otherwise be dropped here without a trace.
a.binaries = [
    b
    for b in a.binaries
    if not (
        os.path.basename(b[0]).lower() == "msvcp140.dll"
        and "sklearn" in (b[1] or "").lower()
    )
]

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='aTrain',
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
    icon=[icon_path],
    plist='Info.plist'
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='aTrain',
)
