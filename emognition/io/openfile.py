# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Cross-platform "open this file" / "show it in the file manager" helpers.

The original called ``explorer.exe`` directly -- Windows only. Here we do the
right thing on each OS:

    open a file        Windows: os.startfile · macOS: ``open`` · Linux: ``xdg-open``
    reveal in folder   Windows: ``explorer /select,`` · macOS: ``open -R`` ·
                       Linux: ``xdg-open <parent dir>`` (no universal "select")

Design note: the OS-specific *decision* (which command for which platform) is a
pure function -- :func:`open_command` / :func:`reveal_command` -- so it can be
unit-tested for every platform on any machine, without actually launching
anything. The thin :func:`open_path` / :func:`reveal_in_file_manager` wrappers
just execute that decision and never raise (a failed "open" shouldn't crash a
finished experiment).
"""

from __future__ import annotations

import os
import subprocess
import sys


def open_command(path: str, platform: str) -> list[str] | None:
    """Return the argv to open *path* with the default app on *platform*.

    Returns ``None`` for Windows, signalling the caller to use ``os.startfile``
    (which has no clean argv form).
    """
    if platform.startswith("win"):
        return None
    if platform == "darwin":
        return ["open", path]
    return ["xdg-open", path]  # Linux and other freedesktop systems


def reveal_command(path: str, platform: str) -> list[str] | str:
    """Return the command to reveal *path* in the OS file manager.

    On Windows this is a single command-line *string*: explorer wants
    ``/select,"C:\\some folder\\file"``, and an argv list would make Python
    quote the whole ``/select,...`` argument, which explorer misreads whenever
    the path contains a space.
    """
    if platform.startswith("win"):
        # explorer's /select takes the path glued to the flag with a comma.
        return f'explorer /select,"{os.path.normpath(path)}"'
    if platform == "darwin":
        return ["open", "-R", path]
    # Linux: no portable "select the file", so open the containing directory.
    return ["xdg-open", os.path.dirname(os.path.abspath(path)) or "."]


def system_env() -> dict[str, str] | None:
    """Environment for launching *system* programs (browser, file manager).

    A frozen (PyInstaller) app on Linux runs with ``LD_LIBRARY_PATH`` pointing
    at its own bundled libraries, keeping the original in
    ``LD_LIBRARY_PATH_ORIG``. ``xdg-open`` and the browser it starts must not
    load those, or they may fail to start, so we restore the original value.
    Returns ``None`` (inherit everything) when not frozen.
    """
    if not getattr(sys, "frozen", False):
        return None
    env = dict(os.environ)
    original = env.pop("LD_LIBRARY_PATH_ORIG", None)
    if original is not None:
        env["LD_LIBRARY_PATH"] = original
    else:
        env.pop("LD_LIBRARY_PATH", None)
    return env


def _spawn(cmd: list[str] | str) -> bool:
    """Launch *cmd* detached; swallow failures and return success as a bool."""
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # don't tie the viewer to our process
            env=system_env(),
        )
        return True
    except (OSError, ValueError):
        return False


def open_path(path: str) -> bool:
    """Open *path* in the OS default application. Returns True on success."""
    cmd = open_command(path, sys.platform)
    if cmd is None:  # Windows
        try:
            os.startfile(path)  # type: ignore[attr-defined]  # noqa: S606
            return True
        except OSError:
            return False
    return _spawn(cmd)


def reveal_in_file_manager(path: str) -> bool:
    """Reveal *path* in the file manager (selected where supported)."""
    return _spawn(reveal_command(path, sys.platform))
