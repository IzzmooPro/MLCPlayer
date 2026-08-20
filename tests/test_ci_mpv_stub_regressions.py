# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Hosted CI may collect mocked mpv tests without shipping native libmpv."""

import sys
from pathlib import Path

import pytest

from scripts.ci_mpv_stub import install_ci_mpv_stub


def test_ci_stub_exposes_only_the_import_time_mpv_contract(monkeypatch):
    monkeypatch.setenv("MLC_CI", "1")
    monkeypatch.delitem(sys.modules, "mpv", raising=False)

    module = install_ci_mpv_stub()

    assert sys.modules["mpv"] is module
    assert issubclass(module.ShutdownError, Exception)
    assert module.__spec__ is not None
    assert Path(module.__spec__.origin).name == "mpv.py"
    with pytest.raises(RuntimeError, match="native libmpv is disabled"):
        module.MPV()


def test_ci_stub_never_replaces_mpv_outside_the_explicit_ci_gate(monkeypatch):
    sentinel = object()
    monkeypatch.delenv("MLC_CI", raising=False)
    monkeypatch.setitem(sys.modules, "mpv", sentinel)

    assert install_ci_mpv_stub() is sentinel
    assert sys.modules["mpv"] is sentinel
