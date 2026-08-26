# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Inno hatalari pahali build baslamadan compiler tarafindan yakalanir."""
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packaging"))

import verify_inno  # noqa: E402


def test_shared_preflight_compiles_main_and_addon_without_output(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(verify_inno.subprocess, "run", fake_run)

    assert verify_inno.verify("all", iscc="C:/Tools/ISCC.exe") is True
    assert calls == [
        (["C:/Tools/ISCC.exe", "/Q", "/O-", "/DMLCCompilePreflight=1",
          "packaging/MLCPlayer.iss"],
         {"cwd": str(ROOT), "capture_output": True, "text": True,
          "encoding": "utf-8", "errors": "replace", "timeout": 60}),
        (["C:/Tools/ISCC.exe", "/Q", "/O-", "/DMLCCompilePreflight=1",
          f"/DAddonVersion={verify_inno.APP_VERSION}",
          f"/DAddonNumericVersion={verify_inno.WINDOWS_VERSION}",
          "packaging/MLCPlayer_InternetVideo.iss"],
         {"cwd": str(ROOT), "capture_output": True, "text": True,
          "encoding": "utf-8", "errors": "replace", "timeout": 60}),
    ]


def test_compiler_failure_stops_before_the_second_script(monkeypatch):
    calls = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 2, "", "syntax error")

    monkeypatch.setattr(verify_inno.subprocess, "run", fake_run)

    assert verify_inno.verify("all", iscc="ISCC.exe", log=lambda *_: None) is False
    assert len(calls) == 1


def test_unknown_scope_fails_without_running_the_compiler(monkeypatch):
    monkeypatch.setattr(
        verify_inno.subprocess, "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("compiler calismamali")))

    assert verify_inno.verify("typo", iscc="ISCC.exe",
                              log=lambda *_: None) is False


def test_compiler_timeout_fails_closed(monkeypatch):
    def time_out(command, **_kwargs):
        raise subprocess.TimeoutExpired(command, 60)

    monkeypatch.setattr(verify_inno.subprocess, "run", time_out)

    assert verify_inno.verify("main", iscc="ISCC.exe",
                              log=lambda *_: None) is False


def test_stale_numeric_version_fails_before_the_compiler(monkeypatch):
    current = verify_inno.WINDOWS_VERSION
    stale = "0.0.0.0" if current != "0.0.0.0" else "1.0.0.0"
    installer = (ROOT / "packaging" / "MLCPlayer.iss").read_text(
        encoding="utf-8-sig").replace(
            f'#define MyAppNumericVersion "{current}"',
            f'#define MyAppNumericVersion "{stale}"')
    messages = []

    assert verify_inno.validate_main_source(installer, messages.append) is False
    assert any("MyAppNumericVersion" in message for message in messages)


def test_current_working_tree_version_contract_passes():
    assert verify_inno.validate_working_tree(log=lambda *_: None) is True


def test_both_build_chains_run_the_shared_gate_before_destructive_or_costly_work():
    release = (ROOT / "packaging" / "build_release.bat").read_text(
        encoding="utf-8")
    unsigned = (ROOT / "packaging" / "build_unsigned_main.bat").read_text(
        encoding="utf-8")

    release_gate = 'python "packaging\\verify_inno.py" all --iscc "%ISCC%"'
    unsigned_gate = 'python "packaging\\verify_inno.py" main --iscc "%ISCC%"'

    assert release_gate in release
    assert unsigned_gate in unsigned
    assert release.index(release_gate) < release.index("Cleaning previous output")
    assert release.index(release_gate) < release.index("run_pyinstaller.py")
    assert unsigned.index(unsigned_gate) < unsigned.index("Clean exact build outputs")
    assert unsigned.index(unsigned_gate) < unsigned.index("run_pyinstaller.py")


def test_preflight_skips_only_the_generated_payload_and_normal_build_does_not():
    installer = (ROOT / "packaging" / "MLCPlayer.iss").read_text(
        encoding="utf-8-sig")
    release = (ROOT / "packaging" / "build_release.bat").read_text(
        encoding="utf-8")
    unsigned = (ROOT / "packaging" / "build_unsigned_main.bat").read_text(
        encoding="utf-8")
    payload = (
        'Source: "..\\dist\\MLC Player\\*"; DestDir: "{app}"; '
        'Flags: ignoreversion recursesubdirs createallsubdirs; '
        'BeforeInstall: BeforeInstallMainPayload'
    )
    guarded = installer.split("#ifndef MLCCompilePreflight", 1)[1].split(
        "#endif", 1)[0]
    active_guarded_lines = [
        line.strip() for line in guarded.splitlines()
        if line.strip() and not line.lstrip().startswith(";")
    ]

    assert payload in guarded
    assert active_guarded_lines == [payload]
    assert installer.count("#ifndef MLCCompilePreflight") == 1
    assert installer.count("#endif") >= 1
    assert '/DMLCCompilePreflight=1' not in release
    assert '/DMLCCompilePreflight=1' not in unsigned
