# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Emognition core: UI-free experiment logic (emotions, stimuli, timing, scoring).

Kept deliberately free of PsychoPy / Qt imports so the scientific logic
(reaction-time math, scoring, file parsing) is unit-testable without a display.
"""

from .emotions import (
    Emotion,
    Gender,
    Stimulus,
    EMOTIONS_IN_ORDER,
    TAG_TO_EMOTION,
)
from .stimuli import parse_stimulus_filename, scan_audio_dir

__all__ = [
    "Emotion",
    "Gender",
    "Stimulus",
    "EMOTIONS_IN_ORDER",
    "TAG_TO_EMOTION",
    "parse_stimulus_filename",
    "scan_audio_dir",
]
