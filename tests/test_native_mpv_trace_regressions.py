# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""NATIVE-001 PDB'siz mpv trace tani kapisinin deterministik sozlesmesi.

Bu dosya gercek MPV/PyQt/video baslatmaz. Trace metni sentetik fixture'larla
degerlendirilir; subprocess siniri sahte runner veya nobetciyle olculur.
"""

import importlib
import importlib.util
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import native_mpv_trace_contract as trace  # noqa: E402
from native_mpv_trace_contract import (  # noqa: E402
    TRACE_FIELD_PREFIX,
    TRACE_LOG_VARIABLE,
    TRACE_OPT_IN_VARIABLE,
    TraceRecord,
    decode_trace_path,
    diagnostic_mpv_config,
    encode_trace_path,
    evaluate_trace_log,
    extract_trace_marker_problems,
    run_native_trace,
    trace_requested,
    trace_run_blockers,
)
from native_shutdown_acceptance import OPT_IN_VARIABLE  # noqa: E402
from native_shutdown_acceptance import resolve_media  # noqa: E402


GOOD_TRACE = b"""[   0.100][v][cplayer] Running hook: ytdl_hook/on_load
[   1.201][w][stats] stack traceback:
[   1.202][e][stats] Lua error: attempt to index a nil value
"""


@pytest.mark.parametrize("value", ["", "0", "true", "yes", "2", "1 ", "TRUE"])
def test_trace_opt_in_is_exact(value):
    assert not trace_requested({TRACE_OPT_IN_VARIABLE: value})


def test_trace_opt_in_accepts_only_one():
    assert trace_requested({TRACE_OPT_IN_VARIABLE: "1"})


def test_diagnostic_config_is_a_copy_with_exact_trace_options(tmp_path):
    original = {"vo": "gpu", "hwdec": "auto-safe"}
    log = tmp_path / "mpv trace.log"

    configured = diagnostic_mpv_config(original, str(log))

    assert original == {"vo": "gpu", "hwdec": "auto-safe"}
    assert configured is not original
    assert configured["log_file"] == os.path.abspath(log)
    assert configured["msg_level"] == "all=trace"
    assert configured["msg_time"] == "yes"
    assert configured["msg_module"] == "yes"


def test_python_mpv_converts_the_option_keys_to_real_dash_names():
    """Kaynak okunur; `mpv` IMPORT EDILMEZ ve DLL yuklenmez."""
    spec = importlib.util.find_spec("mpv")
    assert spec is not None and spec.origin, "python-mpv kaynagi bulunamadi"
    source = open(spec.origin, encoding="utf-8").read()

    assert re.search(
        r"k\.replace\(\s*['\"]_['\"]\s*,\s*['\"]-['\"]\s*\)", source), (
        "python-mpv kwargs icin underscore -> dash donusumu bulunamadi")


def test_trace_mode_off_does_not_mutate_the_player_module(tmp_path):
    class FakePlayerModule:
        MPV_CONFIG = {"vo": "gpu"}

    before = FakePlayerModule.MPV_CONFIG
    marker, problems = trace.configure_trace_mode(
        FakePlayerModule, str(tmp_path / "video.mkv"), env={})

    assert marker is None and problems == []
    assert FakePlayerModule.MPV_CONFIG is before
    assert FakePlayerModule.MPV_CONFIG == {"vo": "gpu"}


def test_an_invalid_trace_request_does_not_mutate_the_player_module(tmp_path):
    media = tmp_path / "video.mkv"
    media.write_bytes(b"media")

    class FakePlayerModule:
        MPV_CONFIG = {"vo": "gpu"}

    before = FakePlayerModule.MPV_CONFIG
    marker, problems = trace.configure_trace_mode(
        FakePlayerModule, str(media),
        env={OPT_IN_VARIABLE: "1", TRACE_OPT_IN_VARIABLE: "1",
             TRACE_LOG_VARIABLE: "relative.log"})

    assert marker is None and problems
    assert FakePlayerModule.MPV_CONFIG is before


def test_a_valid_trace_request_installs_only_a_child_copy(tmp_path):
    media = tmp_path / "video.mkv"
    media.write_bytes(b"media")
    log = str(tmp_path / "trace.log")

    class FakePlayerModule:
        MPV_CONFIG = {"vo": "gpu"}

    original = FakePlayerModule.MPV_CONFIG
    marker, problems = trace.configure_trace_mode(
        FakePlayerModule, str(media),
        env={OPT_IN_VARIABLE: "1", TRACE_OPT_IN_VARIABLE: "1",
             TRACE_LOG_VARIABLE: log})

    assert problems == []
    assert marker == TRACE_FIELD_PREFIX + encode_trace_path(os.path.abspath(log))
    assert original == {"vo": "gpu"}
    assert FakePlayerModule.MPV_CONFIG is not original
    assert FakePlayerModule.MPV_CONFIG["log_file"] == os.path.abspath(log)


@pytest.mark.parametrize("name", [
    "mpv trace.log", "Türkçe günlük.log", "🎬 trace output.log",
])
def test_trace_path_codec_is_lossless_and_token_safe(tmp_path, name):
    path = str(tmp_path / name)
    token = encode_trace_path(path)

    assert token and token.isascii() and not any(ch.isspace() for ch in token)
    assert decode_trace_path(token) == path


@pytest.mark.parametrize("token", ["", "!!!", "/w==", "not_base64*"])
def test_invalid_trace_path_tokens_fail_closed(token):
    assert decode_trace_path(token) is None


@pytest.mark.parametrize("line", [
    "MARK_TRACE_CONFIGURED t=0.10",
    "MARK_TRACE_CONFIGURED t=0.10 trace_b64=",
    "MARK_TRACE_CONFIGURED t=0.10 trace_b64=!!!",
    "MARK_TRACE_CONFIGURED t=0.10 wrong=YWJj",
    "MARK_TRACE_CONFIGURED t=0.10 trace_b64=YWJj extra",
])
def test_malformed_trace_marker_is_rejected(tmp_path, line):
    problems = extract_trace_marker_problems(
        line + "\n", str(tmp_path / "trace.log"))

    assert problems, line


def test_trace_marker_requires_the_exact_expected_path(tmp_path):
    expected = str(tmp_path / "expected.log")
    other = str(tmp_path / "other.log")
    stdout = ("MARK_TRACE_CONFIGURED t=0.10 " + TRACE_FIELD_PREFIX
              + encode_trace_path(other) + "\n")

    problems = extract_trace_marker_problems(stdout, expected)

    assert any("beklenen" in problem for problem in problems), problems


def test_trace_marker_accepts_a_unicode_path(tmp_path):
    expected = str(tmp_path / "Türkçe trace 🎬.log")
    stdout = ("MARK_TRACE_CONFIGURED t=0.10 " + TRACE_FIELD_PREFIX
              + encode_trace_path(expected) + "\n")

    assert extract_trace_marker_problems(stdout, expected) == []


def test_a_real_lua_error_is_extracted_with_script_and_message():
    problems, records = evaluate_trace_log(GOOD_TRACE)

    assert problems == []
    assert TraceRecord("error", "stats",
                       "Lua error: attempt to index a nil value") in records


@pytest.mark.parametrize("module", ["stats", "select", "ytdl_hook", "lua/custom"])
def test_lua_script_modules_are_not_hardcoded_to_one_script(module):
    raw = f"[ 1.0][e][{module}] Lua error: boom\n".encode("utf-8")

    problems, records = evaluate_trace_log(raw)

    assert problems == []
    assert records == [TraceRecord("error", module, "Lua error: boom")]


def test_a_warning_traceback_is_retained_but_not_a_complete_diagnosis():
    problems, records = evaluate_trace_log(
        b"[ 1.0][w][select] stack traceback: script.lua:42\n")

    assert records == [TraceRecord("warning", "select",
                                   "stack traceback: script.lua:42")]
    assert any("asil Lua hata mesaji" in problem for problem in problems)


def test_a_generic_cplayer_lua_message_does_not_invent_a_script_source():
    problems, records = evaluate_trace_log(
        b"[ 1.0][e][cplayer] Lua error: boom\n")

    assert records == [TraceRecord("error", "cplayer", "Lua error: boom")]
    assert any("script kaynagi" in problem for problem in problems)


@pytest.mark.parametrize("raw", [b"", b"[ 0.1][v][cplayer] normal\n"])
def test_missing_lua_error_evidence_is_inconclusive_not_success(raw):
    problems, records = evaluate_trace_log(raw)

    assert problems and records == []
    assert any("Lua" in problem or "bos" in problem for problem in problems)


def test_invalid_utf8_in_the_trace_is_fail_closed():
    problems, records = evaluate_trace_log(
        b"\xff[ 1.0][e][stats] Lua error: boom\n")

    assert problems
    assert any("UTF-8" in problem for problem in problems)
    assert records == []


def test_non_lua_errors_do_not_masquerade_as_the_target():
    problems, records = evaluate_trace_log(
        b"[ 1.0][e][cplayer] Failed to open file\n")

    assert problems and records == []


@pytest.mark.parametrize("path_kind", [
    "relative", "wrong_suffix", "existing", "missing_parent", "same_as_media",
])
def test_invalid_trace_targets_block_the_run_before_the_runner(
        tmp_path, path_kind):
    media = tmp_path / "video.mkv"
    media.write_bytes(b"media")
    if path_kind == "relative":
        log = "relative.log"
    elif path_kind == "wrong_suffix":
        log = str(tmp_path / "trace.txt")
    elif path_kind == "existing":
        log_path = tmp_path / "trace.log"
        log_path.write_bytes(b"old")
        log = str(log_path)
    elif path_kind == "missing_parent":
        log = str(tmp_path / "missing" / "trace.log")
    else:
        log = str(media)

    calls = []
    problems, detail = run_native_trace(
        str(media), log,
        env={OPT_IN_VARIABLE: "1", TRACE_OPT_IN_VARIABLE: "1"},
        shutdown_runner=lambda *args, **kwargs: calls.append((args, kwargs)))

    assert problems and calls == []
    assert detail["trace_records"] == []


def test_both_opt_ins_are_required_before_the_runner(tmp_path):
    media = tmp_path / "video.mkv"
    media.write_bytes(b"media")
    log = str(tmp_path / "trace.log")

    for env in ({}, {OPT_IN_VARIABLE: "1"}, {TRACE_OPT_IN_VARIABLE: "1"}):
        assert trace_run_blockers(str(media), log, env)


def test_a_blocked_run_never_calls_the_shutdown_runner(tmp_path):
    media = tmp_path / "video.mkv"
    media.write_bytes(b"media")
    calls = []

    problems, detail = run_native_trace(
        str(media), str(tmp_path / "trace.log"), env={},
        shutdown_runner=lambda *args, **kwargs: calls.append((args, kwargs)))

    assert problems and calls == []
    assert detail["shutdown_problems"] == []


def test_diagnostic_success_is_separate_from_shutdown_failure(tmp_path):
    media = tmp_path / "video.mkv"
    media.write_bytes(b"media")
    log = tmp_path / "trace.log"
    calls = []

    def fake_shutdown(video, timeout, env):
        calls.append((video, timeout, dict(env)))
        log.write_bytes(GOOD_TRACE)
        marker = ("MARK_TRACE_CONFIGURED t=0.10 " + TRACE_FIELD_PREFIX
                  + encode_trace_path(str(log)) + "\n")
        return ["stderr bos DEGIL"], {
            "returncode": 0, "stdout": marker, "stderr": "fatal",
            "raw_stdout": marker.encode("utf-8"),
            "raw_stderr": b"fatal",
            "media_before": {"size": 5}, "media_after": {"size": 5},
        }

    problems, detail = run_native_trace(
        str(media), str(log), timeout=33,
        env={OPT_IN_VARIABLE: "1", TRACE_OPT_IN_VARIABLE: "1"},
        shutdown_runner=fake_shutdown)

    assert problems == [], problems
    assert len(calls) == 1
    assert detail["shutdown_problems"] == ["stderr bos DEGIL"]
    assert detail["trace_records"][0].module == "stats"
    child_env = calls[0][2]
    assert child_env[TRACE_LOG_VARIABLE] == os.path.abspath(log)


def test_a_missing_trace_after_the_fake_run_is_fail_closed(tmp_path):
    media = tmp_path / "video.mkv"
    media.write_bytes(b"media")
    log = tmp_path / "trace.log"

    def fake_shutdown(video, timeout, env):
        marker = ("MARK_TRACE_CONFIGURED t=0.10 " + TRACE_FIELD_PREFIX
                  + encode_trace_path(str(log)) + "\n")
        return [], {"returncode": 0, "stdout": marker, "stderr": "",
                    "raw_stdout": marker.encode("utf-8"),
                    "raw_stderr": b""}

    problems, detail = run_native_trace(
        str(media), str(log),
        env={OPT_IN_VARIABLE: "1", TRACE_OPT_IN_VARIABLE: "1"},
        shutdown_runner=fake_shutdown)

    assert problems and detail["trace_records"] == []
    assert any("okunamadi" in problem for problem in problems)


def test_an_empty_trace_after_the_fake_run_is_fail_closed(tmp_path):
    media = tmp_path / "video.mkv"
    media.write_bytes(b"media")
    log = tmp_path / "trace.log"

    def fake_shutdown(video, timeout, env):
        log.write_bytes(b"")
        marker = ("MARK_TRACE_CONFIGURED t=0.10 " + TRACE_FIELD_PREFIX
                  + encode_trace_path(str(log)) + "\n")
        return [], {"returncode": 0, "stdout": marker, "stderr": "",
                    "raw_stdout": marker.encode("utf-8"),
                    "raw_stderr": b""}

    problems, detail = run_native_trace(
        str(media), str(log),
        env={OPT_IN_VARIABLE: "1", TRACE_OPT_IN_VARIABLE: "1"},
        shutdown_runner=fake_shutdown)

    assert problems and detail["trace_records"] == []
    assert any("bos" in problem for problem in problems)


def test_an_oversized_trace_after_the_fake_run_is_fail_closed(
        tmp_path, monkeypatch):
    media = tmp_path / "video.mkv"
    media.write_bytes(b"media")
    log = tmp_path / "trace.log"
    monkeypatch.setattr(trace, "MAX_TRACE_BYTES", 8)

    def fake_shutdown(video, timeout, env):
        log.write_bytes(b"123456789")
        marker = ("MARK_TRACE_CONFIGURED t=0.10 " + TRACE_FIELD_PREFIX
                  + encode_trace_path(str(log)) + "\n")
        return [], {"returncode": 0, "stdout": marker, "stderr": "",
                    "raw_stdout": marker.encode("utf-8"),
                    "raw_stderr": b""}

    problems, detail = run_native_trace(
        str(media), str(log),
        env={OPT_IN_VARIABLE: "1", TRACE_OPT_IN_VARIABLE: "1"},
        shutdown_runner=fake_shutdown)

    assert problems and detail["trace_records"] == []
    assert any("boyut sinirini" in problem for problem in problems)


def test_a_good_trace_cannot_rescue_a_wrong_child_marker(tmp_path):
    media = tmp_path / "video.mkv"
    media.write_bytes(b"media")
    log = tmp_path / "trace.log"

    def fake_shutdown(video, timeout, env):
        log.write_bytes(GOOD_TRACE)
        wrong = tmp_path / "other.log"
        marker = ("MARK_TRACE_CONFIGURED t=0.10 " + TRACE_FIELD_PREFIX
                  + encode_trace_path(str(wrong)) + "\n")
        return [], {"returncode": 0, "stdout": marker, "stderr": "",
                    "raw_stdout": marker.encode("utf-8"),
                    "raw_stderr": b""}

    problems, detail = run_native_trace(
        str(media), str(log),
        env={OPT_IN_VARIABLE: "1", TRACE_OPT_IN_VARIABLE: "1"},
        shutdown_runner=fake_shutdown)

    assert any("beklenen" in problem for problem in problems), problems
    assert detail["trace_records"], "trace ayristirilmadi"


def test_injected_trace_environment_does_not_leak_globally(tmp_path,
                                                            monkeypatch):
    media = tmp_path / "video.mkv"
    media.write_bytes(b"media")
    log = tmp_path / "trace.log"
    monkeypatch.delenv(TRACE_LOG_VARIABLE, raising=False)

    def fake_shutdown(video, timeout, env):
        log.write_bytes(GOOD_TRACE)
        marker = ("MARK_TRACE_CONFIGURED t=0.10 " + TRACE_FIELD_PREFIX
                  + encode_trace_path(str(log)) + "\n")
        return [], {"returncode": 0, "stdout": marker, "stderr": "",
                    "raw_stdout": marker.encode("utf-8"),
                    "raw_stderr": b""}

    problems, _ = run_native_trace(
        str(media), str(log),
        env={OPT_IN_VARIABLE: "1", TRACE_OPT_IN_VARIABLE: "1"},
        shutdown_runner=fake_shutdown)

    assert problems == []
    assert TRACE_LOG_VARIABLE not in os.environ


def test_child_artifact_paths_are_derived_without_losing_the_trace_suffix(
        tmp_path):
    log = tmp_path / "mpv trace.log"

    paths = trace.child_artifact_paths(str(log))

    assert paths == {
        "stdout": os.path.abspath(str(log)) + ".child_stdout.bin",
        "stderr": os.path.abspath(str(log)) + ".child_stderr.bin",
    }


def test_the_trace_runner_persists_exact_raw_child_streams(tmp_path):
    media = tmp_path / "video.mkv"
    media.write_bytes(b"media")
    log = tmp_path / "trace.log"
    raw_stdout = b"MARK_TRACE_CONFIGURED t=0.10 " + TRACE_FIELD_PREFIX.encode(
        "ascii") + encode_trace_path(str(log)).encode("ascii") + b"\n\xff"
    raw_stderr = b"Windows fatal exception: code 0xe24c4a02\r\n\xfe"

    def fake_shutdown(video, timeout, env):
        log.write_bytes(GOOD_TRACE)
        marker = ("MARK_TRACE_CONFIGURED t=0.10 " + TRACE_FIELD_PREFIX
                  + encode_trace_path(str(log)) + "\n")
        return ["stderr bos DEGIL"], {
            "returncode": 0,
            "stdout": marker,
            "stderr": "Windows fatal exception: code 0xe24c4a02",
            "raw_stdout": raw_stdout,
            "raw_stderr": raw_stderr,
        }

    problems, detail = run_native_trace(
        str(media), str(log),
        env={OPT_IN_VARIABLE: "1", TRACE_OPT_IN_VARIABLE: "1"},
        shutdown_runner=fake_shutdown)

    paths = trace.child_artifact_paths(str(log))
    assert problems == [], problems
    with open(paths["stdout"], "rb") as handle:
        assert handle.read() == raw_stdout
    with open(paths["stderr"], "rb") as handle:
        assert handle.read() == raw_stderr
    assert detail["child_artifacts"] == paths


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_a_preexisting_child_artifact_blocks_the_runner(tmp_path, stream):
    media = tmp_path / "video.mkv"
    media.write_bytes(b"media")
    log = tmp_path / "trace.log"
    paths = {
        "stdout": os.path.abspath(str(log)) + ".child_stdout.bin",
        "stderr": os.path.abspath(str(log)) + ".child_stderr.bin",
    }
    with open(paths[stream], "wb") as handle:
        handle.write(b"OLD EVIDENCE")
    calls = []

    problems, detail = run_native_trace(
        str(media), str(log),
        env={OPT_IN_VARIABLE: "1", TRACE_OPT_IN_VARIABLE: "1"},
        shutdown_runner=lambda *args, **kwargs: calls.append((args, kwargs)))

    assert calls == []
    assert any("child artifact" in problem and "zaten var" in problem
               for problem in problems), problems
    assert detail["child_artifacts"] == paths
    with open(paths[stream], "rb") as handle:
        assert handle.read() == b"OLD EVIDENCE"


@pytest.mark.parametrize("raw_key", ["raw_stdout", "raw_stderr"])
def test_missing_raw_child_stream_is_fail_closed_without_artifacts(
        tmp_path, raw_key):
    media = tmp_path / "video.mkv"
    media.write_bytes(b"media")
    log = tmp_path / "trace.log"

    def fake_shutdown(video, timeout, env):
        log.write_bytes(GOOD_TRACE)
        marker = ("MARK_TRACE_CONFIGURED t=0.10 " + TRACE_FIELD_PREFIX
                  + encode_trace_path(str(log)) + "\n")
        detail = {
            "returncode": 0, "stdout": marker, "stderr": "",
            "raw_stdout": marker.encode("utf-8"), "raw_stderr": b"",
        }
        del detail[raw_key]
        return [], detail

    problems, detail = run_native_trace(
        str(media), str(log),
        env={OPT_IN_VARIABLE: "1", TRACE_OPT_IN_VARIABLE: "1"},
        shutdown_runner=fake_shutdown)

    assert any(raw_key in problem and "bayt" in problem
               for problem in problems), problems
    assert all(not os.path.exists(path)
               for path in detail["child_artifacts"].values())


def test_an_artifact_write_error_is_reported_without_a_traceback(
        tmp_path, monkeypatch):
    media = tmp_path / "video.mkv"
    media.write_bytes(b"media")
    log = tmp_path / "trace.log"

    def fake_shutdown(video, timeout, env):
        log.write_bytes(GOOD_TRACE)
        marker = ("MARK_TRACE_CONFIGURED t=0.10 " + TRACE_FIELD_PREFIX
                  + encode_trace_path(str(log)) + "\n")
        return [], {
            "returncode": 0, "stdout": marker, "stderr": "",
            "raw_stdout": marker.encode("utf-8"), "raw_stderr": b"",
        }

    def denied_open(*args, **kwargs):
        raise PermissionError("DENIED FOR TEST")

    monkeypatch.setattr(trace, "open", denied_open, raising=False)

    problems, detail = run_native_trace(
        str(media), str(log),
        env={OPT_IN_VARIABLE: "1", TRACE_OPT_IN_VARIABLE: "1"},
        shutdown_runner=fake_shutdown)

    assert any("child artifact yazilamadi" in problem
               and "PermissionError" in problem for problem in problems)
    assert all(not os.path.exists(path)
               for path in detail["child_artifacts"].values())


def test_trace_module_imports_neither_qt_nor_libmpv():
    watched = ("mpv", "PyQt6.QtWidgets", "app.player")
    before = {name: sys.modules.get(name) for name in watched}

    importlib.reload(trace)

    assert {name: sys.modules.get(name) for name in watched} == before


def test_child_has_a_conditional_trace_mode_before_player_creation():
    child = os.path.join(os.path.dirname(__file__),
                         "native_player_shutdown_child.py")
    source = open(child, encoding="utf-8").read()

    configure_at = source.find("configure_trace_mode(")
    create_at = source.find("player = MPVPlayer()")
    assert configure_at != -1 and configure_at < create_at
    assert "diagnostic_mpv_config" not in source, (
        "trace optionlari child'da kopyalanmis; ortak sozlesmeden gelmeli")


def test_product_config_source_contains_no_trace_options():
    config = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                          "app", "config.py")
    source = open(config, encoding="utf-8").read()

    for option in ("log_file", "msg_level", "msg_time", "msg_module"):
        assert option not in source, f"urun MPV_CONFIG trace ile kirlendi: {option}"


def test_the_pdb_free_trace_diagnostic_runs_only_with_explicit_environment():
    """GERCEK TANI DUGUMU; varsayilan pakette daima skip olur.

    Basarisizsa otomatik tekrar YOKTUR. Tani sorunlari ve urun kapanis
    sorunlari ayri raporlanir; trace yakalamasi stderr'i aklamaz.
    """
    env = os.environ
    video = resolve_media(env)
    log = env.get(TRACE_LOG_VARIABLE, "")
    blockers = trace_run_blockers(video, log, env)
    if blockers:
        pytest.skip("PDB'siz trace tanisi kosulmadi: " + "; ".join(blockers))

    problems, detail = run_native_trace(video, log, env=env)

    assert not problems, (
        "PDB'SIZ TRACE TANISI BASARISIZ:\n  - " + "\n  - ".join(problems)
        + f"\n--- shutdown problems: {detail['shutdown_problems']}"
        + f"\n--- trace records: {detail['trace_records']}")
