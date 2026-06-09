"""Take screenshots of each UI panel and save to docs/screenshots/."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv[:1])

out = os.path.join(os.path.dirname(__file__), "..", "docs", "screenshots")
os.makedirs(out, exist_ok=True)


def grab(widget, name):
    widget.show()
    app.processEvents()
    app.processEvents()
    pix = widget.grab()
    pix.save(os.path.join(out, name))
    print(f"Saved {name}")
    widget.close()
    app.processEvents()


# ── 1. Experimenter setup ────────────────────────────────────────────────────
from emognition.ui.config_window import ConfigWindow
from emognition.config import ExperimentSettings

w1 = ConfigWindow(settings_path="/dev/null")   # ignore saved settings
w1.apply_settings(ExperimentSettings(
    participant="P01",
    experimenter="Researcher",
    audio_dir="<your audio folder>",
    save_dir="<your save folder>",
))
grab(w1, "setup.png")

# ── 2. Calibration window ────────────────────────────────────────────────────
from emognition.ui.calibration_window import CalibrationWindow
w2 = CalibrationWindow()
# Clear the pre-filled folder so no local path shows.
w2.findChild(__import__('PyQt6.QtWidgets', fromlist=['QLineEdit']).QLineEdit).setText("")
grab(w2, "calibration.png")

# ── 3. Monitor window (seeded with mid-session data) ─────────────────────────
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
pix = w3.grab()
pix.save(os.path.join(out, "monitor.png"))
print("Saved monitor.png")
w3.close()

print("Done.")
sys.exit(0)
