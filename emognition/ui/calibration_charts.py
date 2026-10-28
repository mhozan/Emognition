# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""The Calibration window's pictures, drawn with QPainter.

* :class:`StripChart` -- every clip before and after calibration, one dot each.
* :class:`BalanceChart` -- clips per emotion and speaker sex.
* :class:`ClipDetail` -- one clip, large, with axes: waveform, spectrogram, RMS,
  and a playhead while it plays.

As in the HTML report's charts (reports/charts.py), a chart is just linear maps
from data to pixels; drawing them by hand rather than through a plotting
library keeps them crisp at any screen scale, in the window's own font, and lets
every mark answer the mouse. The look follows one rule set: thin marks with a
ring in the surface colour, hairline grids, reference lines dashed (they are
thresholds), text in ink colours rather than data colours, and the calibrated
values in the accent over the recorded ones in grey -- the story is "after".
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from html import escape

from PyQt6.QtCore import QPointF, QRect, QRectF, QSize, Qt
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath, QPen, QPolygonF,
)
from PyQt6.QtWidgets import QSizePolicy, QToolTip, QWidget

from ..audio.analysis import DIGITAL_SILENCE_DB, THRESHOLD_DB, ClipAnalysis, ClipStats, Flag
from ..audio.preprocess import DEFAULT_PAD_S
from ..audio.review import Metric
from ..imaging.clips import CURVE_FLOOR_DB, curve_image, spectrogram_image, waveform_image
from . import theme
from .calibration_help import minus

SURFACE = QColor("#ffffff")
INK = QColor(theme.INK)
MUTED = QColor(theme.MUTED)
GRID = QColor("#e8e8f0")          # hairline gridlines, one step off the surface
FRAME = QColor("#c4c4d6")
BEFORE = QColor("#8a8aa6")        # the recorded values: de-emphasis grey (3.4:1 on white)
AFTER = QColor(theme.ACCENT)      # the calibrated values: the accent
LIMITED = QColor("#d9622b")       # peak-limited clips (a warning), always with a triangle
FLAG_BG, FLAG_INK = "#fdecea", "#9b1c1c"
# Speaker sex in the balance chart: three categorical hues, validated for colour-blind
# separation in this order (the light aqua carries its count as a label, as every bar does).
SERIES = (QColor("#2a78d6"), QColor("#eb6834"), QColor("#1baf7a"))

# The clip cards' size in the gallery (logical pixels).
CARD_W, CARD_H = 248, 128


# -- small helpers ------------------------------------------------------------

def nice_ticks(lo: float, hi: float, count: int = 5) -> list[float]:
    """Round tick values (1, 2 or 5 x 10^k apart) from at or below *lo* to at or above *hi*."""
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return [0.0, 1.0]
    lo, hi = min(lo, hi), max(lo, hi)
    if hi - lo < 1e-9:                        # one value: give it some room
        pad = abs(lo) * 0.1 or 1.0
        lo, hi = lo - pad, hi + pad
    raw = (hi - lo) / max(1, count)
    mag = 10.0 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1.0, 2.0, 5.0, 10.0) if m * mag >= raw * 0.999)
    first = math.floor(lo / step + 1e-9) * step
    last = math.ceil(hi / step - 1e-9) * step
    n = int(round((last - first) / step))
    return [round(first + i * step, 10) for i in range(n + 1)]


def _decimals(ticks: Sequence[float]) -> int:
    """Enough decimals to tell neighbouring ticks apart."""
    if len(ticks) < 2:
        return 1
    step = abs(ticks[1] - ticks[0])
    return max(0, -math.floor(math.log10(step) + 1e-9)) if step < 1 else 0


def fmt_value(value: float, unit: str) -> str:
    """A value at the precision its unit deserves (s: 2 decimals, ms: none, dB: one)."""
    decimals = {"s": 2, "ms": 0}.get(unit, 1)
    return minus(f"{value:.{decimals}f}")


def range_text(lo: float, hi: float, unit: str) -> str:
    """'1.55-2.05', or one value when both ends round alike."""
    a, b = fmt_value(lo, unit), fmt_value(hi, unit)
    if a == b:
        return a
    return f"{a} to {b}" if lo < 0 else f"{a}–{b}"


def summary_lines(metrics: Sequence[Metric]) -> list[str]:
    """What calibration does to the set, in a few lines (the chart's last cell)."""
    by = {m.key: m for m in metrics}
    lines: list[str] = []
    loud = by.get("loudness")
    if loud is not None:
        unit = "LU" if loud.unit == "LUFS" else "dB"
        lines.append(f"{loud.title} spread: {fmt_value(loud.spread_before, unit)} → "
                     f"{fmt_value(loud.spread_after, unit)} {unit}")
    for key in ("tail", "lead"):
        m = by.get(key)
        if m is not None:
            lines.append(f"{m.title}: {range_text(*m.span(m.before), 'ms')} → "
                         f"{range_text(*m.span(m.after), 'ms')} ms")
    duration = by.get("duration")
    if duration is not None and duration.before:
        cuts = [b - a for b, a in zip(duration.before, duration.after)]
        lines.append(f"Shorter by {range_text(min(cuts), max(cuts), 's')} s")
    if loud is not None and any(loud.limited):
        n = sum(loud.limited)
        lines.append(f"{n} clip{'s' if n != 1 else ''} peak-limited")
    return lines


def qimage_from_rgb(data: bytes, width: int, height: int, dpr: float = 1.0) -> QImage:
    """A QImage (deep copy) from packed RGB bytes, e.g. a PIL image's tobytes()."""
    image = QImage(data, width, height, 3 * width, QImage.Format.Format_RGB888).copy()
    image.setDevicePixelRatio(dpr)
    return image


def pil_to_qimage(picture, dpr: float = 1.0) -> QImage:
    rgb = picture.convert("RGB")
    return qimage_from_rgb(rgb.tobytes(), rgb.width, rgb.height, dpr)


def _jitter(index: int) -> float:
    """A fixed offset in -0.5..0.5 per clip (golden-ratio steps), so dots overlap less."""
    return (index * 0.6180339887) % 1.0 - 0.5


def _marker(p: QPainter, centre: QPointF, color: QColor, triangle: bool = False,
            radius: float = 4.0) -> None:
    """A filled dot (or downward triangle) with a 2 px ring in the surface colour."""
    p.setPen(QPen(SURFACE, 2.0))
    p.setBrush(QBrush(color))
    if triangle:
        r = radius * 1.3
        p.drawPolygon(QPolygonF([QPointF(centre.x() - r, centre.y() - r * 0.75),
                                 QPointF(centre.x() + r, centre.y() - r * 0.75),
                                 QPointF(centre.x(), centre.y() + r)]))
    else:
        p.drawEllipse(centre, radius + 1.0, radius + 1.0)


def _small(font: QFont, scale: float = 0.9) -> QFont:
    small = QFont(font)
    if font.pointSizeF() > 0:
        small.setPointSizeF(max(7.0, font.pointSizeF() * scale))
    else:
        small.setPixelSize(max(9, round(font.pixelSize() * scale)))
    return small


def _bold(font: QFont) -> QFont:
    bold = QFont(font)
    bold.setBold(True)
    return bold


# -- before vs after ------------------------------------------------------------

class StripChart(QWidget):
    """Before vs after calibration: one panel per quantity, one dot per clip.

    Each panel has two rows on one x axis -- the clips as recorded (grey) and as
    calibrated (the accent) -- with the target, ceiling or padding as a dashed
    line. Hovering a dot names its clip and lights that clip up in every panel,
    so one odd recording can be followed through all of them. Every value is
    also in the table beside the chart (tooltips never gate a number).
    """

    COLUMNS = 2
    PANEL_H = 112
    LEGEND_H = 28
    LABEL_W = 82          # "Recorded" / "Calibrated"
    RANGE_W = 98          # each row's range, at its right end
    RADIUS = 4.0          # 8 px markers
    HIT = 12.0            # 24 px hit targets
    JITTER = 12.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._metrics: list[Metric] = []
        self._measured = False
        self._points: list[tuple[float, float, int, int, int]] = []   # x, y, panel, clip, row
        self._hover: int | None = None

    def set_metrics(self, metrics: Sequence[Metric], *, measured: bool = False) -> None:
        self._metrics = list(metrics)
        self._measured = measured
        self._hover = None
        self.updateGeometry()
        self.update()

    @property
    def metrics(self) -> list[Metric]:
        return list(self._metrics)

    @property
    def measured(self) -> bool:
        return self._measured

    def _rows(self) -> int:
        return math.ceil((len(self._metrics) + 1) / self.COLUMNS) if self._metrics else 1

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(760, self.LEGEND_H + self._rows() * self.PANEL_H + 6)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(560, self.LEGEND_H + self._rows() * 92)

    # painting

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), SURFACE)
        self._points = []
        if not self._metrics:
            p.setPen(MUTED)
            p.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter,
                       "Press Preview to chart every clip before and after calibration.")
            return
        self._paint_legend(p, QRectF(10, 4, self.width() - 20, self.LEGEND_H - 6))
        cell_w = (self.width() - 20) / self.COLUMNS
        cell_h = (self.height() - self.LEGEND_H - 4) / self._rows()
        for i, metric in enumerate(self._metrics):
            row, col = divmod(i, self.COLUMNS)
            self._paint_panel(p, QRectF(10 + col * cell_w, self.LEGEND_H + row * cell_h,
                                        cell_w - 18, cell_h - 8), i, metric)
        row, col = divmod(len(self._metrics), self.COLUMNS)
        self._paint_summary(p, QRectF(10 + col * cell_w + self.LABEL_W, self.LEGEND_H + row * cell_h,
                                      cell_w - 18 - self.LABEL_W, cell_h - 8))

    def _paint_legend(self, p: QPainter, rect: QRectF) -> None:
        after = ("Calibrated: measured in the written files" if self._measured
                 else "Calibrated: as planned (Apply writes it)")
        items = [(BEFORE, False, "Recorded"), (AFTER, False, after)]
        if any(any(m.limited) for m in self._metrics):
            items.append((LIMITED, True, "Peak-limited: held below the target"))
        fm = QFontMetricsF(self.font())
        p.setFont(self.font())
        x, y = rect.left(), rect.center().y()
        for color, triangle, text in items:
            _marker(p, QPointF(x + 5, y), color, triangle, self.RADIUS)
            p.setPen(INK)
            p.drawText(QPointF(x + 15, y + fm.ascent() / 2 - 1.5), text)
            x += 15 + fm.horizontalAdvance(text) + 22

    def _paint_panel(self, p: QPainter, rect: QRectF, index: int, m: Metric) -> None:
        font, small, bold = self.font(), _small(self.font()), _bold(self.font())
        fm, sfm = QFontMetricsF(font), QFontMetricsF(small)

        # The title row: the quantity and its unit, then the reference line's key.
        base = rect.top() + fm.ascent() + 2
        p.setFont(bold)
        p.setPen(INK)
        p.drawText(QPointF(rect.left(), base), m.title)
        p.setFont(small)
        p.setPen(MUTED)
        p.drawText(QPointF(rect.left() + QFontMetricsF(bold).horizontalAdvance(m.title) + 6, base), m.unit)
        if m.reference is not None:
            label = minus(m.reference_label)
            lx = rect.right() - sfm.horizontalAdvance(label)
            p.drawText(QPointF(lx, base), label)
            p.setPen(QPen(INK, 1.0, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(lx - 8, base - sfm.ascent() + 1), QPointF(lx - 8, base + 2))

        top = rect.top() + fm.height() + 8
        plot = QRectF(rect.left() + self.LABEL_W, top, rect.width() - self.LABEL_W - self.RANGE_W,
                      rect.bottom() - top - sfm.height() - 6)
        values = [*m.before, *m.after] + ([m.reference] if m.reference is not None else [])
        ticks = nice_ticks(min(values), max(values), 4)
        lo, hi = ticks[0], ticks[-1]

        def x(v: float) -> float:
            return plot.left() + (v - lo) / ((hi - lo) or 1.0) * plot.width()

        # Hairline grid, tick labels under it.
        p.setPen(QPen(GRID, 1.0))
        for t in ticks:
            xt = round(x(t)) + 0.5
            p.drawLine(QPointF(xt, plot.top()), QPointF(xt, plot.bottom()))
        p.setPen(MUTED)
        decimals = _decimals(ticks)
        for t in ticks:
            label = minus(f"{t:.{decimals}f}")
            p.drawText(QPointF(x(t) - sfm.horizontalAdvance(label) / 2, plot.bottom() + sfm.ascent() + 3), label)

        rows = ((m.before, plot.top() + plot.height() * 0.28, "Recorded", BEFORE),
                (m.after, plot.top() + plot.height() * 0.74, "Calibrated", AFTER))
        p.setFont(font)
        for _values, y, label, _color in rows:
            p.setPen(INK)
            p.drawText(QPointF(rect.left(), y + fm.ascent() / 2 - 1.5), label)

        if m.reference is not None:                        # the threshold itself
            xr = x(m.reference)
            p.setPen(QPen(INK, 1.0, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(xr, plot.top() - 3), QPointF(xr, plot.bottom()))

        def point(row: int, clip: int) -> QPointF:
            values, y = rows[row][0], rows[row][1]
            return QPointF(x(values[clip]), y + _jitter(clip) * self.JITTER)

        limited = m.limited or (False,) * len(m.before)
        for row in (0, 1):
            for clip in range(len(rows[row][0])):
                if clip == self._hover:
                    continue                                # drawn last, on top
                at = point(row, clip)
                held = row == 1 and limited[clip]
                _marker(p, at, LIMITED if held else rows[row][3], held, self.RADIUS)
                self._points.append((at.x(), at.y(), index, clip, row))
        if self._hover is not None and self._hover < len(m.before):
            clip = self._hover
            a, b = point(0, clip), point(1, clip)
            p.setPen(QPen(AFTER, 2.0))
            p.drawLine(a, b)
            _marker(p, a, BEFORE, False, self.RADIUS + 1.5)
            _marker(p, b, LIMITED if limited[clip] else AFTER, limited[clip], self.RADIUS + 1.5)
            self._points += [(a.x(), a.y(), index, clip, 0), (b.x(), b.y(), index, clip, 1)]

        p.setFont(small)
        p.setPen(MUTED)
        for values, y, _label, _color in rows:
            p.drawText(QPointF(plot.right() + 12, y + sfm.ascent() / 2 - 1.5),
                       range_text(*m.span(values), m.unit))

    def _paint_summary(self, p: QPainter, rect: QRectF) -> None:
        font, bold = self.font(), _bold(self.font())
        fm = QFontMetricsF(font)
        p.setFont(bold)
        p.setPen(INK)
        y = rect.top() + fm.ascent() + 2
        p.drawText(QPointF(rect.left(), y), "In short")
        p.setFont(font)
        for line in summary_lines(self._metrics):
            y += fm.height() + 3
            if y > rect.bottom():
                break
            p.drawText(QPointF(rect.left(), y), fm.elidedText(line, Qt.TextElideMode.ElideRight, rect.width()))

    # hover

    def _tip(self, panel: int, clip: int, row: int) -> str:
        m = self._metrics[panel]
        here, there = (m.before, m.after) if row == 0 else (m.after, m.before)
        names = ("recorded", "calibrated") if row == 0 else ("calibrated", "recorded")
        held = "<br>peak-limited: held below the target" if m.limited and m.limited[clip] else ""
        return (f"<b>{fmt_value(here[clip], m.unit)} {m.unit}</b> {names[0]}<br>"
                f"{fmt_value(there[clip], m.unit)} {m.unit} {names[1]}{held}<br>"
                f"<span style='color:#cfcbf3'>{escape(m.names[clip])}</span>")

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        pos = event.position()
        best, best_d = None, self.HIT
        for px, py, panel, clip, row in self._points:
            d = math.hypot(px - pos.x(), py - pos.y())
            if d <= best_d:
                best, best_d = (panel, clip, row), d
        hover = best[1] if best else None
        if hover != self._hover:
            self._hover = hover
            self.update()
        if best:
            QToolTip.showText(event.globalPosition().toPoint(), self._tip(*best), self)
        else:
            QToolTip.hideText()

    def leaveEvent(self, event) -> None:  # noqa: N802
        if self._hover is not None:
            self._hover = None
            self.update()
        QToolTip.hideText()


# -- balance ---------------------------------------------------------------------

class BalanceChart(QWidget):
    """Clips per emotion and speaker sex, as grouped bars with their counts."""

    LEGEND_H = 26
    LABEL_W = 70
    BAR = 11.0            # bar thickness (<= 24 px)
    GAP = 2.0             # the surface gap between touching bars
    GROUP_GAP = 10.0
    AXIS_H = 22

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self._rows: list[tuple[str, tuple[int, ...]]] = []
        self._series: tuple[str, ...] = ()
        self._colors: tuple[QColor, ...] = ()
        self._unrecognized = 0
        self._bars: list[tuple[QRectF, str]] = []

    def set_counts(self, rows: Sequence[tuple[str, Sequence[int]]], series: Sequence[str],
                   unrecognized: int = 0) -> None:
        """*rows*: (emotion, count per series); a series no clip has is left out."""
        keep = [i for i in range(len(series)) if any(counts[i] for _, counts in rows)]
        self._series = tuple(series[i] for i in keep)
        self._colors = tuple(SERIES[i % len(SERIES)] for i in keep)   # colour follows the series
        self._rows = [(label, tuple(counts[i] for i in keep)) for label, counts in rows]
        self._unrecognized = unrecognized
        self.updateGeometry()
        self.update()

    def _group_h(self) -> float:
        n = max(1, len(self._series))
        return n * self.BAR + (n - 1) * self.GAP

    def sizeHint(self) -> QSize:  # noqa: N802
        body = len(self._rows) * (self._group_h() + self.GROUP_GAP)
        return QSize(320, int(self.LEGEND_H + body + self.AXIS_H + 30))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(240, self.sizeHint().height())

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), SURFACE)
        self._bars = []
        font, small = self.font(), _small(self.font())
        fm, sfm = QFontMetricsF(font), QFontMetricsF(small)
        if not self._rows:
            p.setPen(MUTED)
            p.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter, "Press Inspect to count the clips.")
            return

        x, y = 10.0, 6 + fm.ascent()                            # legend: swatch + label
        p.setFont(font)
        for name, color in zip(self._series, self._colors):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(color))
            p.drawRoundedRect(QRectF(x, y - fm.ascent() + 3, 10, 10), 2, 2)
            p.setPen(INK)
            p.drawText(QPointF(x + 15, y), name)
            x += 15 + fm.horizontalAdvance(name) + 18

        top = float(self.LEGEND_H)
        most = max((max(c) if c else 0 for _, c in self._rows), default=0)
        ticks = [t for t in nice_ticks(0, max(1, most), 4) if float(t).is_integer()]   # counts
        plot = QRectF(10 + self.LABEL_W, top, self.width() - 20 - self.LABEL_W - 26,
                      len(self._rows) * (self._group_h() + self.GROUP_GAP))

        def x_of(v: float) -> float:
            return plot.left() + v / (ticks[-1] or 1.0) * plot.width()

        p.setPen(QPen(GRID, 1.0))
        for t in ticks[1:]:
            xt = round(x_of(t)) + 0.5
            p.drawLine(QPointF(xt, plot.top()), QPointF(xt, plot.bottom()))
        p.setFont(small)
        p.setPen(MUTED)
        for t in ticks:
            label = f"{t:.0f}"
            p.drawText(QPointF(x_of(t) - sfm.horizontalAdvance(label) / 2, plot.bottom() + sfm.ascent() + 3), label)

        y = plot.top() + self.GROUP_GAP / 2
        radius = 4.0
        for label, counts in self._rows:
            p.setFont(font)
            p.setPen(INK)
            p.drawText(QPointF(10, y + self._group_h() / 2 + fm.ascent() / 2 - 1.5), label)
            for i, n in enumerate(counts):
                bar = QRectF(plot.left(), y + i * (self.BAR + self.GAP), x_of(n) - plot.left(), self.BAR)
                if n > 0:                                       # rounded tip, square at the baseline
                    path = QPainterPath()
                    path.addRoundedRect(bar, min(radius, bar.width() / 2), min(radius, self.BAR / 2))
                    path.addRect(QRectF(bar.left(), bar.top(), min(radius, bar.width()), bar.height()))
                    p.fillPath(path.simplified(), QBrush(self._colors[i]))
                p.setFont(small)
                p.setPen(INK)
                p.drawText(QPointF(bar.right() + 5, bar.center().y() + sfm.ascent() / 2 - 1.5), str(n))
                hit = QRectF(plot.left(), bar.top() - 1, max(bar.width(), 24.0) + 20, self.BAR + 2)
                self._bars.append((hit, f"<b>{n} clip{'s' if n != 1 else ''}</b> {escape(label)}, "
                                        f"{escape(self._series[i].lower())}"))
            y += self._group_h() + self.GROUP_GAP
        p.setPen(QPen(FRAME, 1.0))                              # the baseline the bars grow from
        xb = round(plot.left()) + 0.5
        p.drawLine(QPointF(xb, plot.top()), QPointF(xb, plot.bottom()))

        if self._unrecognized:
            p.setFont(font)
            p.setPen(INK)
            n = self._unrecognized
            p.drawText(QPointF(10, plot.bottom() + self.AXIS_H + fm.ascent()),
                       f"⚠ {n} file{'s' if n != 1 else ''} unrecognized: never played")

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        pos = event.position()
        for rect, tip in self._bars:
            if rect.contains(pos):
                QToolTip.showText(event.globalPosition().toPoint(), tip, self)
                return
        QToolTip.hideText()


# -- one clip, large -----------------------------------------------------------

def noise_text(clip: ClipStats) -> str:
    floor = clip.noise_floor_db
    return "digital silence" if floor <= DIGITAL_SILENCE_DB else f"{minus(f'{floor:.1f}')} dBFS"


def card_tooltip(clip: ClipStats, flags: Sequence[Flag] = ()) -> str:
    """Every number about one clip, for its card's tooltip."""
    rows = [
        ("Duration", f"{clip.duration:.3f} s"),
        ("Format", f"{clip.rate / 1000:g} kHz, {'mono' if clip.channels == 1 else f'{clip.channels} ch'}"),
        ("Peak", f"{minus(f'{clip.peak_db:.1f}')} dBFS"),
        ("RMS (whole file)", f"{minus(f'{clip.rms_db:.1f}')} dBFS"),
        ("Loudest 20 ms", f"{minus(f'{clip.loudest_db:.1f}')} dBFS"),
        ("Noise floor", noise_text(clip)),
        ("Speech", f"{clip.onset:.3f} to {clip.offset:.3f} s"),
        ("Silence before / after", f"{clip.lead_silence * 1000:.0f} / {clip.tail_silence * 1000:.0f} ms"),
        ("DC offset", f"{minus(f'{clip.dc_offset * 100:+.2f}')} % FS"),
        ("Clipped samples", str(clip.clipped)),
    ]
    table = "".join(f"<tr><td>{k}&nbsp;&nbsp;</td><td><b>{v}</b></td></tr>" for k, v in rows)
    notes = "".join(f"<p><b>⚠ {escape(f.label)}</b>: {escape(f.detail)}</p>" for f in flags)
    return f"<b>{escape(clip.filename)}</b><table>{table}</table>{notes}"


class ClipDetail(QWidget):
    """One clip, large: waveform, spectrogram and RMS curve on one time axis.

    Over the three panels: the detected start and end of speech, and -- washed
    out -- what calibration's trim would cut (it keeps the padding, 100 ms by
    default, beyond the speech), so "end of speech" and "end of file" can be
    seen to differ.
    """

    GUTTER = 50
    AXIS_H = 26
    PANELS = (("wave", "Waveform", 0.24), ("spec", "Spectrogram", 0.42), ("rms", "RMS", 0.34))

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._clip: ClipAnalysis | None = None
        self._flags: tuple[Flag, ...] = ()
        self._pad = DEFAULT_PAD_S
        self._cache: dict[tuple[str, int, int], QImage] = {}
        self._message = ""                      # shown while there is no clip (e.g. measuring)
        self._playhead: float | None = None     # seconds into the clip, while it plays
        self._area = QRectF()                   # where the panels were last drawn
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    @property
    def clip(self) -> ClipAnalysis | None:
        return self._clip

    def set_clip(self, clip: ClipAnalysis | None, flags: Sequence[Flag] = (),
                 pad_s: float = DEFAULT_PAD_S) -> None:
        self._clip, self._flags, self._pad = clip, tuple(flags), pad_s
        self._cache.clear()
        self._playhead = None
        self.update()

    def set_message(self, text: str) -> None:
        """What to say while there's no clip to draw (e.g. "Measuring...")."""
        self._message = text
        self.update()

    def set_playhead(self, seconds: float | None) -> None:
        """Move the playhead to *seconds* (None hides it); repaints just the strips it touched."""
        if seconds == self._playhead:
            return
        for t in (self._playhead, seconds):
            if t is not None and self._clip is not None and self._area.width() > 0:
                x = self._area.left() + min(max(t / max(self._clip.duration, 1e-3), 0.0), 1.0) * self._area.width()
                self.update(QRect(int(x) - 4, int(self._area.top()) - 8, 9, int(self._area.height()) + 10))
        self._playhead = seconds

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(760, 330)

    def _image(self, kind: str, rect: QRectF) -> QImage:
        dpr = self.devicePixelRatioF()
        w, h = max(1, round(rect.width() * dpr)), max(1, round(rect.height() * dpr))
        key = (kind, w, h)
        if key not in self._cache:
            draw = {"wave": waveform_image, "spec": spectrogram_image, "rms": curve_image}[kind]
            self._cache[key] = pil_to_qimage(draw(self._clip, w, h, self._clip.duration), dpr)
        return self._cache[key]

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), SURFACE)
        clip = self._clip
        font, small, bold = self.font(), _small(self.font()), _bold(self.font())
        fm, sfm = QFontMetricsF(font), QFontMetricsF(small)
        if clip is None:
            p.setPen(MUTED)
            p.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter,
                       self._message or "Select a clip to see it here, large.")
            return

        # Header: the name, then the numbers that matter most here.
        y = 4 + fm.ascent()
        p.setFont(bold)
        p.setPen(INK)
        p.drawText(QPointF(10, y), clip.filename)
        stats = (f"{clip.duration:.2f} s · peak {minus(f'{clip.peak_db:.1f}')} dBFS · "
                 f"RMS {minus(f'{clip.rms_db:.1f}')} dBFS · noise {noise_text(clip)}")
        p.setFont(font)
        p.setPen(MUTED)
        p.drawText(QPointF(18 + QFontMetricsF(bold).horizontalAdvance(clip.filename), y), stats)
        if self._flags:
            y += fm.height()
            p.setPen(QColor(FLAG_INK))
            text = "  ".join(f"⚠ {f.label}" for f in self._flags)
            p.drawText(QPointF(10, y), fm.elidedText(text, Qt.TextElideMode.ElideRight, self.width() - 20))
        label_y = y + fm.height() + 2                         # the markers' labels
        top = label_y + 6

        area = QRectF(self.GUTTER, top, self.width() - self.GUTTER - 14, self.height() - top - self.AXIS_H)
        if area.width() < 40 or area.height() < 60:
            return
        gap = 6.0
        usable = area.height() - gap * (len(self.PANELS) - 1)
        rects: dict[str, QRectF] = {}
        y0 = area.top()
        for kind, _title, share in self.PANELS:
            rects[kind] = QRectF(area.left(), y0, area.width(), usable * share)
            y0 += usable * share + gap

        span = max(clip.duration, 1e-3)

        def x(t: float) -> float:
            return area.left() + min(max(t / span, 0.0), 1.0) * area.width()

        self._area = QRectF(area.left(), area.top(), area.width(), rects["rms"].bottom() - area.top())
        for kind, title, _share in self.PANELS:
            rect = rects[kind]
            p.drawImage(rect, self._image(kind, rect))
            p.setPen(QPen(FRAME, 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(rect.adjusted(-0.5, -0.5, 0.5, 0.5))

        # What the trim would cut: washed out, in every panel.
        keep_from = max(0.0, clip.onset - self._pad)
        keep_to = min(clip.duration, clip.offset + self._pad)
        wash = QColor(255, 255, 255, 150)
        for kind in rects:
            rect = rects[kind]
            for a, b in ((0.0, keep_from), (keep_to, clip.duration)):
                if x(b) - x(a) >= 1:
                    p.fillRect(QRectF(x(a), rect.top(), x(b) - x(a), rect.height()), wash)
        p.setFont(small)
        p.setPen(MUTED)
        wave = rects["wave"]
        for a, b in ((0.0, keep_from), (keep_to, clip.duration)):
            if x(b) - x(a) >= sfm.horizontalAdvance("trimmed") + 6:     # at the bottom: the
                p.drawText(QRectF(x(a), wave.bottom() - sfm.height() - 2,   # names sit at the top
                                  x(b) - x(a), sfm.height()),
                           Qt.AlignmentFlag.AlignHCenter, "trimmed")

        # The detected speech: a line at each end, through all three panels.
        p.setPen(QPen(AFTER, 1.5))
        for t in (clip.onset, clip.offset):
            p.drawLine(QPointF(x(t), area.top()), QPointF(x(t), rects["rms"].bottom()))
        p.setFont(small)
        p.setPen(INK)
        start = f"start of speech {clip.onset:.2f} s"
        end = f"end of speech {clip.offset:.2f} s"
        xs, xe = x(clip.onset) + 4, x(clip.offset) - 4 - sfm.horizontalAdvance(end)
        if xs + sfm.horizontalAdvance(start) + 8 < xe:
            p.drawText(QPointF(xs, label_y), start)
        p.drawText(QPointF(max(area.left(), xe), label_y), end)
        eof = f"end of file {clip.duration:.2f} s"
        if x(clip.offset) + 8 < area.right() - sfm.horizontalAdvance(eof):
            p.setPen(MUTED)
            p.drawText(QPointF(area.right() - sfm.horizontalAdvance(eof), label_y), eof)

        # Y axes, in the gutter; each panel's name inside its top-left corner.
        def ytick(rect: QRectF, frac: float, text: str) -> None:
            yy = rect.top() + frac * rect.height()
            p.drawText(QPointF(area.left() - 6 - sfm.horizontalAdvance(text), yy + sfm.ascent() / 2 - 1), text)

        p.setPen(MUTED)
        p.setFont(small)
        ytick(wave, 0.0 + 0.12, "+1")
        ytick(wave, 0.5, "0")
        ytick(wave, 1.0 - 0.12, minus("-1"))
        spec, rms = rects["spec"], rects["rms"]
        top_khz = clip.spec_freqs[-1] / 1000.0 if clip.spec_freqs.size else 8.0
        for khz in range(0, int(top_khz) + 1, 2):
            frac = 1.0 - khz / top_khz if top_khz else 1.0
            ytick(spec, min(max(frac, 0.06), 0.94), f"{khz}")
        for level in (0, -20, -40, -60):
            frac = level / CURVE_FLOOR_DB
            ytick(rms, min(max(frac, 0.08), 0.94), minus(f"{level}"))
        names = {"wave": "Waveform (full scale = 1)", "spec": "Spectrogram (kHz)", "rms": "RMS (dBFS)"}
        for kind, rect in rects.items():
            text = names[kind]
            box = QRectF(rect.left() + 4, rect.top() + 3, sfm.horizontalAdvance(text) + 8, sfm.height() + 2)
            p.fillRect(box, QColor(255, 255, 255, 215))
            p.setPen(INK)
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
        thr = clip.threshold_db
        if thr > CURVE_FLOOR_DB:
            yy = rms.top() + (thr / CURVE_FLOOR_DB) * rms.height()
            text = minus(f"threshold: {abs(THRESHOLD_DB):g} dB below the loudest frame ({thr:.0f} dBFS)")
            p.setPen(MUTED)
            p.drawText(QPointF(rms.right() - sfm.horizontalAdvance(text) - 4, yy - 3), text)

        # The time axis.
        p.setPen(MUTED)
        ticks = [t for t in nice_ticks(0.0, span, 6) if t <= span + 1e-9]
        decimals = _decimals(ticks)
        for i, t in enumerate(ticks):
            label = f"{t:.{decimals}f}"
            width = sfm.horizontalAdvance(label)
            if i == len(ticks) - 1:
                label += " s"                                   # the unit rides on the last tick
            p.drawText(QPointF(x(t) - width / 2, rms.bottom() + sfm.ascent() + 4), label)

        if self._playhead is not None:                          # where the playback is
            xp = x(self._playhead)
            p.setPen(QPen(INK, 2.0))
            p.drawLine(QPointF(xp, area.top()), QPointF(xp, rms.bottom()))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(INK))
            p.drawPolygon(QPolygonF([QPointF(xp - 4, area.top() - 6), QPointF(xp + 4, area.top() - 6),
                                     QPointF(xp, area.top())]))
