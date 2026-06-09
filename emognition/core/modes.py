# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Session mode enum: what the experiment block is trying to accomplish.

Three modes mirror the original MATLAB design intent:

* **TEST** -- the standard mode. No feedback. The participant answers, the app
  records their response and reaction time, and moves on. This is what produces
  the confusion-matrix report. (Original: ``testmode.m``.)

* **PASSIVE_TRAINING** -- the participant just watches. Each clip plays and then
  the correct answer lights up for a moment before the next clip starts. No
  response is collected. Use this before a test block to familiarise the
  participant with the emotion-to-face mapping. (Original: ``practicemode.m``
  passive branch.)

* **ACTIVE_TRAINING** -- the participant answers (same as Test), and immediately
  receives visual feedback: the correct button glows green; if they chose wrong,
  their choice glows orange. They learn from their mistakes. Responses are
  recorded so a learning-curve can be charted. (Original: ``practicemode.m``
  active branch.)
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
            SessionMode.PASSIVE_TRAINING: "Passive Training",
            SessionMode.ACTIVE_TRAINING: "Active Training",
        }[self]
