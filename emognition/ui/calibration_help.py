# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""The words in the Calibration window: tooltips and the "How it works" panels.

Written for the people who run the booth -- a technician, a speech-language
pathology student, an audiologist: what each step measures, by which method,
with which constants, and what it does to the data (reaction times above all).
Wherever a number depends on the recordings, the panel is rebuilt with this
folder's own figures once they're measured.

Plain strings only (Qt renders the HTML subset used here); no Qt imports, so
the texts can be read, and tested, without a display.
"""

from __future__ import annotations

import math

from ..audio.analysis import (
    DC_LIMIT,
    EDGE_S,
    NOISE_MARGIN_DB,
    QUIET_PEAK_DB,
    SPEC_HOP_MS,
    SPEC_MAX_HZ,
    SPEC_RANGE_DB,
    SPEC_WINDOW_MS,
    THRESHOLD_DB,
)
from ..audio.loudness import DEFAULT_CEILING_DB, DEFAULT_TARGET_DB, NormalizationMethod
from ..audio.preprocess import DEFAULT_PAD_S, SIDECAR_NAME, BatchPlan
from ..audio.review import TITLES, in_sentence

# Styles for the QTextBrowser panels (Qt's rich text knows this CSS subset).
HELP_CSS = """
body { color: #20203a; font-size: 13px; }
h3 { color: #2a2250; font-size: 14px; margin: 12px 0 4px 0; }
p, li { margin: 0 0 6px 0; line-height: 135%; }
code { color: #3a2f9a; }
.num { color: #3a2f9a; font-weight: 600; }
.muted { color: #5a5a7a; }
"""

_PAD_MS = DEFAULT_PAD_S * 1000.0
_LUFS_TARGET = DEFAULT_TARGET_DB[NormalizationMethod.LUFS]
_RMS_TARGET = DEFAULT_TARGET_DB[NormalizationMethod.RMS]
_PEAK_TARGET = DEFAULT_TARGET_DB[NormalizationMethod.PEAK]


def db(value: float) -> float:
    """20 log10 of an amplitude (no -inf for silence)."""
    return 20.0 * math.log10(max(value, 1e-12))


def minus(text: str) -> str:
    """Typeset minus signs (U+2212) in a formatted number."""
    return text.replace("-", "−")


def _num(text: str) -> str:
    return f'<span class="num">{minus(text)}</span>'


# -- tooltips ---------------------------------------------------------------

TIPS: dict[str, str] = {
    "folder": (
        "The folder of .wav recordings that every tab works on. Nothing here changes it "
        "except Rename legacy -> canonical; calibrated copies go to a new folder beside it."),
    "help": "Show or hide the explanations beside each tab.",
    # Stimuli / naming
    "inspect": "Read the file names again and list what each one says. Nothing is written.",
    "write_manifest": (
        "Write stimuli.tsv (one row per file, editable in a spreadsheet; what you typed into an "
        "existing one is kept) and stimuli.json (what each column means)."),
    "rename": (
        "Rename legacy files (01_ang_f.wav) to BIDS-style names "
        "(speaker-01_emotion-angry_sex-f.wav) in place. Never overwrites a file; manifest rows "
        "follow their files."),
    "col_file": "The file name in this folder.",
    "col_recording": (
        "The recording's identifier: the legacy prefix (01 in 01_ang_f.wav) or the speaker "
        "entity of a BIDS-style name."),
    "col_emotion": "The intended emotion, read from the name (ANG/HAP/NEU/SAD/SCA, or emotion-...).",
    "col_sex": "The speaker's sex, read from the name: f, m or u (unknown).",
    "col_status": "UNRECOGNIZED files are never played: rename them to include them.",
    "balance": (
        "Clips per emotion and speaker sex. Unequal counts let a response bias score above "
        "chance: always answering the commonest emotion is right as often as it occurs."),
    # Clip check
    "check_again": (
        "Read the folder again and quick-check every file: level, clipping, DC offset, noise "
        "floor, speech span and flags. About a millisecond a clip; nothing is written."),
    "deep": (
        "Make a spectrogram card for every clip (the Cards view), on one time scale, to look "
        "over the whole set at once. The estimate is measured on this computer; Cancel stops "
        "it and keeps the cards made so far."),
    "cancel": "Stop the analysis; the cards made so far stay.",
    "view_table": (
        "One row per clip: the quick check's numbers and flags. Click a column header to sort; "
        "flagged clips come first."),
    "view_cards": "A spectrogram card for every clip (click Analyze to fill it).",
    "flagged_only": "Show only the clips with a flag.",
    "play": (
        "Hear the selected clip as a participant will: through the session's audio path, at its "
        "Volume (Space, or a double-click, does the same). The first play takes a second or two "
        "to open the audio device."),
    "col_flag": "\u26a0 = at least one flag: worth a listen. Hover the row for the details.",
    "col_wave": "The waveform (full scale = the cell's height), the detected speech shaded.",
    "col_duration_clip": "File length.",
    "col_peak_clip": "The highest sample, dBFS (0 = full scale).",
    "col_rms_clip": "RMS level of the whole file, silence included, dBFS.",
    "col_lead_clip": "Silence before the detected start of speech.",
    "col_tail_clip": "Silence after the detected end of speech: what the file-offset RT includes.",
    "col_noise": (
        "The level of the quietest 5 % of 20 ms frames: the background. 'digital silence': at "
        "the 16-bit floor or below."),
    "col_format": "Sample rate and channels.",
    "col_flags": "What the quick check found; hover the row for what each means and what to do.",
    # Loudness & trim
    "method": (
        "What to equalise. RMS level, the default, gives every clip the same average level, "
        "so the SPL tone played from the calibrated folder matches each clip, not just their "
        "average. Perceived loudness (LUFS) weights frequencies roughly as the ear does and "
        "skips pauses. Peak only lines up the loudest samples."),
    "method_lufs": (
        f"ITU-R BS.1770 integrated loudness: K-weighted (the ear's frequency sensitivity, "
        f"roughly) and gated, so pauses don't count. Target {minus(f'{_LUFS_TARGET:g}')} LUFS "
        "(EBU R128). Clips under 0.4 s can't be measured."),
    "method_rms": (
        f"The default. Root-mean-square level of the trimmed clip, pauses included, in dBFS. "
        f"Target {minus(f'{_RMS_TARGET:g}')} dBFS: afterwards every clip has the RMS the SPL "
        "tone plays at. Close to what the original version did."),
    "method_peak": (
        f"Every clip's highest sample brought to {minus(f'{_PEAK_TARGET:g}')} dBFS. Equal peaks "
        "are not equal loudness; use it only to match another lab's peak-normalised set."),
    "preview": (
        "Measure every file and show what calibration would change: the table and the charts. "
        "Nothing is written."),
    "apply": (
        "Write trimmed, loudness-matched copies to a new folder (same names, same sample format) "
        f"plus {SIDECAR_NAME}; the originals are never changed. Then every clip is measured "
        "again, so the charts show what was written."),
    "use_calibrated": (
        "Point this window at the calibrated folder: check it in Clip check, and set the SPL "
        "tone from the set you will actually present."),
    "chart": (
        "Each dot is a clip, as recorded (grey) and calibrated (purple); hover for the file. "
        "Every value is also in the table below."),
    "col_duration": "File length in seconds: as recorded -> after trimming.",
    "col_lead": (
        f"Silence before the detected start of speech, ms: as recorded -> after trimming "
        f"(at most {_PAD_MS:.0f} ms)."),
    "col_tail": (
        f"Silence after the detected end of speech, ms -- the gap between end of speech and "
        f"end of file, which the file-offset RT includes: as recorded -> after trimming "
        f"(at most {_PAD_MS:.0f} ms)."),
    "col_loudness": "Measured on the trimmed clip (how the gain is computed): before -> after.",
    "col_peak": "Highest sample, dBFS: before -> after the gain.",
    "col_gain": "The gain applied: target minus measured, less where the peak ceiling caps it.",
    "col_note": (
        f"PEAK-LIMITED: reaching the target would push a sample above "
        f"{minus(f'{DEFAULT_CEILING_DB:g}')} dBFS, so the gain stops there and the clip stays "
        "quieter than the target by the amount shown."),
    # SPL tone
    "seconds": "How long the tone plays (2-300 s); Stop ends it early.",
    "play": (
        "Play a steady 1 kHz tone at the folder's average level, through the same stereo stream "
        "and at the same Volume as the session's clips."),
    "stop": "Stop the tone.",
    "volume": (
        "The Volume the tone plays at: the setup window's (sessions play at it). Set it there "
        "before calibrating, then leave it alone."),
}


# -- How it works: Stimuli / naming ------------------------------------------

def stimuli_help() -> str:
    return f"""
<h3>What a file name must say</h3>
<p>Each recording needs an <b>emotion</b> and the speaker's <b>sex</b> in its name.
Two schemes are understood (letter case doesn't matter):</p>
<ul>
<li><b>BIDS-style</b> (recommended): key-value pairs joined by "_", e.g.
<code>speaker-01_emotion-happy_sex-f.wav</code>. Required: <code>emotion</code>
(angry, happy, neutral, sad, scared) and <code>sex</code> (f, m, u). Optional:
<code>speaker</code>, <code>lang</code>, <code>intensity</code>, <code>take</code>;
any other key is kept.</li>
<li><b>Legacy</b> (the MATLAB version's): <code>&lt;id&gt;_&lt;EMO&gt;_&lt;G&gt;.wav</code>
with EMO = ANG, HAP, NEU, SAD or SCA and G = F or M, e.g. <code>01_ang_f.wav</code>.</li>
</ul>
<p>A file that matches neither is listed as UNRECOGNIZED and never played. Every
recognised clip of an emotion being tested is one trial. The reports code the
emotions 1 Happy, 2 Scared, 3 Neutral, 4 Sad, 5 Angry, as the original did.</p>

<h3>Balance</h3>
<p>The chart counts clips per emotion and speaker sex. With equal counts,
chance is 1/k for k emotions whatever a participant favours; with unequal
counts, always answering the commonest emotion scores above 1/k.</p>

<h3>The manifest</h3>
<p><b>Write stimuli.tsv + .json</b> saves one row per file &mdash; recording ID,
speaker, emotion, sex, language, intensity, word, processing status (clipped,
trimmed, normalized, loudness), include, notes &mdash; to edit in a spreadsheet;
writing it again keeps what you typed. <code>stimuli.json</code> is its data
dictionary (each column's meaning and allowed values, BIDS-style), so the folder
documents itself.</p>

<h3>Rename legacy &rarr; canonical</h3>
<p>Renames legacy files in place to BIDS-style names
(<code>01_ang_f.wav</code> &rarr; <code>speaker-01_emotion-angry_sex-f.wav</code>).
It is the only button in this window that changes the recordings folder: it never
overwrites a file, and the manifest rows follow their files.</p>
"""


# -- How it works: Clip check ------------------------------------------------

def clips_help() -> str:
    return f"""
<h3>Quick check first, then in depth</h3>
<p>The table checks every file at once, about a millisecond a clip: its level,
clipping, DC offset, noise floor and where the speech starts and ends. Clips
with a flag come first &mdash; those are the ones worth a listen. Click a column
header to sort; hover a row for every number.</p>
<p>Select a clip to see it in full below: waveform, spectrogram and RMS curve,
with the detected speech and, washed out, what trimming would cut. <b>Play</b>
(or Space, or a double-click) plays it through the session's own audio path, at
its Volume, with a playhead.</p>
<p><b>Analyze</b> makes a spectrogram card for every clip (the Cards
view), so the whole set can be looked over at once. The button says roughly how
long it will take on this computer, and it can be cancelled.</p>

<h3>Reading the large view and the cards</h3>
<p>The cards are all on one time scale (the longest file's), so an odd length
stands out; the grey area is past the end of that file.</p>
<ul>
<li><b>Waveform</b> (top): the samples, channels averaged; the edges are full
scale. Red bars at the top and bottom: clipped samples.</li>
<li><b>Spectrogram</b> (middle): 0&ndash;{SPEC_MAX_HZ / 1000:g} kHz,
{SPEC_WINDOW_MS:g} ms Hann windows every {SPEC_HOP_MS:g} ms, a
{SPEC_RANGE_DB:g} dB range below the clip's maximum (brighter is louder).
Look for hum (a steady line at 50/60 Hz and its harmonics, along the bottom),
hiss (a haze over all frequencies in the pauses), clicks (thin vertical lines)
and band limits (nothing above about 3.4 kHz is a telephone-band recording).</li>
<li><b>RMS curve</b> (bottom): the short-time RMS the end-of-speech detector
decides on (20 ms frames every 10 ms), on a fixed
{minus('-70')}&hellip;0 dBFS scale so levels compare from card to card. Dashed:
the detector's threshold, {abs(THRESHOLD_DB):g} dB below the loudest frame.
Shaded, between the lines: the detected speech.</li>
</ul>

<h3>The numbers</h3>
<p><b>Peak</b>: the highest sample. <b>RMS</b>: the whole file, silence
included. <b>Before / after</b>: the silence before the detected start and after
the detected end of speech. <b>Noise</b>: the level of the quietest 5 % of
frames &mdash; "digital silence" means the pauses are at the 16-bit floor or
below. All in dBFS = 20&middot;log<sub>10</sub>(value), full scale = 1, so a
full-scale sine has an RMS of {minus('-3')} dBFS.</p>

<h3>The flags</h3>
<ul>
<li><b>Clipped</b>: samples at full scale. Turning the clip down doesn't remove
the distortion &mdash; re-record it or leave it out.</li>
<li><b>DC offset</b>: the mean sample is {DC_LIMIT * 100:g} % of full scale or
more. It wastes headroom and biases RMS; an editor's high-pass filter removes it.</li>
<li><b>Low level</b>: the peak is below {minus(f'{QUIET_PEAK_DB:g}')} dBFS.
Normalising raises it, noise and all.</li>
<li><b>Noisy</b>: the background is within {NOISE_MARGIN_DB:g} dB of the loudest
speech. The end of speech is found {abs(THRESHOLD_DB):g} dB below the loudest
frame, so noise may count as speech: trimming and the speech-offset RT are
unreliable for that clip.</li>
<li><b>Speech at the edge</b>: under {EDGE_S * 1000:g} ms of silence before or
after the speech &mdash; the recording may be cut off.</li>
<li><b>Sample rate / channels</b> unlike most of the folder: usually a different
recording chain.</li>
</ul>
"""


# -- How it works: Loudness & trim -------------------------------------------

def _folder_numbers(plan: BatchPlan) -> str:
    """This folder's silences and loudness, before and after, in words."""
    clips = plan.clips
    tails = [(c.orig_duration - c.offset_s) * 1000.0 for c in clips]
    leads = [c.onset_s * 1000.0 for c in clips]
    loud = [c.measured_db for c in clips]
    limited = [c for c in clips if c.will_limit]
    unit = "LU" if plan.method is NormalizationMethod.LUFS else "dB"
    pad = plan.pad_s * 1000.0
    short = sum(1 for v in (*tails, *leads) if v < pad)
    parts = [
        f"<p><b>In this folder</b> ({len(clips)} files): speech ends "
        f"{_num(f'{min(tails):.0f}')}&ndash;{_num(f'{max(tails):.0f}')} ms before the end of the "
        f"file (mean {_num(f'{sum(tails) / len(tails):.0f}')} ms) and starts "
        f"{_num(f'{min(leads):.0f}')}&ndash;{_num(f'{max(leads):.0f}')} ms after its beginning. ",
    ]
    if short:
        parts.append(f"{short} of those silences are already under {pad:.0f} ms and are kept as they are. ")
    else:
        parts.append(f"After trimming every clip keeps {pad:.0f} ms on each side. ")
    parts.append(
        f"Measured {in_sentence(TITLES[plan.method])} spans {_num(f'{min(loud):.1f}')} to {_num(f'{max(loud):.1f}')} "
        f"(a spread of {_num(f'{max(loud) - min(loud):.1f}')} {unit}).")
    if limited:
        short_by = [plan.gain_applied_db(c) - c.gain_db for c in limited]
        parts.append(
            f" {len(limited)} clip{'s' if len(limited) != 1 else ''} will be peak-limited, ending "
            f"{_num(f'{-max(short_by):.1f}')}&ndash;{_num(f'{-min(short_by):.1f}')} dB below "
            "the target.")
    parts.append("</p>")
    return "".join(parts)


def loudness_help(plan: BatchPlan | None = None) -> str:
    numbers = _folder_numbers(plan) if plan is not None and plan.clips else (
        '<p class="muted">Press Preview to see this folder\'s numbers here.</p>')
    return f"""
<h3>End of speech is not end of file</h3>
<p>Each file is mixed to mono and its RMS is taken in 20 ms frames every 10 ms.
Frames within {abs(THRESHOLD_DB):g} dB of the file's loudest frame count as
speech (a threshold relative to each recording, so it adapts to its level).
<b>Start of speech</b> = the start of the first speech frame; <b>end of
speech</b> = the end of the last one. What follows it to the end of the file is
trailing silence &mdash; and breaths or noise quieter than the threshold.</p>
{numbers}

<h3>Trimming and padding</h3>
<p>Calibration keeps from {_PAD_MS:.0f} ms before the start of speech to
{_PAD_MS:.0f} ms after its end, cut at the file's own edges: enough to protect
soft onsets (/f/, /s/, /h/) and release bursts without audible dead air.
<b>Silence is never added</b>: a file with less margin keeps what it has. So
before calibration a clip carries whatever silence was recorded; after it, at
most {_PAD_MS:.0f} ms on each side.</p>

<h3>Loudness</h3>
<ul>
<li><b>RMS</b> (default): 20&middot;log<sub>10</sub> of the trimmed clip's RMS,
pauses included. Target {_num(f'{_RMS_TARGET:g}')} dBFS. Every calibrated clip
then has the same RMS, the quantity the SPL tone reproduces, so the meter
reading holds for each clip, not just on average (a PEAK-LIMITED clip stays
below it).</li>
<li><b>LUFS</b>: ITU-R BS.1770 integrated loudness &mdash; K-weighted
(a high-shelf plus a high-pass filter, roughly the ear's sensitivity) and gated
(400 ms blocks quieter than {minus('-70')} LUFS, or more than 10 LU below the
rest, are ignored), so pauses don't count. Target {_num(f'{_LUFS_TARGET:g}')}
LUFS (EBU R128).</li>
<li><b>Peak</b>: the highest sample. Target {_num(f'{_PEAK_TARGET:g}')} dBFS.</li>
</ul>
<p>Gain = target &minus; measured, applied to the trimmed clip. No sample may
pass {_num(f'{DEFAULT_CEILING_DB:g}')} dBFS: where the gain would push one past
it, the gain stops so the peak lands exactly there, and the clip is flagged
<b>PEAK-LIMITED</b> (quieter than the target by the amount shown).</p>

<h3>What Apply writes</h3>
<p>A new folder <code>&lt;folder&gt;_calibrated</code>: the same file names and
sample format (16-bit stays 16-bit), and <code>{SIDECAR_NAME}</code> with the
method, target, ceiling, padding and every file's trims and gain, for the
methods section. The originals are never changed. Point the setup window's
<b>Audio folder</b> at the calibrated folder to use it.</p>

<h3>Reaction times</h3>
<p>Answers are taken once a clip has finished playing. The <b>file-offset
RT</b> (the default, as in the original) counts from the end of the file, so
the trailing silence is time the participant has already had to decide: it
varies from clip to clip before calibration, and becomes a near-constant
&le; {_PAD_MS:.0f} ms after it. The <b>speech-offset RT</b> counts from the
detected end of speech (file-offset RT + trailing silence), so it measures the
same thing before and after trimming &mdash; though it can't be shorter than the
trailing silence, since answers wait for the end of the file: another reason to
trim. Onset RTs count from the start of the file, so trimming shortens them
too.</p>
"""


# -- How it works: SPL tone --------------------------------------------------

def tone_numbers(rms: float, volume: float) -> str:
    """The folder's level, the tone's, and what leaves the app at this Volume."""
    vol_db = db(volume) if volume > 0 else float("-inf")
    out = db(rms) + vol_db
    return (
        f"<p><b>This folder</b>: average RMS {_num(f'{rms:.4f}')} = "
        f"{_num(f'{db(rms):.1f}')} dBFS. <b>The tone</b>: 1 kHz at "
        f"{_num(f'{db(rms):.1f}')} dBFS RMS (peak {_num(f'{db(rms * math.sqrt(2)):.1f}')} dBFS). "
        f"<b>At Volume {volume:.2f}</b> ({minus(f'{vol_db:+.1f}')} dB) it leaves the app at "
        f"{_num(f'{out:.1f}')} dBFS RMS &mdash; as the clips do, on average.</p>")


def tone_help(rms: float | None = None, volume: float = 0.8) -> str:
    numbers = tone_numbers(rms, volume) if rms else (
        '<p class="muted">Measuring the folder...</p>')
    return f"""
<h3>Why a tone</h3>
<p>Digital levels (dBFS) say nothing about how loud a clip is at the
participant's ear: that depends on the sound card, the system volume, the
amplifier and the headphones or loudspeakers. Speech is no good for setting it
&mdash; a meter's reading swings by 20 dB or more between syllables and pauses
&mdash; so you set the level with a steady tone at the stimuli's average level,
and read that.</p>

<h3>What it is</h3>
<p>A 1 kHz sine whose RMS equals the average RMS of the folder's files (each
file's whole length, silence included; a stereo file counts the mean of its two
channels' RMS), so
the meter's reading for the tone is the long-term average level of the stimuli
as they are played. It fades in and out over 50 ms so it starts and stops
without a click.</p>
{numbers}

<h3>How</h3>
<ol>
<li>Set the <b>Volume</b> in the setup window first: the tone plays at it,
through the same stereo stream as the clips.</li>
<li>Put the meter's microphone where the participant's head will be
(loudspeakers), or the earphone on a coupler or artificial ear (headphones).</li>
<li>Press <b>Play tone</b> and turn the amplifier or the system volume (not the
app's Volume) until the meter reads your protocol's level, e.g. 65 dB SPL.
Slow time weighting gives a steady reading; at 1 kHz the A, C and Z weightings
are all 0 dB, so any of them reads the same.</li>
<li>Then leave every volume control alone for all sessions. Changing the app's
Volume from 0.80 to 0.60 lowers every clip by 2.5 dB.</li>
</ol>

<h3>Which folder</h3>
<p>Set the level from the set you will present: after <b>Apply</b> in Loudness
&amp; trim, switch this window to the calibrated folder (trimming and normalising both
change the files' RMS). Check the level again at the start of each testing
day.</p>
"""
