# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Dev tool: measure the CPU cost of drawing one experiment frame.

Run with:  DISPLAY=:0 .venv/bin/python scripts/bench_draw.py [FRAMES]

Reaction times are sampled once per frame, so a slow draw loop coarsens them.
This opens ONE window (no audio), alternates the two trial phases the way a
session does (buttons greyed during playback, active while waiting), and prints
how long the CPU spends inside ``_draw_scene()`` per frame plus PsychoPy's
dropped-frame count. It only uses the long-standing ``TestExperiment`` API, so
it can be pointed at an older checkout (PYTHONPATH=<checkout>) to compare.
"""

from __future__ import annotations

import os
import sys
import time

if "PYTHONPATH" not in os.environ:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from emognition.runtime import bootstrap  # noqa: E402

bootstrap()

import numpy as np  # noqa: E402
from psychopy import visual  # noqa: E402

from emognition.core import EMOTIONS_IN_ORDER  # noqa: E402
from emognition.ui.assets import Caption  # noqa: E402
from emognition.ui.experiment_window import TestExperiment  # noqa: E402


def main() -> int:
    frames = int(sys.argv[1]) if len(sys.argv) > 1 else 240
    win = visual.Window(size=(1280, 800), color=(-0.3, -0.3, -0.3), units="height",
                        fullscr=False, allowGUI=True, screen=0)
    exp = TestExperiment(win, caption=Caption.ENGLISH, emotions=list(EMOTIONS_IN_ORDER))
    for _ in range(30):                       # warm up textures / labels
        exp._draw_scene(enabled=True)
        win.flip()
    win.recordFrameIntervals = True
    costs = []
    for i in range(frames):
        enabled = (i // 60) % 2 == 1          # 1 s greyed, 1 s active, ...
        exp._progress_frac = i / frames
        t0 = time.perf_counter()
        exp._draw_scene(enabled=enabled)
        costs.append(time.perf_counter() - t0)
        win.flip()
    win.recordFrameIntervals = False
    ms = np.asarray(costs) * 1000.0
    print(f"draw CPU per frame: mean {ms.mean():.2f} ms, median {np.median(ms):.2f} ms, "
          f"p95 {np.percentile(ms, 95):.2f} ms, max {ms.max():.2f} ms  "
          f"| dropped frames: {win.nDroppedFrames} of {frames}")
    if hasattr(exp, "close"):
        exp.close()
    win.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
