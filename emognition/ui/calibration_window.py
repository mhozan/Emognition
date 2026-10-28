# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""The experimenter Calibration window (PyQt6): check, document and calibrate a stimulus set.

One recordings folder, chosen at the top, for four tabs:

* **Stimuli / naming** -- what each file name says (emotion, speaker sex), how
  balanced the set is, the manifest (stimuli.tsv + .json), legacy -> BIDS names.
  (wraps emognition.naming)
* **Clip check** -- a card per file (waveform, spectrogram, and the RMS curve the
  end-of-speech detector works from) with sanity flags, and a large view of any
  one: a whole database checked at a glance. (audio.analysis, imaging.clips)
* **Loudness & trim** -- what calibration would change, clip by clip (a table,
  and charts before vs after), then Apply -> a new ``*_calibrated`` folder; the
  written files are measured again, so the charts show what was written.
  (audio.preprocess, audio.review)
* **SPL tone** -- a 1 kHz tone at the folder's average level for setting the
  presentation level on a sound level meter, played by a separate process at the
  session's Volume (audio never touches this Qt process).

Every tab explains its methods in a "How it works" panel (ui/calibration_help.py)
and every control has a tooltip. Anything slow runs on a worker thread. Nothing
writes to the recordings folder except the explicit Rename.
"""

from __future__ import annotations

import os
import sys
from collections import Counter

from PyQt6.QtCore import QObject, QProcess, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..audio import NormalizationMethod, apply_plan, average_rms, plan_batch
from ..audio.analysis import analyse_clip, check_folder, db
from ..audio.review import before_after, measure_written
from ..config import DEFAULT_VOLUME
from ..core.emotions import EMOTIONS_IN_ORDER
from ..imaging.clips import clip_card
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
from .calibration_charts import (
    CARD_H,
    CARD_W,
    BalanceChart,
    ClipCard,
    ClipDetail,
    ClipGallery,
    StripChart,
    fmt_value,
    qimage_from_rgb,
    range_text,
)
from .calibration_help import (
    HELP_CSS,
    TIPS,
    clips_help,
    loudness_help,
    minus,
    stimuli_help,
    tone_help,
    tone_numbers,
)
from .theme import apply_theme

# Layout and accents only; colours, fields and popups come from the shared theme.
_STYLE = """
QWidget { font-size: 13px; }
QLabel { background: transparent; }
QLabel#status { color: #5a5a7a; }
QLabel#heading { font-weight: 700; color: #2a2250; }
QLabel#toneLevel { font-size: 14px; }
QPushButton {
    background: #6c5ce7; color: #ffffff; border: none;
    border-radius: 8px; padding: 7px 14px; font-weight: 700;
}
QPushButton:hover { background: #5a4bd0; }
QPushButton:pressed { background: #4d3fb8; }
QPushButton:disabled { background: #b7b1e0; }
QPushButton#secondary { background: #ececf5; color: #3a3a5a; font-weight: 600; }
QPushButton#secondary:hover { background: #dedeee; }
QPushButton#secondary:checked { background: #dcd8fa; color: #2a2250; }
QTextBrowser { background: #fbfbfe; border: 1px solid #e3e3ef; border-radius: 8px; padding: 4px; }
QFrame#clipCard { background: #ffffff; border: 2px solid #ececf5; border-radius: 8px; }
QFrame#clipCard:hover { border-color: #cfcbf3; }
QFrame#clipCard[selected="true"] { border-color: #6c5ce7; }
QLabel#cardName { font-weight: 700; color: #20203a; }
QLabel#cardStats { color: #5a5a7a; font-size: 12px; }
QWidget#gallery { background: #f4f4f9; }
"""

# The loudness table's short headers (the chart panels carry the long titles).
_COLUMNS = {"duration": "Duration (s)", "lead": "Before speech (ms)", "tail": "After speech (ms)",
            "peak": "Peak (dBFS)"}

_CLIP_ORDERS = {
    "File name": lambda c, f: c.filename.lower(),
    "Flagged first": lambda c, f: (not f, c.filename.lower()),
    "Longest first": lambda c, f: -c.duration,
    "Loudest peak first": lambda c, f: -c.peak_db,
    "Loudest RMS first": lambda c, f: -c.rms_db,
    "Most silence after speech": lambda c, f: -c.tail_silence,
}


def _table(headers: list[str], tips: list[str] | None = None) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    _set_headers(t, headers, tips)
    t.horizontalHeader().setStretchLastSection(True)
    t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    t.setAlternatingRowColors(True)
    t.verticalHeader().setVisible(False)
    return t


def _set_headers(table: QTableWidget, headers: list[str], tips: list[str] | None = None) -> None:
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    for i, tip in enumerate(tips or ()):
        item = table.horizontalHeaderItem(i)
        if item is not None:
            item.setToolTip(tip)


def _fill(table: QTableWidget, rows: list[list[str]]) -> None:
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            table.setItem(r, c, QTableWidgetItem(val))
    table.resizeColumnsToContents()


def _status() -> QLabel:
    label = QLabel("")
    label.setObjectName("status")
    label.setWordWrap(True)
    return label


def _row(*items) -> QHBoxLayout:
    """Widgets (or ints, as spacing) in a row, pushed to the left."""
    row = QHBoxLayout()
    for item in items:
        if isinstance(item, int):
            row.addSpacing(item)
        else:
            row.addWidget(item)
    row.addStretch(1)
    return row


def _calibrated_dir(folder: str) -> str:
    return os.path.normpath(folder) + "_calibrated"


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
    """Tabbed calibration tools for the experimenter.

    *folder* is the recordings folder to start on (the setup window passes its
    Audio folder; default: the bundled clips) and *volume* the session Volume
    the SPL tone must play at (the setup window's; default 0.8).
    """

    def __init__(self, folder: str | None = None, volume: float | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Emognition - Calibration")
        self.setStyleSheet(_STYLE)
        self.resize(1200, 800)
        self._volume = DEFAULT_VOLUME if volume is None else max(0.0, min(1.0, volume))
        self._tone_proc: QProcess | None = None
        self._tone_stopping = False
        self._busy: tuple[QThread, _Task] | None = None   # the one background task
        self._refresh_after_task = False                   # a tab asked while busy
        self._helps: list[QTextBrowser] = []
        # What each tab shows, and for which folder (each refreshes when shown).
        self._stim_for: str | None = None
        self._clips: list = []
        self._clip_flags: list = []
        self._clips_for: str | None = None
        self._plan = None
        self._plan_for: str | None = None
        self._written_dir: str | None = None
        self._tone_rms: float | None = None
        self._tone_for: str | None = None

        self.folder = QLineEdit(folder or audio_dir())
        self.folder.setToolTip(TIPS["folder"])
        self.folder.editingFinished.connect(self._on_folder_edited)
        self._last_folder = self.folder.text()
        browse = self._button("Browse...", "Choose the recordings folder.", secondary=True)
        browse.clicked.connect(self._browse)
        self.folder_info = _status()
        self.folder_info.setWordWrap(False)
        self.help_btn = self._button("How it works", TIPS["help"], secondary=True)
        self.help_btn.setCheckable(True)
        self.help_btn.setChecked(True)
        self.help_btn.toggled.connect(self._show_help)
        top = QHBoxLayout()
        label = QLabel("Recordings folder")
        label.setToolTip(TIPS["folder"])
        top.addWidget(label)
        top.addWidget(self.folder, 1)
        top.addWidget(browse)
        top.addWidget(self.folder_info)
        top.addSpacing(12)
        top.addWidget(self.help_btn)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._stimuli_tab(), "Stimuli / naming")
        self.tabs.addTab(self._clips_tab(), "Clip check")
        self.tabs.addTab(self._loudness_tab(), "Loudness && trim")
        self.tabs.addTab(self._tone_tab(), "SPL tone")
        self.tabs.currentChanged.connect(lambda _index: self._refresh_tab())
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.tabs)
        self._count_files()

    # -- building blocks --------------------------------------------------

    @staticmethod
    def _button(text: str, tip: str, *, secondary: bool = False) -> QPushButton:
        button = QPushButton(text)
        button.setToolTip(tip)
        if secondary:
            button.setObjectName("secondary")
        return button

    def _with_help(self, content: QWidget, html: str) -> tuple[QSplitter, QTextBrowser]:
        """*content* with its "How it works" panel beside it (drag the divider to resize)."""
        browser = QTextBrowser()
        browser.document().setDefaultStyleSheet(HELP_CSS)
        browser.document().setIndentWidth(16)               # list indent (Qt's default is 40 px)
        browser.setHtml(html)
        browser.setMinimumWidth(280)
        browser.setVisible(self.help_btn.isChecked() if hasattr(self, "help_btn") else True)
        self._helps.append(browser)
        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(content)
        split.addWidget(browser)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 1)
        split.setSizes([830, 350])
        split.setChildrenCollapsible(False)
        return split, browser

    def _show_help(self, on: bool) -> None:
        for browser in self._helps:
            browser.setVisible(on)

    # -- Stimuli / naming -------------------------------------------------

    def _stimuli_tab(self) -> QWidget:
        self.stim_table = _table(
            ["File", "Recording ID", "Emotion", "Sex", "Status"],
            [TIPS["col_file"], TIPS["col_recording"], TIPS["col_emotion"], TIPS["col_sex"], TIPS["col_status"]])
        self.stim_status = _status()
        self.balance = BalanceChart()
        inspect = self._button("Inspect", TIPS["inspect"])
        inspect.clicked.connect(self._inspect_stimuli)
        write = self._button("Write stimuli.tsv + .json", TIPS["write_manifest"], secondary=True)
        write.clicked.connect(self._write_manifest)
        rename = self._button("Rename legacy → canonical", TIPS["rename"], secondary=True)
        rename.clicked.connect(self._rename_canonical)

        heading = QLabel("Balance")
        heading.setObjectName("heading")
        heading.setToolTip(TIPS["balance"])
        side = QVBoxLayout()
        side.addWidget(heading)
        side.addWidget(self.balance)
        side.addStretch(1)
        body = QHBoxLayout()
        body.addWidget(self.stim_table, 3)
        body.addLayout(side, 2)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(_row(inspect, write, rename))
        layout.addLayout(body, 1)
        layout.addWidget(self.stim_status)
        split, self.stim_help = self._with_help(content, stimuli_help())
        return split

    def _read_records(self):
        return build_manifest(self.folder.text())

    def _inspect_stimuli(self) -> None:
        folder = self.folder.text()
        try:
            recs = self._read_records()
        except OSError as exc:
            self.stim_status.setText(f"Could not read the folder: {exc}")
            return
        self._stim_for = folder
        _fill(self.stim_table, [
            [r.filename, r.recording_id, r.emotion or "?", r.sex or "?",
             "ok" if r.recognized else "UNRECOGNIZED"]
            for r in recs
        ])
        self._show_balance(recs)
        n_ok = sum(1 for r in recs if r.recognized)
        self.stim_status.setText(f"{n_ok}/{len(recs)} recognized.")

    def _show_balance(self, recs) -> None:
        """Clips per emotion (in report-code order) and speaker sex."""
        rows = []
        for emotion in EMOTIONS_IN_ORDER:
            name = emotion.name.lower()
            rows.append((emotion.label, [sum(1 for r in recs if r.emotion == name and r.sex == sex)
                                         for sex in ("f", "m", "u")]))
        self.balance.set_counts(rows, ("Female", "Male", "Unknown"),
                                unrecognized=sum(1 for r in recs if not r.recognized))

    def _write_manifest(self, renamed=()) -> None:
        """(Re)write stimuli.tsv, keeping anything typed into an existing one."""
        folder = self.folder.text()
        path = os.path.join(folder, "stimuli.tsv")
        try:
            recs = self._read_records()
        except OSError as exc:
            self.stim_status.setText(f"Could not read the folder: {exc}")
            return
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
        folder = self.folder.text()
        try:
            plan = canonical_rename_plan(self._read_records())
        except OSError as exc:
            self.stim_status.setText(f"Could not read the folder: {exc}")
            return
        if not plan:
            self.stim_status.setText("Nothing to rename (already canonical).")
            return
        result = apply_rename_plan(folder, plan)
        if result.applied and os.path.exists(os.path.join(folder, "stimuli.tsv")):
            self._write_manifest(renamed=result.applied)   # rows follow their files
        self._inspect_stimuli()
        self._clips_for = self._plan_for = self._tone_for = None   # the file names changed
        self.stim_status.setText(result.summary())

    # -- Clip check ---------------------------------------------------------

    def _clips_tab(self) -> QWidget:
        analyse = self._button("Analyse", TIPS["analyse"])
        analyse.clicked.connect(lambda: self._analyse_clips())
        self.clip_sort = QComboBox()
        self.clip_sort.addItems(list(_CLIP_ORDERS))
        self.clip_sort.setToolTip(TIPS["sort"])
        self.clip_sort.currentIndexChanged.connect(lambda _i: self._sort_clips())
        self.clip_flagged_only = QCheckBox("Flagged only")
        self.clip_flagged_only.setToolTip(TIPS["flagged_only"])
        self.clip_flagged_only.toggled.connect(lambda _on: self._sort_clips())
        sort_label = QLabel("Order")
        sort_label.setToolTip(TIPS["sort"])
        self.clips_status = _status()
        self.gallery = ClipGallery()
        self.gallery.selected.connect(self._show_clip)
        self.clip_detail = ClipDetail()

        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(self.gallery)
        split.addWidget(self.clip_detail)
        split.setSizes([380, 340])
        split.setChildrenCollapsible(False)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(_row(analyse, 12, sort_label, self.clip_sort, 12, self.clip_flagged_only))
        layout.addWidget(self.clips_status)
        layout.addWidget(split, 1)
        outer, self.clips_help = self._with_help(content, clips_help())
        return outer

    def _analyse_clips(self, queue: bool = False) -> None:
        folder = self.folder.text()
        dpr = self.devicePixelRatioF()

        def work():
            clips, failed = [], []
            for path in _wavs(folder):
                try:
                    clips.append(analyse_clip(path))
                except Exception as exc:  # noqa: BLE001 -- listed; the others are still shown
                    failed.append(os.path.basename(path))
                    print(f"Could not analyse {path}: {exc!r}", file=sys.stderr)
            flags = check_folder(clips)
            span = max((c.duration for c in clips), default=1.0)
            size = (round(CARD_W * dpr), round(CARD_H * dpr))
            pictures = [clip_card(c, width=size[0], height=size[1], span=span).tobytes() for c in clips]
            return folder, clips, flags, pictures, size, dpr, failed

        self._start_task(work, self._show_clips, self._clips_failed, self.clips_status,
                         "Measuring every recording...", queue=queue)

    def _show_clips(self, result) -> None:
        folder, clips, flags, pictures, (w, h), dpr, failed = result
        self._clips, self._clip_flags, self._clips_for = clips, flags, folder
        self.gallery.set_cards([
            ClipCard(i, clip, clip_flags, qimage_from_rgb(data, w, h, dpr))
            for i, (clip, clip_flags, data) in enumerate(zip(clips, flags, pictures))
        ])
        self._sort_clips()
        self.clips_status.setText(self._clips_summary(clips, flags, failed))
        order = self.gallery.order
        first = next((i for i in order if flags[i]), order[0] if order else None)
        if first is None:
            self.clip_detail.set_clip(None)
        else:
            self.gallery.select(first)

    def _clips_failed(self, message: str) -> None:
        self.clips_status.setText(f"Could not read the folder: {message}")

    def _show_clip(self, index: int) -> None:
        if 0 <= index < len(self._clips):
            self.clip_detail.set_clip(self._clips[index], self._clip_flags[index])

    def _sort_clips(self) -> None:
        key = _CLIP_ORDERS[self.clip_sort.currentText()]
        order = sorted(range(len(self._clips)), key=lambda i: key(self._clips[i], self._clip_flags[i]))
        if self.clip_flagged_only.isChecked():
            order = [i for i in order if self._clip_flags[i]]
        self.gallery.show_order(order)

    @staticmethod
    def _clips_summary(clips, flags, failed) -> str:
        """The folder in one line: count, format, ranges, and how many clips are flagged."""
        parts: list[str] = []
        if clips:
            rates = sorted(Counter(c.rate for c in clips))
            channels = set(c.channels for c in clips)
            durations = [c.duration for c in clips]
            peaks = [c.peak_db for c in clips]
            tails = [c.tail_silence * 1000.0 for c in clips]
            n_flagged = sum(1 for f in flags if f)
            parts += [
                f"{len(clips)} clip{'s' if len(clips) != 1 else ''}",
                "/".join(f"{r / 1000:g}" for r in rates) + " kHz" + (" (mixed)" if len(rates) > 1 else ""),
                {frozenset({1}): "mono", frozenset({2}): "stereo"}.get(frozenset(channels), "mono and stereo"),
                f"{range_text(min(durations), max(durations), 's')} s",
                f"peak {range_text(min(peaks), max(peaks), 'dB')} dBFS",
                f"silence after speech {range_text(min(tails), max(tails), 'ms')} ms",
                f"⚠ {n_flagged} flagged" if n_flagged else "no flags",
            ]
        else:
            parts.append("No .wav files here.")
        if failed:
            parts.append(f"{len(failed)} unreadable: " + ", ".join(failed[:3]) + ("..." if len(failed) > 3 else ""))
        return " · ".join(parts)

    # -- Loudness & trim --------------------------------------------------

    def _loudness_tab(self) -> QWidget:
        self.method = QComboBox()
        for method, text, tip in (
            (NormalizationMethod.LUFS, "Perceived loudness (LUFS)", TIPS["method_lufs"]),
            (NormalizationMethod.RMS, "RMS level (dBFS)", TIPS["method_rms"]),
            (NormalizationMethod.PEAK, "Peak level (dBFS)", TIPS["method_peak"]),
        ):
            self.method.addItem(text, method)
            self.method.setItemData(self.method.count() - 1, tip, Qt.ItemDataRole.ToolTipRole)
        self.method.setToolTip(TIPS["method"])
        self.method.currentIndexChanged.connect(self._on_method_changed)
        method_label = QLabel("Equalise")
        method_label.setToolTip(TIPS["method"])
        preview = self._button("Preview", TIPS["preview"])
        preview.clicked.connect(lambda: self._preview_loudness())
        self.apply_btn = self._button("Apply", TIPS["apply"])
        self.apply_btn.clicked.connect(self._apply_loudness)
        self.use_calibrated = self._button("Check the calibrated folder", TIPS["use_calibrated"], secondary=True)
        self.use_calibrated.clicked.connect(self._use_calibrated)
        self.use_calibrated.hide()
        self.loud_status = _status()
        self.strip = StripChart()
        self.loud_table = _table(["File"])
        self._plan = None

        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(self.strip)
        split.addWidget(self.loud_table)
        split.setSizes([400, 260])
        split.setChildrenCollapsible(False)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(_row(method_label, self.method, 12, preview, self.apply_btn, 12, self.use_calibrated))
        layout.addWidget(self.loud_status)
        layout.addWidget(split, 1)
        outer, self.loud_help = self._with_help(content, loudness_help())
        return outer

    def _start_task(self, fn, on_done, on_failed, status: QLabel, message: str,
                    queue: bool = False) -> bool:
        """Run *fn* in the background (one task at a time); False if one is running.

        With *queue*, a refused task's tab is refreshed once the running one ends
        (switching tabs during a long analysis then catches up by itself).
        """
        if self._busy is not None:
            if queue:
                self._refresh_after_task = True
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
        if self._refresh_after_task:
            self._refresh_after_task = False
            QTimer.singleShot(0, self._refresh_tab)

    def _wait_for_task(self, timeout_ms: int = 60000) -> None:
        """Block until a running task ends (closing mid-task would destroy its thread)."""
        if self._busy is not None:
            self._busy[0].wait(timeout_ms)

    def _on_method_changed(self, _index: int) -> None:
        self._plan_for = None                              # the plan was for the old method
        if self.isVisible() and self.tabs.currentIndex() == 2:
            self._preview_loudness(queue=True)

    def _preview_loudness(self, queue: bool = False) -> None:
        folder = self.folder.text()
        out = _calibrated_dir(folder)
        method = self.method.currentData()
        self._start_task(lambda: (folder, plan_batch(_wavs(folder), out, method=method)),
                         self._show_plan, self._loudness_failed, self.loud_status,
                         "Analysing recordings...", queue=queue)

    def _show_plan(self, result) -> None:
        folder, plan = result
        self._plan, self._plan_for, self._written_dir = plan, folder, None
        self.use_calibrated.hide()
        if not plan.clips:
            self.strip.set_metrics([])
            _fill(self.loud_table, [])
            self.loud_help.setHtml(loudness_help())
            self.loud_status.setText("No .wav files in this folder.")
            return
        metrics = before_after(plan)
        self.strip.set_metrics(metrics, measured=False)
        self._fill_loudness_table(plan, metrics)
        self.loud_help.setHtml(loudness_help(plan))
        gains = [plan.gain_applied_db(c) for c in plan.clips]
        loud = next(m for m in metrics if m.key == "loudness")
        unit = "LU" if loud.unit == "LUFS" else "dB"
        self.loud_status.setText(
            f"{len(plan.clips)} clips · up to {plan.max_trim_ms:.0f} ms of silence trimmed per clip "
            f"· gain {minus(f'{min(gains):+.1f}')} to {minus(f'{max(gains):+.1f}')} dB "
            f"· {loud.title.lower()} spread "
            f"{fmt_value(loud.spread_before, unit)} → {fmt_value(loud.spread_after, unit)} {unit}"
            + ("  (already calibrated: nothing here is worth changing)" if plan.is_minor() else "")
        )

    def _fill_loudness_table(self, plan, metrics) -> None:
        """The chart's twin: every charted value, before -> after, plus the gain."""
        headers = (["File"] + [_COLUMNS.get(m.key, f"{m.title} ({m.unit})") for m in metrics]
                   + ["Gain (dB)", "Note"])
        tips = ([TIPS["col_file"]] + [TIPS[f"col_{m.key}"] for m in metrics]
                + [TIPS["col_gain"], TIPS["col_note"]])
        _set_headers(self.loud_table, headers, tips)
        rows = []
        for i, clip in enumerate(plan.clips):
            gain = plan.gain_applied_db(clip)
            rows.append(
                [clip.filename]
                + [f"{fmt_value(m.before[i], m.unit)} → {fmt_value(m.after[i], m.unit)}" for m in metrics]
                + [minus(f"{gain:+.1f}"),
                   f"PEAK-LIMITED, {clip.gain_db - gain:.1f} dB under the target" if clip.will_limit else ""])
        _fill(self.loud_table, rows)

    def _apply_loudness(self) -> None:
        if self._plan is None:
            self.loud_status.setText("Press Preview first to see what would change.")
            return
        if self._plan_for != self.folder.text():
            self.loud_status.setText("The folder or method changed since the preview: press Preview again.")
            return
        plan = self._plan

        def work():
            written = apply_plan(plan)
            return written, measure_written(written, plan.method)

        self._start_task(work, self._show_written, self._loudness_failed,
                         self.loud_status, f"Writing calibrated files to {plan.out_dir}...")

    def _show_written(self, result) -> None:
        written, measured = result
        plan = self._plan
        metrics = before_after(plan, measured)
        self.strip.set_metrics(metrics, measured=True)
        self._fill_loudness_table(plan, metrics)
        self._written_dir = plan.out_dir
        loud = next(m for m in metrics if m.key == "loudness")
        unit = "LU" if loud.unit == "LUFS" else "dB"
        self.loud_status.setText(
            f"Wrote {len(written)} files to {plan.out_dir} · measured again: "
            f"{loud.title.lower()} spread {fmt_value(loud.spread_after, unit)} {unit}. "
            "Point the setup window's Audio folder at it to use it.")
        self.use_calibrated.show()

    def _use_calibrated(self) -> None:
        if self._written_dir:
            self.folder.setText(self._written_dir)
            self._on_folder_changed()

    def _loudness_failed(self, message: str) -> None:
        # e.g. output folder == input folder, or the folder can't be read
        self.loud_status.setText(f"Nothing written: {message}")

    # -- SPL tone ---------------------------------------------------------

    def _tone_tab(self) -> QWidget:
        self.tone_seconds = QDoubleSpinBox()
        self.tone_seconds.setRange(2.0, 300.0)
        self.tone_seconds.setDecimals(0)
        self.tone_seconds.setSuffix(" s")
        self.tone_seconds.setValue(60.0)
        self.tone_seconds.setToolTip(TIPS["seconds"])
        length = QLabel("Length")
        length.setToolTip(TIPS["seconds"])
        play = self._button("Play tone", TIPS["play"])
        play.clicked.connect(self._play_tone)
        stop = self._button("Stop", TIPS["stop"], secondary=True)
        stop.clicked.connect(self._stop_tone)
        self.tone_volume = QLabel(self._volume_text())
        self.tone_volume.setToolTip(TIPS["volume"])
        self.tone_level = QLabel("")
        self.tone_level.setObjectName("toneLevel")
        self.tone_level.setWordWrap(True)
        self.tone_status = _status()

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(_row(length, self.tone_seconds, 12, play, stop))
        layout.addWidget(self.tone_volume)
        layout.addWidget(self.tone_level)
        layout.addWidget(self.tone_status)
        layout.addStretch(1)
        outer, self.tone_help = self._with_help(content, tone_help(None, self._volume))
        outer.setSizes([560, 620])                          # little to show; much to explain
        return outer

    def _volume_text(self) -> str:
        if self._volume <= 0:
            return "Volume 0 (silent): set the Volume in the setup window first."
        return (f"Plays at Volume {self._volume:.2f} ({minus(f'{db(self._volume):+.1f}')} dB), "
                "the session's: set it in the setup window, not here.")

    def _tone_argv(self, rms: float) -> list[str]:
        """The command line that plays the tone: at the session's Volume, as the clips play."""
        return ["--play-tone", "--tone-rms", f"{rms:.5f}",
                "--tone-seconds", f"{self.tone_seconds.value():.0f}",
                "--volume", f"{self._volume:.2f}"]

    def _measure_tone(self, queue: bool = False, then_play: bool = False) -> None:
        folder = self.folder.text()
        done = self._measured_then_play if then_play else self._show_tone_level
        self._start_task(lambda: (folder, average_rms(_wavs(folder))), done,
                         self._tone_failed, self.tone_status, "Measuring the recordings' level...",
                         queue=queue)

    def _show_tone_level(self, result) -> None:
        folder, rms = result
        self._tone_rms, self._tone_for = rms, folder
        if rms <= 0:
            self.tone_level.setText("No recordings found to match.")
            self.tone_help.setHtml(tone_help(None, self._volume))
            return
        self.tone_level.setText(tone_numbers(rms, self._volume))
        self.tone_help.setHtml(tone_help(rms, self._volume))
        self.tone_status.setText("")

    def _measured_then_play(self, result) -> None:
        self._show_tone_level(result)
        self._start_tone(result[1])

    def _play_tone(self) -> None:
        self._stop_tone()
        if self._tone_for == self.folder.text() and self._tone_rms:
            self._start_tone(self._tone_rms)
        else:
            self._measure_tone(then_play=True)

    def _start_tone(self, rms: float) -> None:
        if rms <= 0:
            self.tone_status.setText("No recordings found to match.")
            return
        cmd = self_command(self._tone_argv(rms))
        self._tone_proc = QProcess(self)
        self._tone_proc.finished.connect(self._tone_finished)
        self._tone_proc.setProgram(cmd[0])
        self._tone_proc.setArguments(cmd[1:])
        self._tone_proc.start()
        self.tone_status.setText(f"Playing the tone ({minus(f'{db(rms):.1f}')} dBFS RMS at Volume "
                                 f"{self._volume:.2f})... press Stop to end.")

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

    # -- the shared folder -----------------------------------------------

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose the recordings folder",
                                                self.folder.text() or os.getcwd())
        if path:
            self.folder.setText(path)
            self._on_folder_changed()

    def _on_folder_edited(self) -> None:
        if self.folder.text() != self._last_folder:
            self._on_folder_changed()

    def _on_folder_changed(self) -> None:
        self._last_folder = self.folder.text()
        self._count_files()
        self._refresh_tab()

    def _count_files(self) -> None:
        folder = self.folder.text()
        try:
            n = len(_wavs(folder))
            self.folder_info.setText(f"{n} .wav file{'s' if n != 1 else ''}")
        except OSError:
            self.folder_info.setText("folder not found")
        self.apply_btn.setText(f"Apply → {os.path.basename(_calibrated_dir(folder))}")

    def _refresh_tab(self) -> None:
        """Bring the visible tab up to date with the folder (each tab measures when shown)."""
        if not self.isVisible():
            return
        folder = self.folder.text()
        tab = self.tabs.currentIndex()
        if tab == 0 and self._stim_for != folder:
            self._inspect_stimuli()
        elif tab == 1 and self._clips_for != folder:
            self._analyse_clips(queue=True)
        elif tab == 2 and self._plan_for != folder:
            self._preview_loudness(queue=True)
        elif tab == 3 and self._tone_for != folder:
            self._measure_tone(queue=True)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        QTimer.singleShot(0, self._refresh_tab)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._stop_tone()
        self._wait_for_task()
        super().closeEvent(event)


def _saved_folder_and_volume() -> tuple[str | None, float | None]:
    """The Audio folder and Volume last saved by the setup window, if any."""
    from ..config import ExperimentSettings
    from .config_window import default_settings_path

    path = default_settings_path()
    if not os.path.exists(path):
        return None, None
    try:
        settings = ExperimentSettings.load(path)
    except (OSError, ValueError, TypeError):
        return None, None
    folder = settings.audio_dir if settings.audio_dir and os.path.isdir(settings.audio_dir) else None
    return folder, settings.volume


def run_calibration_ui() -> int:
    """Open the Calibration window standalone; returns the Qt exit code."""
    app = apply_theme(QApplication.instance() or QApplication(sys.argv[:1]))
    folder, volume = _saved_folder_and_volume()
    window = CalibrationWindow(folder=folder, volume=volume)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run_calibration_ui())
