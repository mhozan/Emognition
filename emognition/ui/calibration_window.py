# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""The experimenter Calibration window (PyQt6): naming, loudness/trim, SPL tone.

Tabs:
  * Stimuli   -- inspect a folder; per-file recording_id/emotion/sex + unrecognized
                 flags; write stimuli.tsv + stimuli.json; rename legacy -> canonical.
                 (wraps emognition.naming)
  * Loudness & trim -- preview the per-file normalize/trim plan, then apply to a
                 *_calibrated folder. (wraps emognition.audio)
  * SPL tone  -- play a 1 kHz tone matched to the folder's RMS for booth dB setup
                 (played via a subprocess so audio never touches this Qt process).

All file operations are non-destructive (originals untouched except the explicit
rename, which records the originals via the manifest first).
"""

from __future__ import annotations

import os
import sys

from PyQt6.QtCore import QObject, QProcess, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..audio import NormalizationMethod, apply_plan, average_rms, plan_batch
from ..naming import (
    apply_rename_plan,
    build_manifest,
    canonical_rename_plan,
    merge_manifest,
    read_manifest_tsv,
    write_data_dictionary,
    write_manifest,
)
from .assets import audio_dir, self_command
from .theme import apply_theme


def _table(headers: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setStretchLastSection(True)
    t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    return t


def _fill(table: QTableWidget, rows: list[list[str]]) -> None:
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            table.setItem(r, c, QTableWidgetItem(val))


def _folder_row(line: QLineEdit, on_browse) -> QWidget:
    box = QHBoxLayout()
    browse = QPushButton("Browse...")
    browse.clicked.connect(on_browse)
    box.addWidget(line); box.addWidget(browse)
    w = QWidget(); w.setLayout(box)
    return w


class _Task(QObject):
    """Runs one function on a worker thread and reports the outcome.

    Reading and writing a whole folder of recordings takes seconds; on the GUI
    thread that froze the window. The signals are connected to *methods of the
    window* (a QObject living on the GUI thread), so Qt delivers them there as
    queued calls -- widgets are only ever touched from the GUI thread.
    """

    done = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, fn) -> None:
        super().__init__()
        self._fn = fn

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:  # noqa: BLE001 -- reported to the experimenter
            self.failed.emit(str(exc) or exc.__class__.__name__)
        else:
            self.done.emit(result)


def _wavs(folder: str) -> list[str]:
    """The .wav files in *folder*, sorted (raises OSError if it can't be listed)."""
    return sorted(
        os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(".wav")
    )


class CalibrationWindow(QWidget):
    """Tabbed calibration tools for the experimenter."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Emognition - Calibration")
        self.resize(820, 560)
        self._tone_proc: QProcess | None = None
        self._tone_stopping = False
        self._busy: tuple[QThread, _Task] | None = None   # the one background task

        tabs = QTabWidget()
        tabs.addTab(self._stimuli_tab(), "Stimuli / naming")
        tabs.addTab(self._loudness_tab(), "Loudness && trim")
        tabs.addTab(self._tone_tab(), "SPL tone")
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)

    # -- Stimuli / naming -------------------------------------------------

    def _stimuli_tab(self) -> QWidget:
        self.stim_dir = QLineEdit(audio_dir())
        self.stim_table = _table(["File", "Recording ID", "Emotion", "Sex", "Status"])
        self.stim_status = QLabel("")

        inspect = QPushButton("Inspect")
        inspect.clicked.connect(self._inspect_stimuli)
        write = QPushButton("Write stimuli.tsv + .json")
        write.clicked.connect(self._write_manifest)
        rename = QPushButton("Rename legacy -> canonical")
        rename.clicked.connect(self._rename_canonical)
        buttons = QHBoxLayout()
        for b in (inspect, write, rename):
            buttons.addWidget(b)
        bw = QWidget(); bw.setLayout(buttons)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Recording folder:"))
        layout.addWidget(_folder_row(self.stim_dir, lambda: self._browse(self.stim_dir)))
        layout.addWidget(bw)
        layout.addWidget(self.stim_table)
        layout.addWidget(self.stim_status)
        w = QWidget(); w.setLayout(layout)
        return w

    def _records(self):
        return build_manifest(self.stim_dir.text())

    def _inspect_stimuli(self) -> None:
        recs = self._records()
        _fill(self.stim_table, [
            [r.filename, r.recording_id, r.emotion or "?", r.sex or "?",
             "ok" if r.recognized else "UNRECOGNIZED"]
            for r in recs
        ])
        n_ok = sum(1 for r in recs if r.recognized)
        self.stim_status.setText(f"{n_ok}/{len(recs)} recognized.")

    def _write_manifest(self, renamed=()) -> None:
        """(Re)write stimuli.tsv, keeping anything typed into an existing one."""
        folder = self.stim_dir.text()
        path = os.path.join(folder, "stimuli.tsv")
        recs = self._records()
        if os.path.exists(path):
            try:
                recs = merge_manifest(recs, read_manifest_tsv(path), renamed=renamed)
            except (OSError, ValueError) as exc:
                self.stim_status.setText(f"stimuli.tsv not updated (could not read it: {exc})")
                return
        write_manifest(recs, path)
        write_data_dictionary(os.path.join(folder, "stimuli.json"))
        self.stim_status.setText("Wrote stimuli.tsv + stimuli.json.")

    def _rename_canonical(self) -> None:
        folder = self.stim_dir.text()
        plan = canonical_rename_plan(self._records())
        if not plan:
            self.stim_status.setText("Nothing to rename (already canonical).")
            return
        result = apply_rename_plan(folder, plan)
        if result.applied and os.path.exists(os.path.join(folder, "stimuli.tsv")):
            self._write_manifest(renamed=result.applied)   # rows follow their files
        self._inspect_stimuli()
        self.stim_status.setText(result.summary())

    # -- Loudness & trim --------------------------------------------------

    def _loudness_tab(self) -> QWidget:
        self.loud_dir = QLineEdit(audio_dir())
        self.method = QComboBox(); self.method.addItems([m.value for m in NormalizationMethod])
        self.loud_table = _table(["File", "dur->new (s)", "trim L/T (ms)", "gain (dB)", "flag"])
        self.loud_status = QLabel("")
        self._plan = None

        preview = QPushButton("Preview")
        preview.clicked.connect(self._preview_loudness)
        apply_btn = QPushButton("Apply -> *_calibrated")
        apply_btn.clicked.connect(self._apply_loudness)
        row = QHBoxLayout()
        row.addWidget(QLabel("Method:")); row.addWidget(self.method)
        row.addWidget(preview); row.addWidget(apply_btn)
        rw = QWidget(); rw.setLayout(row)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Recording folder:"))
        layout.addWidget(_folder_row(self.loud_dir, lambda: self._browse(self.loud_dir)))
        layout.addWidget(rw)
        layout.addWidget(self.loud_table)
        layout.addWidget(self.loud_status)
        w = QWidget(); w.setLayout(layout)
        return w

    def _start_task(self, fn, on_done, on_failed, status: QLabel, message: str) -> bool:
        """Run *fn* in the background (one task at a time); False if one is running."""
        if self._busy is not None:
            status.setText("Still working on the previous step...")
            return False
        thread, task = QThread(self), _Task(fn)
        task.moveToThread(thread)
        thread.started.connect(task.run)
        task.done.connect(on_done)
        task.failed.connect(on_failed)
        task.done.connect(thread.quit)
        task.failed.connect(thread.quit)
        thread.finished.connect(self._task_finished)
        self._busy = (thread, task)
        status.setText(message)
        thread.start()
        return True

    def _task_finished(self) -> None:
        if self._busy is not None:
            thread, task = self._busy
            self._busy = None
            task.deleteLater()
            thread.deleteLater()

    def _wait_for_task(self, timeout_ms: int = 60000) -> None:
        """Block until a running task ends (closing mid-task would destroy its thread)."""
        if self._busy is not None:
            self._busy[0].wait(timeout_ms)

    def _preview_loudness(self) -> None:
        folder = self.loud_dir.text()
        out = os.path.normpath(folder) + "_calibrated"
        method = NormalizationMethod(self.method.currentText())
        self._start_task(lambda: plan_batch(_wavs(folder), out, method=method),
                         self._show_plan, self._loudness_failed, self.loud_status,
                         "Analysing recordings...")

    def _show_plan(self, plan) -> None:
        self._plan = plan
        _fill(self.loud_table, [
            [c.filename, f"{c.orig_duration:.2f}->{c.new_duration:.2f}",
             f"{c.lead_trim_s*1000:.0f}/{c.tail_trim_s*1000:.0f}",
             f"{c.gain_db:+.1f}", "PEAK-LIMITED" if c.will_limit else ""]
            for c in plan.clips
        ])
        self.loud_status.setText(
            f"max trim {plan.max_trim_ms:.0f} ms | max |gain| "
            f"{plan.max_abs_gain_db:.1f} dB | spread {plan.loudness_spread_db:.1f} dB"
            + ("  (already calibrated)" if plan.is_minor() else "")
        )

    def _apply_loudness(self) -> None:
        if self._plan is None:
            self.loud_status.setText("Press Preview first to see what would change.")
            return
        plan = self._plan
        self._start_task(lambda: apply_plan(plan), self._show_written, self._loudness_failed,
                         self.loud_status, f"Writing calibrated files to {plan.out_dir}...")

    def _show_written(self, written) -> None:
        self.loud_status.setText(f"Wrote {len(written)} files to {self._plan.out_dir}")

    def _loudness_failed(self, message: str) -> None:
        # e.g. output folder == input folder, or the folder can't be read
        self.loud_status.setText(f"Nothing written: {message}")

    # -- SPL tone ---------------------------------------------------------

    def _tone_tab(self) -> QWidget:
        self.tone_dir = QLineEdit(audio_dir())
        self.tone_seconds = QDoubleSpinBox()
        self.tone_seconds.setRange(2.0, 300.0); self.tone_seconds.setValue(60.0)
        self.tone_status = QLabel("")

        play = QPushButton("Play tone")
        play.clicked.connect(self._play_tone)
        stop = QPushButton("Stop")
        stop.clicked.connect(self._stop_tone)
        row = QHBoxLayout()
        row.addWidget(QLabel("Seconds:")); row.addWidget(self.tone_seconds)
        row.addWidget(play); row.addWidget(stop)
        rw = QWidget(); rw.setLayout(row)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Play a 1 kHz tone matched to the folder's average "
                                "RMS; set the booth level on a dB meter."))
        layout.addWidget(QLabel("Recording folder:"))
        layout.addWidget(_folder_row(self.tone_dir, lambda: self._browse(self.tone_dir)))
        layout.addWidget(rw)
        layout.addWidget(self.tone_status)
        layout.addStretch(1)
        w = QWidget(); w.setLayout(layout)
        return w

    def _play_tone(self) -> None:
        self._stop_tone()
        folder = self.tone_dir.text()
        self._start_task(lambda: average_rms(_wavs(folder)), self._start_tone,
                         self._tone_failed, self.tone_status, "Measuring the recordings' level...")

    def _start_tone(self, rms: float) -> None:
        if rms <= 0:
            self.tone_status.setText("No recordings found to match.")
            return
        argv = ["--play-tone", "--tone-rms", f"{rms:.5f}",
                "--tone-seconds", f"{self.tone_seconds.value():.0f}"]
        cmd = self_command(argv)
        self._tone_proc = QProcess(self)
        self._tone_proc.finished.connect(self._tone_finished)
        self._tone_proc.setProgram(cmd[0]); self._tone_proc.setArguments(cmd[1:])
        self._tone_proc.start()
        self.tone_status.setText(f"Playing tone (RMS {rms:.4f})... press Stop to end.")

    def _tone_finished(self, code: int, status) -> None:
        """Say how the tone ended (it used to say "stopped" even when it failed)."""
        if status == QProcess.ExitStatus.CrashExit or self._tone_stopping:
            self.tone_status.setText("Tone stopped.")
        elif code == 0:
            self.tone_status.setText("Tone finished.")
        else:
            reason = bytes(self._tone_proc.readAllStandardError()).decode("utf-8", "replace").strip()
            self.tone_status.setText(f"Tone failed (exit {code}). {reason[-200:]}")
        self._tone_stopping = False

    def _tone_failed(self, message: str) -> None:
        self.tone_status.setText(f"Could not measure the recordings: {message}")

    def _stop_tone(self) -> None:
        if self._tone_proc is not None and self._tone_proc.state() != QProcess.ProcessState.NotRunning:
            self._tone_stopping = True
            self._tone_proc.kill()

    # -- shared -----------------------------------------------------------

    def _browse(self, target: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose folder", target.text() or os.getcwd())
        if path:
            target.setText(path)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._stop_tone()
        self._wait_for_task()
        super().closeEvent(event)


def run_calibration_ui() -> int:
    """Open the Calibration window standalone; returns the Qt exit code."""
    app = apply_theme(QApplication.instance() or QApplication(sys.argv[:1]))
    window = CalibrationWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run_calibration_ui())
