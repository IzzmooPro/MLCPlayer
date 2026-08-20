# MLC Player

**A cinematic media player for Windows, built on libmpv.**

[![Latest release](https://img.shields.io/github/v/release/IzzmooPro/MLCPlayer)](https://github.com/IzzmooPro/MLCPlayer/releases/latest)
[![Licence: GPL v3](https://img.shields.io/badge/licence-GPLv3-blue)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-informational)](https://github.com/IzzmooPro/MLCPlayer/releases/latest)

MLC Player has one interface and commits to it: a frameless window, an
auto-hiding control layer drawn over the video, a wide timeline, and a
playlist in an owned window beside the main window. The playlist follows the
player but does not overlap the video or stay above other applications. There
is no classic menu-and-panel mode to fall back to.

*[Türkçe README](README.tr.md)*

---

## Features

**Playback.** libmpv provides the container and codec coverage: MP4, MKV,
AVI, MOV, WMV, FLV, MPEG, M4V, WEBM, TS, M2TS, VOB, OGV, 3GP, ASF and MXF for
video; MP3, WAV, FLAC, OGG, M4A, AAC, OPUS, WMA, APE, ALAC, AIFF, AC3, DTS and
MKA for audio. The extension only marks a file as a candidate — libmpv decides
what actually plays. Audio files show their embedded cover art, or a matching
image beside the file, instead of a black frame.

**Playlist.** An owned window beside the main window, with a draggable width,
thumbnails generated in the background, natural `1-2-10` ordering, folder
opening and drag-and-drop. It does not overlap the video or float always on
top.

**Subtitles.** Matching local subtitles are found automatically and stay hidden
until you ask for them, so a file never opens with unexpected text on screen.
The OpenSubtitles-powered Subtitle Centre is temporarily hidden while its API
distribution terms are reviewed; its network code is not exposed in the UI.

**Subtitle appearance.** Text, outline and background colour, size, outline
width, vertical position and synchronisation, with a live preview. A safe
band keeps subtitles clear of the control layer without overwriting the
position you chose.

**Signed updates.** The player checks for updates quietly at start-up, and
`Help → Check for updates` reports every outcome. A downloaded installer must
match the published size and SHA-256, *and* carry a valid Ed25519 signature
from the publisher, before it is allowed to run; anything unverified is
deleted. Access to this repository alone cannot produce an accepted update —
the private key is not in it. Shutdown goes through the player's own closing
sequence, so nothing is force-killed mid-write.

**One instance.** Launching the player again raises the open window and loads
the file there, instead of opening a second copy that would overwrite the
first one's settings on exit.

**Media information.** One readable view of the file, video, audio and
subtitle tracks — no raw mpv property names.

**Careful with your data.** User-facing errors mask real paths, addresses and
tracebacks, with details available separately; remote addresses appear as
`host[:port]` in the window title and recent files rather than in full.

---

## Quick start

- Open one file with `Ctrl+O`, open a folder from `Media → Open Folder`, or
  drag media onto the player. Use `Ctrl+P` to show the adjacent playlist.
- Use `Ctrl+U` for a URL. Direct HTTP/HLS streams can work with the main
  player; website extraction requires the Internet Video add-on described
  below.
- Matching local subtitles are detected automatically but stay hidden until
  selected. Online subtitle search is temporarily hidden; local subtitle
  loading and appearance controls remain available.
- `Tools → Language` selects the interface language after restart.
  `Tools → Keyboard Shortcuts` lists every supported shortcut.

---

## Install

Download the files from the same entry on the
**[Releases](https://github.com/IzzmooPro/MLCPlayer/releases/latest)** page:

1. Install the main player first with `MLCPlayer_Setup_v*.exe`.
2. To play website URLs that need extraction, also install the matching
   `MLCPlayer_InternetVideo_v*.exe`. This optional add-on supplies the bundled
   yt-dlp and Deno components; it is not needed for local media or direct
   HTTP/HLS streams.

The ready installer requires Windows 10 or 11, 64-bit, and administrator
approval. The main package contains the player and libmpv; the separate add-on
keeps the large internet-video tooling out of installations that do not need
it. Installed size therefore depends on whether the add-on is present.

Each installer has a matching `.sig` file — the publisher's Ed25519 signature
over the installer's SHA-256. Before an automatic update is allowed to run,
the player verifies the published size, SHA-256 and signature; anything that
does not match is deleted. You do not run the `.sig` file yourself.

The installer is not yet code-signed, so Windows SmartScreen will warn about
an unknown publisher on first run.

Already installed? `Help → Check for updates` verifies and updates the main
player. The built-in updater updates only the main player; if you use the
Internet Video add-on, download and run its matching new version from the same
release as a separate step.

### Uninstall and user data

Uninstalling either package keeps your settings and logs so an upgrade or
reinstall does not erase your preferences. Logs are stored under
`%APPDATA%\MLCPlayer\logs` and can be inspected or deleted safely from
`Tools → Log Management`. The add-on has its own uninstaller; removing it
disables website extraction without removing the main player.

---

## Build and run from source

The quickest path is `Start.bat`: it locates Python 3.12-3.14, installs it only
if missing, installs the packages from `requirements.txt` only if they are
absent, verifies all three runtime binaries and starts the player.
`Start.bat -CheckOnly` verifies everything without launching.

Manually:

```bash
pip install -r requirements.txt
python main.py
```

Manual local media playback requires Windows, Python 3.12-3.14 and
`bin/mpv-2.dll`. Internet video extraction additionally requires
`bin/yt-dlp.exe` and `bin/deno.exe`; direct HTTP/HLS playback remains an mpv
capability. `Start.bat` currently requires all three binaries. They are not
stored in the repository because of their size; their versions and SHA-256
digests are tracked in `bin/RUNTIME_MANIFEST.txt` and `bin/SHA256SUMS.txt`.

### Tests

```bash
python -m pytest -q tests
```

The default suite runs entirely offscreen, never touches your real settings
or application log, and does not reach the network. Runs that need a real
window and real video are opt-in through environment variables and are not
part of the default suite.

### Packaging

The release chain lives in `packaging/`: `build_release.bat` drives
PyInstaller, Inno Setup, the publisher signature and the verification steps in
`verify_build.py`. It refuses to build a version that installed clients could
not see as an update, and it stops if the installer cannot be signed. The
reasoning behind the packaging decisions is in `docs/PACKAGING_PLAN.md`.

---

## Contributing

Issues and pull requests are welcome at
[github.com/IzzmooPro/MLCPlayer](https://github.com/IzzmooPro/MLCPlayer).

Two things are worth knowing before you send a change:

- The project works defect-first. A fix starts with a failing test that
  measures the real behaviour, then the smallest change that turns it green.
- Some behaviour is deliberately fixed: the cinematic interface is the only
  interface, the playlist stays embedded in the main window, mpv and the
  subtitle workers are shut down cooperatively rather than terminated, and no
  new always-on-top flags or timers are introduced. `CLAUDE.md` records these
  invariants and the reasons behind them.

### Developer setup

`requirements.txt` is enough to run the player. To run the tests or build a
release you also need the tooling:

```
pip install -r requirements-lock.txt
```

The lock file is the reproducible Windows test/release environment.
`requirements.txt` and `requirements-dev.txt` document the smaller direct
runtime and developer dependency sets; their versions must match the lock.

The developer set brings pytest, Pillow, PyInstaller and PySide6. PySide6 is
there for one reason:
it provides `pyside6-lrelease`, which compiles the translations, and
`pyside6-linguist`. PyQt6 — what the player itself runs on — ships
`pylupdate6` but no `lrelease`. PySide6 is build tooling only and is excluded
from the packaged application.

### Translating

The interface is written in Turkish and translated outward; English is
complete. Adding a language does not need a code change:

1. Install the tooling above.
2. Open the file for your language in Qt Linguist, for example
   `pyside6-linguist translations/mlcplayer_de.ts`. Entries are marked
   *unfinished* until you confirm them.
3. Send the `.ts` file as a pull request. Only that file changes.

A language appears in `Tools → Language` on its own once its translation
actually carries content — the menu is derived from the compiled files
rather than a fixed list, so nothing else has to be edited. Partial work is
fine: a string you have not translated falls back to English, not to
Turkish.

One warning. Do **not** run `pyside6-lupdate` on these files. It only
recognises `QCoreApplication.translate(...)` and cannot see the
`app/i18n.tr()` wrapper, so it would rewrite the `.ts` files without most of
our strings. Extraction is done over the AST by
`packaging/extract_translations.py`, and `packaging/compile_translations.py`
turns the result into the `.qm` files that ship.

---

## Licence

Copyright (C) 2026 MLC Player contributors.

MLC Player is licensed under the **GNU General Public License v3.0**, SPDX
identifier **`GPL-3.0-only`**. Every source file carries that identifier in a
two-line SPDX header, and the full licence text is in [`LICENSE`](LICENSE) —
the canonical gnu.org text, byte for byte, which a test keeps pinned by its
SHA-256.

This program is free software: you may redistribute it and/or modify it under
the terms of the GNU GPL version 3. It comes with **no warranty** — not even
the implied warranty of merchantability or fitness for a particular purpose.
See the GNU GPL for details.

### Third-party components

The distributed package includes components under their own licences:

| Component | Licence | Where it ships | Notice |
|---|---|---|---|
| mpv / libmpv (with FFmpeg) | **GPLv3** (`--enable-gpl --enable-version3`, no `--enable-nonfree`) | main package | `licenses/mpv-NOTICE.txt` |
| yt-dlp (source) | Unlicense | Internet Video add-on | `licenses/yt-dlp-LICENSE.txt` |
| yt-dlp (official binary) | GPLv3+ | Internet Video add-on | `licenses/yt-dlp-THIRD_PARTY_LICENSES.txt` |
| deno | MIT | Internet Video add-on | `licenses/deno-LICENSE.txt` |

The official `yt-dlp.exe` contains third-party GPLv3+ code, which makes the
**combined executable GPLv3+**. A project's source licence and the licence of
a binary it ships are not the same thing.

### Corresponding source

For MLC Player itself the corresponding source is this repository. For the
third-party binaries we redistribute, every component is recorded in
[`bin/RUNTIME_MANIFEST.txt`](bin/RUNTIME_MANIFEST.txt) with its exact version,
the upstream URL it came from and its SHA-256, and
[`licenses/mpv-NOTICE.txt`](licenses/mpv-NOTICE.txt) names the upstream
repositories for mpv, FFmpeg and the build recipe. Both files ship inside the
installed package, not only here. We do not modify any of those sources.

If an upstream address ever becomes unreachable, ask for the source through
this repository. To make that offer independent of upstream, run
`python packaging/fetch_sources.py` before publishing a release: it
downloads the archives named in the manifest, verifies each against the
size and SHA-256 recorded there, and leaves them in `source_mirror/` ready
to upload alongside the installer. A file that fails verification is
deleted rather than kept.

### Open items

Two licensing questions are deliberately still open and are tracked in
[`README.tr.md`](README.tr.md#yayın-öncesi-açık-maddeler): the patent side of
the H.264/H.265 codecs, which is separate from licensing, and a review of the
OpenSubtitles API terms. That section is a checklist, not legal advice.
