"""
PyInstaller runtime hook — pre-load Homebrew dylibs into the global symbol namespace.

Several psychtoolbox extensions (PsychHID, PsychPortAudio, ...) are compiled with
macOS's -flat_namespace flag.  They resolve symbols like _libusb_bulk_transfer and
_PaMacCore_GetBufferSizeRange against the *global* dyld namespace at dlopen time.
On a live machine those symbols are already globally loaded (Homebrew); inside a
frozen bundle they are not, so the imports fail with "symbol not found in flat
namespace".

The spec places the required dylibs in _internal/psychtoolbox/ alongside the .so
files.  This hook iterates that directory and loads every .dylib it finds with
RTLD_GLOBAL before any psychtoolbox import, putting all symbols in the global table.
"""
import ctypes
import glob
import os
import sys

if sys.platform == "darwin" and getattr(sys, "frozen", False):
    _ptb_dir = os.path.join(sys._MEIPASS, "psychtoolbox")
    for _dylib in sorted(glob.glob(os.path.join(_ptb_dir, "*.dylib"))):
        try:
            ctypes.CDLL(_dylib, ctypes.RTLD_GLOBAL)
        except OSError:
            pass
