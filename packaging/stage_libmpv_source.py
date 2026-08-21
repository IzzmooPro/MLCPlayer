# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Stage the verified libmpv source bundle without rebuilding libmpv.

The source-captured build is intentionally expensive.  This helper binds its
verified source part to the canonical v0.38 release-asset name in
``corresponding_sources.json``.  It performs no network, build, Git, tag or
release operation.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import fetch_sources


SOURCE_ASSET_NAME = (
    "libmpv-corresponding-source-20260821-g49418246f.tar.zst")


def source_item():
    matches = [item for item in fetch_sources.plan()
               if item.name == SOURCE_ASSET_NAME]
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one {SOURCE_ASSET_NAME!r} contract row")
    return matches[0]


def fingerprint(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def matches(path: Path, item) -> bool:
    try:
        size, digest = fingerprint(path)
    except OSError:
        return False
    return size == item.size and digest.lower() == item.sha256.lower()


def stage(source: str | os.PathLike[str] | None = None, *,
          target_dir: str | os.PathLike[str] | None = None, item=None) -> Path:
    item = source_item() if item is None else item
    folder = Path(fetch_sources.output_dir() if target_dir is None
                  else target_dir)
    target = folder / item.name

    if matches(target, item):
        return target
    if source is None:
        raise ValueError(
            f"staged source is missing or invalid: {target}")

    source_path = Path(source)
    if not source_path.is_file():
        raise ValueError(f"source part does not exist: {source_path}")

    folder.mkdir(parents=True, exist_ok=True)
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="wb", dir=folder, prefix=f".{item.name}.",
                suffix=".tmp", delete=False) as temporary:
            temporary_name = temporary.name
            digest = hashlib.sha256()
            size = 0
            with source_path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    temporary.write(chunk)
                    size += len(chunk)
                    digest.update(chunk)
            temporary.flush()
            os.fsync(temporary.fileno())

        actual_digest = digest.hexdigest().lower()
        if size != item.size or actual_digest != item.sha256.lower():
            raise ValueError(
                "source part does not match the release contract: "
                f"size={size} sha256={actual_digest}")
        os.replace(temporary_name, target)
        temporary_name = None
    finally:
        if temporary_name:
            try:
                os.remove(temporary_name)
            except OSError:
                pass

    if not matches(target, item):
        raise RuntimeError("staged source failed final readback")
    return target


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        help="Downloaded source part from run 32488810460; optional when the "
             "canonical staged file already verifies",
    )
    args = parser.parse_args(argv)
    try:
        item = source_item()
        target = stage(args.source, item=item)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"[ERROR] {exc}")
        return 1

    print(f"[OK] {target}")
    print(f"[OK] {item.size} bytes sha256:{item.sha256}")
    print(f"[INFO] future release URL: {item.url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
