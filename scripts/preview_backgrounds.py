# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Dev tool: capture the Begin screen and a trial frame over every background.

Run with:  DISPLAY=:0 .venv/bin/python scripts/preview_backgrounds.py [OUT_DIR]

Opens ONE windowed PsychoPy window for a few seconds (no audio is played),
saves PNGs (begin.png, trial-<name>.png) into OUT_DIR (default: ./previews),
and closes. Use it to check contrast/readability after changing a picture.
"""

from __future__ import annotations

import ctypes
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from emognition.runtime import bootstrap  # noqa: E402

bootstrap()   # before any psychopy.sound / visual import

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
from psychopy import visual  # noqa: E402
from pyglet import gl  # noqa: E402

from emognition.core import EMOTIONS_IN_ORDER, SessionMode  # noqa: E402
from emognition.core.backgrounds import CALM_GRADIENT, BackgroundPlan, list_pictures  # noqa: E402
from emognition.ui.assets import Caption, backgrounds_dir  # noqa: E402
from emognition.ui.backgrounds import BackgroundLayer  # noqa: E402
from emognition.ui.experiment_window import TestExperiment  # noqa: E402


def _grab(win: visual.Window, path: str) -> None:
    """Save the back buffer (call after drawing, before flipping)."""
    w, h = (int(v) for v in win.frameBufferSize)
    buf = (ctypes.c_ubyte * (w * h * 3))()
    gl.glFinish()
    gl.glReadPixels(0, 0, w, h, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
    frame = np.flipud(np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 3))
    Image.fromarray(frame).save(path)


def _show(win: visual.Window, draw, path: str) -> None:
    for _ in range(3):          # let textures settle on the GPU
        draw()
        win.flip()
    draw()
    _grab(win, path)
    win.flip()


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.getcwd(), "previews")
    os.makedirs(out, exist_ok=True)
    win = visual.Window(size=(1280, 800), color=(-0.3, -0.3, -0.3), units="height",
                        fullscr=False, allowGUI=True, screen=0)
    exp = TestExperiment(win, caption=Caption.ENGLISH, emotions=list(EMOTIONS_IN_ORDER),
                         mode=SessionMode.TEST, background=BackgroundPlan())
    exp._progress_frac = 0.4

    def begin_screen():
        exp.background.draw()
        exp._begin_button.draw()

    _show(win, begin_screen, os.path.join(out, "begin.png"))

    sources = [CALM_GRADIENT, *list_pictures(backgrounds_dir()), None]
    for source in sources:
        exp.background.close()
        exp.background = BackgroundLayer(win, BackgroundPlan(sources=() if source is None else (source,)))
        name = "none" if source is None else os.path.splitext(os.path.basename(source))[0].split(":")[-1]
        _show(win, lambda: exp._draw_scene(enabled=True), os.path.join(out, f"trial-{name}.png"))
    exp.close()
    win.close()
    print(f"Saved {len(sources) + 1} previews to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
