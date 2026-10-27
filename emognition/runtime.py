# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Runtime hardening: isolated, documented work-arounds for third-party quirks.

Anything that exists purely to dodge someone else's bug lives here, quarantined
away from the rest of the codebase, with a paper trail: the PsychoPy TextStim race
(:func:`harden_psychopy`) and the PsychToolbox audio crash on Python 3.12+
(:func:`ptb_audio_problem`).
"""

from __future__ import annotations

import os
import sys
import threading
import warnings as _warnings
from collections.abc import Callable

# The exact (constant) regex PsychoPy compiles on every TextStim construction.
_TEXTSTIM_PYGLET_FILTER = ".*text.Label*"

_hardened = False


def configure_prefs(
    audio_libs: tuple[str, ...] = ("ptb", "sounddevice"),
    audio_latency_mode: int = 1,
) -> None:
    """Select PsychoPy's audio backend(s). MUST run before importing psychopy.sound.

    PsychoPy decides which audio library to use at the moment ``psychopy.sound`` is
    first imported, by reading ``prefs.hardware['audioLib']``. Set it afterwards and
    you're ignored. We list PsychoToolbox (``ptb``) first -- it sample-accurately
    *schedules* onsets (what our reaction times are measured against) -- with
    ``sounddevice`` as a fallback if PTB can't initialise.

    ``audio_latency_mode`` controls how aggressively PsychoToolbox grabs the sound
    device (0 = don't care … 3-4 = exclusive/aggressive). The aggressive default
    takes the ALSA device *exclusively*, which is unstable on shared servers like
    PipeWire and intermittently **segfaults** here. Mode 1 ("share a low-latency
    driver") keeps accurate onset scheduling while cooperating with the audio
    server -- the right trade for reliability. The constant hardware latency that
    adds is irrelevant to RTs measured from the *scheduled* onset.

    Importing :mod:`psychopy.preferences` here is cheap and starts no threads.

    Note (PsychoPy 2026.2): ``audioLib`` is what picks the backend -- for the
    ``Sound`` and for the speaker device behind it (``resolveBackend()`` takes the
    first name it knows). PsychoPy 2026.1 ignored it and hard-wired ``"ptb"``
    instead. ``audioLatencyMode`` is now read only by microphones: playback gets
    the PTB speaker's default latency class, 1 -- exactly the mode asked for
    here. We keep setting it for the PsychoPy versions that read it, and
    ``tests/test_modes_runtime.py`` fails loudly if an upgrade changes either
    outcome.
    """
    from psychopy import prefs

    prefs.hardware["audioLib"] = list(audio_libs)
    prefs.hardware["audioLatencyMode"] = audio_latency_mode


# PsychToolbox asks for this realtime priority (SCHED_FIFO, 0 + tweak 4).
_PTB_AUDIO_PRIORITY = 4


def _realtime_allowed() -> bool:
    """Can a thread of ours switch itself to realtime scheduling, as PTB's will?

    Probed on a throwaway thread: on Linux, ``sched_setscheduler(0, ...)`` changes
    only the calling thread, and this one exits straight away.
    """
    allowed: list[bool] = []

    def probe() -> None:
        try:
            os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(_PTB_AUDIO_PRIORITY))
            allowed.append(True)
        except (OSError, AttributeError):
            allowed.append(False)

    thread = threading.Thread(target=probe, name="emognition-realtime-probe")
    thread.start()
    thread.join()
    return bool(allowed and allowed[0])


def ptb_audio_problem(
    version: tuple[int, int] | None = None,
    platform: str | None = None,
    realtime_allowed: Callable[[], bool] = _realtime_allowed,
) -> str | None:
    """Why PsychToolbox audio would crash this process, or None if it won't.

    **The bug** (psychtoolbox 3.0.19.14 and 3.0.22.2, found 2026-10-27). On Linux
    (ALSA/PulseAudio), PTB's audio thread switches itself to realtime priority on
    its first callback. If the system refuses, as it does for users without an
    ``rtprio`` limit, PTB prints a warning through Python's C API *from that
    non-Python thread*. Up to Python 3.11 that happens to work: the interpreter
    finds the "current" thread state through a process-wide pointer to the thread
    holding the GIL. Python 3.12 made it thread-local, so in PTB's thread it is
    NULL, and the print segfaults the whole experiment at the first sound.

    Hence: Linux + Python 3.12 or later + no realtime permission = a crash. The
    caller turns that into a clear message instead (the arguments exist for
    tests; they default to this process).
    """
    version = version or sys.version_info[:2]
    platform = platform or sys.platform
    if version < (3, 12) or not platform.startswith("linux") or realtime_allowed():
        return None
    return (
        f"PsychToolbox audio crashes on Python {version[0]}.{version[1]} on Linux unless "
        "realtime scheduling is allowed (it prints from its audio thread, which "
        "Python 3.12+ can't survive). Use Python 3.11 (see the README), or allow "
        "realtime priority for this user: add them to a group that "
        "/etc/security/limits.d grants 'rtprio' (e.g. 'pipewire' or 'audio') and "
        "log in again."
    )


def bootstrap() -> None:
    """One call to make PsychoPy safe to use: set audio prefs, then harden.

    Call this once, at the very start of any entry point, BEFORE importing
    ``psychopy.sound`` / ``psychopy.visual`` or creating any window. Order matters:
    audio prefs first (see :func:`configure_prefs`), then the TextStim race fix
    (see :func:`harden_psychopy`).
    """
    configure_prefs()
    harden_psychopy()


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
