# MarkItDown Converter

A standalone Windows desktop app that converts documents — PDF, Word, PowerPoint,
Excel, HTML, e-books, Outlook messages and more — into clean Markdown. It wraps
Microsoft's [`markitdown`](https://github.com/microsoft/markitdown) library in a
simple drag-free GUI: add files or a whole folder, click **Convert**, done.
Everything runs **offline** — no API keys, no network.

---

## Build the `.exe` (on Windows)

> The executable must be built **on a Windows machine**. PyInstaller produces a
> binary for the OS it runs on — it cannot cross-build a Windows `.exe` from
> macOS or Linux. The build itself is one click.

**Prerequisite:** Python 3.10–3.13 installed with *"Add python.exe to PATH"* ticked
(check with `python --version`). Get it at <https://www.python.org/downloads/>.

1. Put this whole folder on the Windows machine.
2. Double-click **`build.bat`** (or run `./build.ps1` in PowerShell).
3. Wait — the first build downloads `onnxruntime`/`pandas`, so it takes a few minutes.
4. When it finishes, the `dist` folder opens automatically. Your app is:

   ```
   dist\MarkItDownConverter.exe
   ```

That single file is fully self-contained — copy it anywhere and run it. No Python
installation is needed on the machines you *run* it on.

---

## Using the app

- **Add files…** or **Add folder…** (folders are scanned recursively).
- Choose where output goes: next to each source file, or all into one folder.
- Click **Convert**. Each row shows its status; double-click a row to open the
  resulting `.md` — or to read the error if something failed.
- **Open output folder** jumps to the results.

Each `report.pdf` becomes `report.md` (UTF-8). Name clashes are auto-suffixed
(`report (1).md`).

---

## Supported formats (offline)

| Category    | Formats                                                    |
|-------------|------------------------------------------------------------|
| Documents   | PDF, DOCX, PPTX, XLSX, XLS                                  |
| Web / data  | HTML, XML, CSV, TSV, JSON, RSS/Atom                         |
| Other       | EPUB, Jupyter `.ipynb`, Outlook `.msg`, `.txt` / `.md`, ZIP |
| Images      | JPG, PNG, GIF, BMP, TIFF, WEBP (metadata — see note below) |

**Images:** without ExifTool installed, image conversion produces only basic
metadata. For rich EXIF output, install ExifTool and ensure `exiftool.exe` is on
PATH. (LLM image captioning is a separate `markitdown` feature that needs an
OpenAI key and is not wired into this offline build.)

**Deliberately excluded** to keep the build offline and lean — add later if you
want them (edit `requirements.txt` and the `hiddenimports` in the spec):
audio transcription (needs ffmpeg + a speech service), YouTube transcripts
(needs network), and Azure Document Intelligence / Content Understanding
(need API keys).

---

## Good-to-know caveats

- **Size:** the executable is large (~150–250 MB). `onnxruntime` — which the
  bundled [magika](https://github.com/google/magika) file-type detector needs —
  accounts for most of it. This is expected.
- **First launch (onefile):** a single-file build unpacks to a temp directory on
  each start, so the *first* launch can take several seconds. Subsequent launches
  are faster.
- **Antivirus / SmartScreen:** unsigned PyInstaller onefile executables are
  sometimes flagged by Windows SmartScreen or antivirus heuristics (a known
  false-positive pattern, not specific to this app). If that's a problem:
  - Build the **folder** version instead — open `MarkItDown-GUI.spec`, set
    `ONEFILE = False`, rebuild. It starts faster and trips AV far less often.
  - For wide distribution, code-sign the executable.

---

## Run from source (for development)

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Customising the build

Open **`MarkItDown-GUI.spec`** and edit the config block at the top:

- `ONEFILE = True` → single `.exe`; `False` → faster-starting folder build.
- `ICON = "app.ico"` → brand the window, taskbar and executable icon.
- `APP_NAME` → output filename.

To freeze your **exact** attached source instead of the PyPI release, change the
first line of `requirements.txt` to point at the extracted package:

```
./markitdown-main/packages/markitdown[pptx,docx,xlsx,xls,pdf,outlook]
```

---

## What's in this folder

| File                   | Purpose                                             |
|------------------------|-----------------------------------------------------|
| `app.py`               | The GUI application.                                 |
| `MarkItDown-GUI.spec`  | PyInstaller build recipe (handles model/DLL bundling).|
| `requirements.txt`     | Pinned dependencies.                                 |
| `build.bat`            | One-click Windows build (CMD).                       |
| `build.ps1`            | One-click Windows build (PowerShell).               |
| `README.md`            | This file.                                           |

`markitdown` is © Microsoft, MIT-licensed.
