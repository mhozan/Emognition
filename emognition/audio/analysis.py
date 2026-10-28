# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""What's in each recording -- the numbers and curves behind the calibration plots.

A sanity check of a stimulus set, at a glance: for every clip, its level (peak,
RMS), any clipping or DC offset, where the speech starts and ends, its waveform,
the RMS curve the endpoint detector worked from, and a spectrogram -- plus the
flags (:func:`check_folder`) that point the experimenter at the clips worth a
listen. Numpy only (no UI, no plotting), so it runs on a worker thread and is
unit-tested.

Levels are dBFS = 20 log10(value), full scale = 1.0: a full-scale sine has an
RMS of -3 dBFS (AES17 would call it 0 dBFS).
"""

from __future__ import annotations

import math
import os
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from .endpoints import detect_endpoints, frame_rms
from .loudness import to_mono

_EPS = 1e-12
# A sample this close to full scale is counted as clipped (the recorder ran out of range).
CLIP_LEVEL = 0.999
# The endpoint detector's settings (audio/endpoints.py), drawn as the threshold line.
THRESHOLD_DB = -40.0
# Spectrogram: 25 ms Hann windows every 10 ms, shown up to 8 kHz (the speech band).
SPEC_WINDOW_MS = 25.0
SPEC_HOP_MS = 10.0
SPEC_MAX_HZ = 8000.0
SPEC_RANGE_DB = 70.0
# The waveform is kept as a min/max envelope in this many bins (enough for any card).
WAVE_BINS = 2000
# The noise floor: the level of the quietest 5 % of RMS frames (pauses, room, hiss).
NOISE_PERCENTILE = 5.0
# Below this a file is digitally silent between words (16-bit dither is ~-96 dBFS).
DIGITAL_SILENCE_DB = -90.0

# When the flags fire (see check_folder).
DC_LIMIT = 0.01             # |mean sample| of 1 % of full scale or more
QUIET_PEAK_DB = -20.0       # the highest sample below -20 dBFS
NOISE_MARGIN_DB = 30.0      # the noise floor within 30 dB of the loudest frame
EDGE_S = 0.02               # speech within 20 ms of the start or the end of the file


def db(value: float) -> float:
    """20 log10 of an amplitude (a silent value gives -240 dB, not -inf)."""
    return 20.0 * math.log10(max(value, _EPS))


@dataclass(frozen=True, slots=True)
class ClipAnalysis:
    """One recording, measured (times in seconds, levels in dBFS)."""

    path: str
    filename: str
    rate: int
    channels: int
    duration: float
    peak_db: float                 # highest sample, either channel
    rms_db: float                  # whole file, silence included
    clipped: int                   # samples at or past CLIP_LEVEL
    dc_offset: float               # mean sample value (should be ~0)
    onset: float                   # detected start of speech
    offset: float                  # detected end of speech
    times: np.ndarray              # centre of each RMS frame
    rms_curve_db: np.ndarray       # the detector's frame RMS, dBFS
    spec_times: np.ndarray
    spec_freqs: np.ndarray         # Hz, up to SPEC_MAX_HZ
    spectrogram_db: np.ndarray     # (freqs, times), dB relative to the clip's maximum
    wave_min: np.ndarray           # the waveform's min and max per bin (mono, -1..1),
    wave_max: np.ndarray           # WAVE_BINS bins over the clip

    @property
    def lead_silence(self) -> float:
        return self.onset

    @property
    def tail_silence(self) -> float:
        """From the end of speech to the end of the file -- what the file-offset RT includes."""
        return max(0.0, self.duration - self.offset)

    @property
    def loudest_db(self) -> float:
        """The loudest 20 ms frame, dBFS RMS (what the detector's threshold hangs from)."""
        return float(self.rms_curve_db.max()) if self.rms_curve_db.size else -240.0

    @property
    def threshold_db(self) -> float:
        """The level the detector called speech: THRESHOLD_DB below the loudest frame."""
        return self.loudest_db + THRESHOLD_DB

    @property
    def noise_floor_db(self) -> float:
        """The level of the quietest frames: the background between and around the speech."""
        if not self.rms_curve_db.size:
            return -240.0
        return float(np.percentile(self.rms_curve_db, NOISE_PERCENTILE))


@dataclass(frozen=True, slots=True)
class Flag:
    """Something about one clip worth a listen: a short label and what it means."""

    key: str        # "clipped", "dc", "quiet", "noisy", "edge", "rate", "channels"
    label: str      # a few words, for the card
    detail: str     # what was found, and what to do about it


def clip_flags(clip: ClipAnalysis, *, rate: int | None = None,
               channels: int | None = None) -> list[Flag]:
    """The sanity checks for one clip; *rate*/*channels* are the folder's usual ones."""
    flags: list[Flag] = []
    if clip.clipped:
        flags.append(Flag("clipped", "Clipped", (
            f"{clip.clipped} samples at full scale: the recording ran out of range. "
            "Turning it down later doesn't remove the distortion -- re-record or leave it out.")))
    if abs(clip.dc_offset) >= DC_LIMIT:
        flags.append(Flag("dc", "DC offset", (
            f"The mean sample is {clip.dc_offset * 100:+.1f} % of full scale (should be ~0). "
            "It wastes headroom and biases RMS; a high-pass filter in an audio editor removes it.")))
    if clip.peak_db < QUIET_PEAK_DB:
        flags.append(Flag("quiet", "Low level", (
            f"The highest sample is {clip.peak_db:.1f} dBFS. Normalising will raise it, "
            "and its background noise with it.")))
    if clip.loudest_db - clip.noise_floor_db < NOISE_MARGIN_DB:
        flags.append(Flag("noisy", "Noisy", (
            f"The background ({clip.noise_floor_db:.1f} dBFS) is within "
            f"{clip.loudest_db - clip.noise_floor_db:.0f} dB of the loudest speech. The end of "
            "speech is found 40 dB below that, so noise may count as speech: trimming and the "
            "speech-offset RT are unreliable for this clip.")))
    if clip.lead_silence < EDGE_S or clip.tail_silence < EDGE_S:
        where = " and ".join(w for w, short in (("start", clip.lead_silence < EDGE_S),
                                               ("end", clip.tail_silence < EDGE_S)) if short)
        flags.append(Flag("edge", "Speech at the edge", (
            f"Speech reaches the {where} of the file (less than {EDGE_S * 1000:.0f} ms of "
            "silence): the recording may be cut off. Listen to it.")))
    if rate is not None and clip.rate != rate:
        flags.append(Flag("rate", f"{clip.rate / 1000:g} kHz", (
            f"Sampled at {clip.rate} Hz; most clips here are {rate} Hz. Mixed rates usually "
            "mean mixed recording chains.")))
    if channels is not None and clip.channels != channels:
        flags.append(Flag("channels", _channel_word(clip.channels).capitalize(), (
            f"{_channel_word(clip.channels).capitalize()}; most clips here are "
            f"{_channel_word(channels)}. A stereo file is played as recorded; a mono one in "
            "both ears.")))
    return flags


def _channel_word(channels: int) -> str:
    return {1: "mono", 2: "stereo"}.get(channels, f"{channels} channels")


def usual(values: Sequence) -> object:
    """The most common value (the first seen on a tie); None for no values."""
    return Counter(values).most_common(1)[0][0] if values else None


def check_folder(clips: Sequence[ClipAnalysis]) -> list[list[Flag]]:
    """The flags of every clip, in order, judging rate and channels against the folder."""
    rate = usual([c.rate for c in clips])
    channels = usual([c.channels for c in clips])
    return [clip_flags(c, rate=rate, channels=channels) for c in clips]


def spectrogram(mono: np.ndarray, rate: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(times, freqs, dB relative to the maximum, clipped at -SPEC_RANGE_DB)."""
    window = max(16, int(rate * SPEC_WINDOW_MS / 1000.0))
    hop = max(1, int(rate * SPEC_HOP_MS / 1000.0))
    nfft = 1 << (window - 1).bit_length()
    if mono.shape[0] < window:
        mono = np.pad(mono, (0, window - mono.shape[0]))
    n_frames = 1 + (mono.shape[0] - window) // hop
    idx = np.arange(window)[None, :] + hop * np.arange(n_frames)[:, None]
    frames = mono[idx] * np.hanning(window)[None, :]
    power = np.abs(np.fft.rfft(frames, n=nfft, axis=1)) ** 2
    freqs = np.fft.rfftfreq(nfft, 1.0 / rate)
    keep = freqs <= min(SPEC_MAX_HZ, rate / 2.0)
    level = 10.0 * np.log10(power[:, keep].T + _EPS)
    level -= level.max()
    times = (np.arange(n_frames) * hop + window / 2.0) / rate
    return times, freqs[keep], np.maximum(level, -SPEC_RANGE_DB)


def waveform_envelope(mono: np.ndarray, bins: int = WAVE_BINS) -> tuple[np.ndarray, np.ndarray]:
    """(min, max) of *mono* in *bins* equal slices: the outline a waveform plot draws."""
    if mono.size == 0:
        return np.zeros(1), np.zeros(1)
    edges = np.linspace(0, mono.size, min(bins, mono.size) + 1).astype(int)
    lo = np.minimum.reduceat(mono, edges[:-1])
    hi = np.maximum.reduceat(mono, edges[:-1])
    return lo.astype(np.float32), hi.astype(np.float32)


def analyse_samples(samples: np.ndarray, rate: int, *, path: str = "") -> ClipAnalysis:
    """Measure *samples* (mono ``(n,)`` or multichannel ``(n, channels)``)."""
    data = samples if samples.ndim == 2 else samples[:, None]
    mono = to_mono(data)
    onset, offset = detect_endpoints(data, rate)
    energies, frame, hop = frame_rms(mono, rate)
    times = (np.arange(energies.size) * hop + frame / 2.0) / rate
    spec_t, spec_f, spec = spectrogram(mono, rate)
    wave_min, wave_max = waveform_envelope(mono)
    rms = float(np.sqrt(np.mean(data.astype(np.float64) ** 2))) if data.size else 0.0
    return ClipAnalysis(
        path=path,
        filename=os.path.basename(path),
        rate=rate,
        channels=data.shape[1],
        duration=data.shape[0] / rate,
        peak_db=db(float(np.max(np.abs(data))) if data.size else 0.0),
        rms_db=db(rms),
        clipped=int(np.count_nonzero(np.abs(data) >= CLIP_LEVEL)),
        dc_offset=float(np.mean(data)) if data.size else 0.0,
        onset=onset,
        offset=offset,
        times=times,
        rms_curve_db=20.0 * np.log10(np.maximum(energies, _EPS)),
        spec_times=spec_t,
        spec_freqs=spec_f,
        spectrogram_db=spec,
        wave_min=wave_min,
        wave_max=wave_max,
    )


def analyse_clip(path: str) -> ClipAnalysis:
    """Read and measure one audio file."""
    import soundfile as sf

    samples, rate = sf.read(path, dtype="float32", always_2d=True)
    return analyse_samples(samples, rate, path=path)
