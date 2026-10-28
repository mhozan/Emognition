# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Session mode enum: what the experiment block is trying to accomplish.

Three modes mirror the original MATLAB design intent -- in the order a
protocol usually runs them, Familiarization, Practice, Test:

* **PASSIVE_TRAINING**, shown as **Familiarization** -- the participant just
  watches and listens. Each clip plays and then the correct answer lights up
  for a moment before the next clip starts. No response is collected: it
  introduces the emotion-to-face mapping. (Original: ``practicemode.m``,
  passive branch.)

* **ACTIVE_TRAINING**, shown as **Practice** -- the participant answers (as in
  a Test) and immediately gets visual feedback: the correct button glows green;
  if they chose wrong, their choice glows orange. Responses are recorded so a
  learning curve can be charted. (Original: ``practicemode.m``, active branch.)

* **TEST** -- the standard mode. No feedback. The participant answers, the app
  records their response and reaction time, and moves on. This is what produces
  the confusion-matrix report. (Original: ``testmode.m``.)

The values (``"test"``, ``"passive"``, ``"active"``) are what the command line,
the settings file and every session record store, so they stay as they were;
only the names people read changed.
"""

from enum import Enum


class SessionMode(str, Enum):
    """The enum values double as CLI ``--mode`` arguments and JSON strings."""

    TEST = "test"
    PASSIVE_TRAINING = "passive"
    ACTIVE_TRAINING = "active"

    @property
    def label(self) -> str:
        """Human-readable label for report headers and UI."""
        return {
            SessionMode.TEST: "Test",
            SessionMode.PASSIVE_TRAINING: "Familiarization",
            SessionMode.ACTIVE_TRAINING: "Practice",
        }[self]
