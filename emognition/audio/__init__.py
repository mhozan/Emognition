# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Audio preprocessing for the soundbooth: loudness normalization + endpoint trim.

Run by the experimenter (via Calibration) BEFORE a session to turn a raw set of
recordings into a calibrated stimulus set:

* equalise *perceived loudness* across clips (LUFS / ITU-R BS.1770), so no clip
  is startlingly louder than another; and
* detect where speech actually starts and ends in each clip and trim the silence,
  so a reaction time measured from audio offset reflects the true end of speech.

Everything here is UI-free and unit-tested. The :mod:`.preprocess` module builds
a *plan* (what would change, per file) that the Calibration UI shows for
confirmation, then *applies* it to a new ``*_calibrated`` folder (originals are
never modified).
"""

from .loudness import NormalizationMethod, apply_gain, gain_db_to_target, measure
from .endpoints import detect_endpoints, trim_samples
from .preprocess import ClipPlan, BatchPlan, plan_batch, apply_plan

__all__ = [
    "NormalizationMethod",
    "measure",
    "gain_db_to_target",
    "apply_gain",
    "detect_endpoints",
    "trim_samples",
    "ClipPlan",
    "BatchPlan",
    "plan_batch",
    "apply_plan",
]
