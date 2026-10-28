# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""The lockfile installs the right packages on every OS.

requirements.txt is generated on Linux, so its macOS lines are written by hand
(see requirements.in) -- and a re-lock would quietly drop them. These tests read
the lock the way ``pip install --no-deps -r requirements.txt`` does on each OS.
"""

from __future__ import annotations

import os

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

LOCK = os.path.join(os.path.dirname(__file__), os.pardir, "requirements.txt")


def _pins(sys_platform: str) -> dict[str, str]:
    """Package -> version that the lock installs on *sys_platform*."""
    pins: dict[str, str] = {}
    for line in open(LOCK, encoding="utf-8"):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        req = Requirement(line)
        if req.marker is not None and not req.marker.evaluate({"sys_platform": sys_platform}):
            continue
        name = canonicalize_name(req.name)
        assert name not in pins, f"{name} is pinned twice for {sys_platform}"   # pip would refuse
        pins[name] = str(req.specifier).removeprefix("==")
    return pins


def test_macos_gets_an_apple_silicon_psychtoolbox_and_pyobjc():
    mac = _pins("darwin")
    assert mac["psychtoolbox"] == "3.0.22.2"      # the first with an arm64 (universal2) wheel
    # PsychoPy's window backend imports AppKit on macOS, and psychopy.iohub imports objc.
    for name in ("pyobjc-core", "pyobjc-framework-cocoa", "pyobjc-framework-quartz"):
        assert name in mac


def test_linux_and_windows_keep_the_psychtoolbox_their_timing_was_verified_with():
    for sys_platform in ("linux", "win32"):
        pins = _pins(sys_platform)
        assert pins["psychtoolbox"] == "3.0.19.14"
        assert not [name for name in pins if name.startswith("pyobjc")]
