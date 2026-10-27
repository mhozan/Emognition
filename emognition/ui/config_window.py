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

import io
import json
import os
import sys
from dataclasses import replace

from PyQt6.QtCore import QProcess
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..config import ALL_EMOTION_TAGS, ExperimentSettings
from ..core.backgrounds import (
    CALM_GRADIENT,
    DEFAULT_EVERY_N,
    MAX_EVERY_N,
    MIN_EVERY_N,
    SPEC_DEFAULT,
    SPEC_NONE,
    SPEC_SLIDESHOW,
    friendly_name,
    list_pictures,
    resolve_background,
)
from .assets import audio_dir as _bundled_audio_dir
from .assets import background_folders, background_path, user_backgrounds_dir, user_data_dir

_CAPTIONS = ["none", "english", "mandarin"]
_MODES = ["test", "passive", "active"]
_MODE_LABELS = {"test": "Test", "passive": "Passive Training", "active": "Active Training"}
_EMOTION_LABELS = {"hap": "Happy", "sca": "Scared", "neu": "Neutral",
                   "sad": "Sad", "ang": "Angry"}

# Background preview size (16:9) and the participant window's plain colour
# (PsychoPy rgb -0.3 -> 89/255), shown for "None (plain)".
_THUMB_SIZE = (160, 90)
_PLAIN_RGB = (89, 89, 89)
# What "Add picture..." offers (patterns repeated in upper case for case-sensitive
# file dialogs on Linux).
_PICTURE_FILTER = "Pictures ({})".format(" ".join(
    f"*.{ext} *.{ext.upper()}" for ext in ("png", "jpg", "jpeg", "bmp", "gif", "webp")
))

# Light, high-contrast theme for the form (overrides the OS theme so labels are
# never light-on-light regardless of the user's desktop appearance).
_STYLE = """
QWidget { font-size: 14px; color: #20203a; }
QLabel { background: transparent; color: #20203a; }
QLabel#title { font-size: 22px; font-weight: 700; color: #2a2250; }
QLabel#subtitle { color: #5a5a7a; }
QFrame#card { background: #ffffff; border-radius: 14px; }
QLineEdit, QComboBox, QSpinBox {
    background: #ffffff; color: #20203a;
    border: 1px solid #c4c4d6; border-radius: 7px; padding: 7px 9px;
}
QLabel#preview { border: 1px solid #c4c4d6; border-radius: 6px; }
QLineEdit:focus, QComboBox:focus { border: 1px solid #6c5ce7; }
QComboBox::drop-down { border: none; width: 22px; }
QCheckBox { background: transparent; color: #20203a; spacing: 7px; }
QPushButton {
    background: #6c5ce7; color: #ffffff; border: none;
    border-radius: 9px; padding: 9px 18px; font-weight: 700;
}
QPushButton:hover { background: #5a4bd0; }
QPushButton:pressed { background: #4d3fb8; }
QPushButton:disabled { background: #b7b1e0; }
QPushButton#browse {
    background: #ececf5; color: #3a3a5a; font-weight: 600; padding: 7px 12px;
}
QPushButton#browse:hover { background: #dedeee; }
"""


def default_settings_path() -> str:
    """Where the last-used settings are remembered (~/.emognition/settings.json)."""
    base = user_data_dir()
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "settings.json")


def _thumbnail_image(value: str):
    """A small PIL preview of a background setting (Pillow only; no PsychoPy)."""
    from PIL import Image

    from ..imaging import render_background

    if value == SPEC_NONE:
        return Image.new("RGB", _THUMB_SIZE, _PLAIN_RGB)
    if value == SPEC_SLIDESHOW:
        # Side-by-side strips of the first few pictures say "these take turns".
        sources = list_pictures(*background_folders())[:3] or [CALM_GRADIENT]
        canvas = Image.new("RGB", _THUMB_SIZE)
        strip = _THUMB_SIZE[0] // len(sources)
        for i, source in enumerate(sources):
            image, _problem = render_background(source, _THUMB_SIZE)
            left = i * strip
            right = _THUMB_SIZE[0] if i == len(sources) - 1 else left + strip
            canvas.paste(image.crop((left, 0, right, _THUMB_SIZE[1])), (left, 0))
        return canvas
    source = CALM_GRADIENT if value == SPEC_DEFAULT else value
    image, _problem = render_background(source, _THUMB_SIZE)
    return image


def _pixmap(image) -> QPixmap:
    """Convert a PIL image to a QPixmap (via PNG bytes: no ImageQt version coupling)."""
    buf = io.BytesIO()
    image.save(buf, "PNG")
    pixmap = QPixmap()
    pixmap.loadFromData(buf.getvalue(), "PNG")
    return pixmap


def _default_save_dir() -> str:
    """Default report output folder: save_location/ beside the exe (or cwd)."""
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.getcwd()
    return os.path.join(base, "save_location")


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
        self._proc: QProcess | None = None
        self._monitor: "MonitorWindow | None" = None
        self._calib: "CalibrationWindow | None" = None
        self._log_fh = None   # open file handle for the session log
        self._thumbs: dict[str, QPixmap] = {}   # background previews, by setting value
        self.setWindowTitle("Emognition - Setup")
        self.setStyleSheet(_STYLE)
        self.resize(780, 700)
        self._build()
        if os.path.exists(self.settings_path):
            try:
                self.apply_settings(ExperimentSettings.load(self.settings_path))
            except Exception:
                pass  # corrupt/old settings -> just start from defaults
        # First-run defaults: pre-fill any folder that is still blank so the
        # experimenter can click Proceed without hunting for paths first.
        if not self.audio_dir.text():
            self.audio_dir.setText(_bundled_audio_dir())
        if not self.save_dir.text():
            self.save_dir.setText(_default_save_dir())

    # -- layout ----------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt signature)
        if not self._bg.isNull():
            QPainter(self).drawPixmap(self.rect(), self._bg)

    def _panel(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")               # styled white card (see _STYLE)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 90))
        frame.setGraphicsEffect(shadow)
        return frame

    def _build(self) -> None:
        self.participant = QLineEdit()
        self.experimenter = QLineEdit()
        self.audio_dir = QLineEdit()
        self.save_dir = QLineEdit()
        self.caption = QComboBox(); self.caption.addItems(_CAPTIONS)
        self.mode = QComboBox()
        self.mode.addItems([_MODE_LABELS[m] for m in _MODES])
        self.fullscreen = QCheckBox("Full screen")
        self.shuffle = QCheckBox("Shuffle order"); self.shuffle.setChecked(True)
        self.allow_replays = QCheckBox("Allow replays")
        self.amp_visualizer = QCheckBox("Amplitude visualizer")
        self.emotion_boxes = {
            tag: QCheckBox(_EMOTION_LABELS[tag]) for tag in ALL_EMOTION_TAGS
        }
        for box in self.emotion_boxes.values():
            box.setChecked(True)
        # Participant-window background (MATLAB: "Pictures Directory", "Pics
        # Interval [1-20]", "Shuffle images randomly").
        self.background = QComboBox()
        self.bg_preview = QLabel()
        self.bg_preview.setObjectName("preview")
        self.bg_preview.setFixedSize(*_THUMB_SIZE)
        self.bg_every = QSpinBox()
        self.bg_every.setRange(MIN_EVERY_N, MAX_EVERY_N)
        self.bg_every.setValue(DEFAULT_EVERY_N)
        self.bg_every.setToolTip("Slideshow: show each picture for this many trials.")
        self.bg_shuffle = QCheckBox("Shuffle pictures")
        self.bg_shuffle.setChecked(True)
        self.bg_shuffle.setToolTip("Slideshow: randomise the order the pictures appear in.")
        self._populate_backgrounds(SPEC_DEFAULT)
        self.background.currentIndexChanged.connect(self._on_background_changed)

        grid = QGridLayout()
        grid.setVerticalSpacing(8)
        grid.setContentsMargins(20, 20, 20, 20)
        r = 0
        title = QLabel("Speech Emotion Recognition")
        title.setObjectName("title")
        grid.addWidget(title, r, 0, 1, 3); r += 1
        subtitle = QLabel("Experimenter setup")
        subtitle.setObjectName("subtitle")
        grid.addWidget(subtitle, r, 0, 1, 3); r += 1

        grid.addWidget(QLabel("Participant"), r, 0); grid.addWidget(self.participant, r, 1, 1, 2); r += 1
        grid.addWidget(QLabel("Experimenter"), r, 0); grid.addWidget(self.experimenter, r, 1, 1, 2); r += 1
        grid.addWidget(QLabel("Audio folder"), r, 0); grid.addWidget(self.audio_dir, r, 1)
        grid.addWidget(self._browse_button(self.audio_dir), r, 2); r += 1
        grid.addWidget(QLabel("Save folder"), r, 0); grid.addWidget(self.save_dir, r, 1)
        grid.addWidget(self._browse_button(self.save_dir), r, 2); r += 1
        grid.addWidget(QLabel("Caption"), r, 0); grid.addWidget(self.caption, r, 1); r += 1
        grid.addWidget(QLabel("Mode"), r, 0); grid.addWidget(self.mode, r, 1); r += 1

        grid.addWidget(QLabel("Background"), r, 0); grid.addWidget(self.background, r, 1)
        add_picture = QPushButton("Add picture...")
        add_picture.setObjectName("browse")
        add_picture.setToolTip("Copy your own pictures into "
                               f"{user_backgrounds_dir()} (metadata such as GPS is removed).")
        add_picture.clicked.connect(self._add_pictures)
        grid.addWidget(add_picture, r, 2); r += 1
        bg_row = QHBoxLayout()
        bg_row.setContentsMargins(0, 0, 0, 0)
        bg_row.addWidget(self.bg_preview)
        bg_row.addStretch(1)
        bg_row.addWidget(QLabel("Change every"))
        bg_row.addWidget(self.bg_every)
        bg_row.addWidget(QLabel("trials"))
        bg_row.addSpacing(12)
        bg_row.addWidget(self.bg_shuffle)
        bg_w = QWidget(); bg_w.setLayout(bg_row)
        grid.addWidget(bg_w, r, 1, 1, 2); r += 1

        self.volume = QDoubleSpinBox()
        self.volume.setRange(0.0, 1.0); self.volume.setSingleStep(0.05); self.volume.setValue(0.8)
        opts = QHBoxLayout()
        for w in (self.fullscreen, self.shuffle, self.allow_replays, self.amp_visualizer):
            opts.addWidget(w)
        opts.addWidget(QLabel("Volume")); opts.addWidget(self.volume)
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
        grid.addWidget(self.status, r, 0, 1, 1)
        calib = QPushButton("Calibration...")
        calib.setObjectName("browse")
        calib.clicked.connect(self._open_calibration)
        grid.addWidget(calib, r, 1)
        self.proceed_btn = QPushButton("Proceed")
        self.proceed_btn.clicked.connect(self._on_proceed)
        # Update the button label when mode changes.
        self.mode.currentTextChanged.connect(self._update_proceed_label)
        self._update_proceed_label(self.mode.currentText())
        grid.addWidget(self.proceed_btn, r, 2); r += 1

        panel = self._panel(); panel.setLayout(grid)
        outer = QVBoxLayout(self)
        outer.addStretch(1)
        row = QHBoxLayout(); row.addStretch(1); row.addWidget(panel); row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)

    def _update_proceed_label(self, mode_label: str) -> None:
        labels = {
            "Test": "Proceed to Test",
            "Passive Training": "Start Passive Training",
            "Active Training": "Start Active Training",
        }
        self.proceed_btn.setText(labels.get(mode_label, "Proceed"))

    def _browse_button(self, target: QLineEdit) -> QPushButton:
        button = QPushButton("Browse...")
        button.setObjectName("browse")
        button.clicked.connect(lambda: self._browse_into(target))
        return button

    def _browse_into(self, target: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose folder", target.text() or os.getcwd())
        if path:
            target.setText(path)

    # -- background picker -------------------------------------------------

    def _populate_backgrounds(self, select: str) -> None:
        """(Re)fill the Background list -- bundled pictures, then the user's -- and select *select*."""
        bundled, user = background_folders()
        self.background.blockSignals(True)
        self.background.clear()
        self.background.addItem("Calm gradient (default)", SPEC_DEFAULT)
        for path in list_pictures(bundled):
            self.background.addItem(friendly_name(path), path)
        for path in list_pictures(user):
            self.background.addItem(f"{friendly_name(path)} (added)", path)
        self.background.addItem("Slideshow (all pictures)", SPEC_SLIDESHOW)
        self.background.addItem("None (plain)", SPEC_NONE)
        self.background.blockSignals(False)
        self._select_background(select)

    def _background_value(self) -> str:
        value = self.background.currentData()
        return value if isinstance(value, str) else SPEC_DEFAULT

    def _select_background(self, value: str) -> None:
        index = self.background.findData(value)
        if index < 0 and value and os.path.isfile(value):
            # A picture set elsewhere (e.g. on the command line): list it too.
            self.background.insertItem(self.background.count() - 2,
                                       f"{friendly_name(value)} (custom)", value)
            index = self.background.findData(value)
        self.background.setCurrentIndex(max(0, index))
        self._on_background_changed()

    def _on_background_changed(self, *_args) -> None:
        value = self._background_value()
        slideshow = value == SPEC_SLIDESHOW
        self.bg_every.setEnabled(slideshow)
        self.bg_shuffle.setEnabled(slideshow)
        if value not in self._thumbs:
            self._thumbs[value] = _pixmap(_thumbnail_image(value))
        self.bg_preview.setPixmap(self._thumbs[value])

    def _add_pictures(self) -> None:
        """"Add picture...": import into ~/.emognition/backgrounds, then select the last one."""
        from ..imaging import PictureError, import_picture

        paths, _filter = QFileDialog.getOpenFileNames(
            self, "Add background pictures", os.path.expanduser("~"), _PICTURE_FILTER)
        if not paths:
            return
        added, problems = [], []
        for path in paths:
            try:
                added.append(import_picture(path, user_backgrounds_dir()))
            except PictureError as exc:
                problems.append(str(exc))
            except OSError as exc:      # e.g. the personal folder isn't writable
                problems.append(f"{os.path.basename(path)}: {exc}")
        if added:
            self._populate_backgrounds(added[-1])
            self.status.setStyleSheet("color:#2e7d32;")
            self.status.setText(f"Added {len(added)} picture(s).")
        if problems:
            QMessageBox.warning(self, "Some pictures were not added", "\n".join(problems))

    # -- settings <-> form ----------------------------------------------

    def settings_from_form(self) -> ExperimentSettings:
        mode_label = self.mode.currentText()
        mode_key = next((k for k, v in _MODE_LABELS.items() if v == mode_label), "test")
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
            volume=self.volume.value(),
            emotions=[t for t, b in self.emotion_boxes.items() if b.isChecked()],
            mode=mode_key,
            background=self._background_value(),
            background_every=self.bg_every.value(),
            background_shuffle=self.bg_shuffle.isChecked(),
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
        self.volume.setValue(s.volume)
        for tag, box in self.emotion_boxes.items():
            box.setChecked(tag in s.emotions)
        if s.mode in _MODE_LABELS:
            self.mode.setCurrentText(_MODE_LABELS[s.mode])
        self.bg_every.setValue(s.background_every)
        self.bg_shuffle.setChecked(s.background_shuffle)
        self._select_background(s.background or SPEC_DEFAULT)

    # -- actions ---------------------------------------------------------

    def _on_proceed(self) -> None:
        if self._proc is not None and self._proc.state() != QProcess.ProcessState.NotRunning:
            return  # a session is already running; ignore (also: window is hidden)
        settings = self.settings_from_form()
        if not settings.emotions:
            self.status.setStyleSheet("color:#c62828;")
            self.status.setText("Select at least one emotion.")
            return
        try:   # same check the session makes, but before anything launches
            resolve_background(settings.background, picture_folders=background_folders())
        except ValueError as exc:
            self.status.setStyleSheet("color:#c62828;")
            self.status.setText(str(exc))
            return
        try:
            settings.save(self.settings_path)   # persist what the experimenter set
        except Exception:
            pass

        # Decide where the experiment runs: on an extended display (not the
        # experimenter's), fullscreen; otherwise honour the Full-screen checkbox.
        self._participant = settings.participant
        launch = replace(settings)
        launch.screen, launch.fullscreen = self._choose_display(settings.fullscreen)
        cmd = _experiment_command(launch.to_argv())
        self._proc = QProcess(self)
        self._proc.finished.connect(self._on_experiment_finished)
        self._proc.errorOccurred.connect(lambda _err: self._on_experiment_finished())
        self._proc.setProgram(cmd[0])
        self._proc.setArguments(cmd[1:])
        # Merge stdout + stderr so both land in our read slot and the log.
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        # We read output ourselves (not setStandardOutputFile) so we can parse
        # JSON status lines for the monitor AND write everything to the log.
        self._log_path = os.path.join(os.path.dirname(self.settings_path),
                                      "last_session.log")
        self._log_fh = open(self._log_path, "w", encoding="utf-8")
        self._proc.readyReadStandardOutput.connect(self._on_proc_output)

        # Open the monitor window on the experimenter's screen.
        # On a single-display setup the monitor would overlay the experiment,
        # so ask the experimenter whether they want it.
        if self._should_open_monitor():
            self._open_monitor(settings.participant, settings.mode)

        self.hide()
        self._proc.start()

    def _choose_display(self, user_fullscreen: bool) -> tuple[int, bool]:
        """Pick (screen_index, fullscreen) for the experiment window.

        With an extended display, run fullscreen on a screen OTHER than the one
        the setup window is on. With a single display, honour the checkbox.
        """
        screens = QApplication.screens()
        if len(screens) > 1:
            try:
                here = screens.index(self.screen())
            except ValueError:
                here = 0
            other = next((i for i in range(len(screens)) if i != here), 0)
            return other, True
        return 0, user_fullscreen

    def _should_open_monitor(self) -> bool:
        """Return True if the monitor window should be opened.

        With multiple screens the monitor always opens (it lives on the
        experimenter's screen while the experiment runs on another).  With a
        single screen, opening the monitor would overlay the experiment window,
        so we ask first.
        """
        if len(QApplication.screens()) > 1:
            return True
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Single monitor detected")
        dlg.setText(
            "Only one monitor is connected.\n\n"
            "The monitoring window will appear on the same screen as the "
            "experiment.\n\nOpen the monitoring window anyway?"
        )
        dlg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        dlg.setDefaultButton(QMessageBox.StandardButton.No)
        return dlg.exec() == QMessageBox.StandardButton.Yes

    def _open_monitor(self, participant: str, mode: str) -> None:
        """Open the experimenter monitor on the same screen as this window."""
        from .monitor_window import MonitorWindow

        if self._monitor is not None:
            self._monitor.close()
        self._monitor = MonitorWindow()
        # Seed it with the start event so the header is populated immediately.
        self._monitor.handle_event({"status": "start", "total": 0,
                                    "mode": mode, "participant": participant})
        # Position the monitor near the config window (top-right corner).
        my_geo = self.frameGeometry()
        self._monitor.move(my_geo.right() + 12, my_geo.top())
        self._monitor.show()

    def _on_proc_output(self) -> None:
        """Read stdout lines from the experiment process.

        Each line is written to the session log. Lines that look like JSON
        status events are also forwarded to the monitor window.
        """
        if self._proc is None:
            return
        data = self._proc.readAllStandardOutput()
        text = bytes(data).decode("utf-8", errors="replace")
        if self._log_fh is not None:
            try:
                self._log_fh.write(text)
                self._log_fh.flush()
            except Exception:
                pass
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("{") and self._monitor is not None:
                try:
                    self._monitor.handle_event(json.loads(line))
                except Exception:
                    pass

    def _open_calibration(self) -> None:
        from .calibration_window import CalibrationWindow

        self._calib = CalibrationWindow()
        self._calib.destroyed.connect(self._on_calibration_closed)
        self.hide()
        self._calib.show()

    def _on_calibration_closed(self) -> None:
        self._calib = None
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._calib is not None:
            self._calib.close()
            self._calib = None
        if self._monitor is not None:
            self._monitor.close()
            self._monitor = None
        if self._proc is not None and self._proc.state() != QProcess.ProcessState.NotRunning:
            self._proc.terminate()
        super().closeEvent(event)

    def _on_experiment_finished(self, *args) -> None:
        """Bring the setup window back once the experiment process has ended."""
        # Flush and close the log file.
        if self._log_fh is not None:
            try:
                self._log_fh.close()
            except Exception:
                pass
            self._log_fh = None
        # Close the monitor window.
        if self._monitor is not None:
            self._monitor.close()
            self._monitor = None
        if self.isVisible():
            return
        self.show()
        self.raise_()
        self.activateWindow()
        code = self._proc.exitCode() if self._proc is not None else 0
        who = getattr(self, "_participant", "")
        if code == 0:
            self.status.setStyleSheet("color:#2e7d32;")
            self.status.setText(f"Session for '{who}' finished.")
        else:
            self.status.setStyleSheet("color:#c62828;")
            self.status.setText(f"Session FAILED (exit {code}). See "
                                f"{getattr(self, '_log_path', 'last_session.log')}")


def run_config_ui(settings_path: str | None = None) -> int:
    """Open the setup screen; returns the Qt exit code when the window closes."""
    app = QApplication.instance() or QApplication(sys.argv[:1])
    window = ConfigWindow(settings_path=settings_path)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run_config_ui())
