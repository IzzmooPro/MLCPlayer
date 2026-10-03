# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""PyInstaller spec dosyaları çalışma dizininden bağımsız yol çözer.

Neden (3 Ekim 2026): spec dosyaları kökten `packaging/` altına taşındı.
PyInstaller göreli betik/veri yollarını SPEC KLASÖRÜNE göre çözer; eski
spec ise kökü `os.getcwd()` ile buluyordu. Bu test spec'i PyInstaller'ın
verdiği isimlerle (SPECPATH, Analysis, PYZ, EXE, COLLECT) ve bilerek
BAŞKA bir çalışma dizininden yürütür; toplanacak her dosyanın var olduğunu
gerçek derleme yapmadan denetler.
"""
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGING = ROOT / "packaging"
#: Large runtime binaries are not tracked (see .gitignore); a clean CI
#: checkout legitimately lacks them.
UNTRACKED_RUNTIME = {"mpv-2.dll"}


def _run_spec(name, monkeypatch, tmp_path):
    pytest.importorskip("PyInstaller")
    captured = {}

    def analysis(scripts, **kwargs):
        captured["scripts"] = scripts
        captured["analysis"] = kwargs
        return SimpleNamespace(binaries=[], datas=[], pure=[], zipped_data=[],
                               scripts=[])

    def exe(*args, **kwargs):
        captured["exe"] = kwargs
        return SimpleNamespace()

    namespace = {
        "__name__": "__main__",
        "SPECPATH": str(PACKAGING),
        "Analysis": analysis,
        "PYZ": lambda *args, **kwargs: SimpleNamespace(),
        "EXE": exe,
        "COLLECT": lambda *args, **kwargs: SimpleNamespace(),
    }
    monkeypatch.chdir(tmp_path)
    source = (PACKAGING / name).read_text(encoding="utf-8")
    exec(compile(source, str(PACKAGING / name), "exec"), namespace)
    return captured, namespace


def _assert_exists(path):
    if Path(path).name in UNTRACKED_RUNTIME:
        return
    assert os.path.isabs(path), f"göreli yol kaldı: {path}"
    assert Path(path).exists(), f"bulunamadı: {path}"


def test_main_spec_resolves_every_input_from_the_project_root(
        monkeypatch, tmp_path):
    captured, namespace = _run_spec("MLCPlayer.spec", monkeypatch, tmp_path)

    assert Path(namespace["_project_root"]) == ROOT
    assert captured["scripts"] == [str(ROOT / "app" / "main.py")]
    for source, _target in captured["analysis"]["datas"]:
        _assert_exists(source)
    _assert_exists(captured["exe"]["icon"])
    version_file = Path(captured["exe"]["version"])
    assert version_file.parent == ROOT / "output" / "build"


def test_cleanup_spec_resolves_every_input_from_the_project_root(
        monkeypatch, tmp_path):
    captured, _namespace = _run_spec(
        "MLCUserCleanup.spec", monkeypatch, tmp_path)

    assert captured["scripts"] == [
        str(ROOT / "app" / "user_cleanup_main.py")]
    _assert_exists(captured["exe"]["icon"])
