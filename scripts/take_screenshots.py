# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Take screenshots of each UI panel and save to docs/screenshots/.

Run with:  DISPLAY=:0 .venv/bin/python scripts/take_screenshots.py
"""
import sys
import os
import io
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt6.QtWidgets import QApplication, QTabWidget
from PIL import Image, ImageDraw, ImageFont

app = QApplication(sys.argv[:1])
OUT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "docs", "screenshots"))
os.makedirs(OUT, exist_ok=True)


def grab_widget(widget) -> Image.Image:
    """Return a PIL Image of the widget's current appearance."""
    widget.show()
    app.processEvents()
    app.processEvents()
    pix = widget.grab()
    buf = pix.toImage()
    ba = __import__('PyQt6.QtCore', fromlist=['QByteArray']).QByteArray()
    buf2 = __import__('PyQt6.QtCore', fromlist=['QBuffer']).QBuffer(ba)
    buf2.open(__import__('PyQt6.QtCore', fromlist=['QIODevice']).QIODevice.OpenModeFlag.WriteOnly)
    buf.save(buf2, "PNG")
    return Image.open(io.BytesIO(bytes(ba)))


def annotate(img: Image.Image, text: str, position: str = "bottom") -> Image.Image:
    """Add a semi-transparent banner with wrapped *text* to top or bottom of *img*."""
    import textwrap
    img = img.convert("RGBA")
    w, h = img.size
    font_size = max(15, h // 28)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    # Wrap text to fit image width (estimate ~chars that fit).
    chars_per_line = max(40, w // (font_size // 2 + 1))
    lines = textwrap.wrap(text, width=chars_per_line)
    wrapped = "\n".join(lines)

    dummy = Image.new("RGBA", (1, 1))
    dc = ImageDraw.Draw(dummy)
    bbox = dc.textbbox((0, 0), wrapped, font=font)
    text_h = bbox[3] - bbox[1]
    bar_h = text_h + 18

    banner = Image.new("RGBA", (w, bar_h), (20, 20, 40, 210))
    draw = ImageDraw.Draw(banner)
    draw.text((12, 9), wrapped, font=font, fill=(220, 220, 255, 255))

    out = Image.new("RGBA", (w, h + bar_h))
    if position == "bottom":
        out.paste(img, (0, 0))
        out.paste(banner, (0, h), banner)
    else:
        out.paste(banner, (0, 0), banner)
        out.paste(img, (0, bar_h))
    return out.convert("RGB")


def save(img: Image.Image, name: str) -> None:
    path = os.path.join(OUT, name)
    img.save(path)
    print(f"Saved {name}")


# ── 1. Experimenter setup ────────────────────────────────────────────────────
from emognition.ui.config_window import ConfigWindow
from emognition.config import ExperimentSettings

w1 = ConfigWindow(settings_path="/dev/null")
w1.apply_settings(ExperimentSettings(
    participant="P01",
    experimenter="Researcher",
    audio_dir="<your audio folder>",
    save_dir="<your save folder>",
))
img = grab_widget(w1)
w1.close()
save(annotate(img, "Experimenter setup: configure participant, audio folder, mode, and emotions before each session."), "setup.png")


# ── 2. Calibration — three tabs ──────────────────────────────────────────────
from emognition.ui.calibration_window import CalibrationWindow
from emognition.ui.assets import audio_dir

w2 = CalibrationWindow()
w2.show()
app.processEvents()
tabs: QTabWidget = w2.findChild(QTabWidget)

# Replace local paths with a generic placeholder for all tabs.
for field in (w2.stim_dir, w2.loud_dir, w2.tone_dir):
    field.setText("<your audio folder>")
app.processEvents()

# Tab 0 — Stimuli / naming: load audio and inspect
tabs.setCurrentIndex(0)
w2.stim_dir.setText(audio_dir())   # real path needed to scan files
app.processEvents()
w2._inspect_stimuli()
w2.stim_dir.setText("<your audio folder>")  # restore placeholder for screenshot
app.processEvents()
app.processEvents()
img = grab_widget(w2)
save(annotate(img, "Stimuli / naming: inspect each clip's recognized emotion, sex, and recording ID. Rename legacy filenames to BIDS-style canonical form."), "calibration_stimuli.png")

# Tab 1 — Loudness & trim: preview normalization plan
tabs.setCurrentIndex(1)
w2.loud_dir.setText(audio_dir())
app.processEvents()
w2._preview_loudness()
w2.loud_dir.setText("<your audio folder>")
app.processEvents()
app.processEvents()
img = grab_widget(w2)
save(annotate(img, "Loudness & trim: preview per-clip gain, silence trim, and duration changes. Apply to write a loudness-normalized copy of the corpus."), "calibration_loudness.png")

# Tab 2 — SPL tone: no data to load, just the controls
tabs.setCurrentIndex(2)
app.processEvents()
img = grab_widget(w2)
save(annotate(img, "SPL tone: play a 1 kHz calibration tone matched to the corpus RMS so you can set booth SPL on a sound-level meter before the session."), "calibration_tone.png")

w2.close()


# ── 3. Monitor window (mid-session data) ─────────────────────────────────────
from emognition.ui.monitor_window import MonitorWindow

w3 = MonitorWindow()
w3.show()
app.processEvents()
w3.handle_event({"status": "start", "total": 10, "mode": "test", "participant": "P01"})
app.processEvents()

for i, (emotion, responded, correct, rt) in enumerate([
    ("happy",   "happy",   True,  780),
    ("sad",     "angry",   False, 1240),
    ("neutral", "neutral", True,  650),
    ("scared",  "scared",  True,  920),
    ("angry",   "sad",     False, 1100),
], start=1):
    w3.handle_event({"status": "trial", "index": i, "total": 10,
                     "emotion": emotion, "sex": "female",
                     "responded": responded, "correct": correct, "rt_ms": rt})
    app.processEvents()

app.processEvents()
img = grab_widget(w3)
w3.close()
save(annotate(img, "Experimenter monitor: live trial count, last response (correct/wrong), reaction time, and running accuracy — visible only to the experimenter."), "monitor.png")

print("All done.")
sys.exit(0)
