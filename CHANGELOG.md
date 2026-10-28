# Changelog

Notable changes to Emognition, the PsychoPy port. Downloads for each version are
on the [Releases page](https://github.com/mhozan/Emognition/releases); the
release notes there repeat the version's section below.

## 3.0.0-alpha.2 — 2026-10-27

### Downloads
- **Mac with Apple silicon**: a native build (M1 or later, macOS 14 or newer),
  alongside Windows and Linux.

### Sessions
- Modes named for what they do: **Familiarization** (was passive training),
  **Practice** (was active training; it can retry until correct, as the
  original did) and **Test**. The command line and the logs keep the old values.
- A **Begin** screen; the session's start time and duration count from it.
- Calm **background pictures**: a gradient by default, 30 bundled scenes, your
  own pictures, or a slideshow.
- Crisp emoticon and replay buttons; captions in English, Spanish or
  Traditional Chinese (Noto Sans), or none.
- Opt-in pacing: a *Next* button between trials, a progress star every N
  trials, a break screen every N trials.
- **P** pauses and **Esc** asks before quitting; an interrupted trial is played
  again.
- A per-trial **replay limit** (replays are off by default).
- A balanced shuffle (at most N of one emotion in a row), reproducible from the
  recorded random seed.

### Data and reports
- Every trial is saved the moment it ends, and an interrupted session
  **resumes** where it stopped.
- A second reaction time, from the **end of speech**, next to the file-offset RT.
- A JSON sidecar per session with its settings, seed and timing checks.
- Reports add the unbiased hit rate, Cohen's kappa, RT spread and row-percent
  confusion matrices; the HTML, PDF, Excel and CSV reports agree with each other.
- Exports neutralise spreadsheet formulas.

### Setup window
- Organised into groups, with a tooltip on every control; options that don't
  apply are hidden.
- BIDS-style participant IDs (`sub-001`), filled in with the next free number;
  an ID that already has reports can be amended, reused or edited.
- Settings are remembered, and **Reset to defaults** restores them;
  **Resume…** lists interrupted sessions and **Clear…** sets them aside.

### Calibration window (new)
- **Stimuli**: what each file name says, the number of clips per emotion and
  speaker sex, a `stimuli.tsv` manifest, and BIDS-style renaming.
- **Clip check**: every clip quick-checked into a table, with flags for
  clipping, DC offset, a low level, noise and cut-off speech; the selected clip
  in full (waveform, spectrogram, RMS curve), and playable; **Analyze** draws a
  spectrogram card for every clip.
- **Loudness & trim**: trims the silence to at most 100 ms on each side of the
  speech and equalises the level (**RMS by default**, or LUFS or peak), with
  before/after charts; writes a calibrated copy and a `calibration.json` record.
- **SPL tone**: a 1 kHz tone at the clips' average RMS, through the same stereo
  path and Volume as a session, for setting the level with a sound level meter.

### Under the hood
- Python 3.11 and PsychoPy 2026.2.5 (PsychToolbox's audio crashes on Python
  3.12 and later on Linux).
- Every change is tested on Linux, Windows and macOS; releases come with
  `SHA256SUMS.txt`.

## 3.0.0-alpha.1 — 2026-06-09

- First pre-release of the PsychoPy port of the MATLAB Emognition, with Windows
  and Linux downloads.
