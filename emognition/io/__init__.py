# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Emognition io: small cross-platform input/output helpers (UI-free).

* :mod:`.openfile` -- open a report / reveal a file with the OS default app.
* :mod:`.lines` -- reassemble text lines from a pipe that delivers arbitrary chunks.
* :mod:`.spreadsheet` -- keep exported text from running as a spreadsheet formula.
"""

from .openfile import (
    open_command,
    open_path,
    reveal_command,
    reveal_in_file_manager,
)

__all__ = [
    "open_command",
    "open_path",
    "reveal_command",
    "reveal_in_file_manager",
]
