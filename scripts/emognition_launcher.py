# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""PyInstaller entry script.

PyInstaller freezes a *script*, not a module, so this thin launcher just calls
the real entry point. Kept separate from the package so freezing has a concrete
file to point at.
"""

import sys

from emognition.app import main

if __name__ == "__main__":
    sys.exit(main())
