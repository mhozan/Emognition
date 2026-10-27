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

from emognition import __version__  # noqa: E402
from emognition.core import build_trial_list, summarize  # noqa: E402
from emognition.io import open_path  # noqa: E402
from emognition.naming import scan_stimuli  # noqa: E402
from emognition.reports import (  # noqa: E402
    SessionInfo,
    write_csv_report,
    write_excel_report,
    write_html_report,
)
from emognition.ui.assets import Caption, audio_dir  # noqa: E402
from emognition.ui.experiment_window import (  # noqa: E402
    ExperimentAborted,
    TestExperiment,
)


def main() -> int:
    stimuli = scan_stimuli(audio_dir())   # canonical (BIDS) and legacy names
    if not stimuli:
        print(f"No stimuli found in {audio_dir()}", file=sys.stderr)
        return 1
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
        onset = "  --  " if r.rt_onset is None else f"{r.rt_onset:6.3f}"
        offset = "  --  " if r.rt_offset is None else f"{r.rt_offset:6.3f}"
        print(
            f"[{i}] {r.stimulus.filename:<16} true={r.true_emotion.label:<8} "
            f"chose={chosen:<8} correct={r.is_correct!s:<5} "
            f"RT_onset={onset}s  RT_offset={offset}s"
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

        # Write all report formats next to each other, then open the HTML one.
        from datetime import datetime

        os.makedirs("save_location", exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = os.path.join("save_location", f"demo_{stamp}")
        info = SessionInfo(participant="DemoParticipant", experimenter="dev",
                           mode="Test", app_version=__version__,
                           started_at=datetime.now())
        html = write_html_report(responses, base + ".html", info=info)
        write_excel_report(responses, base + ".xlsx", info=info)
        write_csv_report(responses, base + ".csv")
        print(f"\nreports written to: {base}.{{html,xlsx,csv,_summary.csv}}")
        print(f"opening {html} ...")
        open_path(html)

    core.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
