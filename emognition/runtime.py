# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Runtime hardening: isolated, documented work-arounds for third-party quirks.

Anything that exists purely to dodge someone else's bug lives here, quarantined
away from the rest of the codebase, with a paper trail. Today there is exactly
one such gremlin -- see :func:`harden_psychopy`.
"""

from __future__ import annotations

import warnings as _warnings

# The exact (constant) regex PsychoPy compiles on every TextStim construction.
_TEXTSTIM_PYGLET_FILTER = ".*text.Label*"

_hardened = False


def harden_psychopy() -> None:
    """Neutralise a PsychoPy ``TextStim`` race that crashes under PsychoToolbox.

    **The bug.** ``psychopy.visual.TextStim.__init__`` runs, on *every* single
    construction, a "temporary fix" dated October 2018 to mute a pyglet
    deprecation warning::

        warnings.filterwarnings(message='.*text.Label*', action='ignore')

    That recompiles a regular expression each time. Under GIL contention with
    PsychoToolbox's C-extension threads -- which we deliberately use for the
    low-latency audio and keyboard backends that give us accurate reaction times
    -- CPython 3.10's ``re.RegexFlag.__and__`` (reached via ``re._compile``'s
    ``if not (flags & DEBUG)``) intermittently raises a C-level

        SystemError: PyArg_UnpackTuple() argument list is not a tuple

    on roughly 1 startup in 6, taking the whole experiment down with it.

    **The fix.** That warning filter only ever needs to be installed *once*. So
    we install it a single time here -- single-threaded, before any PsychoPy or
    PTB threads exist -- and then rebind the *text module's* ``warnings`` name to
    a shim whose ``filterwarnings`` is a no-op. The shim delegates every other
    attribute to the real :mod:`warnings`, so global warning behaviour is
    untouched; only ``TextStim``'s redundant per-init recompile is removed. After
    this, the racy code path is never executed again.

    Call once at process start, **before** creating any ``Window``, ``Keyboard``,
    or ``Sound``. Safe to call more than once (idempotent).
    """
    global _hardened
    if _hardened:
        return

    # 1) Install the intended warning suppression exactly once, single-threaded.
    _warnings.filterwarnings(message=_TEXTSTIM_PYGLET_FILTER, action="ignore")

    # 2) Replace the per-init call *inside PsychoPy's text module only* with a
    #    no-op, delegating everything else to the genuine warnings module.
    from psychopy.visual import text as _pp_text

    class _WarningsShim:
        """Stands in for :mod:`warnings` within psychopy.visual.text only."""

        @staticmethod
        def filterwarnings(*args, **kwargs):  # the racy call -> now a no-op
            return None

        def __getattr__(self, name):  # any other warnings.* -> the real thing
            return getattr(_warnings, name)

    _pp_text.warnings = _WarningsShim()
    _hardened = True
