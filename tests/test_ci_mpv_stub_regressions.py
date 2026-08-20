# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Hosted CI may collect mocked mpv tests without shipping native libmpv."""

import os
import subprocess
import sys
from pathlib import Path

from scripts.ci_mpv_stub import install_ci_mpv_stub


def test_ci_stub_exposes_an_inert_mpv_contract_for_ui_children(monkeypatch):
    monkeypatch.setenv("MLC_CI", "1")
    monkeypatch.delitem(sys.modules, "mpv", raising=False)

    module = install_ci_mpv_stub()

    assert sys.modules["mpv"] is module
    assert issubclass(module.ShutdownError, Exception)
    assert module.__spec__ is not None
    assert Path(module.__spec__.origin).name == "mpv.py"
    player = module.MPV()
    player.observe_property("time-pos", None)
    player.time_pos = 12.0
    player.seek(3, reference="relative")
    assert player.time_pos == 15.0
    assert player.track_list == []
    assert player.terminate() is None


def test_ci_stub_never_replaces_mpv_outside_the_explicit_ci_gate(monkeypatch):
    sentinel = object()
    monkeypatch.delenv("MLC_CI", raising=False)
    monkeypatch.setitem(sys.modules, "mpv", sentinel)

    assert install_ci_mpv_stub() is sentinel
    assert sys.modules["mpv"] is sentinel


def test_ci_stub_is_installed_automatically_in_python_child_processes():
    root = Path(__file__).resolve().parent.parent
    env = os.environ.copy()
    env["MLC_CI"] = "1"
    env["PYTHONPATH"] = str(root / "scripts")

    result = subprocess.run(
        [sys.executable, "-c", (
            "import mpv; "
            "print(getattr(mpv, 'MLC_CI_STUB', False)); "
            "print(mpv.__spec__.origin)"
        )],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert lines[0] == "True"
    assert Path(lines[1]).name == "mpv.py"


def test_sitecustomize_never_stubs_mpv_without_the_ci_gate():
    root = Path(__file__).resolve().parent.parent
    env = os.environ.copy()
    env.pop("MLC_CI", None)
    env["PYTHONPATH"] = str(root / "scripts")

    result = subprocess.run(
        [sys.executable, "-c", (
            "import mpv; "
            "print(getattr(mpv, 'MLC_CI_STUB', False))"
        )],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"
