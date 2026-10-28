# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Tests for audio preprocessing (loudness, endpoints, plan/apply).

All file I/O, no audio device or display -- safe and fast in CI.
"""

import math
import os

import numpy as np
import pytest

from emognition.audio import (
    NormalizationMethod,
    apply_gain,
    detect_endpoints,
    measure,
    plan_batch,
    apply_plan,
    trim_samples,
)
from emognition.audio.loudness import measure as measure_loudness

RATE = 16000
ASSETS_AUDIO = os.path.join(os.path.dirname(__file__), os.pardir, "assets", "audio")


def _sine(amp, dur, freq=440.0, rate=RATE):
    t = np.arange(int(dur * rate)) / rate
    return amp * np.sin(2 * np.pi * freq * t)


# -- loudness measurement --------------------------------------------------

def test_rms_dbfs_of_full_scale_sine():
    # A full-scale sine has RMS = 1/sqrt(2) -> about -3.01 dBFS.
    sig = _sine(1.0, 1.0)
    assert measure(sig, RATE, NormalizationMethod.RMS) == pytest.approx(-3.01, abs=0.1)


def test_peak_dbfs():
    sig = _sine(0.5, 1.0)
    assert measure(sig, RATE, NormalizationMethod.PEAK) == pytest.approx(-6.02, abs=0.1)


# -- gain + ceiling --------------------------------------------------------

def test_apply_gain_without_clipping():
    sig = _sine(0.1, 0.2)             # peak 0.1
    out, limited = apply_gain(sig, gain_db=12.0, ceiling_db=-1.0)
    assert not limited
    assert float(np.max(np.abs(out))) == pytest.approx(0.1 * 10 ** (12 / 20), abs=1e-3)


def test_apply_gain_respects_ceiling():
    sig = _sine(0.1, 0.2)             # peak 0.1; +30 dB would clip
    out, limited = apply_gain(sig, gain_db=30.0, ceiling_db=-1.0)
    assert limited
    ceiling = 10 ** (-1.0 / 20)
    assert float(np.max(np.abs(out))) == pytest.approx(ceiling, abs=1e-3)


# -- endpoint detection ----------------------------------------------------

def test_detect_endpoints_finds_the_burst():
    # 0.5 s silence | 0.5 s tone | 0.5 s silence
    sig = np.concatenate([_sine(0.0, 0.5), _sine(0.5, 0.5), _sine(0.0, 0.5)])
    onset, offset = detect_endpoints(sig, RATE, threshold_db=-40.0)
    assert onset == pytest.approx(0.5, abs=0.05)
    assert offset == pytest.approx(1.0, abs=0.06)


def test_silence_is_not_trimmed():
    sig = _sine(0.0, 1.0)            # pure silence
    onset, offset = detect_endpoints(sig, RATE)
    assert (onset, offset) == (0.0, pytest.approx(1.0))


def test_trim_samples_lengths():
    sig = _sine(0.3, 1.0)
    trimmed = trim_samples(sig, RATE, onset_s=0.4, offset_s=0.6, pad_s=0.05)
    # span (0.35 .. 0.65) = 0.30 s
    assert len(trimmed) == pytest.approx(int(0.30 * RATE), abs=2)


# -- batch plan + apply on the real bundled clips --------------------------

def test_plan_and_apply_on_bundled_clips(tmp_path):
    paths = sorted(
        os.path.join(ASSETS_AUDIO, f)
        for f in os.listdir(ASSETS_AUDIO) if f.endswith(".wav")
    )
    out_dir = str(tmp_path / "audio_calibrated")
    plan = plan_batch(paths, out_dir, method=NormalizationMethod.LUFS, target_db=-23.0)

    assert len(plan.clips) == 10
    # Every clip carries an onset/offset and a finite gain.
    for c in plan.clips:
        assert 0.0 <= c.onset_s <= c.offset_s <= c.orig_duration
        assert math.isfinite(c.gain_db)

    written = apply_plan(plan)
    assert len(written) == 10
    assert all(os.path.exists(p) for p in written)

    # Every normalized clip that wasn't peak-limited should sit near the target
    # (the old loop checked only the first one, and passed vacuously if all
    # clips were limited).
    import soundfile as sf
    unlimited = [(c, p) for c, p in zip(plan.clips, written) if not c.will_limit]
    assert unlimited, "expected at least one clip to reach the target without limiting"
    for _c, p in unlimited:
        data, rate = sf.read(p)
        assert measure_loudness(data, rate, NormalizationMethod.LUFS) == pytest.approx(-23.0, abs=1.5)


# --- preprocess safety and provenance (Phase 3) ----------------------------

def _tone_file(path, seconds=1.0, rate=16000, lead=0.3, tail=0.4, amp=0.2):
    import numpy as np
    import soundfile as sf

    n = int(seconds * rate)
    t = np.arange(n) / rate
    sig = amp * np.sin(2 * np.pi * 440 * t)
    data = np.concatenate([np.zeros(int(lead * rate)), sig, np.zeros(int(tail * rate))])
    sf.write(str(path), data, rate, subtype="PCM_16")
    return str(path)


def test_gui_and_cli_share_one_padding_default():
    import inspect

    from emognition.audio.preprocess import DEFAULT_PAD_S, plan_batch

    assert inspect.signature(plan_batch).parameters["pad_s"].default == DEFAULT_PAD_S
    script = open(os.path.join(os.path.dirname(__file__), os.pardir, "scripts",
                               "calibrate_audio.py"), encoding="utf-8").read()
    assert "default=DEFAULT_PAD_S * 1000.0" in script


def test_rms_is_the_default_method_in_the_library_and_the_cli():
    import inspect

    from emognition.audio.preprocess import plan_batch

    assert inspect.signature(plan_batch).parameters["method"].default is NormalizationMethod.RMS
    script = open(os.path.join(os.path.dirname(__file__), os.pardir, "scripts",
                               "calibrate_audio.py"), encoding="utf-8").read()
    assert 'default="rms"' in script


def test_titles_read_right_inside_a_sentence():
    from emognition.audio.review import TITLES, in_sentence

    assert [in_sentence(TITLES[m]) for m in NormalizationMethod] == ["loudness", "RMS level",
                                                                     "peak level"]


def test_apply_plan_refuses_to_overwrite_originals(tmp_path):
    from emognition.audio import apply_plan, plan_batch

    src = _tone_file(tmp_path / "a_hap_f.wav")
    before = open(src, "rb").read()
    with pytest.raises(ValueError, match="input folder"):
        apply_plan(plan_batch([src], str(tmp_path)))
    assert open(src, "rb").read() == before


def test_apply_plan_refuses_colliding_output_names(tmp_path):
    from emognition.audio import apply_plan, plan_batch

    (tmp_path / "one").mkdir(); (tmp_path / "two").mkdir()
    a = _tone_file(tmp_path / "one" / "x_hap_f.wav")
    b = _tone_file(tmp_path / "two" / "x_hap_f.wav")
    with pytest.raises(ValueError, match="same file"):
        apply_plan(plan_batch([a, b], str(tmp_path / "out")))


def test_untrimmed_normalisation_hits_the_target_and_sidecar_records_it(tmp_path):
    import json

    import soundfile as sf

    from emognition.audio import NormalizationMethod, apply_plan, measure, plan_batch
    from emognition.audio.preprocess import SIDECAR_NAME

    (tmp_path / "in").mkdir()
    src = _tone_file(tmp_path / "in" / "s_hap_f.wav")
    plan = plan_batch([src], str(tmp_path / "out"), method=NormalizationMethod.RMS, target_db=-26.0)
    (out,) = apply_plan(plan, trim=False)
    data, rate = sf.read(out)
    assert abs(measure(data, rate, NormalizationMethod.RMS) - (-26.0)) < 0.1   # was ~0.5-0.8 dB short
    record = json.load(open(tmp_path / "out" / SIDECAR_NAME, encoding="utf-8"))
    assert record["method"] == "rms" and record["trimmed"] is False and record["pad_s"] == plan.pad_s
    assert record["clips"][0]["file"] == "s_hap_f.wav" and record["clips"][0]["lead_trim_s"] == 0.0


# --- the end of speech, for the speech-offset RT (Phase 5) ------------------------------

def test_speech_span_finds_the_speech_inside_the_silence(tmp_path):
    from emognition.audio import speech_span

    onset, offset = speech_span(_tone_file(tmp_path / "x_hap_f.wav", seconds=0.5, lead=0.3, tail=0.7))
    assert onset == pytest.approx(0.3, abs=0.02) and offset == pytest.approx(0.8, abs=0.02)


# --- what the calibration window shows (analysis, cards, the plan's peaks) -------------

def test_analysis_measures_level_clipping_and_the_speech_span(tmp_path):
    import numpy as np
    import soundfile as sf

    from emognition.audio.analysis import analyse_clip

    rate = 16000
    t = np.arange(int(0.5 * rate)) / rate
    tone = 0.5 * np.sin(2 * np.pi * 440 * t)
    tone[100:103] = 1.0                                           # three clipped samples
    data = np.concatenate([np.zeros(int(0.3 * rate)), tone, np.zeros(int(0.7 * rate))])
    path = tmp_path / "x_hap_f.wav"
    sf.write(str(path), data, rate, subtype="FLOAT")
    a = analyse_clip(str(path))
    assert a.duration == pytest.approx(1.5) and a.channels == 1 and a.clipped == 3
    assert a.onset == pytest.approx(0.3, abs=0.02) and a.offset == pytest.approx(0.8, abs=0.02)
    assert a.tail_silence == pytest.approx(0.7, abs=0.02)
    assert a.peak_db == pytest.approx(0.0, abs=0.01)
    assert a.rms_curve_db.max() == pytest.approx(20 * np.log10(0.5 / np.sqrt(2)), abs=0.5)
    assert a.threshold_db == pytest.approx(a.rms_curve_db.max() - 40.0)
    assert a.spectrogram_db.max() == 0.0 and a.spec_freqs.max() <= 8000.0
    peak_bin = a.spec_freqs[int(np.argmax(a.spectrogram_db.max(axis=1)))]
    assert abs(peak_bin - 440.0) < 40.0                           # the tone's frequency


def test_clip_cards_share_a_time_scale(tmp_path):
    import numpy as np

    from emognition.audio.analysis import analyse_samples
    from emognition.imaging.clips import clip_card

    rate = 16000
    short = analyse_samples(0.3 * np.sin(np.arange(rate) * 0.2), rate)          # 1 s
    card = clip_card(short, width=300, height=160, span=2.0)                    # on a 2 s scale
    assert card.size == (300, 160)
    for y in (10, 60, 140):                                     # waveform, spectrogram, RMS curve
        assert card.getpixel((280, y)) == (232, 232, 238)         # blank past its end
    assert min(short.wave_min) == pytest.approx(-0.3, abs=0.01) and max(short.wave_max) == pytest.approx(0.3, abs=0.01)


def test_plan_records_peaks_and_the_gain_really_applied(tmp_path):
    import numpy as np
    import soundfile as sf

    from emognition.audio import NormalizationMethod, plan_batch

    rate = 16000
    loud = np.concatenate([np.zeros(4000), 0.9 * np.sin(np.arange(8000) * 0.3), np.zeros(4000)])
    sf.write(str(tmp_path / "a_hap_f.wav"), loud, rate)
    plan = plan_batch([str(tmp_path / "a_hap_f.wav")], str(tmp_path / "out"),
                      method=NormalizationMethod.RMS, target_db=-3.0)
    (clip,) = plan.clips
    assert clip.peak_db == pytest.approx(20 * np.log10(0.9), abs=0.05)
    assert clip.will_limit and plan.gain_applied_db(clip) == pytest.approx(-1.0 - clip.peak_db)


def test_flags_point_at_the_clips_worth_a_listen():
    from emognition.audio.analysis import analyse_samples, check_folder

    rate = 16000
    speech = np.zeros(rate)
    speech[3200:12800] = 0.5 * np.sin(np.arange(9600) * 2 * np.pi * 220 / rate)   # 0.2-0.8 s
    noise = 0.02 * np.random.default_rng(1).standard_normal(rate)
    clips = [
        analyse_samples(speech, rate, path="clean.wav"),
        analyse_samples(np.clip(speech * 3, -1.0, 1.0), rate, path="clipped.wav"),
        analyse_samples(speech + 0.05, rate, path="dc.wav"),
        analyse_samples(speech * 0.05, rate, path="quiet.wav"),                 # peak -32 dBFS
        analyse_samples(speech + noise, rate, path="noisy.wav"),                # 25 dB margin
        analyse_samples(np.concatenate([speech[3200:12800], np.zeros(3200)]), rate, path="edge.wav"),
        analyse_samples(speech[::2], rate // 2, path="slow.wav"),               # 8 kHz among 16
    ]
    keys = [{f.key for f in flags} for flags in check_folder(clips)]
    assert keys[0] == set()
    assert "clipped" in keys[1] and "dc" in keys[2] and keys[3] == {"quiet"}
    assert keys[4] == {"noisy", "edge"}          # the noise counts as speech, to both ends
    assert keys[5] == {"edge"} and keys[6] == {"rate"}
    assert clips[0].noise_floor_db < -200 and clips[4].noise_floor_db == pytest.approx(-34, abs=2)


def test_before_after_predicts_then_measures(tmp_path):
    import soundfile as sf

    from emognition.audio.review import before_after, measure_written

    rate = 16000
    tone = 0.3 * np.sin(np.arange(8000) * 2 * np.pi * 300 / rate)               # 0.5 s
    for name, tail in (("a_hap_f.wav", 0.30), ("b_sad_m.wav", 0.05)):
        sf.write(str(tmp_path / name), np.concatenate([np.zeros(3200), tone, np.zeros(int(tail * rate))]), rate)
    paths = sorted(str(p) for p in tmp_path.glob("*.wav"))
    plan = plan_batch(paths, str(tmp_path / "out"), method=NormalizationMethod.RMS)
    predicted = {m.key: m for m in before_after(plan)}
    assert predicted["tail"].before == pytest.approx((300, 50), abs=15)
    assert predicted["tail"].after == pytest.approx((100, 50), abs=15)       # trimmed, never padded
    assert predicted["lead"].after == pytest.approx((100, 100), abs=15)
    assert predicted["loudness"].after == pytest.approx((plan.target_db,) * 2, abs=0.01)
    assert predicted["peak"].reference == plan.ceiling_db

    measured = {m.key: m for m in before_after(plan, measure_written(apply_plan(plan), plan.method))}
    assert measured["tail"].after == pytest.approx(predicted["tail"].after, abs=15)
    assert measured["loudness"].after == pytest.approx(predicted["loudness"].after, abs=0.2)
    assert measured["duration"].after == pytest.approx(predicted["duration"].after, abs=0.001)


def test_peak_normalisation_has_no_separate_peak_panel(tmp_path):
    import soundfile as sf

    from emognition.audio.review import before_after

    sf.write(str(tmp_path / "a_hap_f.wav"), 0.2 * np.sin(np.arange(RATE) * 0.1), RATE)
    plan = plan_batch([str(tmp_path / "a_hap_f.wav")], str(tmp_path / "out"), method=NormalizationMethod.PEAK)
    metrics = before_after(plan)
    assert [m.key for m in metrics] == ["duration", "lead", "tail", "loudness"]
    assert metrics[-1].title == "Peak level" and metrics[-1].after == pytest.approx((-1.0,), abs=0.01)


def test_frame_rms_matches_a_frame_by_frame_loop():
    from emognition.audio.endpoints import frame_rms

    rng = np.random.default_rng(3)
    for rate in (16000, 22050, 44100):          # at 22.05 kHz a frame isn't two hops
        x = (rng.standard_normal(rate) * 0.1).astype(np.float32)
        x[: rate // 4] = 0.0                     # digital silence must stay exactly 0
        energies, frame, hop = frame_rms(x, rate)
        reference = np.array([np.sqrt(np.mean(x[s:s + frame].astype(np.float64) ** 2))
                              for s in range(0, x.size - frame + 1, hop)])
        assert energies == pytest.approx(reference, rel=1e-9, abs=1e-12)
        assert energies[0] == 0.0


def test_the_quick_check_and_the_full_analysis_agree(tmp_path):
    import soundfile as sf

    from emognition.audio.analysis import (
        QUICK_WAVE_BINS, WAVE_BINS, ClipStats, analyse_clip, check_files, quick_check,
    )

    speech = np.zeros(RATE)
    speech[3200:12800] = 0.5 * np.sin(np.arange(9600) * 2 * np.pi * 220 / RATE)
    for name in ("a_hap_f.wav", "b_sad_m.wav"):
        sf.write(str(tmp_path / name), speech, RATE)
    (tmp_path / "c_ang_f.wav").write_bytes(b"not audio")
    paths = sorted(str(p) for p in tmp_path.glob("*.wav"))
    seen = []
    clips, unreadable = check_files(paths, progress=lambda done, total: seen.append((done, total)))
    assert len(clips) == 2 and unreadable == ["c_ang_f.wav"] and seen[-1] == (3, 3)
    assert check_files(paths, should_stop=lambda: True) == ([], [])      # cancelled at once
    quick, full = quick_check(paths[0]), analyse_clip(paths[0])
    assert isinstance(full, ClipStats) and not hasattr(quick, "spectrogram_db")
    assert (quick.onset, quick.offset, quick.peak_db, quick.rms_db) == (full.onset, full.offset,
                                                                        full.peak_db, full.rms_db)
    assert quick.wave_max.size == QUICK_WAVE_BINS and full.wave_max.size == WAVE_BINS
