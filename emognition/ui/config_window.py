# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""The experimenter setup screen (PyQt6) -- the app's front door.

It edits an :class:`~emognition.config.ExperimentSettings` and, on "Proceed",
launches the experiment **in a separate process** (``emognition --participant
...``). Running the pyglet/OpenGL experiment window in its own process is what
avoids the Qt-vs-pyglet GL-context crash -- they never share an interpreter.

The window stays open so the experimenter can run participants back-to-back;
settings persist to JSON between launches ("keep previous settings").
"""

from __future__ import annotations

import os
import subprocess
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..config import ALL_EMOTION_TAGS, ExperimentSettings
from .assets import background_path

_CAPTIONS = ["none", "english", "mandarin"]
_EMOTION_LABELS = {"hap": "Happy", "sca": "Scared", "neu": "Neutral",
                   "sad": "Sad", "ang": "Angry"}


def default_settings_path() -> str:
    """Where the last-used settings are remembered (~/.emognition/settings.json)."""
    base = os.path.join(os.path.expanduser("~"), ".emognition")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "settings.json")


def _experiment_command(argv: list[str]) -> list[str]:
    """Command to launch a session in a separate process (frozen or from source)."""
    if getattr(sys, "frozen", False):          # PyInstaller bundle: the exe itself
        return [sys.executable, *argv]
    return [sys.executable, "-m", "emognition", *argv]


class ConfigWindow(QWidget):
    """Setup form over the BTNRH background; launches sessions as subprocesses."""

    def __init__(self, settings_path: str | None = None) -> None:
        super().__init__()
        self.settings_path = settings_path or default_settings_path()
        self._bg = QPixmap(background_path())
        self.setWindowTitle("Emognition - Setup")
        self.resize(720, 600)
        self._build()
        if os.path.exists(self.settings_path):
            try:
                self.apply_settings(ExperimentSettings.load(self.settings_path))
            except Exception:
                pass  # corrupt/old settings -> just start from defaults

    # -- layout ----------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt signature)
        if not self._bg.isNull():
            QPainter(self).drawPixmap(self.rect(), self._bg)

    def _panel(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame{background:rgba(255,255,255,0.90);border-radius:12px;}"
            "QLabel{background:transparent;}"
        )
        return frame

    def _build(self) -> None:
        self.participant = QLineEdit()
        self.experimenter = QLineEdit()
        self.audio_dir = QLineEdit()
        self.save_dir = QLineEdit()
        self.caption = QComboBox(); self.caption.addItems(_CAPTIONS)
        self.fullscreen = QCheckBox("Full screen")
        self.shuffle = QCheckBox("Shuffle order"); self.shuffle.setChecked(True)
        self.allow_replays = QCheckBox("Allow replays")
        self.amp_visualizer = QCheckBox("Amplitude visualizer")
        self.emotion_boxes = {
            tag: QCheckBox(_EMOTION_LABELS[tag]) for tag in ALL_EMOTION_TAGS
        }
        for box in self.emotion_boxes.values():
            box.setChecked(True)

        grid = QGridLayout()
        grid.setVerticalSpacing(8)
        grid.setContentsMargins(20, 20, 20, 20)
        r = 0
        title = QLabel("Speech Emotion Recognition")
        title.setStyleSheet("font-size:20px;font-weight:bold;")
        grid.addWidget(title, r, 0, 1, 3); r += 1

        grid.addWidget(QLabel("Participant"), r, 0); grid.addWidget(self.participant, r, 1, 1, 2); r += 1
        grid.addWidget(QLabel("Experimenter"), r, 0); grid.addWidget(self.experimenter, r, 1, 1, 2); r += 1
        grid.addWidget(QLabel("Audio folder"), r, 0); grid.addWidget(self.audio_dir, r, 1)
        grid.addWidget(self._browse_button(self.audio_dir), r, 2); r += 1
        grid.addWidget(QLabel("Save folder"), r, 0); grid.addWidget(self.save_dir, r, 1)
        grid.addWidget(self._browse_button(self.save_dir), r, 2); r += 1
        grid.addWidget(QLabel("Caption"), r, 0); grid.addWidget(self.caption, r, 1); r += 1

        opts = QHBoxLayout()
        for w in (self.fullscreen, self.shuffle, self.allow_replays, self.amp_visualizer):
            opts.addWidget(w)
        opts_w = QWidget(); opts_w.setLayout(opts)
        grid.addWidget(opts_w, r, 0, 1, 3); r += 1

        emo = QHBoxLayout()
        emo.addWidget(QLabel("Emotions:"))
        for box in self.emotion_boxes.values():
            emo.addWidget(box)
        emo_w = QWidget(); emo_w.setLayout(emo)
        grid.addWidget(emo_w, r, 0, 1, 3); r += 1

        self.status = QLabel("")
        self.status.setStyleSheet("color:#2e7d32;")
        grid.addWidget(self.status, r, 0, 1, 2)
        proceed = QPushButton("Proceed to Test")
        proceed.setStyleSheet("font-weight:bold;padding:8px 16px;")
        proceed.clicked.connect(self._on_proceed)
        grid.addWidget(proceed, r, 2); r += 1

        panel = self._panel(); panel.setLayout(grid)
        outer = QVBoxLayout(self)
        outer.addStretch(1)
        row = QHBoxLayout(); row.addStretch(1); row.addWidget(panel); row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)

    def _browse_button(self, target: QLineEdit) -> QPushButton:
        button = QPushButton("Browse...")
        button.clicked.connect(lambda: self._browse_into(target))
        return button

    def _browse_into(self, target: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose folder", target.text() or os.getcwd())
        if path:
            target.setText(path)

    # -- settings <-> form ----------------------------------------------

    def settings_from_form(self) -> ExperimentSettings:
        return ExperimentSettings(
            participant=self.participant.text().strip() or "Participant01",
            experimenter=self.experimenter.text().strip() or "APPstaff",
            audio_dir=self.audio_dir.text().strip(),
            save_dir=self.save_dir.text().strip(),
            caption=self.caption.currentText(),
            fullscreen=self.fullscreen.isChecked(),
            shuffle=self.shuffle.isChecked(),
            allow_replays=self.allow_replays.isChecked(),
            amp_visualizer=self.amp_visualizer.isChecked(),
            emotions=[t for t, b in self.emotion_boxes.items() if b.isChecked()],
        )

    def apply_settings(self, s: ExperimentSettings) -> None:
        self.participant.setText(s.participant)
        self.experimenter.setText(s.experimenter)
        self.audio_dir.setText(s.audio_dir)
        self.save_dir.setText(s.save_dir)
        if s.caption in _CAPTIONS:
            self.caption.setCurrentText(s.caption)
        self.fullscreen.setChecked(s.fullscreen)
        self.shuffle.setChecked(s.shuffle)
        self.allow_replays.setChecked(s.allow_replays)
        self.amp_visualizer.setChecked(s.amp_visualizer)
        for tag, box in self.emotion_boxes.items():
            box.setChecked(tag in s.emotions)

    # -- actions ---------------------------------------------------------

    def _on_proceed(self) -> None:
        settings = self.settings_from_form()
        if not settings.emotions:
            self.status.setStyleSheet("color:#c62828;")
            self.status.setText("Select at least one emotion.")
            return
        try:
            settings.save(self.settings_path)
        except Exception:
            pass
        subprocess.Popen(_experiment_command(settings.to_argv()), start_new_session=True)
        self.status.setStyleSheet("color:#2e7d32;")
        self.status.setText(f"Launched session for '{settings.participant}'.")


def run_config_ui(settings_path: str | None = None) -> int:
    """Open the setup screen; returns the Qt exit code when the window closes."""
    app = QApplication.instance() or QApplication(sys.argv[:1])
    window = ConfigWindow(settings_path=settings_path)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run_config_ui())
