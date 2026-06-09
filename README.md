# Emognition 3

**Speech Emotion Recognition** — a behavioral experiment in which a participant
hears a short speech clip and identifies the conveyed emotion (happy, scared,
neutral, sad, or angry). Responses and millisecond-accurate reaction times are
recorded and exported as Excel, PDF, HTML, and CSV reports.

This is a full Python / PsychoPy rewrite of the original MATLAB *Emognition 2*
(Mohsen Hozan, Auditory Prostheses & Perception Lab, Boys Town National Research
Hospital, 2014–2020), with feature parity plus a modern UX and cross-platform
support. The original experiment supported research on emotional prosody in
cochlear-implant users in Dr. Monita Chatterjee's
[APPLab](https://sites.northwestern.edu/monitachatterjee/) (now at Northwestern
University) — see e.g. [Chatterjee et al., 2019,
*Front. Psychol.*](https://doi.org/10.3389/fpsyg.2019.02190).

> Original MATLAB sources live under [`matlab/`](matlab/) — preserved as reference
> and homage.

---

## Screenshots

| Experimenter setup | Live monitor |
|:---:|:---:|
| ![Experimenter setup panel](docs/screenshots/setup.png) | ![Live monitor during a session](docs/screenshots/monitor.png) |
| Configure participant, audio folder, mode, and emotions before each session. | Accuracy and reaction time update trial-by-trial on the experimenter's screen. |

<details>
<summary><strong>Calibration window (3 tabs)</strong></summary>

| Stimuli / naming | Loudness & trim | SPL tone |
|:---:|:---:|:---:|
| ![Stimuli tab](docs/screenshots/calibration_stimuli.png) | ![Loudness tab](docs/screenshots/calibration_loudness.png) | ![SPL tone tab](docs/screenshots/calibration_tone.png) |

</details>

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

## Quick start — Linux

```bash
# Download emognition-linux-x86_64.zip from the Releases page, then:
unzip emognition-linux-x86_64.zip
chmod +x emognition/emognition
./emognition/emognition
```

---

<details>
<summary><strong>Installing on Windows (no technical knowledge needed)</strong></summary>

**No Python, no installation program — just unzip and run.**

1. Go to the [**Releases page**](https://github.com/mhozan/Emognition/releases)
   and click the latest release (top of the list).

2. Under **Assets**, click **`emognition-windows-x86_64.zip`** to download it.

3. **Extract the zip:**
   - Find the downloaded file (usually in your `Downloads` folder).
   - Right-click it → **Extract All…**
   - Choose where to put it — e.g. your Desktop or Documents folder — then
     click **Extract**.
   - This creates an **`emognition`** folder at that location.

4. **Open the `emognition` folder** (double-click it).
   Inside you will see `emognition.exe` alongside many support files — this is
   normal. The support files must stay in the same folder as the `.exe`.

5. **Double-click `emognition.exe`** to launch the experiment.

> **"Windows protected your PC" warning** — if Windows SmartScreen appears,
> click **More info** then **Run anyway**. This warning appears because the app
> has not been submitted to Microsoft's paid signing programme; the software
> itself is safe and open-source.

> **Black terminal window** — a small black window may appear behind the main
> window when the app starts. This is normal; you can minimise or ignore it.
> It closes automatically when you exit the app.

> **Slow first launch** — the first start can take 10–20 seconds while Windows
> scans the bundle. Subsequent launches are faster.

</details>

<details>
<summary><strong>Running from source — Windows (PowerShell, step by step)</strong></summary>

PsychoPy requires **Python 3.10 exactly** — 3.11 and later are not compatible.

All commands below are for **PowerShell**. Do not use Command Prompt — the
activation script will not work there.

**Step 1 — Open PowerShell**

- **Windows 11:** press `Win + X` → click **Terminal** (or **Terminal (Admin)**).
- **Windows 10:** press `Win`, type `PowerShell`, right-click
  **Windows PowerShell** → **Run as administrator**.

> **"Running scripts is disabled"?** Run this once in an administrator PowerShell, then reopen:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

**Step 2 — Install Python 3.10**

Download **Windows installer (64-bit)** from
[python.org/downloads/release/python-31011](https://www.python.org/downloads/release/python-31011/)
(`python-3.10.11-amd64.exe`). On the first screen, tick **"Add Python 3.10 to PATH"** before clicking Install Now.

Verify: `python --version` → should print `Python 3.10.11`.

**Step 3 — Install Git**

Download from [git-scm.com/download/win](https://git-scm.com/download/win), run with default options, then reopen PowerShell.

**Step 4 — Download and set up**

```powershell
cd "$HOME\Documents"
git clone https://github.com/mhozan/Emognition.git
cd Emognition
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install --no-deps -r requirements.txt
python -m emognition
```

> **Next time:** open PowerShell in the `Emognition` folder, then:
> ```powershell
> .venv\Scripts\Activate.ps1
> python -m emognition
> ```

</details>

<details>
<summary><strong>Running from source — macOS (step by step)</strong></summary>

**Step 1 — Install Python 3.10**

Option A (simpler): download **macOS 64-bit universal2 installer** from
[python.org/downloads/release/python-31011](https://www.python.org/downloads/release/python-31011/) and run it.

Option B (Homebrew):
```bash
brew install pyenv && pyenv install 3.10.11 && pyenv local 3.10.11
```

**Step 2 — Install PortAudio** (required for PsychoPy audio)

```bash
brew install portaudio
```

No Homebrew? Install it first: [brew.sh](https://brew.sh).

**Step 3 — Download and set up**

```bash
git clone https://github.com/mhozan/Emognition.git
cd Emognition
python3.10 -m venv .venv
source .venv/bin/activate
pip install --no-deps -r requirements.txt
python -m emognition
```

> Run `source .venv/bin/activate` at the start of each new terminal session.

</details>

<details>
<summary><strong>Running from source — Linux / Ubuntu (step by step)</strong></summary>

**Step 1 — Install system libraries**

```bash
sudo apt-get update
sudo apt-get install -y \
  python3.10 python3.10-venv python3.10-dev \
  libglu1-mesa libgl1 libegl1 libsndfile1 libportaudio2 \
  libxcb-cursor0 libxcb-xinerama0 libxkbcommon-x11-0 libdbus-1-3 \
  git
```

> Ubuntu 24.04+: add the deadsnakes PPA first:
> `sudo add-apt-repository ppa:deadsnakes/ppa && sudo apt-get update`

**Step 2 — Download and set up**

```bash
git clone https://github.com/mhozan/Emognition.git
cd Emognition
python3.10 -m venv .venv
source .venv/bin/activate
pip install --no-deps -r requirements.txt
python -m emognition
```

</details>

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

If you use Emognition in a publication, please cite the software:

```
Hozan, M. (2026). Emognition 3: A cross-platform Speech Emotion Recognition
experiment (PsychoPy). GitHub. https://github.com/mhozan/Emognition
```

> A methods paper describing the updated platform is in preparation.

Representative peer-reviewed studies produced with Emognition:

> Chatterjee, M., Kulkarni, A. M., Siddiqui, R. M., Christensen, J. A.,
> Hozan, M., Sis, J. L., & Damm, S. A. (2019). Acoustics of emotional prosody
> produced by prelingually deaf children with cochlear implants.
> *Frontiers in Psychology*, 10, 2190.
> [doi:10.3389/fpsyg.2019.02190](https://doi.org/10.3389/fpsyg.2019.02190)

> Cannon, S. A., & Chatterjee, M. (2019). Voice emotion recognition by children
> with mild-to-moderate hearing loss.
> *Ear and Hearing*, 40(3), 477–492.
> [doi:10.1097/AUD.0000000000000637](https://doi.org/10.1097/AUD.0000000000000637)

> Christensen, J. A., Sis, J., Kulkarni, A. M., & Chatterjee, M. (2019).
> Effects of age and hearing loss on the recognition of emotions in speech.
> *Ear and Hearing*, 40(5), 1069–1083.
> [doi:10.1097/AUD.0000000000000694](https://doi.org/10.1097/AUD.0000000000000694)

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
  Auditory Prostheses & Perception Lab, Boys Town National Research Hospital,
  2014–2020)
- **Dr. Monita Chatterjee** and the
  [APPLab](https://sites.northwestern.edu/monitachatterjee/) (now at
  Northwestern University, Dept. of Communication Sciences and Disorders),
  whose research program on emotional prosody in cochlear-implant users this
  software was built for

