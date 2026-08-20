# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""The post-build gate must verify every user- and licence-critical file.

Static references in ``MLCPlayer.spec`` are not sufficient: a collection or
translation-build regression can still produce a runnable but incomplete
``dist`` tree.  These checks make the actual post-build inventory fail closed.
"""

import os
import sys

import pytest


sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "packaging"))

import verify_build


CRITICAL_DIST_FILES = (
    "MLC Player.exe",
    os.path.join("_internal", "bin", "mpv-2.dll"),
    os.path.join("_internal", "bin", "RUNTIME_MANIFEST.txt"),
    os.path.join("_internal", "licenses", "mpv-NOTICE.txt"),
    os.path.join("_internal", "assets", "mlc-player-icon.ico"),
    os.path.join("_internal", "assets", "mlc-player-icon-transparent.ico"),
    os.path.join("_internal", "translations", "mlcplayer_en.qm"),
    os.path.join("_internal", "LICENSE"),
    os.path.join("_internal", "README.md"),
    os.path.join("_internal", "README.tr.md"),
)


@pytest.mark.parametrize("relative", CRITICAL_DIST_FILES)
def test_post_build_inventory_covers_every_critical_file(relative):
    assert relative in verify_build.REQUIRED_IN_DIST


def test_post_build_rejects_each_missing_critical_file(tmp_path, monkeypatch):
    dist = tmp_path / "MLC Player"
    for relative in CRITICAL_DIST_FILES:
        target = dist / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"present")

    monkeypatch.setattr(verify_build, "DIST", str(dist))

    for missing in CRITICAL_DIST_FILES:
        target = dist / missing
        original = target.read_bytes()
        target.unlink()
        try:
            assert verify_build.check_post() is False, (
                f"post-build gate accepted missing critical file: {missing}")
        finally:
            target.write_bytes(original)
