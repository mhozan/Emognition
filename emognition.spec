# -*- mode: python ; coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# PyInstaller build spec for Emognition.
#
# Why a hand-written spec (not just `pyinstaller script.py`)? PsychoPy and its
# audio/visual backends are PyInstaller's worst-case: hundreds of data files,
# compiled extensions (PsychoToolbox, libsndfile via soundfile), and lots of
# dynamic imports PyInstaller's static analysis can't see. We therefore
# force-collect the troublesome packages wholesale with collect_all(), and bundle
# our own assets/ tree.
#
# Build (one directory, recommended for PsychoPy):
#     pyinstaller emognition.spec
# Result: dist/emognition/emognition   (run with --selfcheck to verify the bundle)

import os
import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = []
binaries = []
hiddenimports = []

# psychtoolbox's PsychHID links against libusb, which PyInstaller won't find
# automatically for Homebrew-installed dylibs.  We add it to binaries so it
# lands in the bundle; the CI workflow then runs install_name_tool to rewrite
# the rpath in PsychHID (PyInstaller doesn't do that for manually-added libs).
if sys.platform == "darwin":
    for _candidate in (
        "/opt/homebrew/lib/libusb-1.0.0.dylib",  # Homebrew Apple Silicon
        "/usr/local/lib/libusb-1.0.0.dylib",       # Homebrew Intel
    ):
        if os.path.exists(_candidate):
            binaries.append((_candidate, "psychtoolbox"))  # place next to PsychHID
            break

# Packages PyInstaller can't figure out on its own -> grab everything.
for pkg in (
    "psychopy",
    "psychtoolbox",
    "pyglet",
    "soundfile",      # bundles libsndfile
    "freetype",       # freetype-py, used by PsychoPy text
    "questplus",
    "json_tricks",
    "openpyxl",       # ships .xlsx template files that static analysis misses
    "fpdf2",          # ships bundled font files
):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

# The audio backend we actually use is imported lazily by PsychoPy.
hiddenimports += ["psychopy.sound.backend_ptb"]
# Report writers and naming module are imported lazily from app.py.
hiddenimports += [
    "emognition.reports",
    "emognition.naming",
    "emognition.audio",
]

# Our own package + its asset tree (audio clips, emoticon images, background).
hiddenimports += collect_submodules("emognition")
datas += [("assets", "assets")]

a = Analysis(
    ["scripts/emognition_launcher.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # Drop heavyweight packages PsychoPy only imports lazily for features we
    # don't use (movies, camera, the Coder IDE, Arrow/HDF5 data export). This
    # is the difference between a ~1.1 GB and a ~0.4 GB bundle. wxPython is
    # likewise unused (we build the UI on PyQt6).
    excludes=[
        "wx",
        "cv2", "opencv_python",          # camera / OpenCV
        "imageio_ffmpeg", "ffpyplayer", "moviepy", "proglog",  # movie playback
        "pyarrow", "tables", "numexpr", "blosc2",  # Arrow / HDF5 data export
        "jedi", "parso", "IPython",      # Coder IDE autocomplete
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="emognition",
    debug=False,
    strip=False,
    upx=False,
    console=True,       # keep a console during bring-up so errors are visible
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="emognition",
)
