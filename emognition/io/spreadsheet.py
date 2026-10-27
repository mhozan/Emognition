# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Keep exported text from running as a spreadsheet formula (CSV/Excel injection).

Excel and LibreOffice evaluate a cell whose text starts with ``= + - @`` (and,
after stripping, a tab or carriage return) as a formula. Our exports contain
text we don't control -- stimulus file names, participant labels, notes -- so a
file called ``=HYPERLINK("http://...","x")_hap_f.wav`` would become a live link
in the report someone opens later.

The OWASP mitigation is to prefix such text with a single quote, which
spreadsheets display as plain text. :func:`restore` undoes it when *we* read a
file back (the stimulus manifest), so round trips stay exact. Excel files don't
need the prefix: the writer stores those cells as text instead.
"""

from __future__ import annotations

# Leading characters that make a spreadsheet treat a cell as a formula.
FORMULA_TRIGGERS: tuple[str, ...] = ("=", "+", "-", "@", "\t", "\r")


def neutralize(value: object) -> object:
    """Prefix formula-like text with ``'``; anything else is returned unchanged."""
    if isinstance(value, str) and value.startswith(FORMULA_TRIGGERS):
        return "'" + value
    return value


def restore(value: str) -> str:
    """Undo :func:`neutralize` for text read back from a file we wrote."""
    if value.startswith("'") and value[1:].startswith(FORMULA_TRIGGERS):
        return value[1:]
    return value
