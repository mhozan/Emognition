# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""The UI-free packages must never pull in PsychoPy, pyglet or Qt.

That separation is what keeps the science testable headless (and stops a stray
import from opening an audio device or a GL context in a report-only run). Each
import runs in a fresh interpreter, because pytest's own process may already
have loaded anything.
"""

import os
import subprocess
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FORBIDDEN = ("psychopy", "psychtoolbox", "pyglet", "PyQt6")


@pytest.mark.parametrize("module", [
    "emognition.core",
    "emognition.core.backgrounds",
    "emognition.core.pacing",
    "emognition.io",
    "emognition.io.autosave",
    "emognition.config",
    "emognition.imaging",
    "emognition.naming",
    "emognition.reports",
    "emognition.audio",
    "emognition.ui.assets",
    "emognition.ui.geometry",
])
def test_module_imports_no_gui_or_psychopy(module):
    code = (
        f"import sys, {module}\n"
        f"bad = sorted({{m.split('.')[0] for m in sys.modules}} & set({_FORBIDDEN!r}))\n"
        "print(','.join(bad))\n"
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=_REPO,
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", f"{module} imported: {result.stdout.strip()}"
