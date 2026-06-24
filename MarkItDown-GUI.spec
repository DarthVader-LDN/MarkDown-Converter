# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build spec for MarkItDown Converter.

This spec encodes the *exact* data/binary-collection recipe needed to make a
self-contained executable, validated end-to-end. The three things a naive
build silently drops (and that cause runtime crashes) are handled explicitly:

  1. magika      -> ships a ~3 MB ONNX model + JSON configs. Without them,
                    MarkItDown() crashes on startup ("model not found").
  2. onnxruntime -> native runtime libraries (DLLs on Windows). magika needs
                    these to load the model.
  3. pdfminer.six-> ~150 CMap resources required to decode many PDFs.

Build (from this folder, on Windows):
    pyinstaller --clean --noconfirm MarkItDown-GUI.spec
Output:
    dist\\MarkItDownConverter.exe        (ONEFILE = True)
    dist\\MarkItDownConverter\\...        (ONEFILE = False)
"""

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    copy_metadata,
)

# --------------------------------------------------------------------------- #
# Build configuration — tweak these, not the logic below.
# --------------------------------------------------------------------------- #
APP_NAME = "MarkItDownConverter"
ENTRY = "app.py"
ONEFILE = True          # True -> single .exe (what "standalone" usually means).
                        # False -> a folder build: starts faster, fewer antivirus
                        #          false-positives. Recommended if the onefile
                        #          build is slow to launch or gets AV-flagged.
ICON = None             # e.g. "app.ico" to brand the window/taskbar/exe icon.

# --------------------------------------------------------------------------- #
# Collection recipe (do not remove items without testing).
# --------------------------------------------------------------------------- #
datas, binaries, hiddenimports = [], [], []

# (1) magika model + content-type configs — mandatory.
datas += collect_data_files("magika")
# (2) pdfminer CMap resources — needed for robust PDF text extraction.
datas += collect_data_files("pdfminer")
# (3) onnxruntime native libraries + helper data.
datas += collect_data_files("onnxruntime")
binaries += collect_dynamic_libs("onnxruntime")

# Several libraries read their own version via importlib.metadata at runtime.
# Bundling the *.dist-info prevents "PackageNotFoundError" after freezing.
for _pkg in (
    "markitdown", "magika", "onnxruntime", "numpy",
    "pdfminer.six", "pdfplumber", "markdownify",
    "beautifulsoup4", "charset-normalizer", "defusedxml",
    "python-pptx", "mammoth", "openpyxl", "xlrd", "pandas", "lxml", "olefile",
):
    try:
        datas += copy_metadata(_pkg)
    except Exception:
        # Optional/renamed packages: skip silently rather than fail the build.
        pass

# MarkItDown imports converter back-ends lazily; declare them so PyInstaller's
# static analysis doesn't miss them.
hiddenimports += [
    "magika", "onnxruntime", "numpy",
    "pandas", "openpyxl", "xlrd",
    "pdfminer", "pdfminer.high_level", "pdfplumber",
    "mammoth", "lxml", "pptx", "olefile",
    "bs4", "markdownify",
    "charset_normalizer", "defusedxml", "defusedxml.minidom",
]

# --------------------------------------------------------------------------- #
# Analysis / packaging
# --------------------------------------------------------------------------- #
a = Analysis(
    [ENTRY],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Trim weight: these are not used by the offline converters.
        "matplotlib", "scipy", "PyQt5", "PyQt6", "PySide2", "PySide6",
        "IPython", "notebook", "pytest",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

if ONEFILE:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,            # UPX off: it routinely triggers antivirus heuristics.
        runtime_tmpdir=None,
        console=False,        # windowed GUI app — no console window.
        disable_windowed_traceback=False,
        icon=ICON,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=APP_NAME,
        debug=False,
        strip=False,
        upx=False,
        console=False,
        icon=ICON,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        name=APP_NAME,
    )
