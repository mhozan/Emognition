# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""LineBuffer: complete lines out of arbitrarily split byte chunks (emognition/io/lines.py)."""

import json

from emognition.io.lines import LineBuffer


def test_a_json_line_split_across_reads_is_kept():
    buf = LineBuffer()
    line = json.dumps({"status": "trial", "index": 3}).encode()
    assert buf.feed(line[:10]) == []
    assert buf.feed(line[10:] + b"\n") == [line.decode()]


def test_multibyte_character_split_between_chunks_survives():
    data = "Participant José\n".encode("utf-8")
    cut = data.index("é".encode("utf-8")) + 1          # split inside the 2-byte é
    buf = LineBuffer()
    assert buf.feed(data[:cut]) == [] and buf.feed(data[cut:]) == ["Participant José"]


def test_crlf_lines_and_unterminated_tail():
    buf = LineBuffer()
    assert buf.feed(b"one\r\ntwo\nthr") == ["one", "two"]
    assert buf.flush() == ["thr"] and buf.flush() == []


def test_invalid_bytes_are_replaced_not_fatal():
    assert LineBuffer().feed(b"bad \xff byte\n") == ["bad � byte"]
