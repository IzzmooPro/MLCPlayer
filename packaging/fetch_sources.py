# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Mirrors the corresponding source archives for the binaries we ship.

WHY THIS EXISTS (GPLv3 section 6). The source for the third-party binaries
MLC Player redistributes currently lives only at upstream addresses. If
shinchiro's release, yt-dlp's tag or deno's version ever disappears, we
have nowhere to point a user who asks for the source. This script fetches
the archives recorded in `bin/RUNTIME_MANIFEST.txt`, verifies each one
against the size and SHA-256 already written there, and leaves them in a
folder ready to be uploaded to the release as extra assets.

MEASURED TRAP - NOT EVERY MANIFEST ROW IS A DOWNLOADABLE ARCHIVE.
The manifest carries seven rows, and what the SHA-256 is a digest OF
changes from row to row:

    mpv-2.dll        digest of the DLL,     URL is a .7z archive   DIFFER
    deno.exe         digest of the EXE,     URL is a .zip archive  DIFFER
    mpv-dev-....7z   digest of the archive, URL is that archive    SAME
    yt-dlp.exe       digest of the exe,     URL is that exe        SAME

A naive fetcher would download the URL on the `mpv-2.dll` row and compare
it against the DLL's digest, then report a corrupt file - while having
downloaded exactly the right archive.

Comparing names does not settle it either: the row named
`yt-dlp-THIRD_PARTY_LICENSES.txt` does not match the `THIRD_PARTY_LICENSES.txt`
at the end of its URL, yet it is directly downloadable and its digest is of
what the URL returns.

So the classification below is EXPLICIT. Every manifest row appears either
in `FETCHABLE` or in `NOT_FETCHABLE` with a reason, and a test fails if a
new component is added to the manifest without being classified. Silent
gaps are the thing this file exists to prevent.

Usage:
    python packaging/fetch_sources.py
"""

import hashlib
import os
import sys
from collections import namedtuple
from urllib.parse import urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_PATH = os.path.join(ROOT, "bin", "RUNTIME_MANIFEST.txt")

#: Downloaded archives land here. Build output, never tracked.
OUTPUT_DIR_NAME = "source_mirror"

#: Only these hosts are contacted. An address that drifts elsewhere is a
#: reason to stop, not to follow.
TRUSTED_HOSTS = frozenset({"github.com", "raw.githubusercontent.com",
                           "objects.githubusercontent.com",
                           "release-assets.githubusercontent.com"})

#: Rows whose SHA-256 is the digest of exactly what their URL returns.
FETCHABLE = (
    "mpv-dev-x86_64-20260814-git-7b8915bc1d.7z",
    "yt-dlp.exe",
    "deno-x86_64-pc-windows-msvc.zip",
    "yt-dlp-THIRD_PARTY_LICENSES.txt",
)

#: Rows we deliberately do not fetch, each with the reason. Keeping the
#: reason here is what stops one of them being "fixed" into FETCHABLE later.
NOT_FETCHABLE = {
    "mpv-2.dll":
        "digest is of the extracted DLL; the URL returns the .7z archive, "
        "which is mirrored under its own row",
    "libmpv.dll.a":
        "extracted from the same .7z archive and carries no URL of its own",
    "deno.exe":
        "digest is of the extracted EXE; the URL returns the .zip archive, "
        "which is mirrored under its own row",
}

Item = namedtuple("Item", "name url size sha256")


def manifest_rows(path=MANIFEST_PATH):
    """Parses `file | version | url | size | sha256` rows."""
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line.startswith("#") or "|" not in line:
                continue
            parts = [part.strip() for part in line.split("|")]
            if len(parts) != 5:
                continue
            rows.append(parts)
    return rows


def plan(path=MANIFEST_PATH):
    """The archives to mirror. Reads only; touches no network."""
    items = []
    for name, _version, url, size, digest in manifest_rows(path):
        if name not in FETCHABLE:
            continue
        items.append(Item(name=name, url=url, size=int(size),
                          sha256=digest.lower()))
    return items


def verify(path, size, sha256):
    """Checks a downloaded file. FAIL-CLOSED: a bad file is DELETED.

    Size is compared first because it is cheap; there is no point hashing
    40 MB to learn the download was truncated. A half-good mirror is worse
    than none, so nothing unverified is left on disk.
    """
    try:
        actual_size = os.path.getsize(path)
    except OSError:
        return False
    if actual_size != size:
        _remove(path)
        return False

    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest().lower() != sha256.lower():
        _remove(path)
        return False
    return True


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def output_dir():
    return os.path.join(ROOT, OUTPUT_DIR_NAME)


def _download(url, target):
    """Fetches one URL. Imported here so importing this module stays cheap."""
    import urllib.request

    host = urlsplit(url).hostname or ""
    if host not in TRUSTED_HOSTS:
        raise ValueError(f"untrusted host: {host}")
    with urllib.request.urlopen(url, timeout=60) as response:
        final = urlsplit(response.geturl()).hostname or ""
        if final not in TRUSTED_HOSTS:
            raise ValueError(f"redirected to an untrusted host: {final}")
        with open(target, "wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)


def main():
    items = plan()
    if not items:
        print("[ERROR] Nothing to mirror; is the manifest readable?")
        return 1

    folder = output_dir()
    os.makedirs(folder, exist_ok=True)
    print(f"[INFO] Mirroring {len(items)} archives into {folder}")

    failed = []
    for item in items:
        target = os.path.join(folder, item.name)
        if os.path.isfile(target) and verify(target, item.size, item.sha256):
            print(f"[OK] {item.name} (already verified)")
            continue
        print(f"[INFO] Downloading {item.name} "
              f"({item.size / 1024 / 1024:.1f} MB)...")
        try:
            _download(item.url, target)
        except Exception as exc:
            print(f"[ERROR] {item.name}: {type(exc).__name__}")
            _remove(target)
            failed.append(item.name)
            continue
        if verify(target, item.size, item.sha256):
            print(f"[OK] {item.name}")
        else:
            print(f"[ERROR] {item.name}: size or SHA-256 does not match the "
                  f"manifest; the file was deleted")
            failed.append(item.name)

    if failed:
        print(f"[ERROR] {len(failed)} archives could not be mirrored: "
              + ", ".join(failed))
        return 1
    print(f"[INFO] {len(items)} archives verified. Upload the contents of "
          f"{OUTPUT_DIR_NAME}/ to the release as additional assets.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
