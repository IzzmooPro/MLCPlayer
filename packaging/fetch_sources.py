# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Fetches only verified corresponding-source archives for a release.

The old release flow treated redistributable executables and an mpv developer
archive as "source". They are provenance inputs, not complete rebuildable
source. This module uses a separate contract and fails closed while that
contract has an open blocker.

Usage:
    python packaging/fetch_sources.py
    python packaging/fetch_sources.py --allow-incomplete

The second form is a collection aid only. It downloads the already verified
subset while preserving every blocker; it never makes a release publishable.
"""

import hashlib
import json
import os
import sys
from collections import namedtuple
from urllib.parse import urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_MANIFEST_NAME = "corresponding_sources.json"
SOURCE_MANIFEST_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), SOURCE_MANIFEST_NAME)
OUTPUT_DIR_NAME = "source_mirror"

TRUSTED_HOSTS = frozenset({
    "github.com",
    "raw.githubusercontent.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
    "codeload.github.com",
    "crates.io",
    "download.qt.io",
    "ftp.fau.de",
    "files.pythonhosted.org",
    "static.crates.io",
    "www.python.org",
})

Item = namedtuple("Item", "name url size sha256")


def load_contract(path=SOURCE_MANIFEST_PATH):
    with open(path, encoding="utf-8") as handle:
        contract = json.load(handle)
    if contract.get("schema") != 1:
        raise ValueError("unsupported corresponding-source schema")
    if not isinstance(contract.get("blockers"), list):
        raise ValueError("blockers must be a list")
    if not isinstance(contract.get("sources"), list):
        raise ValueError("sources must be a list")
    return contract


def blockers(path=SOURCE_MANIFEST_PATH):
    """Returns every reason that keeps the source contract closed."""
    contract = load_contract(path)
    result = [str(value).strip() for value in contract["blockers"]
              if str(value).strip()]
    if contract.get("status") != "ready":
        result.append("corresponding-source contract status is not ready")
    if not contract["sources"]:
        result.append("no corresponding-source archive is declared")
    return result


def plan(path=SOURCE_MANIFEST_PATH):
    """Returns source archives declared by the contract; no network."""
    items = []
    seen = set()
    for raw in load_contract(path)["sources"]:
        try:
            name = raw["name"].strip()
            url = raw["url"].strip()
            size = int(raw["size"])
            digest = raw["sha256"].strip().lower()
        except (KeyError, AttributeError, TypeError, ValueError) as exc:
            raise ValueError("invalid corresponding-source row") from exc
        if not name or os.path.basename(name) != name or name in seen:
            raise ValueError(f"invalid or duplicate source name: {name!r}")
        if urlsplit(url).scheme != "https" or size <= 0 or len(digest) != 64:
            raise ValueError(f"invalid source metadata: {name}")
        int(digest, 16)
        seen.add(name)
        items.append(Item(name=name, url=url, size=size, sha256=digest))
    return items


def verify(path, size, sha256):
    """Checks a downloaded file; a bad or incomplete file is deleted."""
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


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    allow_incomplete = False
    for argument in argv:
        if argument == "--allow-incomplete":
            allow_incomplete = True
        else:
            print(f"[ERROR] Unknown argument: {argument}")
            return 1
    try:
        open_blockers = blockers()
        items = plan()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERROR] Corresponding-source contract cannot be read: {exc}")
        return 1
    if open_blockers and not allow_incomplete:
        print("[ERROR] Release source gate is CLOSED:")
        for reason in open_blockers:
            print(f"  - {reason}")
        return 1
    if not items:
        print("[ERROR] No verified source archive is declared.")
        return 1
    if open_blockers:
        print("[WARNING] Collecting the verified subset only; release remains "
              "BLOCKED:")
        for reason in open_blockers:
            print(f"  - {reason}")

    folder = output_dir()
    os.makedirs(folder, exist_ok=True)
    print(f"[INFO] Mirroring {len(items)} source archives into {folder}")

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
            print(f"[ERROR] {item.name}: size or SHA-256 mismatch; deleted")
            failed.append(item.name)

    if failed:
        print(f"[ERROR] {len(failed)} source archives failed: "
              + ", ".join(failed))
        return 1
    print(f"[INFO] {len(items)} corresponding-source archives verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
