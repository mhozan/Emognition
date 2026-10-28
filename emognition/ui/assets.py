# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Locating bundled asset files (emoticon images, audio, backgrounds).

Why a dedicated module? Two reasons:

1. *Single source of truth for paths.* Every other UI module asks here instead of
   hard-coding ``"assets/images/0happy.png"`` all over the place. If we move or
   rename assets (we already did once), there's one spot to fix.
2. *Packaging.* When we later freeze the app with PyInstaller, data files don't
   live next to the source any more -- PyInstaller unpacks them to a temp dir it
   advertises via ``sys._MEIPASS``. Centralising path resolution here means the
   PyInstaller fix is a one-line change, not a scavenger hunt.

The emoticon images come in caption variants, encoded by a leading digit in the
filename (a quirk we inherit from the original MATLAB assets):

    "0happy.png"  -> English caption    (rb1 in the old UI)
    "1happy.png"  -> Mandarin caption    (rb2; Traditional characters)
    "2happy.png"  -> no caption          (rb0, the original default)
    "3happy.png"  -> Spanish caption     (new)

They are drawn by ``scripts/generate_emoticons.py`` (512 px, from the original
artwork's measured geometry); edit and re-run that, not the PNGs.
"""

from __future__ import annotations

import os
import sys
from enum import Enum

from ..core.emotions import Emotion


class Caption(Enum):
    """Which caption variant of the emoticon images to show under the faces."""

    ENGLISH = "0"
    MANDARIN = "1"
    NONE = "2"  # the original program's default
    SPANISH = "3"


def assets_root() -> str:
    """Absolute path to the ``assets/`` directory, in-repo or frozen.

    When running from source, assets live at ``<repo>/assets`` (two levels up
    from this file: emognition/ui/assets.py -> emognition/ -> <repo>). When frozen
    by PyInstaller, they're unpacked under ``sys._MEIPASS``.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base is not None:  # running inside a PyInstaller bundle
        return os.path.join(base, "assets")
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, os.pardir, os.pardir, "assets"))


def audio_dir() -> str:
    """Folder holding the bundled reference ``.wav`` stimuli."""
    return os.path.join(assets_root(), "audio")


def _image(name: str) -> str:
    return os.path.join(assets_root(), "images", name)


def emoticon_path(emotion: Emotion, caption: Caption = Caption.NONE) -> str:
    """Path to the emoticon button image for *emotion* in the given caption style.

    Example: ``emoticon_path(Emotion.HAPPY, Caption.ENGLISH)`` -> ".../0happy.png".
    """
    # Emotion.name is "HAPPY"; the files are lowercase "happy" etc.
    return _image(f"{caption.value}{emotion.name.lower()}.png")


def background_path() -> str:
    """The image painted behind the experimenter setup window."""
    return _image("background_main.jpg")


def backgrounds_dir() -> str:
    """Folder of the bundled, child-friendly participant-window backgrounds.

    The MATLAB app shipped a ``background_pics/`` folder beside the executable
    for the same purpose; these pictures are generated reproducibly by
    ``scripts/generate_backgrounds.py``.
    """
    return os.path.join(assets_root(), "backgrounds")


def user_data_dir() -> str:
    """The per-user Emognition folder (``~/.emognition``): settings, log, pictures."""
    return os.path.join(os.path.expanduser("~"), ".emognition")


def user_backgrounds_dir() -> str:
    """Where "Add picture..." keeps the experimenter's own background pictures."""
    return os.path.join(user_data_dir(), "backgrounds")


def background_folders() -> tuple[str, str]:
    """Folders searched for background pictures: the bundled ones, then the user's."""
    return backgrounds_dir(), user_backgrounds_dir()


def ui_icon_path(name: str) -> str:
    """A control icon of the Qt theme (check mark, arrows), drawn by scripts/generate_ui_icons.py."""
    return _image(os.path.join("ui", f"{name}.png"))


def replay_button_path() -> str:
    """The replay-button icon (shown after each clip when replays are allowed)."""
    return _image("replaybutton.png")


def default_save_dir() -> str:
    """Default report folder: ``save_location/`` beside the executable (frozen)
    or the current folder (from source) -- as the original's exe-relative
    ``save_location``."""
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.getcwd()
    return os.path.join(base, "save_location")


def self_command(argv: list[str]) -> list[str]:
    """The command that runs Emognition itself with *argv* (frozen exe or ``-m``).

    The setup window launches sessions, and Calibration the tone, as separate
    processes this way (Qt and the PsychoPy window must never share one).
    """
    if getattr(sys, "frozen", False):          # PyInstaller bundle: the exe itself
        return [sys.executable, *argv]
    return [sys.executable, "-m", "emognition", *argv]
