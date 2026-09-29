# -*- mode: python ; coding: utf-8 -*-
"""Đóng gói langstudyguard thành một file langstudyguard.exe.

Chạy: python -m PyInstaller DutchGuard.spec --noconfirm
"""

import os

# Miniconda để DLL ở Library\bin, PyInstaller không tự tìm thấy.
_conda_bin = os.path.join(os.path.expanduser("~"), "miniconda3", "Library", "bin")
_dll_names = (
    "tcl86t.dll",
    "tk86t.dll",
    "ffi.dll",
    "libssl-3-x64.dll",
    "libcrypto-3-x64.dll",
    "libexpat.dll",
    "liblzma.dll",
    "libbz2.dll",
    "libmpdec-4.dll",
    "zlib.dll",
    "sqlite3.dll",
)
_binaries = [
    (os.path.join(_conda_bin, name), ".")
    for name in _dll_names
    if os.path.isfile(os.path.join(_conda_bin, name))
]

a = Analysis(
    ["app/main.py"],
    pathex=["app"],
    binaries=_binaries,
    datas=[
        ("data/vocab.json", "."),
        ("data/starters", "starters"),
        ("data/Reading", "Reading"),
        ("bundled_secrets.json", "."),
    ],
    hiddenimports=["dotenv"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="langstudyguard",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
)
