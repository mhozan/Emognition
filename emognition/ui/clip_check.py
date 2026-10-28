# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""The Calibration window's Clip check tab: a whole folder at a glance, any clip in depth.

Built to stay responsive with a large stimulus set:

1. **Quick check** (automatic; about a millisecond a clip): every file's level,
   clipping, DC offset, noise floor and speech span, and the flags, in a
   sortable table -- flagged clips first -- with a small waveform per row. Only
   the rows on screen are drawn.
2. **The selected clip** is fully analysed on its own (a few milliseconds for a
   short clip): waveform, spectrogram and RMS curve, large, with the speech
   span and what the trim would cut. It can be played -- Space, a double-click
   or the Play button -- through the session's own audio path and Volume, with
   a playhead.
3. **Analyze** (the deep analysis, on request, with an estimate of how long it
   will take): a spectrogram card for every clip, filled in as they're made; cancellable.
   Cards are kept as compressed PNG and decoded only when they're on screen, so
   even a large folder costs little memory.

Measuring runs on a thread pool (ui/jobs.py) and playing in a helper process
(ui/audition.py), so the window never waits for either.
"""

from __future__ import annotations

import io
import time
from collections import Counter, OrderedDict
from collections.abc import Callable, Sequence

import numpy as np
from PyQt6.QtCore import (
    QAbstractListModel,
    QAbstractTableModel,
    QEvent,
    QItemSelectionModel,
    QModelIndex,
    QPointF,
    QRectF,
    QSize,
    QSortFilterProxyModel,
    Qt,
    QThreadPool,
    QTimer,
)
from PyQt6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListView,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ..audio.analysis import (
    DIGITAL_SILENCE_DB,
    ClipAnalysis,
    ClipStats,
    Flag,
    analyse_clip,
    check_files,
    check_folder,
    db,
    wav_files,
)
from ..imaging.clips import clip_card
from .audition import AuditionPlayer
from .calibration_charts import CARD_H, CARD_W, FLAG_INK, ClipDetail, card_tooltip, range_text
from .calibration_help import TIPS, minus
from .jobs import Job

SORT_ROLE = Qt.ItemDataRole.UserRole          # what a column sorts by
CLIP_ROLE = Qt.ItemDataRole.UserRole + 1      # the row's ClipStats (the waveform cell)
ROW_ROLE = Qt.ItemDataRole.UserRole + 2       # a card's row in the table model

# (key, header, tooltip) for each table column.
_COLUMNS = (
    ("flag", "", "col_flag"),
    ("file", "File", "col_file"),
    ("wave", "Waveform", "col_wave"),
    ("duration", "Duration (s)", "col_duration_clip"),
    ("peak", "Peak (dBFS)", "col_peak_clip"),
    ("rms", "RMS (dBFS)", "col_rms_clip"),
    ("lead", "Before (ms)", "col_lead_clip"),
    ("tail", "After (ms)", "col_tail_clip"),
    ("noise", "Noise (dBFS)", "col_noise"),
    ("format", "Format", "col_format"),
    ("flags", "Flags", "col_flags"),
)
_KEYS = [key for key, _title, _tip in _COLUMNS]
_NUMERIC = {"duration", "peak", "rms", "lead", "tail", "noise"}
_SPEECH_WASH = QColor(234, 231, 252)
_WAVE = QColor(84, 72, 196)
_CLIPPED = QColor(214, 48, 49)
_DECODED_CARDS = 96          # card pictures kept decoded (the ones on screen, and a few more)
_FULL_ANALYSES = 32          # full analyses kept for the large view (spectrograms are big)
# Until this computer has been measured: seconds of work per second of audio, and per card.
_GUESS_PER_AUDIO_S = 0.004
_GUESS_PER_CARD = 0.006


def eta_text(seconds: float) -> str:
    """'about 3 s' / 'about 2 min' -- an estimate, so never more precise than that."""
    if seconds < 1.5:
        return "about 1 s"
    if seconds < 90:
        return f"about {round(seconds)} s"
    return f"about {round(seconds / 60)} min"


def folder_summary(clips: Sequence[ClipStats], flags: Sequence[Sequence[Flag]],
                   unreadable: Sequence[str] = ()) -> str:
    """The folder in one line: count, format, ranges, and how many clips are flagged."""
    parts: list[str] = []
    if clips:
        rates = sorted(Counter(c.rate for c in clips))
        channels = {c.channels for c in clips}
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
    if unreadable:
        parts.append(f"{len(unreadable)} unreadable: " + ", ".join(unreadable[:3])
                     + ("..." if len(unreadable) > 3 else ""))
    return " · ".join(parts)


def _card_png(analysis: ClipAnalysis, width: int, height: int, span: float) -> bytes:
    """A clip's card, as PNG bytes (small to keep; decoded only when it's on screen)."""
    buf = io.BytesIO()
    clip_card(analysis, width=width, height=height, span=span).save(buf, "PNG", compress_level=1)
    return buf.getvalue()


# -- the table ------------------------------------------------------------------

class ClipTable(QAbstractTableModel):
    """The quick check, one row per clip (sorting and filtering are the proxy's)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.clips: list[ClipStats] = []
        self.flags: list[list[Flag]] = []
        self._noise: list[float] = []

    def set_clips(self, clips: Sequence[ClipStats], flags: Sequence[Sequence[Flag]]) -> None:
        self.beginResetModel()
        self.clips, self.flags = list(clips), [list(f) for f in flags]
        self._noise = [c.noise_floor_db for c in self.clips]   # a percentile: once, not per paint
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.clips)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(_COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if orientation != Qt.Orientation.Horizontal:
            return None
        _key, title, tip = _COLUMNS[section]
        if role == Qt.ItemDataRole.DisplayRole:
            return title
        if role == Qt.ItemDataRole.ToolTipRole:
            return TIPS.get(tip)
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row, key = index.row(), _KEYS[index.column()]
        clip, flags = self.clips[row], self.flags[row]
        if role == Qt.ItemDataRole.DisplayRole:
            return self._text(key, clip, flags, row)
        if role == SORT_ROLE:
            return self._sort_key(key, clip, flags, row)
        if role == CLIP_ROLE:
            return clip
        if role == Qt.ItemDataRole.ToolTipRole:
            return card_tooltip(clip, flags)
        if role == Qt.ItemDataRole.ForegroundRole and flags and key in ("flag", "flags"):
            return QBrush(QColor(FLAG_INK))
        if role == Qt.ItemDataRole.TextAlignmentRole and key in _NUMERIC:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        return None

    def _text(self, key: str, clip: ClipStats, flags: list[Flag], row: int) -> str:
        if key == "flag":
            return "⚠" if flags else ""
        if key == "file":
            return clip.filename
        if key == "duration":
            return f"{clip.duration:.2f}"
        if key == "peak":
            return minus(f"{clip.peak_db:.1f}")
        if key == "rms":
            return minus(f"{clip.rms_db:.1f}")
        if key == "lead":
            return f"{clip.lead_silence * 1000:.0f}"
        if key == "tail":
            return f"{clip.tail_silence * 1000:.0f}"
        if key == "noise":
            noise = self._noise[row]
            return minus(f"< {DIGITAL_SILENCE_DB:.0f}") if noise <= DIGITAL_SILENCE_DB else minus(f"{noise:.1f}")
        if key == "format":
            layout = {1: "mono", 2: "stereo"}.get(clip.channels, f"{clip.channels} ch")
            return f"{clip.rate / 1000:g} kHz {layout}"
        if key == "flags":
            return ", ".join(f.label for f in flags)
        return ""                                         # the waveform is drawn, not written

    def _sort_key(self, key: str, clip: ClipStats, flags: list[Flag], row: int):
        name = clip.filename.lower()
        return {
            "flag": (0 if flags else 1, name),            # flagged first
            "file": name,
            "wave": clip.duration,
            "duration": clip.duration,
            "peak": clip.peak_db,
            "rms": clip.rms_db,
            "lead": clip.lead_silence,
            "tail": clip.tail_silence,
            "noise": self._noise[row],
            "format": (clip.rate, clip.channels),
            "flags": (-len(flags), ", ".join(f.label for f in flags), name),
        }[key]


class _ClipFilter(QSortFilterProxyModel):
    """Sorts by each column's own key, and can hide the clips without a flag."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._flagged_only = False
        self.setSortRole(SORT_ROLE)

    def set_flagged_only(self, on: bool) -> None:
        self.beginFilterChange()                      # (Qt 6.10+; invalidateFilter is deprecated)
        self._flagged_only = on
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:  # noqa: N802
        return not self._flagged_only or bool(self.sourceModel().flags[source_row])

    def lessThan(self, left, right) -> bool:  # noqa: N802
        a, b = left.data(SORT_ROLE), right.data(SORT_ROLE)
        try:
            return a < b
        except TypeError:
            return str(a) < str(b)


class _WaveDelegate(QStyledItemDelegate):
    """A clip's waveform in its table cell, with the detected speech shaded.

    The outline is built once per clip and cell size, then only translated: the
    rows on screen repaint at scrolling speed.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._paths: OrderedDict[tuple[str, int, int], QPainterPath] = OrderedDict()

    def sizeHint(self, option, index) -> QSize:  # noqa: N802
        return QSize(150, 30)

    def _outline(self, clip: ClipStats, w: int, h: int) -> QPainterPath:
        key = (clip.path, w, h)
        path = self._paths.get(key)
        if path is None:
            hi, lo = clip.wave_max, clip.wave_min
            n = hi.size
            cols = max(2, w // 2)                      # a point every 2 px is plenty
            edges = np.linspace(0, n, min(cols, n) + 1).astype(int)
            top = np.maximum.reduceat(hi, edges[:-1]) if n > 1 else hi
            bottom = np.minimum.reduceat(lo, edges[:-1]) if n > 1 else lo
            xs = np.linspace(0.0, float(w), top.size)
            mid, half = h / 2.0, h / 2.0
            path = QPainterPath()
            path.moveTo(QPointF(xs[0], mid - top[0] * half))
            for x, v in zip(xs[1:], top[1:]):
                path.lineTo(QPointF(x, mid - v * half))
            for x, v in zip(xs[::-1], bottom[::-1]):
                path.lineTo(QPointF(x, mid - v * half))
            path.closeSubpath()
            self._paths[key] = path
            while len(self._paths) > 2000:
                self._paths.popitem(last=False)
        return path

    def paint(self, painter: QPainter, option, index) -> None:
        super().paint(painter, option, index)          # background and selection
        clip = index.data(CLIP_ROLE)
        rect = QRectF(option.rect).adjusted(4, 3, -4, -3)
        if clip is None or rect.width() < 8 or rect.height() < 6:
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        span = max(clip.duration, 1e-3)
        x0 = rect.left() + clip.onset / span * rect.width()
        x1 = rect.left() + clip.offset / span * rect.width()
        painter.fillRect(QRectF(x0, rect.top(), max(1.0, x1 - x0), rect.height()), _SPEECH_WASH)
        painter.translate(rect.topLeft())
        painter.fillPath(self._outline(clip, int(rect.width()), int(rect.height())), QBrush(_WAVE))
        if clip.clipped:                               # clipped: red rails, as on the cards
            painter.setPen(QPen(_CLIPPED, 2.0))
            painter.drawLine(QPointF(0, 1), QPointF(rect.width(), 1))
            painter.drawLine(QPointF(0, rect.height() - 1), QPointF(rect.width(), rect.height() - 1))
        painter.restore()


# -- the deep analysis' cards --------------------------------------------------------

class _CardList(QAbstractListModel):
    """The deep analysis' cards, in the order they were made (each a PNG and its row)."""

    def __init__(self, table: ClipTable, parent=None) -> None:
        super().__init__(parent)
        self._table = table
        self.rows: list[int] = []
        self.pngs: list[bytes] = []

    def clear(self) -> None:
        self.beginResetModel()
        self.rows, self.pngs = [], []
        self.endResetModel()

    def add(self, row: int, png: bytes) -> None:
        if row in self.rows:
            return
        i = len(self.rows)
        self.beginInsertRows(QModelIndex(), i, i)
        self.rows.append(row)
        self.pngs.append(png)
        self.endInsertRows()

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.rows)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        if role == ROW_ROLE:
            return row
        if role == Qt.ItemDataRole.ToolTipRole and row < len(self._table.clips):
            return card_tooltip(self._table.clips[row], self._table.flags[row])
        return None


class _CardDelegate(QStyledItemDelegate):
    """Paints a card -- picture, name, numbers, flags -- decoding its PNG on first sight."""

    def __init__(self, table: ClipTable, cards: _CardList, parent=None) -> None:
        super().__init__(parent)
        self._table, self._cards = table, cards
        self._decoded: OrderedDict[int, QImage] = OrderedDict()
        self.dpr = 1.0

    def forget(self) -> None:
        self._decoded.clear()

    def sizeHint(self, option, index) -> QSize:  # noqa: N802
        return QSize(CARD_W + 16, CARD_H + 62)

    def _image(self, i: int) -> QImage:
        image = self._decoded.get(i)
        if image is None:
            image = QImage.fromData(self._cards.pngs[i], "PNG")
            image.setDevicePixelRatio(self.dpr)
            self._decoded[i] = image
            while len(self._decoded) > _DECODED_CARDS:
                self._decoded.popitem(last=False)
        else:
            self._decoded.move_to_end(i)
        return image

    def paint(self, painter: QPainter, option, index) -> None:
        row = index.data(ROW_ROLE)
        if row is None or row >= len(self._table.clips):
            return
        clip, flags = self._table.clips[row], self._table.flags[row]
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        rect = QRectF(option.rect).adjusted(3, 3, -3, -3)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#6c5ce7") if selected else QColor("#e3e3ef"), 2.0))
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawRoundedRect(rect, 8, 8)
        picture = QRectF(rect.left() + 5, rect.top() + 5, CARD_W, CARD_H)
        painter.drawImage(picture, self._image(index.row()))
        font = QFont(option.font)
        bold = QFont(font)
        bold.setBold(True)
        small = QFont(font)
        if font.pointSizeF() > 0:
            small.setPointSizeF(max(7.0, font.pointSizeF() * 0.88))
        y = picture.bottom() + 4
        fm = QFontMetricsF(bold)
        painter.setFont(bold)
        painter.setPen(QColor("#20203a"))
        painter.drawText(QPointF(picture.left(), y + fm.ascent()),
                         fm.elidedText(clip.filename, Qt.TextElideMode.ElideMiddle, CARD_W))
        y += fm.height()
        sfm = QFontMetricsF(small)
        painter.setFont(small)
        painter.setPen(QColor("#5a5a7a"))
        stats = minus(f"{clip.duration:.2f} s · peak {clip.peak_db:.1f} · "
                      f"RMS {clip.rms_db:.1f} dBFS")
        painter.drawText(QPointF(picture.left(), y + sfm.ascent()),
                         sfm.elidedText(stats, Qt.TextElideMode.ElideRight, CARD_W))
        if flags:
            y += sfm.height()
            painter.setPen(QColor(FLAG_INK))
            text = "  ".join(f"⚠ {f.label}" for f in flags)
            painter.drawText(QPointF(picture.left(), y + sfm.ascent()),
                             sfm.elidedText(text, Qt.TextElideMode.ElideRight, CARD_W))
        painter.restore()


# -- the tab ------------------------------------------------------------------------------

class ClipCheckTab(QWidget):
    """Quick check of a folder, the selected clip in depth (and playable), deep analysis on request.

    *volume* is the session's (clips play at it); *folder_source* gives the
    window's recordings folder (for Check again); *before_play* is called before
    a clip plays, to stop anything else using the audio device (the SPL tone).
    """

    def __init__(self, volume: float, folder_source: Callable[[], str],
                 before_play: Callable[[], None] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._volume = volume
        self._folder_source = folder_source
        self._before_play = before_play or (lambda: None)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(2)          # a folder job, and the selected clip beside it
        self.folder: str | None = None            # the folder the table shows
        self._check_job: Job | None = None
        self._clip_job: Job | None = None
        self._deep_job: Job | None = None
        self._analyses: OrderedDict[str, ClipAnalysis] = OrderedDict()   # full, for the large view
        self._card_pngs: dict[str, bytes] = {}    # cards already made (selected clips): reused
        self._per_audio_s: float | None = None    # measured: seconds of work per audio second
        self._per_card: float | None = None       # measured: seconds per card
        self._current: int | None = None          # the table row in the large view
        self._syncing = False
        self._playing = ""                        # the path being played
        self._play_t0 = 0.0
        self._play_duration = 0.0
        self._deep_t0 = 0.0

        self._build()
        self.player = AuditionPlayer(volume, self)
        self.player.starting.connect(lambda: self._say_play("Opening the audio device (a second or two)..."))
        self.player.playing.connect(self._on_playing)
        self.player.finished.connect(self._on_play_ended)
        self.player.stopped.connect(self._on_play_ended)
        self.player.failed.connect(self._on_play_failed)
        self._playhead = QTimer(self)
        self._playhead.setInterval(33)            # ~30 fps
        self._playhead.timeout.connect(self._tick)

    # -- layout -------------------------------------------------------------------

    def _build(self) -> None:
        self.check_btn = self._button("Check again", TIPS["check_again"], secondary=True)
        self.check_btn.clicked.connect(lambda: self.refresh(self._folder_source(), force=True))
        self.deep_btn = self._button("Analyze", TIPS["deep"])
        self.deep_btn.clicked.connect(self.start_deep_analysis)
        self.cancel_btn = self._button("Cancel", TIPS["cancel"], secondary=True)
        self.cancel_btn.clicked.connect(self.cancel_deep_analysis)
        self.cancel_btn.hide()
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(220)
        self.progress.setTextVisible(True)
        self.progress.hide()
        self.view_table = self._button("Table", TIPS["view_table"], secondary=True)
        self.view_cards = self._button("Cards", TIPS["view_cards"], secondary=True)
        views = QButtonGroup(self)
        for i, button in enumerate((self.view_table, self.view_cards)):
            button.setCheckable(True)
            views.addButton(button, i)
        self.view_table.setChecked(True)
        views.idClicked.connect(lambda i: self.stack.setCurrentIndex(i))
        self.flagged_only = QCheckBox("Flagged only")
        self.flagged_only.setToolTip(TIPS["flagged_only"])
        self.flagged_only.toggled.connect(self._on_flagged_only)
        self.status = QLabel("")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)

        self.table_model = ClipTable(self)
        self.proxy = _ClipFilter(self)
        self.proxy.setSourceModel(self.table_model)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.SortOrder.AscendingOrder)       # flagged first
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.setWordWrap(False)
        self.table.setItemDelegateForColumn(_KEYS.index("wave"), _WaveDelegate(self.table))
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        for key, width in (("flag", 28), ("file", 260), ("wave", 150)):
            self.table.setColumnWidth(_KEYS.index(key), width)
        self.table.selectionModel().currentRowChanged.connect(self._on_table_row)
        self.table.doubleClicked.connect(lambda _index: self.play_selected())

        self.cards_model = _CardList(self.table_model, self)
        self.cards = QListView()
        self.cards.setModel(self.cards_model)
        self._card_delegate = _CardDelegate(self.table_model, self.cards_model, self.cards)
        self.cards.setItemDelegate(self._card_delegate)
        self.cards.setViewMode(QListView.ViewMode.IconMode)
        self.cards.setResizeMode(QListView.ResizeMode.Adjust)
        self.cards.setMovement(QListView.Movement.Static)
        self.cards.setUniformItemSizes(True)
        self.cards.setSpacing(6)
        self.cards.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.cards.selectionModel().currentChanged.connect(self._on_card)
        self.cards.doubleClicked.connect(lambda _index: self.play_selected())
        for view in (self.table, self.cards):
            view.installEventFilter(self)              # Space plays / stops

        self.stack = QStackedWidget()
        self.stack.addWidget(self.table)
        self.stack.addWidget(self.cards)

        self.play_btn = self._button("▶ Play", TIPS["play"])
        self.play_btn.clicked.connect(self.toggle_play)
        self.play_btn.setEnabled(False)
        self.play_status = QLabel("")
        self.play_status.setObjectName("status")
        self.detail = ClipDetail()
        lower = QWidget()
        lower_layout = QVBoxLayout(lower)
        lower_layout.setContentsMargins(0, 4, 0, 0)
        lower_layout.addLayout(self._row(self.play_btn, 10, self.play_status))
        lower_layout.addWidget(self.detail, 1)

        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(self.stack)
        split.addWidget(lower)
        split.setSizes([360, 380])
        split.setChildrenCollapsible(False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._row(self.check_btn, self.deep_btn, self.progress, self.cancel_btn, 18,
                                   self.view_table, self.view_cards, 12, self.flagged_only))
        layout.addWidget(self.status)
        layout.addWidget(split, 1)

    @staticmethod
    def _button(text: str, tip: str, *, secondary: bool = False) -> QPushButton:
        button = QPushButton(text)
        button.setToolTip(tip)
        if secondary:
            button.setObjectName("secondary")
        return button

    @staticmethod
    def _row(*items) -> QHBoxLayout:
        row = QHBoxLayout()
        for item in items:
            if isinstance(item, int):
                row.addSpacing(item)
            else:
                row.addWidget(item)
        row.addStretch(1)
        return row

    @property
    def busy(self) -> bool:
        """True while anything is being measured (the quick check, a clip, the deep analysis)."""
        return any(job is not None for job in (self._check_job, self._clip_job, self._deep_job))

    # -- the quick check ----------------------------------------------------------------

    def refresh(self, folder: str, *, force: bool = False) -> None:
        """Quick-check *folder* (unless it's already the one shown and not *force*d)."""
        if folder == self.folder and not force:
            return
        self._stop_everything()
        self.folder = folder
        self._analyses.clear()
        self._card_pngs.clear()
        self._current = None
        self.cards_model.clear()
        self._card_delegate.forget()
        self.detail.set_clip(None)
        self.detail.set_message("Checking the folder...")

        def work(job: Job):
            t0 = time.perf_counter()
            clips, unreadable = check_files(wav_files(folder), progress=job.report,
                                            should_stop=lambda: job.cancelled)
            return clips, check_folder(clips), unreadable, time.perf_counter() - t0

        job = Job(work, self)
        job.progress.connect(lambda done, total: self._show_progress("Checking", done, total))
        job.done.connect(self._on_checked)
        job.failed.connect(self._on_check_failed)
        self._check_job = job
        self.status.setText("Checking the folder...")
        job.start(self._pool)

    def forget(self) -> None:
        """The folder's files changed (renamed): check it again next time it's shown."""
        self.folder = None

    def _on_checked(self, result) -> None:
        if self.sender() is not self._check_job:
            return
        self._check_job = None
        self.progress.hide()
        clips, flags, unreadable, seconds = result
        self.table_model.set_clips(clips, flags)
        self.table.resizeColumnsToContents()              # samples the rows; cheap
        for key, cap in (("file", 300), ("wave", 150)):
            column = _KEYS.index(key)
            self.table.setColumnWidth(column, min(max(self.table.columnWidth(column), 120), cap))
        self.status.setText(folder_summary(clips, flags, unreadable)
                            + f" · checked in {seconds:.2f} s")
        self._update_deep_button()
        if self.proxy.rowCount():
            self.table.setCurrentIndex(self.proxy.index(0, 0))   # the first flagged clip, or the first
            self.table.setFocus()
        else:
            self.detail.set_message("No clips to show.")

    def _on_check_failed(self, message: str) -> None:
        if self.sender() is not self._check_job:
            return
        self._check_job = None
        self.progress.hide()
        self.table_model.set_clips([], [])
        self.detail.set_message("")
        self.status.setText(f"Could not read the folder: {message}")

    def _on_flagged_only(self, on: bool) -> None:
        self.proxy.set_flagged_only(on)

    # -- the selected clip, in depth -----------------------------------------------------

    def _on_table_row(self, current, _previous) -> None:
        if self._syncing or not current.isValid():
            return
        self._show(self.proxy.mapToSource(current).row())

    def _on_card(self, current, _previous) -> None:
        if self._syncing or not current.isValid():
            return
        row = current.data(ROW_ROLE)
        if row is None:
            return
        self._show(row)
        source = self.table_model.index(row, 0)          # follow it in the table too
        index = self.proxy.mapFromSource(source)
        if index.isValid():
            self._syncing = True
            self.table.selectionModel().setCurrentIndex(
                index, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
            self._syncing = False

    def selected_clip(self) -> ClipStats | None:
        if self._current is None or self._current >= len(self.table_model.clips):
            return None
        return self.table_model.clips[self._current]

    def _show(self, row: int) -> None:
        """Put the clip of table *row* in the large view (analysing it first if need be)."""
        if row == self._current:
            return
        if self._playing:
            self.player.stop()                             # a new clip: the old one stops
        self._current = row
        clip, flags = self.table_model.clips[row], self.table_model.flags[row]
        self.play_btn.setEnabled(True)
        analysis = self._analyses.get(clip.path)
        if analysis is not None:
            self._analyses.move_to_end(clip.path)
            self.detail.set_clip(analysis, flags)
            return
        self.detail.set_clip(None)
        self.detail.set_message(f"Analysing {clip.filename}...")
        self._analyse(row)

    def _analyse(self, row: int) -> None:
        if self._clip_job is not None:
            self._clip_job.cancel()                        # its result is no longer wanted
        clip = self.table_model.clips[row]
        dpr, span = self.devicePixelRatioF(), self._span()
        size = (round(CARD_W * dpr), round(CARD_H * dpr))

        def work(job: Job):
            t0 = time.perf_counter()
            analysis = analyse_clip(clip.path)
            t1 = time.perf_counter()
            png = _card_png(analysis, size[0], size[1], span)   # for the gallery, and to time it
            return row, analysis, png, t1 - t0, time.perf_counter() - t1

        job = Job(work, self)
        job.done.connect(self._on_analysed)
        job.failed.connect(self._on_analysis_failed)
        self._clip_job = job
        job.start(self._pool)

    def _on_analysed(self, result) -> None:
        row, analysis, png, t_analysis, t_card = result
        self._remember(analysis, png)
        self._learn(analysis.duration, t_analysis, t_card)
        if self.sender() is self._clip_job:
            self._clip_job = None
        if row == self._current:
            self.detail.set_clip(analysis, self.table_model.flags[row])
        self._update_deep_button()

    def _on_analysis_failed(self, message: str) -> None:
        if self.sender() is self._clip_job:
            self._clip_job = None
            self.detail.set_message(f"Could not analyse this clip: {message}")

    def _remember(self, analysis: ClipAnalysis, png: bytes | None = None) -> None:
        self._analyses[analysis.path] = analysis
        self._analyses.move_to_end(analysis.path)
        while len(self._analyses) > _FULL_ANALYSES:
            self._analyses.popitem(last=False)
        if png is not None:
            self._card_pngs[analysis.path] = png

    def _learn(self, duration: float, t_analysis: float, t_card: float) -> None:
        """Refine the estimate of a deep analysis from one clip really done here."""
        per_s = t_analysis / max(duration, 0.05)
        self._per_audio_s = per_s if self._per_audio_s is None else 0.7 * self._per_audio_s + 0.3 * per_s
        self._per_card = t_card if self._per_card is None else 0.7 * self._per_card + 0.3 * t_card

    def _span(self) -> float:
        """The cards' shared time scale: the longest clip."""
        return max((c.duration for c in self.table_model.clips), default=1.0)

    # -- deep analysis ----------------------------------------------------------------

    def estimate(self) -> float:
        """Seconds a deep analysis of the whole folder should take on this computer."""
        clips = self.table_model.clips
        per_s = self._per_audio_s if self._per_audio_s is not None else _GUESS_PER_AUDIO_S
        per_card = self._per_card if self._per_card is not None else _GUESS_PER_CARD
        todo = [c for c in clips if c.path not in self._card_pngs]
        return sum(c.duration for c in todo) * per_s + len(todo) * per_card

    def _update_deep_button(self) -> None:
        clips = self.table_model.clips
        self.deep_btn.setEnabled(bool(clips) and self._deep_job is None)
        if not clips:
            self.deep_btn.setText("Analyze")
        elif all(c.path in self._card_pngs for c in clips):
            self.deep_btn.setText("Analyze (done)")         # shows the cards again, at once
        else:
            self.deep_btn.setText(f"Analyze ({eta_text(self.estimate())})")

    def start_deep_analysis(self) -> None:
        """A spectrogram card for every clip, flagged first; shown as they're made."""
        if self._deep_job is not None or not self.table_model.clips:
            return
        clips, flags = self.table_model.clips, self.table_model.flags
        order = sorted(range(len(clips)), key=lambda r: (not flags[r], clips[r].filename.lower()))
        known = dict(self._card_pngs)                      # a snapshot: the worker never shares
        dpr, span = self.devicePixelRatioF(), self._span()
        size = (round(CARD_W * dpr), round(CARD_H * dpr))
        self._card_delegate.dpr = dpr
        self.cards_model.clear()
        self._card_delegate.forget()
        self.view_cards.setChecked(True)
        self.stack.setCurrentIndex(1)

        def work(job: Job):
            for i, row in enumerate(order):
                if job.cancelled:
                    break
                clip = clips[row]
                png = known.get(clip.path)
                analysis = None
                if png is None:
                    analysis = analyse_clip(clip.path)
                    png = _card_png(analysis, size[0], size[1], span)
                job.deliver((row, analysis, png))
                job.report(i + 1, len(order))
            return job.cancelled

        job = Job(work, self)
        job.item.connect(self._on_card_made)
        job.progress.connect(lambda done, total: self._show_progress("Analysing", done, total, eta=True))
        job.done.connect(self._on_deep_done)
        job.failed.connect(self._on_deep_failed)
        self._deep_job = job
        self._deep_t0 = time.perf_counter()
        self.deep_btn.setEnabled(False)
        self.cancel_btn.show()
        self._show_progress("Analysing", 0, len(order), eta=True)
        job.start(self._pool)

    def cancel_deep_analysis(self) -> None:
        if self._deep_job is not None:
            self._deep_job.cancel()

    def _on_card_made(self, item) -> None:
        if self.sender() is not self._deep_job:
            return
        row, analysis, png = item
        if analysis is not None:
            self._card_pngs[analysis.path] = png           # small; the analysis itself isn't kept
        self.cards_model.add(row, png)

    def _on_deep_done(self, cancelled: bool) -> None:
        if self.sender() is not self._deep_job:
            return
        self._deep_job = None
        self.progress.hide()
        self.cancel_btn.hide()
        seconds = time.perf_counter() - self._deep_t0
        n = self.cards_model.rowCount()
        self.status.setText(
            folder_summary(self.table_model.clips, self.table_model.flags)
            + (f" · analysis cancelled after {n} cards" if cancelled
               else f" · analysis: {n} cards in {seconds:.1f} s"))
        self._update_deep_button()

    def _on_deep_failed(self, message: str) -> None:
        if self.sender() is not self._deep_job:
            return
        self._deep_job = None
        self.progress.hide()
        self.cancel_btn.hide()
        self.status.setText(f"Analysis stopped: {message}")
        self._update_deep_button()

    def _show_progress(self, what: str, done: int, total: int, *, eta: bool = False) -> None:
        self.progress.setMaximum(max(1, total))
        self.progress.setValue(done)
        self.progress.setFormat(f"{what} %v / %m")
        self.progress.show()
        if eta and done:
            left = (time.perf_counter() - self._deep_t0) / done * (total - done)
            self.status.setText(f"Analysis: {done} of {total} clips · {eta_text(left)} left")

    # -- listening ---------------------------------------------------------------------

    def toggle_play(self) -> None:
        if self._playing:
            self.player.stop()
        else:
            self.play_selected()

    def play_selected(self) -> None:
        clip = self.selected_clip()
        if clip is None:
            return
        self._before_play()                               # e.g. the SPL tone
        self._playing = clip.path
        self.play_btn.setText("■ Stop")
        if self.player.ready:
            self._say_play("")
        self.player.play(clip.path)

    def _on_playing(self, path: str, duration: float) -> None:
        self._playing, self._play_duration = path, duration
        self._play_t0 = time.monotonic()
        self._say_play(f"Playing · {duration:.2f} s · at Volume {self._volume:.2f} "
                       f"({minus(f'{db(self._volume):+.1f}')} dB), as in a session")
        self._playhead.start()

    def _tick(self) -> None:
        clip = self.selected_clip()
        t = time.monotonic() - self._play_t0
        if not self._playing or t > self._play_duration + 0.1:
            self._playhead.stop()
            self.detail.set_playhead(None)
            return
        if clip is not None and clip.path == self._playing:
            self.detail.set_playhead(min(t, self._play_duration))
        else:
            self.detail.set_playhead(None)

    def _on_play_ended(self, _path: str = "") -> None:
        self._playing = ""
        self._playhead.stop()
        self.detail.set_playhead(None)
        self.play_btn.setText("▶ Play")
        self._say_play("")

    def _on_play_failed(self, message: str) -> None:
        self._on_play_ended()
        self._say_play(message, error=True)

    def _say_play(self, text: str, *, error: bool = False) -> None:
        self.play_status.setStyleSheet("color: #c62828;" if error else "")
        self.play_status.setText(text)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Space:
            self.toggle_play()
            return True
        return super().eventFilter(obj, event)

    # -- the end ----------------------------------------------------------------------

    def _stop_everything(self) -> None:
        for job in (self._check_job, self._clip_job, self._deep_job):
            if job is not None:
                job.cancel()
        self._check_job = self._clip_job = self._deep_job = None
        self.progress.hide()
        self.cancel_btn.hide()
        if self._playing:
            self.player.stop()

    def stop_audio(self) -> None:
        """Free the audio device (the player helper ends)."""
        self._on_play_ended()
        self.player.shutdown()

    def shutdown(self, wait_ms: int = 5000) -> None:
        """Before the window closes: stop the work, end the player, wait for the threads."""
        self._stop_everything()
        self.stop_audio()
        self._pool.waitForDone(wait_ms)
