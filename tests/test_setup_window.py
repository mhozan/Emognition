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
    assert not window.bg_every.isEnabled()
    window.apply_settings(ExperimentSettings(background="slideshow", background_every=3,
                                             background_shuffle=False))
    assert window.bg_every.isEnabled() and window.bg_every.value() == 3
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
