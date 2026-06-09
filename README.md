# Emognition 3

**Speech Emotion Recognition** — a behavioral experiment in which a participant
hears a short speech clip and identifies the conveyed emotion (happy, scared,
neutral, sad, or angry). Responses and millisecond-accurate reaction times are
recorded and exported as Excel, PDF, HTML, and CSV reports.

This is a full Python / PsychoPy rewrite of the original MATLAB *Emognition 2*
(Mohsen Hozan, APP Lab, BTNRH / Allen Institute, 2014–2020), with feature parity
plus a modern UX and cross-platform support.

> Original MATLAB sources live under [`matlab/`](matlab/) — preserved as reference
> and homage.

---

## Features

| | |
|---|---|
| **Millisecond-accurate RTs** | PTB-scheduled audio onset; RT measured from both offset (default, matching legacy) and onset |
| **Test mode** | Blind test — no feedback — full confusion-matrix report |
| **Passive training** | Correct label revealed after each clip; participant learns the mapping |
| **Active training** | Participant responds, then correct (green) / wrong (orange) feedback before advancing |
| **Calibration** | Per-corpus loudness normalization (LUFS), speech-endpoint trim, BIDS-style renaming |
| **Experimenter monitor** | Live per-trial accuracy and RT on the experimenter's screen while the participant runs |
| **Reports** | Self-contained HTML, PDF (confusion heatmap + RT charts), Excel (4 sheets), CSV |
| **Multi-display** | Experiment auto-routes to the participant's screen; setup stays on the experimenter's |
| **Stimulus flexibility** | Legacy `01_ang_f.wav` and BIDS-style `speaker-01_emotion-angry_sex-f.wav` both accepted |
| **FOSS** | AGPL-3.0-or-later; no MATLAB, no proprietary toolboxes |

---

## Quick start — pre-built executable

Download the latest release for your OS from
[**Releases**](https://github.com/mhozan/Emognition/releases):

| Platform | File |
|---|---|
| Linux x86_64 | `emognition-linux-x86_64.zip` |
| macOS Intel | `emognition-macos-x86_64.zip` |
| macOS Apple Silicon (M1/M2/M3/M4) | `emognition-macos-arm64.zip` |
| Windows x86_64 | `emognition-windows-x86_64.zip` |

Unzip and double-click `emognition` (Linux/macOS) or `emognition.exe` (Windows).
No Python install needed.

> **macOS Gatekeeper** — on first launch right-click → Open and confirm.
> **Linux** — you may need `chmod +x emognition` the first time.

---

## Quick start — run from source

PsychoPy requires **Python 3.10** (not 3.11+). Install it with
[pyenv](https://github.com/pyenv/pyenv) or from python.org, then:

```bash
git clone https://github.com/mhozan/Emognition.git
cd Emognition
git checkout port/psychopy

python3.10 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Exact known-good dependency set (PsychoPy installed without its optional wx):
pip install --no-deps -r requirements.txt
```

**Linux** — a few system packages are required for OpenGL and audio:

```bash
sudo apt-get install -y \
  libglu1-mesa libgl1 libegl1 libsndfile1 libportaudio2 \
  libxcb-cursor0 libxcb-xinerama0 libxkbcommon-x11-0 libdbus-1-3
```

**macOS** — install [PortAudio](https://www.portaudio.com/) via Homebrew if not
already present:

```bash
brew install portaudio
```

**Windows** — no additional system packages needed.

Then launch:

```bash
python -m emognition          # opens the experimenter setup window
```

---

## Using the app

### 1. Setup window

Fill in the participant ID, select your audio folder, and choose a session mode:

| Mode | What it does |
|---|---|
| **Test** | Blind test — no feedback |
| **Passive Training** | Correct answer shown after each clip |
| **Active Training** | Participant responds, then correct/wrong feedback |

Click **Calibration** before your first run with a new stimulus corpus to
normalize loudness and inspect file naming.

### 2. Stimulus corpus

The app accepts two naming conventions:

**Legacy** (Emognition 2 / rename-it):
```
01_ang_f.wav   02_hap_m.wav   03_neu_f.wav ...
 ^  ^   ^
 ID emo sex   (ang/hap/sad/neu/sca  ×  f/m)
```

**BIDS-style canonical** (produced by the Calibration → Rename step):
```
speaker-01_emotion-angry_sex-f.wav
speaker-01_emotion-angry_sex-m.wav
speaker-02_emotion-happy_sex-f.wav  ...
```

Use **Calibration → Stimuli / Naming** to inspect what the app has parsed from
your folder and confirm each file's detected emotion and sex before running.

### 3. Reports

After each session, four reports are written to your chosen save folder:

- `ParticipantID_YYYYMMDD_HHMMSS.html` — self-contained dark-themed report with
  confusion matrix, RT distribution charts (onset + offset), per-trial table
- `.pdf` — same content, portable
- `.xlsx` — four sheets: Session Info, Confusion Matrix (heat-mapped), Percentages
  (by sex), Pressed Keys (with RT + quality flags + recording ID)
- `.csv` — per-trial raw data + summary

---

## CLI reference

```
python -m emognition [OPTIONS]

Options:
  (no args)          Open the experimenter setup window
  --setup            Same as above
  --calibrate        Open the Calibration window
  --selfcheck        Headless import test — use to verify a frozen bundle
  --participant ID   Participant label [Participant01]
  --experimenter ID  Experimenter name [APPstaff]
  --audio-dir PATH   Folder of .wav stimuli (default: bundled reference clips)
  --save-dir PATH    Output folder for reports [./save_location]
  --mode MODE        test | passive | active  [test]
  --emotions TAGS    Comma-separated subset, e.g. hap,sad,ang  [all five]
  --caption LANG     none | english | mandarin  [none]
  --volume FLOAT     Playback volume 0–1  [0.8]
  --fullscreen       Run the experiment window fullscreen
  --screen INT       Display index for the experiment window [0]
  --no-shuffle       Present clips in folder order instead of shuffled
  --allow-replays    Show a replay button (and 'r' key)
  --amp-visualizer   Show a green amplitude LED during playback
  --version          Print version and exit
```

---

## Building a standalone executable

Requires PyInstaller (included in the dev environment):

```bash
scripts/build_executable.sh       # Linux / macOS
scripts\build_executable.bat      # Windows
```

Output: `dist/emognition/` (~0.5 GB folder; zip to distribute).

Verify the bundle without a display:

```bash
./dist/emognition/emognition --selfcheck
```

Per-OS binaries are also built automatically by
[GitHub Actions](.github/workflows/build.yml) on every tagged release.

---

## Development

```bash
pytest                 # 88 tests, no display/audio required
pytest -v tests/test_timing.py   # just the timing tests
```

### Project layout

```
emognition/
  core/        UI-free logic: emotions, stimuli, timing, scoring, session modes
  audio/       Loudness normalization (LUFS), speech endpoint detection/trim
  naming/      BIDS-style canonical names + legacy parser + TSV manifest
  ui/          PyQt6 setup/calibration/monitor windows; PsychoPy experiment window
  reports/     HTML, PDF, Excel, CSV writers
  io/          Cross-platform file-open helper
assets/
  audio/       10 reference clips (5 emotions × 2 sexes), BIDS-named
  images/      Emoticon buttons, backgrounds, icon
matlab/        Original MATLAB sources (reference + homage)
scripts/       Build helpers; timing spike
tests/         pytest suite
```

### Adding a new report format

Implement a `write_XYZ_report(responses, path, *, info)` function in
`emognition/reports/XYZ.py`, import it in `emognition/reports/__init__.py`,
and call it in `emognition/app.py`. The test fixtures in `tests/conftest.py`
generate a `responses` list you can use.

---

## Reaction-time definition

Reaction times are measured **two ways**, matching the original tool:

- **From audio offset** *(default, matches legacy `reactiontime.m`)* — time from
  when the clip *ends* to the response. Positive = answered after the clip.
- **From audio onset** — time from when the clip *starts*. Both are included in
  the Excel and HTML reports.

The RT quality flags `anticipatory` (< 100 ms from onset) and `outlier`
(> 3 × IQR) are marked in the reports and excluded from summary statistics.

---

## Citation

If you use Emognition in a publication, please cite:

```
Hozan, M. (2026). Emognition 3: A cross-platform Speech Emotion Recognition
experiment (PsychoPy). GitHub. https://github.com/mhozan/Emognition
```

> A methods paper describing the updated platform is in preparation.

---

## License

[GNU AGPL-3.0-or-later](LICENSE). Copyleft; compatible with PsychoPy (GPLv3+).
Derivatives — **including modified versions offered over a network** — must remain
open under the same license.

For commercial / proprietary licensing inquiries regarding the original author's
own contributions, contact the author directly.

---

## Acknowledgements

Emognition 3 builds on the shoulders of:

- **PsychoPy** (Peirce et al.) — experiment engine and PTB audio backend
- **PyQt6** — experimenter UI
- **pyloudnorm** — ITU-R BS.1770 loudness normalization
- **openpyxl**, **fpdf2**, **matplotlib** — report generation
- **soundfile / libsndfile** — audio I/O
- The original **Emognition 2** design and MATLAB implementation (Mohsen Hozan,
  APP Lab, Boys Town National Research Hospital, 2014–2020)
