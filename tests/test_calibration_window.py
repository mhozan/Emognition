# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""The Calibration window under Qt's offscreen platform (nothing is shown or played).

Heavy work runs off the GUI thread; the clip check flags what it should; the
charts are fed predicted values, then measured ones; the SPL tone is launched
at the session's Volume; and the explanations carry the folder's own numbers.
"""

import math
import os
import shutil

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtCore = pytest.importorskip("PyQt6.QtCore")
QtGui = pytest.importorskip("PyQt6.QtGui")
QtWidgets = pytest.importorskip("PyQt6.QtWidgets")

from emognition.audio import average_rms  # noqa: E402
from emognition.ui import calibration_window  # noqa: E402
from emognition.ui.assets import audio_dir  # noqa: E402
from emognition.ui.calibration_charts import nice_ticks, range_text, summary_lines  # noqa: E402
from emognition.ui.calibration_help import clips_help, tone_numbers  # noqa: E402
from emognition.ui.config_window import configure_app  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return configure_app(QtWidgets.QApplication.instance() or QtWidgets.QApplication([]))


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
    w = calibration_window.CalibrationWindow(volume=0.6)
    yield w
    w.clip_check.shutdown()
    w._wait_for_task()
    w.deleteLater()


@pytest.fixture
def two_clips(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    for name in sorted(n for n in os.listdir(audio_dir()) if n.endswith(".wav"))[:2]:
        shutil.copy(os.path.join(audio_dir(), name), src / name)
    return src


def _bundled_wavs():
    return sorted(os.path.join(audio_dir(), n) for n in os.listdir(audio_dir()) if n.endswith(".wav"))


# -- Loudness & trim ---------------------------------------------------------------

def test_preview_and_apply_run_in_the_background(app, calib, two_clips, tmp_path):
    calib.folder.setText(str(two_clips))
    calib._preview_loudness()
    assert calib._busy is not None and "Analysing" in calib.loud_status.text()   # returned at once
    assert _wait(app, lambda: calib._busy is None and calib.loud_table.rowCount() == 2)
    assert not calib.strip.measured and len(calib.strip.metrics) == 5            # predicted
    assert "In this folder" in calib.loud_help.toPlainText()                     # its own numbers
    calib._apply_loudness()
    assert _wait(app, lambda: calib.loud_status.text().startswith("Wrote 2 files"))
    assert (tmp_path / "in_calibrated" / "calibration.json").exists()
    assert calib.strip.measured                                     # measured in the written files
    by = {m.key: m for m in calib.strip.metrics}
    assert max(by["loudness"].after) - min(by["loudness"].after) < 0.5      # equal loudness, really
    assert max(by["tail"].after) <= 110                             # the 100 ms pad (+ one frame)
    assert not calib.use_calibrated.isHidden()
    calib._use_calibrated()
    assert calib.folder.text() == str(tmp_path / "in_calibrated")


def test_unreadable_folder_is_reported_not_fatal(app, calib, tmp_path):
    calib.folder.setText(str(tmp_path / "does-not-exist"))
    calib._preview_loudness()
    assert _wait(app, lambda: calib.loud_status.text().startswith("Nothing written"))
    calib._apply_loudness()                       # no plan yet: explains instead of crashing
    assert "Preview first" in calib.loud_status.text()


def test_strip_chart_hover_names_the_clip(app, calib, two_clips):
    calib.folder.setText(str(two_clips))
    calib._preview_loudness()
    assert _wait(app, lambda: calib._busy is None and calib.strip.metrics)
    strip = calib.strip
    strip.resize(900, 440)
    assert not strip.grab().isNull()                              # paints (and records its dots)
    x, y, panel, clip, row = strip._points[0]
    move = QtGui.QMouseEvent(QtCore.QEvent.Type.MouseMove, QtCore.QPointF(x + 3, y), QtCore.QPointF(x + 3, y),
                             QtCore.Qt.MouseButton.NoButton, QtCore.Qt.MouseButton.NoButton,
                             QtCore.Qt.KeyboardModifier.NoModifier)
    strip.mouseMoveEvent(move)                                    # within the 24 px hit target
    assert strip._hover == clip
    assert strip.metrics[panel].names[clip] in strip._tip(panel, clip, row)


# -- Clip check -------------------------------------------------------------------------

def _clipped_clip(folder):
    import soundfile as sf

    t = np.arange(11025) / 22050.0                                # 0.5 s of a too-loud tone
    loud = np.clip(1.5 * np.sin(2 * math.pi * 440 * t), -1.0, 1.0)
    sf.write(folder / "zz_clipped.wav", np.concatenate([np.zeros(4410), loud, np.zeros(4410)]), 22050)


def test_clip_check_lists_every_clip_flagged_first_and_shows_one_in_full(app, calib, two_clips):
    from emognition.audio.analysis import ClipAnalysis

    _clipped_clip(two_clips)
    cc = calib.clip_check
    cc.refresh(str(two_clips))
    assert _wait(app, lambda: not cc.busy and cc.table_model.rowCount() == 3)
    first = cc.proxy.mapToSource(cc.proxy.index(0, 0)).row()
    assert cc.table_model.clips[first].filename == "zz_clipped.wav"           # flagged first
    assert {f.key for f in cc.table_model.flags[first]} >= {"clipped", "rate"}  # 22.05 kHz among 44.1
    assert _wait(app, lambda: cc.detail.clip is not None)
    assert cc.detail.clip.filename == "zz_clipped.wav" and isinstance(cc.detail.clip, ClipAnalysis)
    text = cc.status.text()
    assert "3 clips" in text and "1 flagged" in text and "checked in" in text
    cc.flagged_only.setChecked(True)
    assert cc.proxy.rowCount() == 1
    cc.flagged_only.setChecked(False)
    cc.table.setCurrentIndex(cc.proxy.index(1, 0))                              # another clip
    assert _wait(app, lambda: cc.detail.clip is not None and cc.detail.clip.filename != "zz_clipped.wav")
    assert "about" in cc.deep_btn.text()                                         # with an estimate
    cc.table.resize(900, 300)
    assert not cc.table.grab().isNull()                                          # waveforms paint


def test_deep_analysis_makes_a_card_per_clip(app, calib, two_clips):
    cc = calib.clip_check
    cc.refresh(str(two_clips))
    assert _wait(app, lambda: not cc.busy and cc.table_model.rowCount() == 2)
    cc.start_deep_analysis()
    assert cc.stack.currentIndex() == 1                                          # the Cards view
    assert _wait(app, lambda: not cc.busy)
    assert cc.cards_model.rowCount() == 2 and cc.deep_btn.text() == "Deep analysis (done)"
    cc.cards.resize(800, 400)
    assert not cc.cards.grab().isNull()
    cc.cards.setCurrentIndex(cc.cards_model.index(1, 0))                        # a card shows its clip
    path = cc.table_model.clips[cc.cards_model.rows[1]].path
    assert _wait(app, lambda: cc.detail.clip is not None and cc.detail.clip.path == path)


def test_deep_analysis_can_be_cancelled(app, calib, two_clips, monkeypatch):
    import time as _time

    from emognition.ui import clip_check

    slow = clip_check.analyse_clip
    monkeypatch.setattr(clip_check, "analyse_clip", lambda path: (_time.sleep(0.2), slow(path))[1])
    cc = calib.clip_check
    cc.refresh(str(two_clips))
    assert _wait(app, lambda: cc._check_job is None and cc.table_model.rowCount() == 2)
    cc.start_deep_analysis()
    cc.cancel_deep_analysis()
    assert _wait(app, lambda: cc._deep_job is None)
    assert "cancelled" in cc.status.text() and cc.cards_model.rowCount() <= 2


def test_play_runs_the_helper_and_moves_the_playhead(app, calib, two_clips, monkeypatch, tmp_path):
    import sys
    import textwrap

    from emognition.ui import audition

    script = tmp_path / "fake_player.py"                          # speaks --audition's protocol
    script.write_text(textwrap.dedent("""
        import json, sys
        print(json.dumps({"status": "ready"}), flush=True)
        for raw in sys.stdin.buffer:
            command, _, arg = raw.decode().strip().partition(" ")
            if command == "play":
                print(json.dumps({"status": "playing", "path": arg, "duration": 0.6}), flush=True)
            elif command == "stop":
                print(json.dumps({"status": "stopped", "path": arg}), flush=True)
            elif command == "quit":
                break
    """), encoding="utf-8")
    monkeypatch.setattr(audition, "self_command", lambda argv: [sys.executable, str(script), *argv])
    cc = calib.clip_check
    cc.refresh(str(two_clips))
    assert _wait(app, lambda: cc.detail.clip is not None)
    cc.toggle_play()
    assert _wait(app, lambda: cc.detail._playhead is not None)                # the playhead moves
    assert cc.play_btn.text().startswith("\u25a0") and "Volume 0.60" in cc.play_status.text()
    cc.toggle_play()                                                              # Stop
    assert _wait(app, lambda: cc.play_btn.text().startswith("\u25b6") and cc.detail._playhead is None)
    cc.toggle_play()                                                              # again, then
    assert _wait(app, lambda: cc.detail._playhead is not None)

    class _NoStart(QtCore.QProcess):                              # the tone, not really played
        def start(self, *args):
            pass

    monkeypatch.setattr(calibration_window, "QProcess", _NoStart)
    calib._start_tone(0.05)
    assert not cc.player.running                                  # the tone gets the audio device


# -- Stimuli / naming ----------------------------------------------------------------

def test_inspect_counts_the_balance(app, calib):
    calib.folder.setText(audio_dir())
    calib._inspect_stimuli()
    assert dict(calib.balance._rows) == {e: (1, 1) for e in ("Happy", "Scared", "Neutral", "Sad", "Angry")}
    assert calib.balance._series == ("Female", "Male")       # no clip of unknown sex: no third bar
    calib.balance.resize(360, 240)
    assert not calib.balance.grab().isNull()


# -- SPL tone ------------------------------------------------------------------------

def test_tone_plays_at_the_session_volume(app, calib, monkeypatch):
    launched = []

    class _NoStart(QtCore.QProcess):              # record the command instead of playing
        def start(self, *args):
            launched.append(list(self.arguments()))

    monkeypatch.setattr(calibration_window, "QProcess", _NoStart)
    calib.folder.setText(audio_dir())
    calib._play_tone()                            # measures first, then plays
    assert _wait(app, lambda: launched)
    (args,) = launched
    assert args[args.index("--volume") + 1] == "0.60"
    assert float(args[args.index("--tone-rms") + 1]) == pytest.approx(average_rms(_bundled_wavs()), rel=1e-3)
    assert "Volume 0.60" in calib.tone_level.text()
    assert "This folder" in calib.tone_help.toPlainText()


def test_tone_numbers_add_the_volume_in_db():
    text = tone_numbers(0.1, 0.5)                 # -20 dBFS, and -6.0 dB of Volume
    assert "−20.0" in text and "−26.0" in text and "−6.0 dB" in text


# -- the pieces ----------------------------------------------------------------------

def test_nice_ticks_are_round_and_cover_the_range():
    assert nice_ticks(0.0, 1.92, 6) == [0.0, 0.5, 1.0, 1.5, 2.0]
    assert nice_ticks(-35.5, -20.2, 4) == [-40.0, -35.0, -30.0, -25.0, -20.0]
    assert nice_ticks(100.0, 100.0)[0] < 100.0 < nice_ticks(100.0, 100.0)[-1]   # a single value


def test_ranges_and_the_summary_read_well():
    from emognition.audio.review import Metric

    assert range_text(188.4, 276.2, "ms") == "188–276"
    assert range_text(-35.5, -20.2, "dB") == "−35.5 to −20.2"
    loud = Metric("loudness", "Loudness", "LUFS", ("a", "b"), (-30.0, -20.0), (-23.0, -24.0),
                  reference=-23.0, limited=(False, True))
    lines = summary_lines([loud])
    assert lines[0] == "Loudness spread: 10.0 → 1.0 LU" and lines[-1] == "1 clip peak-limited"


def test_the_explanations_quote_the_detectors_constants():
    text = clips_help()
    assert "40 dB below the loudest frame" in text and "25 ms Hann" in text
