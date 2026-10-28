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
import math
import os
import sys
from dataclasses import replace

from PyQt6.QtCore import QProcess, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..config import (
    ALL_EMOTION_TAGS,
    ExperimentSettings,
    amend_participant_id,
    has_reports,
    next_participant_id,
    resume_argv,
)
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
from ..io.autosave import find_interrupted, read_session_log
from ..io.lines import LineBuffer
from .theme import apply_theme
from .assets import audio_dir as _bundled_audio_dir
from .assets import (
    background_folders,
    background_path,
    default_save_dir as _default_save_dir,
    self_command,
    user_backgrounds_dir,
    user_data_dir,
)

_CAPTIONS = ["none", "english", "mandarin", "spanish"]
_MODES = ["test", "passive", "active"]
_MODE_LABELS = {"test": "Test", "passive": "Passive Training", "active": "Active Training"}
_EMOTION_LABELS = {"hap": "Happy", "sca": "Scared", "neu": "Neutral",
                   "sad": "Sad", "ang": "Angry"}

# Background preview size (16:9) and the participant window's plain colour
# (PsychoPy rgb -0.3 -> 89/255), shown for "None (plain)".
_THUMB_SIZE = (160, 90)
_ICON_SIZE = (48, 27)        # the small previews in the Background list
_PLAIN_RGB = (89, 89, 89)
# What "Add picture..." offers (patterns repeated in upper case for case-sensitive
# file dialogs on Linux).
_PICTURE_FILTER = "Pictures ({})".format(" ".join(
    f"*.{ext} *.{ext.upper()}" for ext in ("png", "jpg", "jpeg", "bmp", "gif", "webp")
))

# Layout and accents only: the colours, fields, checkboxes and arrows come from
# the shared theme (ui/theme.py), so every window and dialog looks the same.
_STYLE = """
QWidget { font-size: 14px; }
QLabel { background: transparent; }
QLabel#title { font-size: 22px; font-weight: 700; color: #2a2250; }
QLabel#subtitle { color: #5a5a7a; }
QFrame#card { background: #ffffff; border-radius: 14px; }
QLabel#preview { border: 1px solid #c4c4d6; border-radius: 6px; }
QCheckBox { background: transparent; }
QGroupBox { background: #fbfbfe; border: 1px solid #e3e3ef; border-radius: 10px;
            margin-top: 12px; padding-top: 6px; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px;
                   color: #5a4bd0; font-weight: 700; }
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
QPushButton#browse:disabled { background: #f2f2f7; color: #a3a3b8; }
"""


def default_settings_path() -> str:
    """Where the last-used settings are remembered (~/.emognition/settings.json)."""
    base = user_data_dir()
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "settings.json")


def _thumbnail_image(value: str, size: tuple[int, int] = _THUMB_SIZE):
    """A small PIL preview of a background setting (Pillow only; no PsychoPy)."""
    from PIL import Image

    from ..imaging import render_background

    if value == SPEC_NONE:
        return Image.new("RGB", size, _PLAIN_RGB)
    if value == SPEC_SLIDESHOW:
        # Side-by-side strips of the first few pictures say "these take turns".
        sources = list_pictures(*background_folders())[:3] or [CALM_GRADIENT]
        canvas = Image.new("RGB", size)
        strip = size[0] // len(sources)
        for i, source in enumerate(sources):
            image, _problem = render_background(source, size)
            left = i * strip
            right = size[0] if i == len(sources) - 1 else left + strip
            canvas.paste(image.crop((left, 0, right, size[1])), (left, 0))
        return canvas
    source = CALM_GRADIENT if value == SPEC_DEFAULT else value
    image, _problem = render_background(source, size)
    return image


def _pixmap(image) -> QPixmap:
    """Convert a PIL image to a QPixmap (via PNG bytes: no ImageQt version coupling)."""
    buf = io.BytesIO()
    image.save(buf, "PNG")
    pixmap = QPixmap()
    pixmap.loadFromData(buf.getvalue(), "PNG")
    return pixmap


def _unless_default(path: str, default: str) -> str:
    """"" if *path* is the default location (so the default is resolved at run time)."""
    if path and os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(default)):
        return ""
    return path


# Tooltips, written for the experimenter -- a technician, an SLP or an audiologist:
# what each setting does, what it changes in the data, and its default.
_TIPS = {
    "participant": (
        "Pseudonymous participant label, BIDS style (sub-001, sub-002, ...). Pre-filled with the "
        "next free number in the save folder; type your own if your study uses another scheme. "
        "It names every report file (letters, digits, '-' and '_' are kept)."),
    "new_id": "Fill in the next free BIDS-style ID (sub-NNN) for the save folder.",
    "experimenter": "Who runs the session. Recorded in every report and in the session's .json.",
    "mode": (
        "Test: no feedback; scored (confusion matrix, % correct, Wagner's Hu, Cohen's kappa).\n"
        "Passive training: each clip plays, then the correct face is shown; nothing is answered.\n"
        "Active training: the participant answers, then sees the correct face (green) and, if "
        "wrong, their choice (orange)."),
    "practice": (
        "Training modes: N warm-up trials, answered with feedback, before the session. Picked "
        "from the clips (one per emotion before any repeats) with the session's seed. Never "
        "scored; kept in the session's .json. 'off' = none."),
    "retry": (
        "Active training: a wrong answer greys out that face and asks again until the right one "
        "is chosen (the original's behaviour). Only the first answer is scored and timed; every "
        "answer is kept in the per-trial CSV ('attempts', 'choices')."),
    "emotions": (
        "The emotions tested: only their clips are presented and their faces shown, renumbered "
        "1..N. The confusion matrix, chance level (1/N) and kappa depend on this set."),
    "shuffle": (
        "Random presentation order, reproducible from the seed recorded in every report. "
        "Unticked: folder order."),
    "max_run": (
        "Constrained shuffle: never more than N clips of the same emotion in a row (long runs "
        "invite response strategies). 'off' = a plain shuffle."),
    "allow_replays": (
        "Show a replay button (and the R key) once each clip has ended. A replay restarts the RT "
        "clock, so the RT counts from the last playback; the number of replays is saved per trial "
        "('replays')."),
    "max_replays": (
        "Replays allowed per trial. Starts at the number of selected emotions (2 for happy vs "
        "sad) and follows it until you change it; 'no limit' allows any number. The button "
        "disappears once a trial's replays are used up."),
    "caption": "The word under each face: none (the original default), English, Spanish or Traditional Chinese.",
    "background": (
        "What the participant sees behind the faces. Pictures change only between trials and are "
        "decoded in advance, so they never affect audio timing or RTs. Bright pictures are dimmed "
        "so the white text stays readable."),
    "add_picture": (
        "Copy your own pictures into {folder}: turned upright, resized, converted to sRGB, and "
        "stripped of metadata such as phone GPS."),
    "bg_every": "Slideshow: each picture stays for this many trials (1-20).",
    "bg_shuffle": "Slideshow: random picture order (from the session's seed, so it is reproducible).",
    "fullscreen": (
        "Run the participant window full screen. With a second display connected, the session "
        "opens full screen there automatically, and this window stays on yours."),
    "amp_visualizer": "A small light that follows each clip's RMS envelope while it plays: a visual cue that sound is on.",
    "next_button": (
        "After each answer the participant clicks 'Ready for the next one?' (or you press Space) "
        "to hear the next clip: the original's Extra button. Untimed."),
    "stars_every": "A star every N trials, filling a row under the progress bar. Never tied to correctness. 'off' = no stars.",
    "break_every": "A 'Time for a short break!' screen every N trials; it waits for Continue. 'off' = no breaks.",
    "audio_dir": (
        "Folder of .wav stimuli, named 01_ang_f.wav (legacy) or speaker-01_emotion-angry_sex-f.wav "
        "(BIDS). Use Calibration... first to inspect the names, equalise loudness and trim silence."),
    "volume": (
        "Digital gain applied to every clip, 0-1 (0.80 = -1.9 dB). Set the presentation level "
        "with the SPL tone (Calibration...) at this same value, then leave it -- and the system "
        "volume -- unchanged."),
    "save_dir": "Where the reports (CSV, Excel, HTML, PDF, JSON) and the autosave of unfinished sessions go.",
    "calibration": "Inspect and rename the stimuli, equalise loudness, trim silence, and play the SPL calibration tone.",
    "resume": (
        "Finish a session that stopped early (a crash, a power cut, the window closed, or Esc then "
        "Y): it continues at the next trial with the same settings and order, and its reports "
        "cover the whole session."),
    "proceed": "Save these settings and start the session in its own window.",
}


class _ReplayLimitBox(QSpinBox):
    """Replays per trial: 1 to 10, then "no limit" (stored as 0)."""

    NO_LIMIT = 11

    def __init__(self) -> None:
        super().__init__()
        self.setRange(1, self.NO_LIMIT)
        self.lineEdit().setReadOnly(True)       # arrows and the wheel only: no stray typing

    def textFromValue(self, value: int) -> str:  # noqa: N802 (Qt signature)
        return "no limit" if value == self.NO_LIMIT else str(value)

    @property
    def limit(self) -> int:
        return 0 if self.value() == self.NO_LIMIT else self.value()

    def set_limit(self, limit: int) -> None:
        self.setValue(self.NO_LIMIT if limit <= 0 else min(limit, self.NO_LIMIT - 1))


def _row(*items, stretch: bool = True) -> QWidget:
    """Widgets (and str labels) side by side, as one widget a layout can hide."""
    box = QHBoxLayout()
    box.setContentsMargins(0, 0, 0, 0)
    for item in items:
        if isinstance(item, int):
            box.addSpacing(item)
        else:
            box.addWidget(QLabel(item) if isinstance(item, str) else item)
    if stretch:
        box.addStretch(1)
    widget = QWidget()
    widget.setLayout(box)
    return widget


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
        self._icon_queue: list[int] = []        # background items still waiting for an icon
        self._auto_id = ""                      # the ID this window filled in itself
        self._replays_auto = True               # the replay limit follows the emotion count
        self._notice_unfinished = False         # the status line is the "unfinished" notice
        self.setWindowTitle("Emognition - Setup")
        self.setStyleSheet(_STYLE)
        self.resize(1080, 780)
        self._build()
        notice = ""
        if os.path.exists(self.settings_path):
            try:
                self.apply_settings(ExperimentSettings.load(self.settings_path))
            except Exception:
                notice = "Saved settings could not be read; starting from defaults."
        if self.audio_dir.text() and not os.path.isdir(self.audio_dir.text()):
            notice = f"Saved audio folder not found ({self.audio_dir.text()}); using the bundled clips."
            self.audio_dir.clear()
        # First-run defaults: pre-fill any folder that is still blank so the
        # experimenter can click Proceed without hunting for paths first.
        if not self.audio_dir.text():
            self.audio_dir.setText(_bundled_audio_dir())
        if not self.save_dir.text():
            self.save_dir.setText(_default_save_dir())
        # A new session is usually a new participant: start from the next free ID.
        self._fill_next_id()
        if notice:
            self._say(notice, "#c62828")
        self._refresh_resume(announce=not notice)
        QTimer.singleShot(0, self._start_background_icons)    # after the window is up

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

    @staticmethod
    def _group(title: str) -> tuple[QGroupBox, QGridLayout]:
        box = QGroupBox(title)
        grid = QGridLayout(box)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        grid.setContentsMargins(12, 18, 12, 12)
        return box, grid

    @staticmethod
    def _tip(tip: str, *widgets: QWidget) -> None:
        for widget in widgets:
            widget.setToolTip(tip)

    def _labelled(self, grid: QGridLayout, row: int, text: str, widget: QWidget, tip: str,
                  extra: QWidget | None = None) -> None:
        """'Label  [widget] [extra]' on one grid row, the tooltip on both."""
        label = QLabel(text)
        self._tip(tip, label, widget)
        grid.addWidget(label, row, 0)
        grid.addWidget(widget, row, 1, 1, 1 if extra is not None else 2)
        if extra is not None:
            grid.addWidget(extra, row, 2)

    def _build(self) -> None:
        self._make_widgets()
        left, right = QVBoxLayout(), QVBoxLayout()
        left.setSpacing(12)
        right.setSpacing(12)

        box, g = self._group("Participant")
        self._labelled(g, 0, "Participant ID", self.participant, _TIPS["participant"], self.new_id_btn)
        self._labelled(g, 1, "Experimenter", self.experimenter, _TIPS["experimenter"])
        left.addWidget(box)

        box, g = self._group("Session")
        self._labelled(g, 0, "Mode", self.mode, _TIPS["mode"])
        g.addWidget(self.practice_row, 1, 0, 1, 3)
        g.addWidget(self.retry, 2, 0, 1, 3)
        emotions = QLabel("Emotions")
        self._tip(_TIPS["emotions"], emotions, *self.emotion_boxes.values())
        g.addWidget(emotions, 3, 0, Qt.AlignmentFlag.AlignTop)
        faces = QGridLayout()
        faces.setContentsMargins(0, 0, 0, 0)
        for i, box_ in enumerate(self.emotion_boxes.values()):
            faces.addWidget(box_, i // 3, i % 3)
        holder = QWidget(); holder.setLayout(faces)
        g.addWidget(holder, 3, 1, 1, 2)
        left.addWidget(box)

        box, g = self._group("Order and replays")
        g.addWidget(_row(self.shuffle, 16, self.max_run_label, self.max_run,
                         "of one emotion in a row"), 0, 0, 1, 3)
        g.addWidget(_row(self.allow_replays, 16, self.replay_limit_row), 1, 0, 1, 3)
        left.addWidget(box)
        left.addStretch(1)

        box, g = self._group("Participant screen")
        self._labelled(g, 0, "Caption", self.caption, _TIPS["caption"])
        self._labelled(g, 1, "Background", self.background, _TIPS["background"])
        g.addWidget(_row(self.bg_preview, 12, self.add_picture), 2, 1, 1, 2)
        g.addWidget(self.slideshow_row, 3, 0, 1, 3)
        g.addWidget(_row(self.fullscreen, 16, self.amp_visualizer), 4, 0, 1, 3)
        right.addWidget(box)

        box, g = self._group("Engagement and pacing")
        g.addWidget(self.next_button, 0, 0, 1, 3)
        g.addWidget(_row(self.stars_label, self.stars_every, "trials", 16,
                         self.break_label, self.break_every, "trials"), 1, 0, 1, 3)
        right.addWidget(box)

        box, g = self._group("Audio and files")
        self._labelled(g, 0, "Audio folder", self.audio_dir, _TIPS["audio_dir"],
                       self._browse_button(self.audio_dir))
        self._labelled(g, 1, "Volume", _row(self.volume, 8, self.volume_db), _TIPS["volume"])
        self._labelled(g, 2, "Save folder", self.save_dir, _TIPS["save_dir"],
                       self._browse_button(self.save_dir, on_change=self._on_save_dir_changed))
        right.addWidget(box)
        right.addStretch(1)

        title = QLabel("Speech Emotion Recognition")
        title.setObjectName("title")
        subtitle = QLabel("Experimenter setup -- hover over any setting for details")
        subtitle.setObjectName("subtitle")
        columns = QHBoxLayout()
        columns.setSpacing(16)
        columns.addLayout(left, 1)
        columns.addLayout(right, 1)
        footer = QHBoxLayout()
        footer.addWidget(self.status, 1)
        for button in (self.calib_btn, self.resume_btn, self.proceed_btn):
            footer.addWidget(button)

        card = QVBoxLayout()
        card.setContentsMargins(22, 20, 22, 18)
        card.setSpacing(10)
        card.addWidget(title)
        card.addWidget(subtitle)
        card.addLayout(columns)
        card.addLayout(footer)
        panel = self._panel(); panel.setLayout(card)
        outer = QVBoxLayout(self)
        outer.addStretch(1)
        row = QHBoxLayout(); row.addStretch(1); row.addWidget(panel); row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)

        self.mode.currentTextChanged.connect(self._on_mode_changed)
        self._on_mode_changed(self.mode.currentText())
        self.allow_replays.toggled.connect(self._on_replays_toggled)
        self.max_replays.valueChanged.connect(self._on_replay_limit_edited)
        for box_ in self.emotion_boxes.values():
            box_.toggled.connect(self._on_emotions_changed)
        self._on_replays_toggled(self.allow_replays.isChecked())
        self.save_dir.editingFinished.connect(self._on_save_dir_changed)

    def _make_widgets(self) -> None:
        """Every control, with its tooltip; :meth:`_build` lays them out."""
        tips = _TIPS
        self.participant = QLineEdit()
        self.new_id_btn = QPushButton("New ID")
        self.new_id_btn.setObjectName("browse")
        self.new_id_btn.clicked.connect(self._fill_next_id)
        self._tip(tips["new_id"], self.new_id_btn)
        self.experimenter = QLineEdit()
        self.audio_dir = QLineEdit()
        self.save_dir = QLineEdit()
        self.caption = QComboBox(); self.caption.addItems(_CAPTIONS)
        self.mode = QComboBox()
        self.mode.addItems([_MODE_LABELS[m] for m in _MODES])

        self.practice = self._every_spinbox(tips["practice"], maximum=20)
        practice_label = QLabel("Practice trials")
        self._tip(tips["practice"], practice_label)
        self.practice_row = _row(practice_label, self.practice, "before the session (not scored)")
        self.retry = QCheckBox("Retry until correct")
        self._tip(tips["retry"], self.retry)

        self.emotion_boxes = {tag: QCheckBox(_EMOTION_LABELS[tag]) for tag in ALL_EMOTION_TAGS}
        for box in self.emotion_boxes.values():
            box.setChecked(True)
        self.shuffle = QCheckBox("Shuffle order"); self.shuffle.setChecked(True)
        self._tip(tips["shuffle"], self.shuffle)
        self.max_run = self._every_spinbox(tips["max_run"], maximum=10)
        self.max_run_label = QLabel("At most")
        self._tip(tips["max_run"], self.max_run_label)
        self.allow_replays = QCheckBox("Allow replays")
        self._tip(tips["allow_replays"], self.allow_replays)
        self.max_replays = _ReplayLimitBox()
        self._tip(tips["max_replays"], self.max_replays)
        self.replay_limit_row = _row(self.max_replays, "per trial", stretch=False)
        self._tip(tips["max_replays"], self.replay_limit_row)

        self._tip(tips["caption"], self.caption)
        # Participant-window background (MATLAB: "Pictures Directory", "Pics
        # Interval [1-20]", "Shuffle images randomly").
        self.background = QComboBox()
        self.background.setIconSize(QSize(*_ICON_SIZE))
        self.add_picture = QPushButton("Add picture...")
        self.add_picture.setObjectName("browse")
        self._tip(tips["add_picture"].format(folder=user_backgrounds_dir()), self.add_picture)
        self.add_picture.clicked.connect(self._add_pictures)
        self.bg_preview = QLabel()
        self.bg_preview.setObjectName("preview")
        self.bg_preview.setFixedSize(*_THUMB_SIZE)
        self.bg_every = QSpinBox()
        self.bg_every.setRange(MIN_EVERY_N, MAX_EVERY_N)
        self.bg_every.setValue(DEFAULT_EVERY_N)
        self.bg_shuffle = QCheckBox("Shuffle pictures")
        self.bg_shuffle.setChecked(True)
        every_label = QLabel("Change picture every")
        self._tip(tips["bg_every"], every_label, self.bg_every)
        self._tip(tips["bg_shuffle"], self.bg_shuffle)
        self.slideshow_row = _row(every_label, self.bg_every, "trials", 16, self.bg_shuffle)
        self._populate_backgrounds(SPEC_DEFAULT)
        self.background.currentIndexChanged.connect(self._on_background_changed)
        self.fullscreen = QCheckBox("Full screen")
        self._tip(tips["fullscreen"], self.fullscreen)
        self.amp_visualizer = QCheckBox("Amplitude visualizer")
        self._tip(tips["amp_visualizer"], self.amp_visualizer)

        self.next_button = QCheckBox("Next button between trials")
        self._tip(tips["next_button"], self.next_button)
        self.stars_every = self._every_spinbox(tips["stars_every"])
        self.stars_label = QLabel("Star every")
        self._tip(tips["stars_every"], self.stars_label)
        self.break_every = self._every_spinbox(tips["break_every"])
        self.break_label = QLabel("Break every")
        self._tip(tips["break_every"], self.break_label)

        self.volume = QDoubleSpinBox()
        self.volume.setRange(0.0, 1.0); self.volume.setSingleStep(0.05); self.volume.setValue(0.8)
        self.volume.setMinimumWidth(110)
        self.volume_db = QLabel()                 # the same gain in dB, for the calibration notes
        self.volume.valueChanged.connect(self._show_volume_db)
        self._show_volume_db(self.volume.value())

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.calib_btn = QPushButton("Calibration...")
        self.calib_btn.setObjectName("browse")
        self.calib_btn.clicked.connect(self._open_calibration)
        self._tip(tips["calibration"], self.calib_btn)
        self.resume_btn = QPushButton("Resume...")
        self.resume_btn.setObjectName("browse")
        self.resume_btn.clicked.connect(self._resume_dialog)
        self._tip(tips["resume"], self.resume_btn)
        self.proceed_btn = QPushButton("Proceed")
        self.proceed_btn.clicked.connect(self._on_proceed)
        self._tip(tips["proceed"], self.proceed_btn)

    @staticmethod
    def _every_spinbox(tooltip: str, maximum: int = 50) -> QSpinBox:
        """A 0-*maximum* count box where 0 reads "off"."""
        box = QSpinBox()
        box.setRange(0, maximum)
        box.setSpecialValueText("off")
        box.setToolTip(tooltip)
        return box

    def _say(self, text: str, color: str = "#2e7d32") -> None:
        self.status.setStyleSheet(f"color:{color};")
        self.status.setText(text)
        self._notice_unfinished = False

    def _show_volume_db(self, value: float) -> None:
        db = 20.0 * math.log10(value) if value > 0 else float("-inf")
        self.volume_db.setText("silent" if value <= 0 else f"{db:+.1f} dB")

    # -- what applies when -----------------------------------------------------

    def _on_mode_changed(self, mode_label: str) -> None:
        """Proceed's label, and the options of this mode only (the rest are hidden)."""
        labels = {
            "Test": "Proceed to Test",
            "Passive Training": "Start Passive Training",
            "Active Training": "Start Active Training",
        }
        self.proceed_btn.setText(labels.get(mode_label, "Proceed"))
        training = mode_label in (_MODE_LABELS["passive"], _MODE_LABELS["active"])
        self.practice_row.setVisible(training)
        self.retry.setVisible(mode_label == _MODE_LABELS["active"])

    def _n_emotions(self) -> int:
        return max(1, sum(1 for b in self.emotion_boxes.values() if b.isChecked()))

    def _set_replay_limit(self, limit: int) -> None:
        """Set the limit without counting it as the experimenter's own choice."""
        self.max_replays.blockSignals(True)
        self.max_replays.set_limit(limit)
        self.max_replays.blockSignals(False)

    def _on_replays_toggled(self, on: bool) -> None:
        """Ticking Allow replays starts the limit at the number of selected emotions."""
        self.replay_limit_row.setVisible(on)
        if on:
            self._replays_auto = True
            self._set_replay_limit(self._n_emotions())

    def _on_replay_limit_edited(self, *_args) -> None:
        self._replays_auto = False              # from now on the experimenter's number stands

    def _on_emotions_changed(self, *_args) -> None:
        if self.allow_replays.isChecked() and self._replays_auto:
            self._set_replay_limit(self._n_emotions())

    # -- participant IDs and unfinished sessions -------------------------------

    def _save_folder(self) -> str:
        return self.save_dir.text().strip() or _default_save_dir()

    def _fill_next_id(self) -> None:
        """Put the save folder's next free BIDS-style ID in the field."""
        self._auto_id = next_participant_id(self._save_folder())
        self.participant.setText(self._auto_id)

    def _on_save_dir_changed(self) -> None:
        """A new save folder has its own IDs and unfinished sessions."""
        if self.participant.text().strip() in ("", self._auto_id):
            self._fill_next_id()                # only replace an ID the window chose
        self._refresh_resume()

    def _interrupted_sessions(self) -> list[tuple[str, str, dict]]:
        """(label, log path, header) for each unfinished session in the save folder."""
        sessions = []
        for path in find_interrupted(self._save_folder()):
            try:
                header, done = read_session_log(path)
            except (OSError, ValueError):
                continue
            total = len(header.get("trial_order") or [])
            started = str(header.get("started_at", ""))[:16].replace("T", " ")
            mode = _MODE_LABELS.get((header.get("settings") or {}).get("mode", "test"), "Test")
            label = f"{header.get('participant', '?')}  -  {mode}, started {started}  -  {len(done)} of {total} trials done"
            sessions.append((label, path, header))
        return sessions

    def _refresh_resume(self, announce: bool = False) -> int:
        """Show how many unfinished sessions the save folder has (button, and status line).

        The status line says so when *announce* is set, or when it already showed
        this notice (it then follows a change of save folder).
        """
        n = len(find_interrupted(self._save_folder()))
        self.resume_btn.setEnabled(n > 0)
        self.resume_btn.setText(f"Resume... ({n})" if n else "Resume...")
        if announce or self._notice_unfinished:
            if n:
                self._say(f"{n} unfinished session{'s' if n > 1 else ''} in the save folder: "
                          "click Resume... to finish it.", "#8a5300")
                self._notice_unfinished = True
            else:
                self._say("")
        return n

    def _resume_dialog(self) -> None:
        """Pick an unfinished session and carry it on where it stopped."""
        sessions = self._interrupted_sessions()
        if not sessions:
            self._say("No unfinished sessions in the save folder.")
            self._refresh_resume()
            return
        labels = [label for label, _path, _header in sessions]
        label, ok = QInputDialog.getItem(
            self, "Resume a session",
            "Unfinished sessions in the save folder (newest first). The session carries on at\n"
            "the next trial, with the settings and trial order it started with:",
            labels, 0, False)
        if not ok:
            return
        _label, path, header = sessions[labels.index(label)]
        settings = self.settings_from_form()          # only its display choice is used
        mode = (header.get("settings") or {}).get("mode", "test")
        self._launch(replace(settings, participant=str(header.get("participant", "")), mode=mode),
                     resume=path)

    def _resolve_existing_id(self, settings: ExperimentSettings) -> ExperimentSettings | None:
        """When the ID already has reports: use the next free one, reuse it, or edit it.

        Returns the settings to run with (possibly a new ID), or None to go back to
        the form. Reusing never touches the earlier reports: every file name has
        its own date and time.
        """
        folder = settings.save_dir or _default_save_dir()
        pid = settings.participant
        if not has_reports(pid, folder):
            return settings
        amended = amend_participant_id(pid, folder)
        use, reuse = f"Use {amended}", f"Reuse {pid}"
        choice = self._choose(
            "Participant ID already used",
            f"'{pid}' already has reports in {folder}.",
            f"{use}: a new participant gets the next free ID.\n"
            f"{reuse}: another session for the same participant; the earlier reports "
            "stay (every file name has its own date and time).\n"
            "Edit ID: go back and type a different one.",
            [use, reuse, "Edit ID"],
        )
        if choice == use:
            self.participant.setText(amended)
            self._auto_id = amended
            return replace(settings, participant=amended)
        if choice == reuse:
            return settings
        self.participant.setFocus()
        self.participant.selectAll()
        return None

    def _browse_button(self, target: QLineEdit, on_change=None) -> QPushButton:
        button = QPushButton("Browse...")
        button.setObjectName("browse")
        button.setToolTip("Choose a folder.")
        button.clicked.connect(lambda: self._browse_into(target, on_change))
        return button

    def _browse_into(self, target: QLineEdit, on_change=None) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose folder", target.text() or os.getcwd())
        if path:
            target.setText(path)
            if on_change is not None:
                on_change()

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
        self._start_background_icons()

    def _start_background_icons(self) -> None:
        """Give each Background item a small preview, one per event-loop turn."""
        self._icon_queue = list(range(self.background.count()))
        QTimer.singleShot(0, self._next_background_icon)

    def _next_background_icon(self) -> None:
        while self._icon_queue:
            index = self._icon_queue.pop(0)
            value = self.background.itemData(index)
            if not isinstance(value, str):
                continue
            try:
                icon = QIcon(_pixmap(_thumbnail_image(value, _ICON_SIZE)))
            except Exception:  # noqa: BLE001 -- a preview is a nicety
                continue
            self.background.setItemIcon(index, icon)
            QTimer.singleShot(0, self._next_background_icon)
            return

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
        self.slideshow_row.setVisible(value == SPEC_SLIDESHOW)     # slideshow settings only then
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
            self._say(f"Added {len(added)} picture(s).")
        if problems:
            QMessageBox.warning(self, "Some pictures were not added", "\n".join(problems))

    # -- settings <-> form ----------------------------------------------

    def settings_from_form(self) -> ExperimentSettings:
        mode_label = self.mode.currentText()
        mode_key = next((k for k, v in _MODE_LABELS.items() if v == mode_label), "test")
        return ExperimentSettings(
            participant=self.participant.text().strip() or next_participant_id(self._save_folder()),
            experimenter=self.experimenter.text().strip() or "APPstaff",
            # The bundled clips / default save folder are stored as "" ("use the
            # default"), never as this install's absolute path: after an upgrade
            # or a move, that path would point at a stale or missing copy.
            audio_dir=_unless_default(self.audio_dir.text().strip(), _bundled_audio_dir()),
            save_dir=_unless_default(self.save_dir.text().strip(), _default_save_dir()),
            caption=self.caption.currentText(),
            fullscreen=self.fullscreen.isChecked(),
            shuffle=self.shuffle.isChecked(),
            allow_replays=self.allow_replays.isChecked(),
            max_replays=self.max_replays.limit,
            amp_visualizer=self.amp_visualizer.isChecked(),
            volume=self.volume.value(),
            emotions=[t for t, b in self.emotion_boxes.items() if b.isChecked()],
            mode=mode_key,
            background=self._background_value(),
            background_every=self.bg_every.value(),
            background_shuffle=self.bg_shuffle.isChecked(),
            retry_until_correct=self.retry.isChecked(),
            next_button=self.next_button.isChecked(),
            stars_every=self.stars_every.value(),
            break_every=self.break_every.value(),
            max_run=self.max_run.value(),
            practice=self.practice.value(),
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
        self.amp_visualizer.setChecked(s.amp_visualizer)
        self.volume.setValue(s.volume)
        for tag, box in self.emotion_boxes.items():
            box.setChecked(tag in s.emotions)
        self.allow_replays.setChecked(s.allow_replays)
        if s.allow_replays:
            self._set_replay_limit(s.max_replays)   # the saved number is the experimenter's
            self._replays_auto = False
        if s.mode in _MODE_LABELS:
            self.mode.setCurrentText(_MODE_LABELS[s.mode])
        self.bg_every.setValue(s.background_every)
        self.bg_shuffle.setChecked(s.background_shuffle)
        self.retry.setChecked(s.retry_until_correct)
        self.next_button.setChecked(s.next_button)
        self.stars_every.setValue(s.stars_every)
        self.break_every.setValue(s.break_every)
        self.max_run.setValue(s.max_run)
        self.practice.setValue(s.practice)
        self._select_background(s.background or SPEC_DEFAULT)

    # -- actions ---------------------------------------------------------

    def _on_proceed(self) -> None:
        if self._proc is not None and self._proc.state() != QProcess.ProcessState.NotRunning:
            return  # a session is already running; ignore (also: window is hidden)
        settings = self.settings_from_form()
        if not settings.emotions:
            self._say("Select at least one emotion.", "#c62828")
            return
        try:   # same check the session makes, but before anything launches
            resolve_background(settings.background, picture_folders=background_folders())
        except ValueError as exc:
            self._say(str(exc), "#c62828")
            return
        resume = self._ask_resume(settings)
        if resume is None:
            return
        if not resume:
            settings = self._resolve_existing_id(settings)
            if settings is None:
                return
        self._launch(settings, resume=resume)

    def _launch(self, settings: ExperimentSettings, resume: str = "") -> None:
        """Start a session (or, with *resume*, carry an unfinished one on) in its own process."""
        self._settings_warning = ""
        if not resume:
            try:
                settings.save(self.settings_path)   # persist what the experimenter set
            except OSError as exc:
                self._settings_warning = f" (Settings could not be saved: {exc})"

        # Decide where the experiment runs: on an extended display (not the
        # experimenter's), fullscreen; otherwise honour the Full-screen checkbox.
        self._participant = settings.participant
        launch = replace(settings)
        launch.screen, launch.fullscreen = self._choose_display(settings.fullscreen)
        if resume:     # the log holds the settings; only the display is chosen now
            cmd = self_command(resume_argv(resume, launch.screen, launch.fullscreen))
        else:
            cmd = self_command(launch.to_argv())
        self._proc = QProcess(self)
        self._out = LineBuffer()            # reassembles lines split across pipe reads
        self._launch_error: str | None = None
        self._proc.finished.connect(self._on_experiment_finished)
        self._proc.errorOccurred.connect(self._on_process_error)
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

    def _ask_resume(self, settings: ExperimentSettings) -> str | None:
        """Offer to finish this participant's interrupted session, if one is saved.

        Returns the log to resume, "" for a new session, or None to cancel. The
        unfinished log is never deleted from here: its trials are real data.
        """
        folder = settings.save_dir or _default_save_dir()
        logs = find_interrupted(folder, settings.participant)
        if not logs:
            return ""
        try:
            header, done = read_session_log(logs[0])
        except (OSError, ValueError):
            return ""                         # unreadable: don't block a new session over it
        total = len(header.get("trial_order") or [])
        started = str(header.get("started_at", ""))[:16].replace("T", " ")
        choice = self._choose(
            "Unfinished session found",
            f"'{settings.participant}' has an unfinished session from {started}: "
            f"{len(done)} of {total} trials done.",
            "Resume carries on where it stopped, with the same settings and trial "
            "order. Either way, the trials already done stay saved.",
            ["Resume", "Start new", "Cancel"],
        )
        return {"Resume": logs[0], "Start new": ""}.get(choice)

    def _choose(self, title: str, text: str, detail: str, buttons: list[str]) -> str | None:
        """Ask a question with named buttons; return the one clicked (the first is the default)."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(title)
        box.setText(text)
        box.setInformativeText(detail)
        made = [box.addButton(label, QMessageBox.ButtonRole.ActionRole) for label in buttons]
        box.setDefaultButton(made[0])
        box.exec()
        clicked = box.clickedButton()
        return next((label for label, b in zip(buttons, made) if b is clicked), None)

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

        Every complete line goes to the session log; lines that look like JSON
        status events are also forwarded to the monitor window. Bytes are
        buffered until a line is complete (a pipe read can end mid-line, or in
        the middle of a multi-byte character).
        """
        if self._proc is None:
            return
        self._handle_lines(self._out.feed(bytes(self._proc.readAllStandardOutput())))

    def _handle_lines(self, lines: list[str]) -> None:
        for line in lines:
            if self._log_fh is not None:
                try:
                    self._log_fh.write(line + "\n")
                    self._log_fh.flush()
                except Exception:
                    pass
            stripped = line.strip()
            if stripped.startswith("{") and self._monitor is not None:
                try:
                    self._monitor.handle_event(json.loads(stripped))
                except Exception:
                    pass

    def _on_process_error(self, error) -> None:
        """QProcess error: a launch that never started must not look like success."""
        if error == QProcess.ProcessError.FailedToStart:
            detail = self._proc.errorString() if self._proc is not None else ""
            self._launch_error = f"Could not start the session: {detail}"
            self._on_experiment_finished()

    def _open_calibration(self) -> None:
        from .calibration_window import CalibrationWindow

        # The folder being set up, and the Volume the SPL tone must play at (the session's).
        self._calib = CalibrationWindow(folder=self.audio_dir.text().strip() or None,
                                        volume=self.volume.value())
        # Delete on close so 'destroyed' fires and the setup window comes back.
        self._calib.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
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
            self._proc.terminate()             # WM_CLOSE on Windows, SIGTERM elsewhere
            if not self._proc.waitForFinished(3000):
                self._proc.kill()
        super().closeEvent(event)
        # The app quits only when this window closes (see run_config_ui).
        QApplication.instance().quit()

    def _on_experiment_finished(self, *args) -> None:
        """Bring the setup window back once the experiment process has ended."""
        # Pass on a last line that had no newline, then close the log file.
        if getattr(self, "_out", None) is not None:
            self._handle_lines(self._out.flush())
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
        self._show_outcome()
        self._refresh_resume()            # a session may have finished one, or left one

    def _show_outcome(self) -> None:
        """Tell the experimenter honestly how the session ended."""
        log = getattr(self, "_log_path", "last_session.log")
        who = getattr(self, "_participant", "")
        launch_error = getattr(self, "_launch_error", None)
        proc = self._proc
        crashed = proc is not None and proc.exitStatus() == QProcess.ExitStatus.CrashExit
        code = proc.exitCode() if proc is not None else 0
        if launch_error:
            message, ok = launch_error, False
        elif crashed:
            message, ok = f"Session for '{who}' CRASHED. See {log}", False
        elif code == 3:     # app.py: the session ran but a report format failed
            message, ok = f"Session for '{who}' finished, but some reports failed. See {log}", False
        elif code != 0:
            message, ok = f"Session FAILED (exit {code}). See {log}", False
        else:
            message, ok = f"Session for '{who}' finished.", True
        message += getattr(self, "_settings_warning", "")
        self._say(message, "#2e7d32" if ok else "#c62828")
        if ok or code == 3:
            # A session was recorded: move on to the next free ID, so the next
            # participant isn't saved under this one by accident.
            self._fill_next_id()


def configure_app(app: QApplication) -> QApplication:
    """The shared light theme (ui/theme.py), and quit only when the setup window closes.

    Qt's default -- quit when the last *visible* window closes -- fired when the
    experimenter closed the monitor mid-session (the setup window is hidden
    then), and quitting destroys the QProcess, which kills the experiment.
    """
    apply_theme(app)
    app.setQuitOnLastWindowClosed(False)
    return app


def run_config_ui(settings_path: str | None = None) -> int:
    """Open the setup screen; returns the Qt exit code when the window closes."""
    app = configure_app(QApplication.instance() or QApplication(sys.argv[:1]))
    window = ConfigWindow(settings_path=settings_path)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run_config_ui())
