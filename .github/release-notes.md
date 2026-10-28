## Emognition {{TAG}}

Ready-to-run apps — **no Python and no installation needed**. Pick the download
for your computer under **Assets** below.

| Computer | Download |
|---|---|
| **Windows** 10 or 11 (64-bit) | `emognition-windows-x86_64.zip` |
| **Mac** with Apple silicon (M1 or later), macOS 14 or newer | `emognition-macos-arm64.zip` |
| **Linux** x86_64 (Ubuntu 22.04 or newer) | `emognition-linux-x86_64.zip` |

On an Intel Mac, run Emognition from source: see the
[README](https://github.com/mhozan/Emognition#installation).

### Windows

1. Download **`emognition-windows-x86_64.zip`**.
2. Right-click it → **Extract All…** → choose a place, e.g. your Desktop → **Extract**.
3. Open the extracted **`emognition`** folder and double-click **`emognition.exe`**.

> **"Windows protected your PC"?** Click **More info** → **Run anyway**. Windows
> shows this for apps that aren't in Microsoft's paid signing programme. A black
> console window may open beside the app; leave it open (it closes with the app).

### Mac (Apple silicon)

1. Download **`emognition-macos-arm64.zip`** and double-click it in **Downloads**
   to unpack the **`emognition`** folder (Safari may already have unpacked it).
2. **Once:** the app isn't signed with an Apple developer certificate yet, so
   clear the download flag before you open it. Open **Terminal** (press
   `⌘ Space`, type `Terminal`, press Return) and paste:
   ```bash
   xattr -dr com.apple.quarantine ~/Downloads/emognition
   ```
   (Moved the folder? Type `xattr -dr com.apple.quarantine ` and drag the folder
   onto the Terminal window to fill in its path.)
3. Double-click **`emognition`** inside the folder. A Terminal window opens
   beside the app; leave it open.

> **"Apple could not verify 'emognition' is free of malware"?** Click **Done**,
> not *Move to Trash*, and do step 2: the flag is still on. *Open Anyway* in
> System Settings doesn't help here, because macOS would ask again for each of
> the app's several hundred libraries.
>
> **"Operation not permitted" in Terminal?** Let Terminal into your Downloads
> folder: **System Settings → Privacy & Security → Files and Folders →
> Terminal → Downloads Folder**, then run the command again.

### Linux

```bash
unzip emognition-linux-x86_64.zip
./emognition/emognition
```

(`chmod +x emognition/emognition` first if your unzip tool dropped the permission.)

### Check the download (optional)

`SHA256SUMS.txt` lists each zip's checksum. In the folder with your download:

- Linux: `sha256sum -c --ignore-missing SHA256SUMS.txt`
- Mac: `shasum -a 256 -c SHA256SUMS.txt` (the zips you didn't download are reported missing; that's fine)
- Windows (PowerShell): `Get-FileHash .\emognition-windows-x86_64.zip`, and compare with its line in `SHA256SUMS.txt`

The [README](https://github.com/mhozan/Emognition/blob/master/README.md) explains
how to set up stimuli, run sessions and read the reports.
