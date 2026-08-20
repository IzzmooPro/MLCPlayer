# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Native feature smoke icin fail-closed ebeveyn kapi regresyonlari.

Bu dosya gercek child'i BASLATMAZ. Subprocess ve Windows Job Object siniri
tamamen sahte nesnelerle olculur; gercek koşum ayri acik onay ister.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

import native_feature_acceptance as acceptance
from native_feature_contract import (MEDIA_VARIABLE, OPTIONAL_CHECKS,
                                     OPT_IN_VALUE, OPT_IN_VARIABLE,
                                     REQUIRED_CHECKS)


def healthy_stdout(include_screenshot=False):
    names = list(REQUIRED_CHECKS)
    if include_screenshot:
        names.extend(OPTIONAL_CHECKS)
    lines = [f"CHECK PASS {name} :: measured" for name in names]
    return "\n".join(lines + ["RESULT failures=0", "MARK_DONE", ""])


def replace_line(stdout, prefix, replacement):
    lines = [replacement if line.startswith(prefix) else line
             for line in stdout.splitlines()]
    return "\n".join(lines) + "\n"


def test_a_completely_healthy_feature_smoke_is_accepted():
    assert acceptance.evaluate_feature_result(
        0, healthy_stdout(), b"") == []


@pytest.mark.parametrize("name", REQUIRED_CHECKS)
def test_every_required_check_is_mandatory(name):
    stdout = "\n".join(
        line for line in healthy_stdout().splitlines()
        if not line.startswith(f"CHECK PASS {name} ::")) + "\n"

    problems = acceptance.evaluate_feature_result(0, stdout, b"")

    assert any(f"eksik CHECK: {name}" in problem for problem in problems)


def test_a_failed_check_cannot_be_acquitted_by_exit_zero():
    stdout = replace_line(
        healthy_stdout(), "CHECK PASS maximize_toggle ::",
        "CHECK FAIL maximize_toggle :: entered=False")

    problems = acceptance.evaluate_feature_result(0, stdout, b"")

    assert any("FAIL CHECK: maximize_toggle" in problem for problem in problems)


def test_a_child_parent_contract_mismatch_is_always_rejected():
    stdout = healthy_stdout().replace(
        "RESULT failures=0", "CONTRACT_ERROR expected=[] actual=[]\n"
        "RESULT failures=0")

    problems = acceptance.evaluate_feature_result(0, stdout, b"")

    assert any("CONTRACT_ERROR" in problem for problem in problems)


def test_duplicate_unexpected_and_malformed_checks_are_rejected():
    stdout = healthy_stdout().replace(
        "RESULT failures=0",
        "CHECK PASS maximize_toggle :: duplicate\n"
        "CHECK PASS surprise_check :: unexpected\n"
        "CHECK PASS malformed\nRESULT failures=0")

    problems = acceptance.evaluate_feature_result(0, stdout, b"")

    assert any("2 kez" in problem for problem in problems)
    assert any("beklenmeyen CHECK" in problem for problem in problems)
    assert any("bozuk CHECK" in problem for problem in problems)


@pytest.mark.parametrize("returncode,stderr", (
    (1, b""),
    (0, b"warning"),
    (0, b"Windows fatal exception: code 0xe24c4a02"),
))
def test_nonzero_exit_or_any_stderr_is_rejected(returncode, stderr):
    assert acceptance.evaluate_feature_result(
        returncode, healthy_stdout(), stderr)


@pytest.mark.parametrize("result", (
    "RESULT failures=1", "RESULT failures=00", "RESULT", ""))
def test_only_the_exact_success_result_is_accepted(result):
    stdout = replace_line(healthy_stdout(), "RESULT failures=0", result)

    problems = acceptance.evaluate_feature_result(0, stdout, b"")

    assert problems


def test_mark_done_is_unique_and_the_last_nonempty_line():
    duplicated = healthy_stdout() + "MARK_DONE\n"
    trailing = healthy_stdout() + "AFTER_DONE\n"

    assert acceptance.evaluate_feature_result(0, duplicated, b"")
    assert acceptance.evaluate_feature_result(0, trailing, b"")


def test_screenshot_check_is_required_only_when_requested():
    assert acceptance.evaluate_feature_result(
        0, healthy_stdout(include_screenshot=True), b"",
        expect_screenshot=True) == []
    assert acceptance.evaluate_feature_result(
        0, healthy_stdout(), b"", expect_screenshot=True)
    assert acceptance.evaluate_feature_result(
        0, healthy_stdout(include_screenshot=True), b"")


def valid_video(tmp_path, name="ornek.mkv"):
    path = tmp_path / name
    path.write_bytes(b"video" * 1024)
    return str(path)


class SubprocessSentinel:
    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        raise AssertionError(f"BEKLENMEYEN child baslatma: {args!r}")


@pytest.fixture
def no_subprocess(monkeypatch):
    sentinel = SubprocessSentinel()
    monkeypatch.setattr(acceptance.subprocess, "Popen", sentinel)
    return sentinel


def test_general_native_smoke_flag_does_not_authorize_this_run(
        tmp_path, no_subprocess):
    problems, detail = acceptance.run_native_feature(
        valid_video(tmp_path), env={"MLC_NATIVE_SMOKE": "1"})

    assert problems and no_subprocess.calls == []
    assert detail["returncode"] is None


def test_specific_opt_in_without_valid_media_never_starts_child(
        tmp_path, no_subprocess):
    invalid = tmp_path / "not-video.py"
    invalid.write_text("pass", encoding="utf-8")

    problems, _ = acceptance.run_native_feature(
        str(invalid), env={OPT_IN_VARIABLE: OPT_IN_VALUE})

    assert problems and no_subprocess.calls == []


class FakeProcess:
    def __init__(self, stdout=None, stderr=b"", returncode=0,
                 timeout_once=False):
        self.pid = 4242
        self.returncode = returncode
        self.stdout = healthy_stdout().encode() if stdout is None else stdout
        self.stderr = stderr
        self.timeout_once = timeout_once
        self.communicate_calls = 0
        self.killed = False

    def communicate(self, timeout=None):
        self.communicate_calls += 1
        if self.timeout_once and self.communicate_calls == 1:
            raise subprocess.TimeoutExpired(
                cmd=["child"], timeout=timeout, output=b"partial",
                stderr=b"")
        return self.stdout, self.stderr

    def kill(self):
        self.killed = True
        self.returncode = -9


class FakeJob:
    def __init__(self, active=0):
        self.active = active
        self.closed = False

    def active_processes(self):
        return self.active

    def close(self):
        self.closed = True


def install_fake_run(monkeypatch, process=None, job=None):
    process = process or FakeProcess()
    job = job or FakeJob()
    popen_calls = []

    def popen(*args, **kwargs):
        popen_calls.append((args, kwargs))
        return process

    monkeypatch.setattr(acceptance.subprocess, "Popen", popen)
    monkeypatch.setattr(acceptance, "create_job_guard",
                        lambda candidate: job)
    return process, job, popen_calls


def test_valid_opt_in_uses_exact_media_and_an_isolated_child_environment(
        tmp_path, monkeypatch):
    process, job, calls = install_fake_run(monkeypatch)
    video = valid_video(tmp_path, "bosluklu video.mp4")
    env = {OPT_IN_VARIABLE: OPT_IN_VALUE, "QT_QPA_PLATFORM": "offscreen"}

    problems, detail = acceptance.run_native_feature(video, env=env)

    assert problems == []
    assert len(calls) == 1 and job.closed
    command = calls[0][0][0]
    child_env = calls[0][1]["env"]
    assert command == [acceptance.sys.executable, acceptance.CHILD]
    assert child_env[MEDIA_VARIABLE] == os.path.abspath(video)
    assert child_env[OPT_IN_VARIABLE] == OPT_IN_VALUE
    assert "MLC_NATIVE_SMOKE" not in child_env
    assert "QT_QPA_PLATFORM" not in child_env
    assert detail["child_pid"] == process.pid
    assert detail["active_processes_after"] == 0


def test_timeout_kills_only_the_contained_job_and_is_a_controlled_failure(
        tmp_path, monkeypatch):
    process = FakeProcess(timeout_once=True)
    job = FakeJob(active=1)
    install_fake_run(monkeypatch, process, job)

    problems, _ = acceptance.run_native_feature(
        valid_video(tmp_path), timeout=0.1,
        env={OPT_IN_VARIABLE: OPT_IN_VALUE})

    assert any("timeout" in problem for problem in problems)
    assert process.killed and job.closed


def test_a_surviving_descendant_fails_and_is_closed_with_its_job(
        tmp_path, monkeypatch):
    job = FakeJob(active=1)
    install_fake_run(monkeypatch, job=job)

    problems, detail = acceptance.run_native_feature(
        valid_video(tmp_path), env={OPT_IN_VARIABLE: OPT_IN_VALUE})

    assert any("surec sizintisi" in problem for problem in problems)
    assert detail["active_processes_after"] == 1 and job.closed


def test_media_fingerprint_change_fails_the_run(tmp_path, monkeypatch):
    install_fake_run(monkeypatch)
    video = valid_video(tmp_path)
    first = {"path": os.path.abspath(video), "size": 5120,
             "mtime_ns": 1, "hash_mode": "full", "sha256": "a",
             "stable_during_read": True}
    second = dict(first, sha256="b")
    values = iter((first, second))
    monkeypatch.setattr(acceptance, "media_fingerprint",
                        lambda _path: next(values))

    problems, _ = acceptance.run_native_feature(
        video, env={OPT_IN_VARIABLE: OPT_IN_VALUE})

    assert any("sha256" in problem for problem in problems)


def test_unreadable_media_blocks_before_subprocess(
        tmp_path, monkeypatch, no_subprocess):
    video = valid_video(tmp_path)
    monkeypatch.setattr(acceptance, "media_fingerprint", lambda _path: None)

    problems, _ = acceptance.run_native_feature(
        video, env={OPT_IN_VARIABLE: OPT_IN_VALUE})

    assert problems and no_subprocess.calls == []


def test_small_media_uses_a_full_read_only_sha256(tmp_path):
    video = valid_video(tmp_path)

    fingerprint = acceptance.media_fingerprint(video)

    assert fingerprint["hash_mode"] == "full"
    assert len(fingerprint["sha256"]) == 64
    assert fingerprint["stable_during_read"] is True


def test_child_uses_specific_opt_in_and_explicit_media_not_user_recents():
    child = Path(acceptance.CHILD).read_text(encoding="utf-8")

    assert "from native_feature_contract import" in child
    assert "OPT_IN_VARIABLE" in child and "MEDIA_VARIABLE" in child
    assert "REQUIRED_CHECKS" in child and "OPTIONAL_CHECKS" in child
    assert "recent_files" not in child
    assert "user_settings()" not in child


def test_the_runner_imports_neither_qt_nor_mpv():
    source = Path(acceptance.__file__).read_text(encoding="utf-8")

    assert "PyQt6" not in source
    assert "from app.player" not in source


def test_the_opt_in_gate_precedes_popen_in_source():
    source = Path(acceptance.__file__).read_text(encoding="utf-8")
    body = source[source.index("def run_native_feature"):]

    assert body.index("native_feature_requested") < body.index(
        "subprocess.Popen(")


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object contract")
def test_windows_job_guard_contains_one_benign_python_child():
    process = subprocess.Popen(
        [sys.executable, "-c", "pass"], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    guard = None
    try:
        guard = acceptance.create_job_guard(process)
        stdout, stderr = process.communicate(timeout=5)
        assert process.returncode == 0
        assert stdout == b"" and stderr == b""
        assert guard.active_processes() == 0
    finally:
        if guard is not None:
            guard.close()
        if process.poll() is None:
            process.kill()
            process.communicate()
