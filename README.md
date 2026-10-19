# Universal RE Toolkit v1.0 — Linux Edition

Linux-first packaging of Universal RE Toolkit. The original extraction pipeline and core analysis stages are preserved; Linux launch/dependency handling and split-archive instructions have been added. The Windows launcher and bundled Windows 7-Zip files are retained for Windows users.

> Use only on software you own or are legally permitted to analyze. This tool treats installers as archives; it does not launch the installer itself.

## বাংলা সংক্ষেপ

এই Linux edition-এ মূল project-এর প্রধান feature রাখা হয়েছে:

- Installer/archive-এর SHA-256 hash এবং size report
- NSIS installer-এর `$PLUGINSDIR`-এর ভেতরের `.7z` payload খোঁজা ও extract করা
- Portable Electron layout ও সাধারণ archive extract করার চেষ্টা
- `app.asar`-সহ সব `.asar` archive-এর source tree extract করা (pure Python; Node.js লাগে না)
- `INVENTORY.txt`, `SHA256SUMS.txt`, এবং `RE-REPORT.md` তৈরি
- `*-FULL-RE.zip` বানানো
- `--split` দিয়ে 45 MB sequential part তৈরি; Linux/macOS ও Windows-এর join instructions লেখা
- `--store` এবং `--skip-zip` options
- Windows `.bat` launcher আগের মতো রাখা

**গুরুত্বপূর্ণ:** সব installer format extract হবে—এমন নিশ্চয়তা নেই। ফলাফল installer-এর format ও installed 7-Zip build-এর supported formats-এর ওপর নির্ভর করে। Linux-এর জন্য Windows `7z.exe` চালানো হয় না; system-এর 7-Zip command-line utility ব্যবহার হয়।

## Requirements

- Linux x86_64/ARM64 distribution (distribution-এর package availability অনুযায়ী)
- Python 3.8+
- 7-Zip command-line tool: `7zz`, `7z`, অথবা `7za`
- পর্যাপ্ত free disk space: সাধারণত installer size-এর প্রায় 3× বা তার বেশি
- Internet কেবল dependency install করার সময় প্রয়োজন; extraction নিজে offline চলে

## Install on Linux VPS

```bash
cd Universal-RE-Toolkit-Linux
chmod +x run.sh install-deps.sh
./install-deps.sh
python3 --version
7z
```

`install-deps.sh` supported package manager detect করে dependency install করার চেষ্টা করে। Distribution-এ package name আলাদা হলে নিজে 7-Zip CLI install করে নিশ্চিত করুন যে `7zz`, `7z`, বা `7za` command পাওয়া যায়।

### Debian / Ubuntu manual install

```bash
sudo apt-get update
sudo apt-get install -y python3 p7zip-full
```

### Fedora manual install

```bash
sudo dnf install -y p7zip p7zip-plugins
```

### Alpine manual install

```bash
sudo apk add python3 p7zip
```

## Run

### Recommended launcher

```bash
./run.sh "/path/to/installer.exe"
```

### Direct Python

```bash
python3 re_toolkit.py "/path/to/installer.exe"
```

### Archive input

```bash
python3 re_toolkit.py "/path/to/archive.7z"
python3 re_toolkit.py "/path/to/archive.zip"
```

### Options

```bash
python3 re_toolkit.py "/path/to/installer.exe" --outdir "/path/to/output"
python3 re_toolkit.py "/path/to/installer.exe" --split
python3 re_toolkit.py "/path/to/installer.exe" --store
python3 re_toolkit.py "/path/to/installer.exe" --skip-zip
```

- `--outdir DIR`: output base directory (default: `../RE-OUTPUT`, relative to this project directory)
- `--split`: additionally split final ZIP into 45 MB parts
- `--store`: create ZIP without compression (faster, larger)
- `--skip-zip`: do extraction and reports, but skip final ZIP

Paths containing spaces should be quoted.

## Output

```text
RE-OUTPUT/
├── <App-name>/
│   ├── app/                         # extracted application tree
│   │   └── resources/
│   │       ├── app.asar             # original ASAR, if present
│   │       └── app.asar-extracted/  # readable ASAR contents
│   ├── STAGE1-installer-opened/
│   └── RE-DOCS/
│       ├── RE-REPORT.md
│       ├── INVENTORY.txt
│       └── SHA256SUMS.txt
└── <App-name>-FULL-RE.zip
```

With `--split`, additional `.01`, `.02`, … parts and a `-JOIN.txt` file are generated. On Linux/macOS, the join file gives a `cat` command; on Windows, it gives `copy /b`.

## Optional Docker use

Build the image:

```bash
docker build -t universal-re-toolkit .
```

Run it with an input directory mounted at `/input` and output mounted at `/output`:

```bash
docker run --rm \
  -v "$PWD/input:/input:ro" \
  -v "$PWD/output:/output" \
  universal-re-toolkit \
  /input/installer.exe --outdir /output
```

The container needs enough memory and disk for the target installer and extracted files. Containerization does not add support for installer formats unsupported by the installed 7-Zip build.

## What the pipeline does

1. **Stage 0:** hash installer with SHA-256 and record size.
2. **Stage 1:** list/open installer with 7-Zip and look for NSIS `$PLUGINSDIR/*.7z` payload.
3. **Stage 2:** extract inner payload, or try a portable Electron/generic archive layout.
4. **Stage 3:** extract discovered `.asar` files using `asar_tool.py`, a pure-Python ASAR parser; no Node.js required.
5. **Stage 4:** build file-category inventory, detect some runtimes/app metadata, list 30 largest files.
6. **Stage 5:** hash files into `SHA256SUMS.txt`.
7. **Stage 6:** write `RE-REPORT.md`.
8. **Stage 7:** create the final ZIP and, optionally, split it into 45 MB parts.

## ASAR utility standalone

List ASAR entries:

```bash
python3 asar_tool.py list "/path/to/app.asar"
```

Extract an ASAR:

```bash
python3 asar_tool.py extract "/path/to/app.asar" "/path/to/output"
```

The extractor supports normal files, directory entries, symlinks, and sibling `.asar.unpacked` data when that directory is present.

## Troubleshooting

| Problem | Solution |
|---|---|
| `7-Zip CLI not found` | Run `./install-deps.sh` or install a supported CLI manually. |
| `No module named asar_tool` | Run the script from this extracted project directory; do not move `re_toolkit.py` alone. |
| `no payload could be extracted` | The installer may use an unsupported/custom format (for example, some Inno Setup installers). Inspect it separately with 7-Zip. |
| ASAR extraction reports failure | The ASAR may be corrupt, use an unexpected layout, or require files not present beside the archive. Check `RE-REPORT.md`. |
| Disk space runs out | Use a larger disk; extraction, ASAR contents, and final ZIP can require several times the input size. |
| Split parts won't extract | Rebuild the ZIP using the command in `*-JOIN.txt`, then run `unzip <name>-FULL-RE.zip`. |

## Integrity verification

The generated `RE-DOCS/SHA256SUMS.txt` contains SHA-256 hashes for files included in the working tree at the time of hashing. To verify on Linux:

```bash
cd RE-OUTPUT/<App-name>
sha256sum -c RE-DOCS/SHA256SUMS.txt
```

Run the check from the app output directory's parent (`RE-OUTPUT/<App-name>`). The manifest itself is excluded to avoid hashing itself.

## Windows compatibility

The original `RE-Toolkit.bat` and bundled `tools/7z/7z.exe` + `7z.dll` remain in the package. Windows users can continue to drag an installer onto the batch file or use:

```bat
python re_toolkit.py "D:\Downloads\installer.exe"
```

## Legal / Ethics

Use this tool only on software you own or are legally authorized to analyze. Compliance with software licenses and applicable law is your responsibility. The toolkit does not run the installer, but extracted files may themselves be unsafe; do not execute extracted binaries unless you trust them.

---
Universal RE Toolkit v1.0 — Linux Edition
