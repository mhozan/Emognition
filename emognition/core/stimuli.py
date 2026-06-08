# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Discovering and parsing audio stimuli from a folder.

This is the Python re-implementation of the filename-parsing half of the original
``analyzeaudiodir.m``. The naming contract (verbatim spirit of the MATLAB tooltip
in Emognition2.m) is:

    Any filename that ends with the pattern   ..._EMO_G.wav
        EMO -> one of {ANG, HAP, SAD, NEU, SCA}   (case-insensitive)
        G   -> F or M                              (case-insensitive)
    Anything preceding the trailing "_EMO_G.wav" is ignored, so
    "01_ang_f.wav", "subjectA_recording12_HAP_M.wav", etc. are all valid.

Files that do not match are skipped -- echoing the v1.14 changelog note:
    "Skips loading of non-WAV audio files."
"""

from __future__ import annotations

import os
import re

from .emotions import Emotion, Gender, Stimulus, TAG_TO_EMOTION

# Match a trailing  _EMO_G  just before the .wav extension.
# Example matches: "_ang_f", "_HAP_M". The leading part of the name is free-form.
_PATTERN = re.compile(
    r"_(?P<emo>ang|hap|sad|neu|sca)_(?P<gender>[fm])\.wav$",
    re.IGNORECASE,
)


def parse_stimulus_filename(path: str) -> Stimulus | None:
    """Parse one filename into a :class:`Stimulus`, or ``None`` if it doesn't match.

    Args:
        path: A filename or full path ending in the ``_EMO_G.wav`` pattern.

    Returns:
        A :class:`Stimulus` carrying the correct emotion + speaker gender, or
        ``None`` if the name doesn't follow the convention (caller should skip it).
    """
    name = os.path.basename(path)
    match = _PATTERN.search(name)
    if match is None:
        return None

    emotion: Emotion = TAG_TO_EMOTION[match.group("emo").lower()]
    gender = Gender.FEMALE if match.group("gender").lower() == "f" else Gender.MALE
    return Stimulus(path=path, emotion=emotion, gender=gender)


def scan_audio_dir(directory: str) -> list[Stimulus]:
    """Return every valid stimulus in *directory*, sorted by filename.

    Non-matching files (wrong extension, missing EMO_G suffix) are silently
    skipped, exactly as the original program tolerated stray files in the folder.
    """
    stimuli: list[Stimulus] = []
    for entry in sorted(os.listdir(directory)):
        stim = parse_stimulus_filename(os.path.join(directory, entry))
        if stim is not None:
            stimuli.append(stim)
    return stimuli
