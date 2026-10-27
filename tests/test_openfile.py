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


def test_reveal_command_windows_quotes_only_the_path():
    # A string, so Python can't wrap the whole /select,... argument in quotes
    # (explorer misreads that when the path contains a space).
    cmd = reveal_command(r"C:\my reports\r.html", "win32")
    assert isinstance(cmd, str)
    assert cmd.startswith('explorer /select,"') and cmd.endswith('r.html"')


def test_system_env_restores_the_original_library_path(monkeypatch):
    from emognition.io.openfile import system_env

    monkeypatch.delattr("sys.frozen", raising=False)
    assert system_env() is None                       # running from source: inherit
    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/bundle/_internal")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/usr/local/lib")
    env = system_env()
    assert env["LD_LIBRARY_PATH"] == "/usr/local/lib" and "LD_LIBRARY_PATH_ORIG" not in env
    monkeypatch.delenv("LD_LIBRARY_PATH_ORIG")
    assert "LD_LIBRARY_PATH" not in system_env()      # none originally: drop the bundle's
