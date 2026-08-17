# MLC Player

**A cinematic media player for Windows, built on libmpv.**

[![Latest release](https://img.shields.io/github/v/release/IzzmooPro/MLCPlayer)](https://github.com/IzzmooPro/MLCPlayer/releases/latest)
[![Licence: GPL v3](https://img.shields.io/badge/licence-GPLv3-blue)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-informational)](https://github.com/IzzmooPro/MLCPlayer/releases/latest)

MLC Player has one interface and commits to it: a frameless window, an
auto-hiding control layer drawn over the video, a wide timeline, and a
playlist docked inside the main window rather than floating above it. There
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

**Playlist.** Docked in the main window with a draggable width, thumbnails
generated in the background, natural `1-2-10` ordering, folder opening and
drag-and-drop.

**Subtitle Centre.** Search, download and apply subtitles from OpenSubtitles.
A downloaded subtitle is written next to the media as an atomic `.srt`.
Local subtitles matching the media are found automatically and stay hidden
until you ask for them, so a file never opens with unexpected text on screen.

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

## Install

Download the latest `MLCPlayer_Setup_v*.exe` from
**[Releases](https://github.com/IzzmooPro/MLCPlayer/releases/latest)** and run
it. Windows 10 or 11, 64-bit. Installed size is roughly 300 MB, most of it
libmpv and the media tooling.

Each release also carries a `.sig` file — the publisher's signature over the
installer's SHA-256. The player uses it to verify updates automatically; you
can also check the digest by hand against the one printed in the release notes.

The installer is not yet code-signed, so Windows SmartScreen will warn about
an unknown publisher on first run.

Already installed? `Help → Check for updates` does the rest.

---

## Build and run from source

The quickest path is `Start.bat`: it locates Python 3.12+, installs it only
if missing, installs the packages from `requirements.txt` only if they are
absent, and starts the player. `Start.bat -CheckOnly` verifies everything
without launching.

Manually:

```bash
pip install -r requirements.txt
python main.py
```

Requirements: Windows, Python 3.12+, and the runtime binaries in `bin/`
(`mpv-2.dll`, `yt-dlp.exe`, `deno.exe`). Those binaries are not stored in the
repository because of their size; their versions and SHA-256 digests are
tracked in `bin/RUNTIME_MANIFEST.txt` and `bin/SHA256SUMS.txt`.

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
