# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Setup + monitor windows under Qt's offscreen platform (nothing is shown).

Covers the window lifecycle that once killed sessions (closing the monitor quit
the app), the background picker, and how the session's output is handled.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtCore = pytest.importorskip("PyQt6.QtCore")
QtWidgets = pytest.importorskip("PyQt6.QtWidgets")

from emognition.config import ExperimentSettings  # noqa: E402
from emognition.ui import config_window  # noqa: E402
from emognition.ui.config_window import ConfigWindow, configure_app  # noqa: E402
from emognition.ui.monitor_window import MonitorWindow  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return configure_app(QtWidgets.QApplication.instance() or QtWidgets.QApplication([]))


@pytest.fixture
def window(app, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))          # ~/.emognition lives in tmp
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    w = ConfigWindow(settings_path=str(tmp_path / "settings.json"))
    yield w
    w.hide()
    w.deleteLater()


def _run_until(app, steps, timeout_ms=3000):
    """Run the event loop through (delay_ms, action) steps; return the exit code."""
    for delay, action in steps:
        QtCore.QTimer.singleShot(delay, action)
    QtCore.QTimer.singleShot(timeout_ms, lambda: app.exit(99))
    return app.exec()


def test_closing_the_monitor_mid_session_keeps_the_app_alive(app, window):
    assert not app.quitOnLastWindowClosed()
    seen = []

    def start_session():
        window._monitor = MonitorWindow()
        window._monitor.show()
        window.hide()                                  # what Proceed does
        QtCore.QTimer.singleShot(100, window._monitor.close)

    code = _run_until(app, [(50, start_session), (500, lambda: (seen.append("alive"), app.exit(7)))])
    assert code == 7 and seen == ["alive"]


def test_closing_calibration_brings_the_setup_window_back(app, window):
    window.show()
    code = _run_until(app, [
        (50, window._open_calibration),
        (200, lambda: window._calib.close()),
        (600, lambda: app.exit(0 if window.isVisible() and window._calib is None else 1)),
    ])
    assert code == 0


def test_background_picker_round_trips_settings(window):
    labels = [window.background.itemText(i) for i in range(window.background.count())]
    assert labels[0] == "Calm gradient (default)" and labels[-2:] == ["Slideshow (all pictures)", "None (plain)"]
    assert window.slideshow_row.isHidden()                 # slideshow settings: only for a slideshow
    window.apply_settings(ExperimentSettings(background="slideshow", background_every=3,
                                             background_shuffle=False))
    assert not window.slideshow_row.isHidden() and window.bg_every.value() == 3
    s = window.settings_from_form()
    assert (s.background, s.background_every, s.background_shuffle) == ("slideshow", 3, False)


def test_add_picture_imports_and_selects_it(window, tmp_path, monkeypatch):
    from PIL import Image

    photo = tmp_path / "beach day.jpg"
    Image.new("RGB", (3000, 2000), (60, 120, 160)).save(photo)
    monkeypatch.setattr(config_window.QFileDialog, "getOpenFileNames",
                        lambda *a, **k: ([str(photo)], ""))
    window._add_pictures()
    chosen = window._background_value()
    assert chosen.endswith(os.path.join(".emognition", "backgrounds", "beach-day.jpg"))
    assert os.path.isfile(chosen) and "Added 1" in window.status.text()


def test_output_lines_reach_log_and_monitor(window, tmp_path):
    window._monitor = MonitorWindow()
    window._log_fh = open(tmp_path / "log.txt", "w", encoding="utf-8")
    window._handle_lines(['{"status": "waiting"}', "plain text",
                          '{"status": "begun", "total": 12}'])
    window._log_fh.close()
    window._log_fh = None
    assert window._monitor._lbl_trial.text() == "0 / 12"
    assert open(tmp_path / "log.txt", encoding="utf-8").read().splitlines()[1] == "plain text"


class _FakeProc:
    def __init__(self, code, crashed=False):
        self._code, self._crashed = code, crashed

    def exitCode(self):
        return self._code

    def exitStatus(self):
        status = QtCore.QProcess.ExitStatus
        return status.CrashExit if self._crashed else status.NormalExit


@pytest.mark.parametrize("proc, error, expect", [
    (_FakeProc(0), None, "finished."),
    (_FakeProc(3), None, "some reports failed"),
    (_FakeProc(1), None, "FAILED (exit 1)"),
    (_FakeProc(0, crashed=True), None, "CRASHED"),
    (_FakeProc(0), "Could not start the session: no such file", "Could not start"),
])
def test_outcome_messages_are_honest(window, proc, error, expect):
    window._proc, window._launch_error, window._participant = proc, error, "P01"
    window._show_outcome()
    assert expect in window.status.text()


# --- settings and participant-ID hygiene (Phase 3) -----------------------------

def test_default_folders_are_stored_as_defaults_not_absolute_paths(window):
    s = window.settings_from_form()               # first run: fields show bundled/default paths
    assert window.audio_dir.text() and s.audio_dir == "" and s.save_dir == ""
    window.audio_dir.setText("/data/my-clips")
    assert window.settings_from_form().audio_dir == "/data/my-clips"


def test_a_vanished_audio_folder_falls_back_to_the_bundled_clips(app, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    settings = tmp_path / "settings.json"
    ExperimentSettings(audio_dir=str(tmp_path / "old-install" / "assets" / "audio")).save(str(settings))
    w = ConfigWindow(settings_path=str(settings))
    assert "not found" in w.status.text()
    assert os.path.isdir(w.audio_dir.text())      # re-filled with the bundled folder


def test_the_next_free_id_is_filled_in_and_follows_recorded_sessions(window, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    window.save_dir.setText(str(out))
    window._on_save_dir_changed()
    assert window.participant.text() == "sub-001"
    (out / "sub-001_20261027_101500.csv").write_text("trial\n")
    window._proc, window._launch_error, window._participant = _FakeProc(0), None, "sub-001"
    window._show_outcome()
    assert window.participant.text() == "sub-002"            # recorded: on to the next one
    window.participant.setText("custom-7")
    window._proc = _FakeProc(1)
    window._show_outcome()
    assert window.participant.text() == "custom-7"           # failed: keep it for a retry


@pytest.mark.parametrize("clicked, expect", [
    ("Use sub-002", "sub-002"), ("Reuse sub-001", "sub-001"), ("Edit ID", None), (None, None),
])
def test_an_existing_id_offers_the_next_free_reuse_or_edit(window, tmp_path, clicked, expect):
    out = tmp_path / "reports"
    out.mkdir()
    s = ExperimentSettings(participant="sub-001", save_dir=str(out))
    asked = []
    window._choose = lambda *a: asked.append(a) or clicked
    assert window._resolve_existing_id(s) is s and not asked     # no reports yet: no question
    (out / "sub-001_20261027_101500.csv").write_text("trial\n")
    result = window._resolve_existing_id(s)
    assert (result.participant if result else None) == expect
    assert asked[0][3] == ["Use sub-002", "Reuse sub-001", "Edit ID"]
    if expect == "sub-002":
        assert window.participant.text() == "sub-002"


def test_another_participants_reports_are_not_a_reused_id(window, tmp_path):
    out = tmp_path / "reports"
    out.mkdir()
    (out / "P09_retest_20261027_101500.csv").write_text("trial\n")   # "P09_..." but not P09
    s = ExperimentSettings(participant="P09", save_dir=str(out))
    assert window._resolve_existing_id(s) is s


def _unfinished_log(folder, participant="P10"):
    from datetime import datetime

    from emognition.core import Emotion, Response, Sex, Stimulus
    from emognition.io.autosave import PARTIAL_SUFFIX, SessionLog

    path = str(folder / f"{participant}_20261027_101500{PARTIAL_SUFFIX}")
    log = SessionLog(path, {"participant": participant, "started_at": datetime(2026, 10, 27, 10, 15),
                            "trial_order": ["/c/a_hap_f.wav", "/c/b_sad_m.wav"]})
    log.append(Response(Stimulus("/c/a_hap_f.wav", Emotion.HAPPY, Sex.FEMALE), Emotion.HAPPY, 1.2, 0.3))
    log.close()
    return path


@pytest.mark.parametrize("clicked, expect", [("Resume", "log"), ("Start new", ""), (None, None)])
def test_an_unfinished_session_is_offered_for_resume(window, tmp_path, clicked, expect):
    out = tmp_path / "reports"
    out.mkdir()
    s = ExperimentSettings(participant="P10", save_dir=str(out))
    asked = []
    window._choose = lambda *a: asked.append(a) or clicked
    assert window._ask_resume(s) == "" and not asked               # nothing unfinished: no question
    log = _unfinished_log(out)
    assert window._ask_resume(s) == (log if expect == "log" else expect)
    assert "1 of 2 trials" in asked[0][1]


def test_resuming_launches_with_the_log_and_only_the_display(window, tmp_path, monkeypatch):
    out = tmp_path / "reports"
    out.mkdir()
    log = _unfinished_log(out)
    launched = []

    class _NoStart(QtCore.QProcess):              # record the command instead of running it
        def start(self, *args):
            launched.append(list(self.arguments()))

    monkeypatch.setattr(config_window, "QProcess", _NoStart)
    monkeypatch.setattr(window, "_should_open_monitor", lambda: False)
    window._choose = lambda *a: "Resume"
    window.participant.setText("P10")
    window.save_dir.setText(str(out))
    window._on_proceed()
    window._log_fh.close()
    (args,) = launched
    assert f"--resume={log}" in args
    assert not any(a.startswith(("--participant", "--mode", "--emotions")) for a in args)


# --- calibration window: heavy work off the GUI thread (Phase 3) ----------------

def _wait(app, predicate, timeout_ms=20000):
    """Spin the event loop until *predicate()* is true (or time runs out)."""
    loop = QtCore.QEventLoop()
    timer = QtCore.QTimer()
    timer.timeout.connect(lambda: predicate() and loop.quit())
    timer.start(20)
    QtCore.QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    timer.stop()
    return predicate()


@pytest.fixture
def calib(app, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from emognition.ui.calibration_window import CalibrationWindow

    w = CalibrationWindow()
    yield w
    w._wait_for_task()
    w.deleteLater()


def test_preview_and_apply_run_in_the_background(app, calib, tmp_path):
    import shutil

    from emognition.ui.assets import audio_dir

    src = tmp_path / "in"
    src.mkdir()
    for name in sorted(os.listdir(audio_dir()))[:2]:
        if name.endswith(".wav"):
            shutil.copy(os.path.join(audio_dir(), name), src / name)
    calib.loud_dir.setText(str(src))
    calib._preview_loudness()
    assert calib._busy is not None and "Analysing" in calib.loud_status.text()   # returned at once
    assert _wait(app, lambda: calib._busy is None and calib.loud_table.rowCount() == 2)
    calib._apply_loudness()
    assert _wait(app, lambda: calib.loud_status.text().startswith("Wrote 2 files"))
    assert (tmp_path / "in_calibrated" / "calibration.json").exists()


def test_unreadable_folder_is_reported_not_fatal(app, calib, tmp_path):
    calib.loud_dir.setText(str(tmp_path / "does-not-exist"))
    calib._preview_loudness()
    assert _wait(app, lambda: calib.loud_status.text().startswith("Nothing written"))
    calib._apply_loudness()                       # no plan yet: explains instead of crashing
    assert "Preview first" in calib.loud_status.text()


def test_audio_package_no_longer_loads_scipy_at_import():
    import subprocess
    import sys

    code = "import sys, emognition.audio; print('scipy' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert out.stdout.strip() == "False", out.stderr


# --- monitor events (Phase 4) ---------------------------------------------------

def test_monitor_tracks_trials_badges_and_final_accuracy(app):
    m = MonitorWindow()
    m.handle_event({"status": "start", "total": 3, "mode": "active", "participant": "P1"})
    m.handle_event({"status": "trial", "index": 1, "total": 3, "emotion": "happy", "sex": "female",
                    "responded": "happy", "correct": True, "rt_ms": 640})
    m.handle_event({"status": "trial", "index": 2, "total": 3, "emotion": "sad", "sex": "male",
                    "responded": "angry", "correct": False, "rt_ms": 900})
    assert m._lbl_trial.text() == "2 / 3" and m._lbl_rt.text() == "900 ms"
    assert "1 / 2" in m._lbl_accuracy.text() and m._lbl_responded.objectName() == "wrong_badge"
    m.handle_event({"status": "trial", "index": 3, "total": 3, "responded": None, "correct": None})
    assert m._lbl_responded.objectName() == "neutral_badge" and m._lbl_responded.text() == "(passive)"
    m.handle_event({"status": "done", "n_correct": 1, "n_trials": 3, "n_answered": 2, "aborted": True})
    assert "1 / 2" in m._lbl_accuracy.text() and "aborted" in m._lbl_trial.text()


def test_monitor_carries_counts_across_a_resume(app):
    m = MonitorWindow()
    m.handle_event({"status": "start", "total": 20, "mode": "test", "participant": "P1",
                    "done": 7, "n_correct": 5, "n_answered": 7})
    assert m._lbl_trial.text() == "7 / 20" and "5 / 7" in m._lbl_accuracy.text()
    m.handle_event({"status": "begun", "total": 20, "done": 7})
    assert m._lbl_trial.text() == "7 / 20"
    m.handle_event({"status": "trial", "index": 8, "total": 20, "emotion": "happy", "sex": "female",
                    "responded": "happy", "correct": True, "rt_ms": 500})
    assert m._lbl_trial.text() == "8 / 20" and "6 / 8" in m._lbl_accuracy.text()


def test_mode_options_show_only_in_their_modes(window):
    window.mode.setCurrentText("Test")
    assert window.retry.isHidden() and window.practice_row.isHidden()
    window.mode.setCurrentText("Passive Training")
    assert window.retry.isHidden() and not window.practice_row.isHidden()
    window.mode.setCurrentText("Active Training")
    assert not window.retry.isHidden() and not window.practice_row.isHidden()
    window.retry.setChecked(True)
    s = window.settings_from_form()
    assert s.mode == "active" and s.retry_until_correct
    window.apply_settings(ExperimentSettings(mode="test", retry_until_correct=False))
    assert not window.retry.isChecked() and window.retry.isHidden()


def test_replay_limit_starts_at_the_number_of_emotions(window):
    assert window.replay_limit_row.isHidden()                # replays off by default
    for tag in ("sca", "neu", "ang"):                        # happy vs sad
        window.emotion_boxes[tag].setChecked(False)
    window.allow_replays.setChecked(True)
    assert not window.replay_limit_row.isHidden() and window.max_replays.limit == 2
    window.emotion_boxes["ang"].setChecked(True)             # follows the emotions...
    assert window.max_replays.limit == 3
    window.max_replays.setValue(5)                           # ...until the experimenter sets it
    window.emotion_boxes["neu"].setChecked(True)
    assert window.max_replays.limit == 5 and window.settings_from_form().max_replays == 5
    window.max_replays.setValue(window.max_replays.NO_LIMIT)
    assert window.max_replays.text() == "no limit" and window.settings_from_form().max_replays == 0


def test_resume_button_lists_unfinished_sessions(window, tmp_path, monkeypatch):
    out = tmp_path / "reports"
    out.mkdir()
    window.save_dir.setText(str(out))
    window._on_save_dir_changed()
    assert not window.resume_btn.isEnabled()
    log = _unfinished_log(out, participant="sub-007")
    window._on_save_dir_changed()
    assert window.resume_btn.isEnabled() and window.resume_btn.text() == "Resume... (1)"
    offered, launched = [], []
    monkeypatch.setattr(config_window.QInputDialog, "getItem",
                        lambda *a: offered.append(a[3]) or (a[3][0], True))
    monkeypatch.setattr(window, "_launch", lambda settings, resume="": launched.append((settings, resume)))
    window._resume_dialog()
    assert "sub-007" in offered[0][0] and "1 of 2 trials" in offered[0][0]
    (settings, resume), = launched
    assert resume == log and settings.participant == "sub-007"


def test_pacing_controls_round_trip_and_read_off_at_zero(window):
    assert window.stars_every.text() == "off" and window.break_every.text() == "off"
    assert window.practice.text() == "off" and window.max_run.text() == "off"
    window.apply_settings(ExperimentSettings(next_button=True, stars_every=5, break_every=10,
                                             max_run=2, practice=3))
    s = window.settings_from_form()
    assert (s.next_button, s.stars_every, s.break_every) == (True, 5, 10)
    assert (s.max_run, s.practice) == (2, 3)


def test_monitor_counts_practice_trials_separately(app):
    m = MonitorWindow()
    m.handle_event({"status": "start", "total": 10, "mode": "test", "participant": "P1"})
    m.handle_event({"status": "practice", "index": 2, "total": 3, "correct": True})
    assert m._lbl_trial.text() == "Practice 2 / 3" and m._lbl_accuracy.text() == "Accuracy:  —"


def test_monitor_shows_a_break(app):
    m = MonitorWindow()
    m.handle_event({"status": "trial", "index": 10, "total": 30, "responded": "sad", "correct": True})
    m.handle_event({"status": "paused", "reason": "break"})
    assert m._lbl_trial.text() == "Break"
    m.handle_event({"status": "resumed"})
    assert m._lbl_trial.text() == "10 / 30"


def test_monitor_shows_retries_on_the_badge(app):
    m = MonitorWindow()
    m.handle_event({"status": "start", "total": 2, "mode": "active", "participant": "P1"})
    m.handle_event({"status": "trial", "index": 1, "total": 2, "emotion": "sad", "sex": "female",
                    "responded": "angry", "correct": False, "rt_ms": 700, "attempts": 3})
    assert m._lbl_responded.text().endswith("(3 tries)")


def test_monitor_shows_a_pause_and_puts_the_counter_back(app):
    m = MonitorWindow()
    m.handle_event({"status": "start", "total": 10, "mode": "test", "participant": "P1"})
    m.handle_event({"status": "trial", "index": 3, "total": 10, "responded": "sad", "correct": True})
    m.handle_event({"status": "paused", "reason": "pause"})
    assert m._lbl_trial.text() == "Paused"
    m.handle_event({"status": "paused", "reason": "quit"})       # still held: counter kept
    assert m._lbl_trial.text() == "Quit?"
    m.handle_event({"status": "resumed"})
    assert m._lbl_trial.text() == "3 / 10"


def test_monitor_shrugs_off_unknown_or_odd_events(app):
    m = MonitorWindow()
    m.handle_event({"status": "something-new"})
    m.handle_event({})
    m.handle_event({"status": "trial", "index": 1, "total": 0})     # used to divide by zero
    assert m._lbl_trial.text() == "1 / 0"


# --- one readable theme, whatever the desktop's (ui/theme.py) -----------------------

def test_theme_overrides_a_dark_desktop_palette(app):
    from PyQt6.QtGui import QColor, QPalette

    from emognition.ui.theme import apply_theme

    dark = QPalette()
    for role in (QPalette.ColorRole.Window, QPalette.ColorRole.Base, QPalette.ColorRole.Button):
        dark.setColor(role, QColor("#202020"))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        dark.setColor(role, QColor("#f0f0f0"))
    app.setPalette(dark)                     # what a dark desktop theme hands Qt
    apply_theme(app)
    p, R, G = app.palette(), QPalette.ColorRole, QPalette.ColorGroup
    assert p.color(R.Base).lightness() > 240 and p.color(R.Window).lightness() > 230
    assert p.color(R.Text).lightness() < 60 and p.color(R.ButtonText).lightness() < 60
    assert p.color(G.Disabled, R.Text) != p.color(G.Active, R.Text)   # greyed, visibly
    assert p.color(R.ToolTipBase).lightness() < 80 and p.color(R.ToolTipText).lightness() > 240
