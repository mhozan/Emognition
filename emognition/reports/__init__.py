# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Emognition reports: turn a session's responses into Excel / PDF / HTML reports.

All writers consume the same inputs (a list of ``core.Response`` plus an optional
``SessionSummary`` and ``SessionInfo``) so the three formats stay consistent.
"""

from .charts import reaction_time_svg
from .common import SessionInfo
from .csv import write_csv_report, write_summary_csv, write_trials_csv
from .excel import write_excel_report
from .html import render_html_report, write_html_report
from .pdf import write_pdf_report

__all__ = [
    "SessionInfo",
    "write_excel_report",
    "render_html_report",
    "write_html_report",
    "write_csv_report",
    "write_trials_csv",
    "write_summary_csv",
    "reaction_time_svg",
    "write_pdf_report",
]
