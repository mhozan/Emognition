# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""A machine-readable record of one session: ``<participant>_<stamp>.json``.

The human reports say *what* the participant did; this sidecar says *how the
session was run* -- every setting, the random seed and the resulting trial
order, the background plan, timing quality (refresh rate, dropped frames, audio
latency) and the software versions. That is what a methods section needs, and
what lets someone re-run the exact same order later (``--seed``). Written in the
spirit of BIDS JSON sidecars: plain JSON, one file per data file, next to it.
"""

from __future__ import annotations

import importlib.metadata
import json
import platform
import sys
from datetime import date, datetime
from enum import Enum

# Bump when the layout changes in a way readers must know about.
SIDECAR_FORMAT = "emognition-session"
SIDECAR_VERSION = 1

_PACKAGES = ("psychopy", "psychtoolbox", "numpy", "pillow", "pyglet", "PyQt6")


def _jsonable(value: object) -> object:
    """Fallback encoder: timestamps as ISO 8601, enums by value, anything else as text."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return str(value)


def environment_info() -> dict:
    """OS, Python and package versions -- read from metadata, nothing imported."""
    versions = {}
    for name in _PACKAGES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return {
        "os": platform.platform(),
        "python": sys.version.split()[0],
        "frozen": bool(getattr(sys, "frozen", False)),
        "packages": versions,
    }


def write_session_sidecar(path: str, record: dict) -> str:
    """Write *record* (plus the format marker) as pretty, UTF-8 JSON; return the path."""
    payload = {"format": SIDECAR_FORMAT, "format_version": SIDECAR_VERSION, **record}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False, default=_jsonable)
        fh.write("\n")
    return path
