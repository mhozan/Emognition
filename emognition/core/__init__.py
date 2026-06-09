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
    Sex,
    Stimulus,
    EMOTIONS_IN_ORDER,
    SEXES_IN_ORDER,
    TAG_TO_EMOTION,
    TAG_TO_SEX,
)
from .stimuli import parse_stimulus_filename, scan_audio_dir
from .responses import Response
from .trials import build_trial_list, summarize_stimuli, StimulusBreakdown
from .timing import ReactionTime, reaction_time
from .scoring import (
    GroupStats,
    SessionSummary,
    confusion_matrix,
    summarize,
)
from .quality import RtFlag, flag_responses, scrub_flagged_rts
from .modes import SessionMode

__all__ = [
    # emotions / stimuli
    "Emotion",
    "Sex",
    "Stimulus",
    "EMOTIONS_IN_ORDER",
    "SEXES_IN_ORDER",
    "TAG_TO_EMOTION",
    "TAG_TO_SEX",
    "parse_stimulus_filename",
    "scan_audio_dir",
    # trial sequencing
    "build_trial_list",
    "summarize_stimuli",
    "StimulusBreakdown",
    # responses + timing
    "Response",
    "ReactionTime",
    "reaction_time",
    # scoring
    "GroupStats",
    "SessionSummary",
    "confusion_matrix",
    "summarize",
    # reaction-time quality control
    "RtFlag",
    "flag_responses",
    "scrub_flagged_rts",
    # session mode
    "SessionMode",
]
