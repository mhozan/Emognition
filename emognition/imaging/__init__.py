# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Emognition imaging: background pictures for the participant window.

Pillow + numpy only -- no PsychoPy, no Qt -- so the same code serves the
experiment process (rendering), the setup window (thumbnails, "Add picture...")
and headless tests.
"""

from .backgrounds import (
    DEFAULT_MAX_LUMA,
    IMPORT_BOX,
    MAX_IMPORT_PIXELS,
    PictureError,
    calm_gradient,
    cap_luminance,
    import_picture,
    load_cover,
    mean_luminance,
    render_background,
)

__all__ = [
    "DEFAULT_MAX_LUMA",
    "IMPORT_BOX",
    "MAX_IMPORT_PIXELS",
    "PictureError",
    "calm_gradient",
    "cap_luminance",
    "import_picture",
    "load_cover",
    "mean_luminance",
    "render_background",
]
