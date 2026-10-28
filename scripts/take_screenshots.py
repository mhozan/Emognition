# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Take screenshots of each UI panel and save to docs/screenshots/.

Run with (nothing is shown on screen):
    QT_QPA_PLATFORM=offscreen .venv/bin/python scripts/take_screenshots.py
"""
import sys
import os
import io
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt6.QtWidgets import QApplication
from PIL import Image, ImageDraw, ImageFont

from emognition.ui.config_window import configure_app

app = configure_app(QApplication(sys.argv[:1]))     # the app's own light theme
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

import tempfile

# A fresh settings file (none yet: the defaults), and placeholders for local paths.
w1 = ConfigWindow(settings_path=os.path.join(tempfile.mkdtemp(), "settings.json"))
w1.apply_settings(ExperimentSettings(
    participant="sub-001",
    experimenter="Researcher",
    audio_dir="<your audio folder>",
    save_dir="<your save folder>",
))
w1._refresh_resume()                 # the placeholder folder has no unfinished sessions
img = grab_widget(w1)
w1.close()
save(annotate(img, "Experimenter setup: configure participant, audio folder, mode, and emotions before each session."), "setup.png")


# ── 2. Calibration — four tabs ───────────────────────────────────────────────
from PyQt6.QtCore import QEventLoop, QTimer

from emognition.ui.assets import audio_dir
from emognition.ui.calibration_window import CalibrationWindow


def settle(window, timeout_ms: int = 30000) -> None:
    """Wait for the tab's background measurement (each tab measures when shown)."""
    loop, timer = QEventLoop(), QTimer()
    done = lambda: window._busy is None and not window._refresh_after_task  # noqa: E731
    timer.timeout.connect(lambda: done() and loop.quit())
    timer.start(20)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    timer.stop()
    for _ in range(3):
        app.processEvents()


w2 = CalibrationWindow(folder=audio_dir(), volume=0.8)
w2.resize(1280, 820)
w2.show()
for index, name, caption in (
    (0, "calibration_stimuli.png",
     "Stimuli / naming: what each file name says (emotion, speaker sex), how balanced the set is, "
     "and the manifest. Every tab explains its methods in the panel on the right."),
    (1, "calibration_clips.png",
     "Clip check: a card per recording (waveform, spectrogram, and the RMS curve the end-of-speech "
     "detector uses) with sanity flags; click one for the large view."),
    (2, "calibration_loudness.png",
     "Loudness & trim: every clip before and after calibration (duration, silence around the speech, "
     "loudness, peak); Apply writes a calibrated copy and measures it again."),
    (3, "calibration_tone.png",
     "SPL tone: a 1 kHz tone at the recordings' average level, played at the session's Volume, "
     "for setting the presentation level on a sound level meter."),
):
    w2.tabs.setCurrentIndex(index)
    settle(w2)
    w2.folder.setText("<your audio folder>")      # no local paths in the docs
    img = grab_widget(w2)
    w2.folder.setText(audio_dir())
    save(annotate(img, caption), name)
w2._wait_for_task()
w2.close()


# ── 3. Monitor window (mid-session data) ─────────────────────────────────────
from emognition.ui.monitor_window import MonitorWindow

w3 = MonitorWindow()
w3.show()
app.processEvents()
w3.handle_event({"status": "start", "total": 10, "mode": "test", "participant": "sub-001"})
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
