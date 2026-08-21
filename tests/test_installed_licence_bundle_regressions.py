# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Kurulu paketin lisans bildirimi ve Qt degistirme yolu kaybolmasin."""

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LICENCES = ROOT / "licenses"
SPEC = ROOT / "MLCPlayer.spec"
VERIFY = ROOT / "packaging" / "verify_build.py"

REQUIRED = (
    "THIRD_PARTY_NOTICES.txt",
    "Qt-LGPL-3.0.txt",
    "Qt-RELINKING.txt",
    "Python-LICENSE.txt",
    "PyQt6_sip-LICENSE.txt",
    "cffi-LICENSE.txt",
    "cryptography-LICENSE.txt",
    "OpenSSL-LICENSE.txt",
    "pycparser-LICENSE.txt",
    "python-mpv-LICENSE-GPL.txt",
    "python-mpv-LICENSE-LGPL.txt",
)

OFFICIAL_TEXT_SHA256 = {
    "Qt-LGPL-3.0.txt": "6c671e2912ec69c0832f32066c0313cee5fdc3bbcbce237822e89f3da58edd4e",
    "Python-LICENSE.txt": "26fac80422e9c8f621bf0552239608bc425f481983acdc81e2fe554189c74421",
    "PyQt6_sip-LICENSE.txt": "3e6f5b427c36f94ecf86bc01698af7030a1ed6eb3748110d5dbb8d142d804611",
    "cffi-LICENSE.txt": "ebb618637439262c8f3afd1837f7c69a2d13a69033caaf0e5cf534b260eed804",
    "cryptography-LICENSE.txt": "05e7953f6e1ba2403d1efac6e6ec2fde5a9482951220b7a404fa227c1c451795",
    "OpenSSL-LICENSE.txt": "7d5450cb2d142651b8afa315b5f238efc805dad827d91ba367d8516bc9d49e7a",
    "pycparser-LICENSE.txt": "b345a9762fdc5175d3d486d344cdcbb79078aee7c00e47fcc756ef2c4f5dcb61",
    "python-mpv-LICENSE-GPL.txt": "8177f97513213526df2cf6184d8ff986c675afb514d4e68a404010521b880643",
    "python-mpv-LICENSE-LGPL.txt": "dc626520dcd53a22f727af3ee42c770e56c97a64fe3adb063799d8ab032fe551",
}


def test_the_complete_installed_licence_bundle_is_checked_in():
    for name in REQUIRED:
        path = LICENCES / name
        assert path.is_file() and path.stat().st_size > 100, name


def test_the_checked_in_licence_texts_are_hash_locked():
    for name, expected in OFFICIAL_TEXT_SHA256.items():
        payload = (LICENCES / name).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == expected, name


def test_the_notice_names_every_bundled_runtime_family_and_version():
    notice = (LICENCES / "THIRD_PARTY_NOTICES.txt").read_text(
        encoding="utf-8")
    for fact in (
        "Python 3.14.3",
        "PyQt6 6.10.2",
        "Qt 6.10.2",
        "PyQt6_sip 13.11.1",
        "cffi 2.1.1",
        "cryptography 50.0.0",
        "pycparser 3.0",
        "python-mpv 1.0.8",
        "mpv-2.dll",
    ):
        assert fact in notice, fact


def test_qt_can_be_replaced_without_application_object_files():
    guide = (LICENCES / "Qt-RELINKING.txt").read_text(encoding="utf-8")
    for fact in (
        "_internal\\PyQt6\\Qt6",
        "dynamically loaded",
        "does not enforce a signature",
        "qtbase-everywhere-src-6.10.2.tar.xz",
        "qtsvg-everywhere-src-6.10.2.tar.xz",
        "qtimageformats-everywhere-src-6.10.2.tar.xz",
    ):
        assert fact in guide, fact
    assert "object files are not required" in guide


def test_pyinstaller_and_post_build_gate_ship_the_bundle():
    spec = SPEC.read_text(encoding="utf-8")
    verify = VERIFY.read_text(encoding="utf-8")
    for name in REQUIRED:
        assert f"licenses/{name}" in spec, name
        expected = f'os.path.join("_internal", "licenses", "{name}")'
        assert expected in verify, name
