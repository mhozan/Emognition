# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Self-contained, styled HTML report.

Pure standard library -- no template engine, no CSS framework, no external assets
-- so the output is a single ``.html`` file you can open anywhere, email, archive
alongside a paper, or "Print -> Save as PDF" from the browser.

Design:
  * ``render_html_report(...)`` returns the markup as a *string* (testable and
    embeddable); ``write_html_report(...)`` is the thin file wrapper.
  * Every value that originates from the user (participant name, filenames,
    notes) goes through :func:`html.escape` before it touches the page.
  * The confusion matrix is heat-mapped with inline ``background`` colours
    computed the same way as the Excel report, so the two look like siblings.
"""

from __future__ import annotations

from collections.abc import Sequence
from html import escape

from ..core import SEXES_IN_ORDER, Response, RtFlag, SessionSummary
from ..core.scoring import DEFAULT_RT_KIND, GroupStats
from .charts import reaction_time_svg
from .common import (
    EMPTY,
    RT_FLAG_LABEL,
    STAT_COLUMNS,
    SessionInfo,
    fmt_pct,
    fmt_pct_unit,
    fmt_replays,
    fmt_seconds,
    fmt_seconds_unit,
    heat_rgb,
    info_rows,
    prepare_summary,
)

# --------------------------------------------------------------------------
# colour helpers (mirror the Excel heat-map: green = correct, red = confusion)
# --------------------------------------------------------------------------

def _heat_css(count: int, row_total: int, on_diagonal: bool) -> str | None:
    """CSS ``rgb(...)`` for a confusion cell (shared shading), or None if empty."""
    rgb = heat_rgb(count, row_total, on_diagonal)
    return None if rgb is None else "rgb({},{},{})".format(*rgb)


# --------------------------------------------------------------------------
# section builders (each returns an HTML fragment)
# --------------------------------------------------------------------------

def _info_section(info: SessionInfo, summary: SessionSummary) -> str:
    rows = info_rows(info, summary.rt_kind)
    items = "".join(
        f"<div class='kv'><span class='k'>{escape(str(k))}</span>"
        f"<span class='v'>{escape(str(v)) if v else EMPTY}</span></div>"
        for k, v in rows
    )
    return f"<section class='info'>{items}</section>"


def _cards_section(summary: SessionSummary) -> str:
    t = summary.total
    cards = [
        ("Overall accuracy", fmt_pct_unit(t.pct_correct)),
        ("Mean reaction", fmt_seconds_unit(t.mean_rt)),
        ("Trials answered", f"{t.n_answered} / {t.n_presented}"),
        ("Correct", str(t.n_correct)),
    ]
    blocks = "".join(
        f"<div class='card'><div class='card-val'>{escape(v)}</div>"
        f"<div class='card-lbl'>{escape(l)}</div></div>"
        for l, v in cards
    )
    return f"<section class='cards'>{blocks}</section>"


def _confusion_section(summary: SessionSummary) -> str:
    labels = [e.label for e in summary.emotion_order]
    head = "".join(f"<th>{escape(l)}</th>" for l in labels)
    body_rows = []
    for i, (lab, row) in enumerate(zip(labels, summary.confusion)):
        cells = []
        for j, count in enumerate(row):
            rgb = _heat_css(count, sum(row), on_diagonal=(i == j))
            style = f" style='background:{rgb};color:#1a1a1a'" if rgb else ""
            cells.append(f"<td{style}>{count}</td>")
        body_rows.append(f"<tr><th class='rowhead'>{escape(lab)}</th>{''.join(cells)}</tr>")
    return f"""
    <section>
      <h2>Confusion matrix</h2>
      <p class='muted'>Rows = emotion played (true); columns = emotion chosen.</p>
      <table class='confusion'>
        <thead><tr><th class='corner'>true \\ chosen</th>{head}</tr></thead>
        <tbody>{''.join(body_rows)}</tbody>
      </table>
    </section>"""


def _stat_cells(stats: GroupStats) -> str:
    return (
        f"<td>{fmt_pct(stats.pct_correct)}</td>"
        f"<td>{fmt_seconds(stats.mean_rt)}</td>"
        f"<td>{fmt_replays(stats.mean_replays)}</td>"
    )


def _stats_section(summary: SessionSummary) -> str:
    head = "".join(f"<th>{escape(c)}</th>" for c in STAT_COLUMNS)
    rows = []
    for emo in summary.emotion_order:
        rows.append(
            f"<tr><th class='rowhead'>{escape(emo.label)}</th>"
            f"{_stat_cells(summary.per_emotion[emo])}</tr>"
        )
    for sex in SEXES_IN_ORDER:
        rows.append(
            f"<tr class='group'><th class='rowhead'>{escape(sex.label)}</th>"
            f"{_stat_cells(summary.per_sex[sex])}</tr>"
        )
    rows.append(
        f"<tr class='total'><th class='rowhead'>Total</th>{_stat_cells(summary.total)}</tr>"
    )
    return f"""
    <section>
      <h2>Statistics</h2>
      <table class='stats'>
        <thead><tr><th></th>{head}</tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </section>"""


def _trials_section(responses: Sequence[Response], flags: Sequence[RtFlag]) -> str:
    rows = []
    for i, (r, flag) in enumerate(zip(responses, flags), start=1):
        chosen = r.responded.label if r.responded else EMPTY
        cls = "ok" if r.is_correct else ("miss" if r.answered else "blank")
        mark = "✓" if r.is_correct else ("✗" if r.answered else EMPTY)
        flag_label = RT_FLAG_LABEL[flag]
        flag_html = (
            f"<span class='flag'>{escape(flag_label)}</span>" if flag_label else ""
        )
        rows.append(
            f"<tr class='{cls}'>"
            f"<td>{i}</td>"
            f"<td class='mono'>{escape(r.stimulus.filename)}</td>"
            f"<td>{escape(r.true_emotion.label)}</td>"
            f"<td>{escape(chosen)}</td>"
            f"<td class='center'>{mark}</td>"
            f"<td>{fmt_seconds(r.rt_onset)}</td>"
            f"<td>{fmt_seconds(r.rt_offset)}</td>"
            f"<td class='center'>{r.n_replays}</td>"
            f"<td class='flagcell'>{flag_html}</td>"
            f"</tr>"
        )

    n_anti = sum(1 for f in flags if f is RtFlag.ANTICIPATORY)
    n_slow = sum(1 for f in flags if f is RtFlag.SLOW_OUTLIER)
    note = ""
    if n_anti or n_slow:
        note = (
            f"<p class='muted'>Reaction-time means exclude "
            f"{n_anti} anticipatory and {n_slow} slow-outlier trial(s); "
            f"accuracy uses all answered trials.</p>"
        )
    return f"""
    <section>
      <h2>Per-trial detail</h2>
      {note}
      <table class='trials'>
        <thead><tr>
          <th>#</th><th>Audio file</th><th>Played</th><th>Chosen</th>
          <th>OK</th><th>RT onset (s)</th><th>RT offset (s)</th><th>Replays</th>
          <th>Flag</th>
        </tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </section>"""


_CSS = """
  :root { --bg:#0f1226; --panel:#171a33; --ink:#e9ebff; --muted:#9aa0c7;
          --line:#2a2e52; --accent:#7c6cff; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
         font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }
  .wrap { max-width:980px; margin:0 auto; padding:32px 24px 64px; }
  header h1 { margin:0 0 4px; font-size:26px; }
  header .sub { color:var(--muted); margin-bottom:24px; }
  h2 { font-size:18px; margin:28px 0 10px; }
  .muted { color:var(--muted); font-size:13px; margin:.2em 0 .8em; }
  section.info { display:grid; grid-template-columns:repeat(2,1fr); gap:6px 28px;
                 background:var(--panel); border:1px solid var(--line);
                 border-radius:12px; padding:16px 20px; }
  .kv { display:flex; justify-content:space-between; gap:16px;
        border-bottom:1px dashed var(--line); padding:4px 0; }
  .kv .k { color:var(--muted); } .kv .v { font-weight:600; }
  section.cards { display:grid; grid-template-columns:repeat(4,1fr); gap:14px;
                  margin:20px 0; }
  .card { background:var(--panel); border:1px solid var(--line);
          border-radius:12px; padding:18px; text-align:center; }
  .card-val { font-size:26px; font-weight:700; color:#fff; }
  .card-lbl { color:var(--muted); font-size:13px; margin-top:4px; }
  table { border-collapse:collapse; width:100%; background:var(--panel);
          border:1px solid var(--line); border-radius:12px; overflow:hidden; }
  th,td { padding:8px 12px; text-align:right; border-bottom:1px solid var(--line); }
  thead th { background:#1f2347; color:#cdd2ff; font-weight:600; text-align:right; }
  .rowhead,.corner { text-align:left; color:#cdd2ff; font-weight:600; }
  table.confusion td { text-align:center; font-variant-numeric:tabular-nums; }
  .center { text-align:center; } .mono { font-family:ui-monospace,monospace; text-align:left; }
  tr.total th, tr.total td { font-weight:700; background:#20254d; }
  tr.group td, tr.group th { color:#cdd2ff; }
  tr.ok td:nth-child(5) { color:#5ad17a; } tr.miss td:nth-child(5) { color:#ff7b7b; }
  .flagcell { text-align:left; }
  .flag { background:#3a2140; color:#ffb38a; border:1px solid #6b3f54;
          border-radius:6px; padding:1px 7px; font-size:11px; white-space:nowrap; }
  .chart { background:var(--panel); border:1px solid var(--line);
           border-radius:12px; padding:10px; } .chart svg { width:100%; height:auto; }
  h3.charth { font-size:14px; color:var(--muted); margin:16px 0 6px; font-weight:600; }
  footer { color:var(--muted); font-size:12px; margin-top:36px;
           border-top:1px solid var(--line); padding-top:12px; }
  @media print {
    body { background:#fff; color:#111; }
    .card,section.info,table { background:#fff; border-color:#ccc; }
    .card-val,thead th,.rowhead,.corner { color:#111; }
  }
"""


def render_html_report(
    responses: Sequence[Response],
    *,
    summary: SessionSummary | None = None,
    info: SessionInfo | None = None,
    rt_kind: str = DEFAULT_RT_KIND,
) -> str:
    """Render the full report as a self-contained HTML document string."""
    summary, flags = prepare_summary(responses, summary=summary, rt_kind=rt_kind)
    info = info or SessionInfo(rt_kind=rt_kind)

    title = "Emognition — Session Report"
    subtitle = escape(info.participant or "Unnamed participant")
    chart_offset = reaction_time_svg(responses, rt_kind="offset")
    chart_onset = reaction_time_svg(responses, rt_kind="onset")
    chart_section = (
        "<section><h2>Reaction time per trial</h2>"
        "<p class='muted'>Marker size grows with replays; "
        "green = correct, red = incorrect.</p>"
        "<h3 class='charth'>From audio offset (default)</h3>"
        f"<div class='chart'>{chart_offset}</div>"
        "<h3 class='charth'>From audio onset</h3>"
        f"<div class='chart'>{chart_onset}</div>"
        "</section>"
    )
    body = "".join([
        _info_section(info, summary),
        _cards_section(summary),
        _confusion_section(summary),
        _stats_section(summary),
        chart_section,
        _trials_section(responses, flags),
    ])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>{_CSS}</style></head>
<body><div class="wrap">
  <header><h1>{escape(title)}</h1><div class="sub">{subtitle}</div></header>
  {body}
  <footer>Generated by Emognition · Speech Emotion Recognition · AGPL-3.0</footer>
</div></body></html>"""


def write_html_report(
    responses: Sequence[Response],
    path: str,
    *,
    summary: SessionSummary | None = None,
    info: SessionInfo | None = None,
    rt_kind: str = DEFAULT_RT_KIND,
) -> str:
    """Render and write the HTML report to *path*; return the path."""
    html = render_html_report(responses, summary=summary, info=info, rt_kind=rt_kind)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return path
