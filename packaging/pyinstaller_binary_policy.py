# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Fail-closed policy for auto-discovered PyInstaller root binaries."""

import os
import ntpath
from pathlib import Path
import posixpath
import re


_ROOT_ICU = re.compile(r"^icu(?:uc|in|dt)\d*\.dll$", re.IGNORECASE)
_ROOT_API_SET = re.compile(r"^api-ms-win-.*\.dll$", re.IGNORECASE)
_ROOT_EXACT = {"ucrtbase.dll"}


class BinaryPolicyError(RuntimeError):
    """A root collision has provenance that cannot be safely classified."""


def _normal_destination(destination):
    raw = str(destination).replace("\\", "/")
    drive, _tail = ntpath.splitdrive(raw)
    if not raw or drive or raw.startswith("/"):
        raise BinaryPolicyError(
            f"binary destination is not relative: {destination}")

    components = []
    for component in raw.split("/"):
        if component in ("", ".", ".."):
            components.append(component)
            continue
        # Win32 aliases trailing spaces and dots to the same filesystem name.
        normalized_component = component.rstrip(" .")
        if not normalized_component:
            raise BinaryPolicyError(
                f"binary destination has an unsafe component: {destination}")
        components.append(normalized_component)

    normalized = posixpath.normpath("/".join(components))
    if normalized in ("", ".", "..") or normalized.startswith("../"):
        raise BinaryPolicyError(
            f"binary destination escapes the package root: {destination}")
    return normalized


def is_forbidden_root_destination(destination):
    """Return True only for forbidden DLL names at the TOC root."""
    normalized = _normal_destination(destination)
    if "/" in normalized:
        return False
    name = normalized.casefold()
    return (name in _ROOT_EXACT or _ROOT_ICU.fullmatch(name) is not None
            or _ROOT_API_SET.fullmatch(name) is not None)


def _is_within(path, root):
    try:
        return os.path.commonpath((os.path.normcase(path),
                                   os.path.normcase(root))) == os.path.normcase(root)
    except ValueError:
        return False


def sanitize_binaries(entries, project_root, python_root):
    """Remove classified foreign root collisions; fail on ambiguous sources.

    PyInstaller TOC entries are ``(destination, source, type)`` tuples. Nested
    destinations are deliberately outside this policy: a future wheel may own
    a private ICU namespace and must not be broken by a global basename drop.
    """
    project_root = os.path.realpath(os.fspath(project_root))
    python_root = os.path.realpath(os.fspath(python_root))
    kept = []
    removed = []
    for entry in entries:
        if not is_forbidden_root_destination(entry[0]):
            kept.append(entry)
            continue
        source = os.fspath(entry[1])
        if not os.path.isabs(source):
            raise BinaryPolicyError(
                f"root binary provenance is not absolute: {entry[0]}")
        resolved = os.path.realpath(source)
        if not os.path.isfile(resolved):
            raise BinaryPolicyError(
                f"root binary provenance does not exist: {entry[0]}")
        if (_is_within(resolved, project_root)
                or _is_within(resolved, python_root)):
            raise BinaryPolicyError(
                f"trusted root binary collision requires review: {entry[0]}")
        removed.append(entry)
    return kept, removed
