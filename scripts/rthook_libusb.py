"""
PyInstaller runtime hook — pre-load libusb into the global symbol namespace.

psychtoolbox's PsychHID extension is compiled with macOS's -flat_namespace
flag, which means it resolves symbols like _libusb_bulk_transfer against the
*global* dynamic linker namespace at dlopen time.  On a live machine libusb is
already loaded globally (via Homebrew or the system); inside a frozen bundle it
is not, so the import fails with "symbol not found in flat namespace".

Loading libusb via ctypes.RTLD_GLOBAL before any psychtoolbox import puts its
symbols in the global table and makes PsychHID's flat-namespace resolution
succeed.
"""
import ctypes
import os
import sys

if sys.platform == "darwin" and getattr(sys, "frozen", False):
    _libusb = os.path.join(sys._MEIPASS, "psychtoolbox", "libusb-1.0.0.dylib")
    if os.path.exists(_libusb):
        try:
            ctypes.CDLL(_libusb, ctypes.RTLD_GLOBAL)
        except OSError:
            pass
