# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Reassembling text lines from a byte stream that arrives in arbitrary chunks.

The setup window reads the experiment process's stdout as it arrives. A pipe
hands over whatever bytes are ready, so one JSON status line can be split across
two reads -- and so can a multi-byte UTF-8 character such as the "é" in a
participant's name. Splitting each chunk on its own silently drops the line
(and mangles the character). :class:`LineBuffer` keeps the unfinished tail until
the rest arrives.
"""

from __future__ import annotations

import codecs


class LineBuffer:
    """Feed it byte chunks; get back only complete lines (without line endings)."""

    def __init__(self, encoding: str = "utf-8") -> None:
        self._decoder = codecs.getincrementaldecoder(encoding)(errors="replace")
        self._tail = ""

    def feed(self, data: bytes) -> list[str]:
        """Add *data*; return every line it completed (``\\r\\n`` or ``\\n`` endings)."""
        text = self._tail + self._decoder.decode(data)
        *lines, self._tail = text.split("\n")
        return [line.rstrip("\r") for line in lines]

    def flush(self) -> list[str]:
        """Return whatever is left (a last line without a newline), then reset."""
        text = self._tail + self._decoder.decode(b"", final=True)
        self._tail = ""
        return [text.rstrip("\r")] if text else []
