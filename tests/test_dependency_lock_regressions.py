# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Runtime, test and release environments must resolve the same versions."""

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "requirements.txt"
DEV = ROOT / "requirements-dev.txt"
LOCK = ROOT / "requirements-lock.txt"


def exact_pins(path):
    pins = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s;]+)", line)
        assert match, f"exact pin required in {path.name}: {line}"
        name, version = match.groups()
        key = re.sub(r"[-_.]+", "-", name).lower()
        assert key not in pins, f"duplicate package in {path.name}: {name}"
        pins[key] = version
    return pins


def test_runtime_and_developer_dependencies_are_exactly_pinned():
    runtime = exact_pins(RUNTIME)
    dev = exact_pins(DEV)

    assert {"pyqt6", "python-mpv", "cryptography"} <= runtime.keys()
    assert {"pytest", "pyside6", "pyinstaller", "pillow"} <= dev.keys()


def test_lock_covers_every_direct_dependency_at_the_same_version():
    assert LOCK.is_file(), "deterministic CI/release lock is missing"
    lock = exact_pins(LOCK)
    direct = exact_pins(RUNTIME) | exact_pins(DEV)

    for name, version in direct.items():
        assert lock.get(name) == version, (
            f"{name} differs between direct requirements and lock")


def test_lock_contains_the_known_build_and_qt_transitive_packages():
    lock = exact_pins(LOCK)
    assert {
        "pyqt6-qt6", "pyqt6-sip", "pyside6-essentials",
        "pyside6-addons", "shiboken6", "pyinstaller-hooks-contrib",
        "altgraph", "pefile", "pywin32-ctypes", "cffi", "pycparser",
    } <= lock.keys()


def test_bootstrap_checks_versions_instead_of_only_import_presence():
    bootstrap = (ROOT / "scripts" / "bootstrap.ps1").read_text(
        encoding="utf-8")
    assert "verify_dependencies.py" in bootstrap
    assert "requirements.txt" in bootstrap
    assert 'MaximumPythonExclusive = [Version]"3.15"' in bootstrap


def test_release_build_fails_before_cleanup_on_an_unlocked_environment():
    build = (ROOT / "packaging" / "build_release.bat").read_text(
        encoding="utf-8")
    check = build.index("verify_dependencies.py")
    cleanup = build.index("STEP 2/8  Cleaning previous output")
    assert check < cleanup
    assert "requirements-lock.txt" in build


def test_dependency_verifier_fails_closed_for_a_missing_package(tmp_path):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        "package-that-does-not-exist-mlc==1.0\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(ROOT / "packaging" / "verify_dependencies.py"),
         str(requirements)],
        capture_output=True, text=True, timeout=15)

    assert result.returncode == 1
    assert "missing (expected 1.0)" in result.stdout


def test_dependency_verifier_rejects_non_exact_input(tmp_path):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("pytest>=9\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(ROOT / "packaging" / "verify_dependencies.py"),
         str(requirements)],
        capture_output=True, text=True, timeout=15)

    assert result.returncode == 1
    assert "exact 'package==version' pin required" in result.stdout
