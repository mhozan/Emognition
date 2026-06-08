# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Tests for the cross-platform open/reveal command selection (pure, no launch)."""

import os

from emognition.io import open_command, reveal_command


def test_open_command_per_platform():
    assert open_command("/tmp/r.html", "linux") == ["xdg-open", "/tmp/r.html"]
    assert open_command("/tmp/r.html", "darwin") == ["open", "/tmp/r.html"]
    # Windows has no clean argv form -> None (caller uses os.startfile).
    assert open_command(r"C:\r.html", "win32") is None


def test_reveal_command_linux_opens_parent_dir():
    cmd = reveal_command("/tmp/sub/r.html", "linux")
    assert cmd[0] == "xdg-open"
    assert cmd[1] == os.path.dirname(os.path.abspath("/tmp/sub/r.html"))


def test_reveal_command_macos_selects_file():
    assert reveal_command("/tmp/r.html", "darwin") == ["open", "-R", "/tmp/r.html"]


def test_reveal_command_windows_uses_select_flag():
    cmd = reveal_command(r"C:\reports\r.html", "win32")
    assert cmd[0] == "explorer"
    assert cmd[1].startswith("/select,")
    assert cmd[1].endswith("r.html")
