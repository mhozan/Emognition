# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Experimenter monitor window: live session status, shown on the experimenter's display.

While the participant sees the PsychoPy experiment window on a second monitor,
the experimenter sees this compact Qt widget on their own screen. It updates in
real time as each trial completes, fed by JSON status lines the experiment
subprocess writes to its stdout.

Layout::

    ┌──────────────────────────────────────┐
    │ Participant01        [Test Mode]     │
    │──────────────────────────────────────│
    │          Trial  7 / 30              │
    │  ██████████░░░░░░░░░░░░  23 %       │
    │──────────────────────────────────────│
    │ Played:    Angry (Female)            │
    │ Response:  Happy       ✗ Wrong       │
    │ RT:        847 ms                   │
    │──────────────────────────────────────│
    │ Accuracy:  6 / 7   (86 %)           │
    │ ████████████████░░  86 %            │
    └──────────────────────────────────────┘

The window is intentionally compact and read-only; the experimenter cannot
intervene in a running session from here.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

_STYLE = """
QWidget {
    background: #12122a;
    color: #e0e0f0;
    font-size: 13px;
}
QLabel#header {
    font-size: 15px;
    font-weight: 700;
    color: #c8c8f0;
}
QLabel#mode_badge {
    font-size: 11px;
    font-weight: 700;
    color: #a0a0d0;
    background: #2a2a50;
    border-radius: 6px;
    padding: 3px 8px;
}
QLabel#trial_counter {
    font-size: 28px;
    font-weight: 700;
    color: #ffffff;
}
QLabel#correct_badge {
    font-weight: 700;
    color: #4caf50;
}
QLabel#wrong_badge {
    font-weight: 700;
    color: #ef5350;
}
QLabel#neutral_badge {
    color: #9090b0;
}
QLabel#stat {
    color: #b0b0d0;
}
QFrame#divider {
    background: #2a2a50;
    max-height: 1px;
    min-height: 1px;
}
QProgressBar {
    background: #2a2a50;
    border: none;
    border-radius: 4px;
    height: 8px;
}
QProgressBar::chunk {
    background: #4c8caf;
    border-radius: 4px;
}
QProgressBar#accuracy_bar::chunk {
    background: #4caf50;
}
"""


def _divider(parent: QWidget | None = None) -> QFrame:
    f = QFrame(parent)
    f.setObjectName("divider")
    f.setFrameShape(QFrame.Shape.HLine)
    return f


class MonitorWindow(QWidget):
    """Live read-only view of a running experiment session.

    Call :meth:`handle_event` with parsed JSON dicts from the experiment process.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("Emognition — Monitor")
        self.setStyleSheet(_STYLE)
        self.setFixedWidth(360)
        self._n_correct = 0
        self._n_responded = 0
        self._build()

    # -- layout -----------------------------------------------------------

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(10)

        # Header row: participant name + mode badge
        header_row = QHBoxLayout()
        self._lbl_participant = QLabel("—")
        self._lbl_participant.setObjectName("header")
        self._lbl_mode = QLabel("Test")
        self._lbl_mode.setObjectName("mode_badge")
        header_row.addWidget(self._lbl_participant)
        header_row.addStretch()
        header_row.addWidget(self._lbl_mode)
        outer.addLayout(header_row)
        outer.addWidget(_divider())

        # Trial counter + progress
        self._lbl_trial = QLabel("Waiting…")
        self._lbl_trial.setObjectName("trial_counter")
        self._lbl_trial.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self._lbl_trial)

        self._bar_progress = QProgressBar()
        self._bar_progress.setRange(0, 100)
        self._bar_progress.setValue(0)
        self._bar_progress.setTextVisible(False)
        self._bar_progress.setFixedHeight(8)
        outer.addWidget(self._bar_progress)
        outer.addWidget(_divider())

        # Last trial detail
        grid = QVBoxLayout()
        grid.setSpacing(4)
        self._lbl_played = self._stat_row(grid, "Played:")
        self._lbl_responded = self._stat_row(grid, "Response:")
        self._lbl_rt = self._stat_row(grid, "RT:")
        outer.addLayout(grid)
        outer.addWidget(_divider())

        # Accuracy summary
        acc_layout = QVBoxLayout()
        acc_layout.setSpacing(4)
        self._lbl_accuracy = QLabel("Accuracy:  —")
        self._lbl_accuracy.setObjectName("stat")
        acc_layout.addWidget(self._lbl_accuracy)
        self._bar_accuracy = QProgressBar()
        self._bar_accuracy.setObjectName("accuracy_bar")
        self._bar_accuracy.setRange(0, 100)
        self._bar_accuracy.setValue(0)
        self._bar_accuracy.setTextVisible(False)
        self._bar_accuracy.setFixedHeight(8)
        acc_layout.addWidget(self._bar_accuracy)
        outer.addLayout(acc_layout)

        self.adjustSize()

    @staticmethod
    def _stat_row(parent_layout: QVBoxLayout, label: str) -> QLabel:
        """Add a 'Label: Value' row; return the value QLabel for later updates."""
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setObjectName("stat")
        lbl.setFixedWidth(80)
        val = QLabel("—")
        row.addWidget(lbl)
        row.addWidget(val)
        row.addStretch()
        parent_layout.addLayout(row)
        return val

    # -- event handling ---------------------------------------------------

    def handle_event(self, evt: dict) -> None:
        """Update the display from a parsed JSON status event."""
        kind = evt.get("status")
        if kind == "start":
            self._on_start(evt)
        elif kind == "waiting":
            # The participant window shows the Begin screen (pb_beginner.m's button).
            self._lbl_trial.setText("Waiting for Begin")
        elif kind == "begun":
            self._lbl_trial.setText(f"0 / {evt.get('total', 0)}")
        elif kind == "trial":
            self._on_trial(evt)
        elif kind == "done":
            self._on_done(evt)

    def _on_start(self, evt: dict) -> None:
        self._n_correct = 0
        self._n_responded = 0
        self._lbl_participant.setText(evt.get("participant", "—"))
        mode_labels = {"test": "Test", "passive": "Passive", "active": "Active"}
        self._lbl_mode.setText(mode_labels.get(evt.get("mode", "test"), "Test"))
        total = evt.get("total", 0)
        self._lbl_trial.setText(f"0 / {total}")
        self._bar_progress.setValue(0)
        self._lbl_played.setText("—")
        self._lbl_responded.setText("—")
        self._lbl_rt.setText("—")
        self._lbl_accuracy.setText("Accuracy:  —")
        self._bar_accuracy.setValue(0)

    def _on_trial(self, evt: dict) -> None:
        index = evt.get("index", 0)
        total = evt.get("total", 1)
        self._lbl_trial.setText(f"{index} / {total}")
        self._bar_progress.setValue(round(100 * index / total))

        emotion = evt.get("emotion") or "—"
        sex_tag = evt.get("sex", "")
        sex_str = {"female": "F", "male": "M", "unknown": "?"}.get(sex_tag, "")
        played_text = emotion.capitalize()
        if sex_str:
            played_text += f"  ({sex_str})"
        self._lbl_played.setText(played_text)

        responded = evt.get("responded")
        correct = evt.get("correct")
        rt_ms = evt.get("rt_ms")

        if responded is None:
            # Passive training — no response
            self._lbl_responded.setObjectName("neutral_badge")
            self._lbl_responded.setText("(passive)")
            self._lbl_rt.setText("—")
        else:
            self._n_responded += 1
            if correct:
                self._n_correct += 1
                self._lbl_responded.setObjectName("correct_badge")
                self._lbl_responded.setText(f"{responded.capitalize()}   ✓ Correct")
            else:
                self._lbl_responded.setObjectName("wrong_badge")
                self._lbl_responded.setText(f"{responded.capitalize()}   ✗ Wrong")
            # Force Qt to re-evaluate the stylesheet after objectName change.
            self._lbl_responded.style().unpolish(self._lbl_responded)
            self._lbl_responded.style().polish(self._lbl_responded)

            if rt_ms is not None:
                self._lbl_rt.setText(f"{rt_ms} ms")
            else:
                self._lbl_rt.setText("—")

            pct = round(100 * self._n_correct / self._n_responded)
            self._lbl_accuracy.setText(
                f"Accuracy:  {self._n_correct} / {self._n_responded}   ({pct} %)"
            )
            self._bar_accuracy.setValue(pct)

    def _on_done(self, evt: dict) -> None:
        n_trials = evt.get("n_trials", self._n_responded)
        n_correct = evt.get("n_correct", self._n_correct)
        aborted = evt.get("aborted", False)
        suffix = "  (aborted)" if aborted else ""
        if n_trials > 0:
            pct = round(100 * n_correct / n_trials)
            self._lbl_accuracy.setText(
                f"Accuracy:  {n_correct} / {n_trials}   ({pct} %){suffix}"
            )
            self._bar_accuracy.setValue(pct)
        self._lbl_trial.setText(f"Done{suffix}")
