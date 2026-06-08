# Emognition

**Speech Emotion Recognition** — a behavioral experiment in which a participant
hears short speech clips and identifies the emotion conveyed (happy, scared,
neutral, sad, or angry). The program plays the audio, records the participant's
response and **reaction time**, and generates per-session reports.

This repository is a modern, cross-platform, open-source re-implementation of the
original MATLAB application (Mohsen Hozan, APP Lab, 2014–2020), rebuilt on
[PsychoPy](https://psychopy.org/) for millisecond-accurate timing.

> The original MATLAB sources live under [`matlab/`](matlab/) — preserved as
> reference and as homage to where this started.

---

## Status — Phase 0 (scaffolding + timing validation)

The port is being built in phases (see the roadmap below). Right now:

- [x] Project structure, dependency lockfile, AGPL-3.0 license
- [x] UI-free core: emotion model + `..._EMO_G.wav` stimulus parser (+ tests)
- [x] **Timing spike** — proves audio-onset-synced reaction times work
      (`scripts/timing_spike.py`)
- [ ] Phase 1: core Test-mode experiment + Excel/PDF reports → first executable
- [ ] Phase 2: full parity (Training, Calibration, experimenter monitor window,
      amplitude visualizer, replays) + modern UX
- [ ] Phase 3: per-OS installers, documented run-from-source, hosted-web spike

## Layout

```
emognition/        # the Python package
  core/            # UI-free experiment logic (emotions, stimuli, timing, scoring) — unit-tested
  ui/              # PyQt6 config screens + PsychoPy experiment/monitor windows
  reports/         # Excel (openpyxl) + PDF (fpdf2 / matplotlib) report writers
  io/              # config load/save, session logging, cross-platform helpers
assets/audio/      # the 5-emotion × male/female reference .wav stimuli
assets/images/     # emoticon buttons, backgrounds, icon, splash
scripts/           # developer tools (e.g. the Phase-0 timing spike)
tests/             # pytest — runs without a display or audio device
matlab/            # original MATLAB sources (reference + homage)
```

## Setup (developers)

PsychoPy targets **Python 3.10**. This repo pins it via `.python-version`
(use [pyenv](https://github.com/pyenv/pyenv) or any 3.10 interpreter).

```bash
python -m venv .venv && source .venv/bin/activate

# Reproduce the exact known-good environment:
pip install --no-deps -r requirements.txt
```

> **Why `--no-deps`?** PsychoPy's metadata hard-requires `wxPython`, which has no
> Linux PyPI wheel and is only used by PsychoPy's *Builder/Coder IDE* — not by the
> experiment runtime. We deliberately omit it and build our UI on **PyQt6** (which
> PsychoPy already depends on), keeping the install smaller and far easier to
> package cross-platform. The lockfile already excludes it; see `requirements.in`.

On Linux you also need a few system libraries for OpenGL/audio (PsychoPy renders
via OpenGL):

```bash
sudo apt-get install -y libglu1-mesa libgl1 libegl1 \
  libxcb-cursor0 libxcb-xinerama0 libxkbcommon-x11-0 libdbus-1-3
```

### Run the tests
```bash
pytest
```

### Run the timing spike
```bash
python scripts/timing_spike.py   # needs a display + audio device
```

## Reaction time

Reaction time is reported **two ways**, matching the original tool:

- **From audio offset** *(default)* — time from when the clip finishes to the
  response. This mirrors the legacy `reactiontime.m`, which measured from the audio
  "stop" instant to the click.
- **From audio onset** — time from when the clip *starts* to the response (the more
  common convention in the literature).

## License

[GNU AGPL-3.0-or-later](LICENSE). Copyleft, and compatible with PsychoPy (GPLv3+).
Derivatives — **including modified versions offered over a network** — must remain
open under the same license.

*For commercial/proprietary licensing inquiries regarding the original
author's own contributions, please contact the author.*
