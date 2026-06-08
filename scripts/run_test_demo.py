# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Developer demo: run a short Test-mode block end-to-end and print the results.

This wires the real pieces together -- scan stimuli, build the trial list, run the
PsychoPy Test window, then score with the UI-free core -- so we can eyeball that
responses and reaction times flow through correctly. It's a dev tool, not the app.

    .venv/bin/python scripts/run_test_demo.py        # 5 shuffled trials
"""

from __future__ import annotations

import os
import random
import sys

# 'emognition' importable from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Make PsychoPy safe BEFORE importing visual/sound (audio prefs + TextStim fix).
from emognition.runtime import bootstrap  # noqa: E402

bootstrap()

from psychopy import core, visual  # noqa: E402

from emognition.core import build_trial_list, scan_audio_dir, summarize  # noqa: E402
from emognition.ui.assets import Caption, audio_dir  # noqa: E402
from emognition.ui.experiment_window import (  # noqa: E402
    ExperimentAborted,
    TestExperiment,
)


def main() -> int:
    stimuli = scan_audio_dir(audio_dir())
    trials = build_trial_list(stimuli, shuffle=True, rng=random.Random(0))[:5]

    win = visual.Window(
        size=(1000, 700), color=(-0.3, -0.3, -0.3), units="height", fullscr=False
    )
    experiment = TestExperiment(win, caption=Caption.NONE)

    aborted = False
    try:
        responses = experiment.run(trials)
    except ExperimentAborted as abort:
        responses = getattr(abort, "partial", [])
        aborted = True
    finally:
        win.close()

    print(f"\n--- responses ({'ABORTED' if aborted else 'complete'}) ---")
    for i, r in enumerate(responses, start=1):
        chosen = r.responded.label if r.responded else "(none)"
        print(
            f"[{i}] {r.stimulus.filename:<16} true={r.true_emotion.label:<8} "
            f"chose={chosen:<8} correct={r.is_correct!s:<5} "
            f"RT_onset={r.rt_onset:6.3f}s  RT_offset={r.rt_offset:6.3f}s"
        )

    if responses:
        s = summarize(responses)
        print("\n--- summary ---")
        print(f"overall accuracy: {s.total.pct_correct:.0f}%  "
              f"mean RT (offset): {s.total.mean_rt:.3f}s")
        print("confusion matrix (rows=true, cols=chosen; "
              "order Happy,Scared,Neutral,Sad,Angry):")
        for emo, row in zip(s.emotion_order, s.confusion):
            print(f"  {emo.label:<8} {row}")
    core.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
