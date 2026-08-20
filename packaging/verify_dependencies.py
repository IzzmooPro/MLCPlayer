# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Fail closed when the active Python environment differs from a pin file."""

import argparse
import re
import sys
from importlib import metadata
from pathlib import Path


MIN_PYTHON = (3, 12)
MAX_PYTHON_EXCLUSIVE = (3, 15)
PIN_RE = re.compile(r"([A-Za-z0-9_.-]+)==([^\s;]+)")


def normalized(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def read_pins(path):
    pins = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = PIN_RE.fullmatch(line)
        if not match:
            raise ValueError(f"{path}:{number}: exact 'package==version' pin required")
        package, version = match.groups()
        key = normalized(package)
        if key in pins:
            raise ValueError(f"{path}:{number}: duplicate package {package}")
        pins[key] = (package, version)
    return pins


def verify(path):
    errors = []
    if not (MIN_PYTHON <= sys.version_info[:2] < MAX_PYTHON_EXCLUSIVE):
        errors.append(
            "Python 3.12, 3.13 or 3.14 is required; "
            f"active version is {sys.version_info.major}.{sys.version_info.minor}")

    try:
        pins = read_pins(path)
    except (OSError, UnicodeError, ValueError) as exc:
        return [str(exc)]

    for _key, (package, expected) in pins.items():
        try:
            actual = metadata.version(package)
        except metadata.PackageNotFoundError:
            errors.append(f"{package}: missing (expected {expected})")
            continue
        if actual != expected:
            errors.append(f"{package}: installed {actual}, expected {expected}")
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("requirements", type=Path)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    errors = verify(args.requirements)
    if errors:
        if not args.quiet:
            for error in errors:
                print(f"[ERROR] {error}")
        return 1
    if not args.quiet:
        print(f"[OK] Dependency pins match {args.requirements}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
