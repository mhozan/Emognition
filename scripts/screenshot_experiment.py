# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Capture a screenshot of the experiment response screen.

Run with:  DISPLAY=:0 .venv/bin/python scripts/screenshot_experiment.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

OUT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "docs", "screenshots"))

# Bootstrap must come before any psychopy.sound / psychopy.visual import.
from emognition.runtime import bootstrap
bootstrap()

from psychopy import visual
from emognition.core.backgrounds import SPEC_DEFAULT, resolve_background
from emognition.core.emotions import EMOTIONS_IN_ORDER
from emognition.ui.assets import Caption, background_folders
from emognition.ui.experiment_window import TestExperiment
from emognition.core import SessionMode

# Open a windowed (non-fullscreen) window at a fixed size.
# allowGUI=True keeps the window manager border; screen=0 keeps it on the
# primary display where PIL.ImageGrab can reach it.
win = visual.Window(
    size=(1280, 800),
    fullscr=False,
    color=(-0.3, -0.3, -0.3),   # the session window's own settings (app.py)
    units="height",
    title="Emognition",
    allowGUI=True,
    screen=0,
)

# Build a TestExperiment in Test mode with English captions, all 5 emotions,
# over the default background (the calm gradient), with replays allowed so the
# replay button is in the picture.
exp = TestExperiment(
    win,
    caption=Caption.ENGLISH,
    emotions=list(EMOTIONS_IN_ORDER),
    mode=SessionMode.TEST,
    background=resolve_background(SPEC_DEFAULT, picture_folders=background_folders()),
    allow_replays=True,
    max_replays=5,
)

# Simulate mid-session state: 4 of 10 trials done.
exp._progress_frac = 0.4

# Draw several times so textures are fully uploaded to the GPU.
for _ in range(5):
    exp._draw_scene(enabled=True)
    win.flip()

# Read the back buffer with glReadPixels before the next flip.
exp._draw_scene(enabled=True)

import numpy as np
import ctypes
from pyglet.gl import (
    glReadPixels, glFinish,
    GL_RGB, GL_UNSIGNED_BYTE,
)

w_px, h_px = win.size  # actual pixel dimensions
buf = (ctypes.c_ubyte * (w_px * h_px * 3))()
glFinish()
glReadPixels(0, 0, w_px, h_px, GL_RGB, GL_UNSIGNED_BYTE, buf)

arr = np.frombuffer(buf, dtype=np.uint8).reshape((h_px, w_px, 3))
arr = np.flipud(arr)   # OpenGL origin is bottom-left

from PIL import Image as _PILImage
img_raw = _PILImage.fromarray(arr, "RGB")
img_raw.save(os.path.join(OUT, "experiment_raw.png"))
win.close()

# Annotate with PIL.
import textwrap
from PIL import Image, ImageDraw, ImageFont

img = Image.open(os.path.join(OUT, "experiment_raw.png"))
w, h = img.size
font_size = max(15, h // 28)
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
except Exception:
    font = ImageFont.load_default()

text = ("Experiment screen: participant hears a speech clip, then clicks "
        "the emotion they perceived. Buttons activate only after the clip ends; "
        "the replay button (bottom left) appears when replays are allowed.")
chars_per_line = max(40, w // (font_size // 2 + 1))
wrapped = "\n".join(textwrap.wrap(text, width=chars_per_line))

dummy = Image.new("RGBA", (1, 1))
dc = ImageDraw.Draw(dummy)
bbox = dc.textbbox((0, 0), wrapped, font=font)
bar_h = (bbox[3] - bbox[1]) + 18

banner = Image.new("RGBA", (w, bar_h), (20, 20, 40, 210))
draw = ImageDraw.Draw(banner)
draw.text((12, 9), wrapped, font=font, fill=(220, 220, 255, 255))

out_img = Image.new("RGB", (w, h + bar_h))
out_img.paste(img.convert("RGB"), (0, 0))
out_img.paste(banner.convert("RGB"), (0, h))
out_img.save(os.path.join(OUT, "experiment.png"))
os.remove(os.path.join(OUT, "experiment_raw.png"))

print(f"Saved experiment.png ({w}x{h + bar_h})")
sys.exit(0)
