# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Native matrix runner'ın güvenilirlik regresyon testleri.

Bu testler ürün koduna (app/) dokunmaz ve hiçbir native MPV/Qt süreci
başlatmaz; yalnızca tests/run_native_overlay_matrix.py içindeki karar
mantığını ölçer.
"""
import importlib.util
import os

import pytest

RUNNER_PATH = os.path.join(os.path.dirname(__file__), "run_native_overlay_matrix.py")
SMOKE_CHILD_PATH = os.path.join(
    os.path.dirname(__file__), "native_overlay_smoke_child.py")


def load_runner():
    spec = importlib.util.spec_from_file_location("mlc_native_matrix_runner", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_runner()


def make_row(**overrides):
    row = {
        "name": "case",
        "preview": "1",
        "video": True,
        "focus": True,
        "variant": "none",
        "exit_code": 0,
        "hex": "0x00000000",
        "last_marker": "MARK_DONE",
        "results_seen": True,
        "done_seen": True,
        "elapsed_s": 10.0,
        "leaked_children": [],
        "timed_out": False,
        "python_exception": False,
        "cleanup_error": None,
        "behavior_failures": [],
        "stdout": "",
        "stderr": "",
    }
    row.update(overrides)
    return row


# --- 1. Başarısızlık exit code'a yansımalı ---

@pytest.mark.parametrize("overrides", [
    {"exit_code": 3221226505, "hex": "0xC0000409"},
    {"timed_out": True, "exit_code": None},
    {"python_exception": True},
    {"results_seen": False},
    {"done_seen": False},
    {"leaked_children": [4242]},
])
def test_failure_conditions_are_detected(overrides):
    assert runner.failure_reasons(make_row(**overrides))


def test_behavior_failures_are_detected_and_named():
    reasons = runner.failure_reasons(make_row(
        behavior_failures=["overlay_not_hidden_on_deactivate"]))
    assert "behavior:overlay_not_hidden_on_deactivate" in reasons


def test_clean_row_has_no_failure_reasons():
    assert runner.failure_reasons(make_row()) == []


def test_matrix_exit_code_is_zero_when_all_rows_clean():
    assert runner.matrix_exit_code([make_row(), make_row()]) == 0


def test_matrix_exit_code_is_non_zero_when_any_row_fails():
    rows = [make_row(), make_row(exit_code=3221226505, hex="0xC0000409")]
    assert runner.matrix_exit_code(rows) != 0


def test_main_returns_non_zero_when_a_case_fails(monkeypatch):
    """Runner bütün satırları raporlasa bile başarısızlıkta 0 dönmemeli."""
    monkeypatch.setenv("MLC_NATIVE_SMOKE", "1")
    monkeypatch.setattr(
        runner, "run_case",
        lambda case, project_root, timeout: make_row(
            name=case["name"], exit_code=3221226505, hex="0xC0000409",
            last_marker="MARK_ACTIVE_READ", results_seen=False, done_seen=False),
    )
    monkeypatch.setattr(
        "sys.argv",
        ["run_native_overlay_matrix.py", "--only", "default_cinematic_novideo_nofocus"],
    )
    assert runner.main() != 0


def test_main_returns_zero_when_all_cases_pass(monkeypatch):
    monkeypatch.setenv("MLC_NATIVE_SMOKE", "1")
    monkeypatch.setattr(
        runner, "run_case",
        lambda case, project_root, timeout: make_row(name=case["name"]),
    )
    monkeypatch.setattr(
        "sys.argv",
        ["run_native_overlay_matrix.py", "--only", "default_cinematic_novideo_nofocus"],
    )
    assert runner.main() == 0


def test_normal_run_does_not_enable_force_pyexc_demo(monkeypatch):
    """Kontrollü PYEXC gösterimi normal matrix koşumuna sızmamalı."""
    monkeypatch.setenv("MLC_NATIVE_FORCE_PYEXC", "1")
    captured = {}

    def fake_run(argv, env=None, **kwargs):
        captured["env"] = env
        raise AssertionError("stop-before-launch")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    case = {"name": "c", "preview": "1", "video": "", "focus": False}
    with pytest.raises(AssertionError):
        runner.run_case(case, os.path.dirname(os.path.dirname(__file__)), 5)
    assert captured["env"].get("MLC_NATIVE_FORCE_PYEXC") in (None, "0")


# --- 2. Cleanup yalnızca bu koşumun PID'ini hedeflemeli ---

def test_parse_focus_child_pid_reads_marker_line():
    out = "MARK_SHOWN t=0.15\nMARK_FOCUS_CHILD_STARTED t=5.68 pid=4404\nRESULTS: x=1\n"
    assert runner.parse_focus_child_pid(out) == 4404


def test_parse_focus_child_pid_returns_none_for_synthetic_mode():
    out = "MARK_FOCUS_CHILD_STARTED t=5.65 mode=SYNTHETIC pid=self\n"
    assert runner.parse_focus_child_pid(out) is None


def test_parse_focus_child_pid_returns_none_when_marker_absent():
    assert runner.parse_focus_child_pid("MARK_SHOWN t=0.1\nSKIP_FOCUS_HANDOFF\n") is None


def test_cleanup_kills_only_the_tracked_pid(monkeypatch):
    killed = []
    monkeypatch.setattr(runner, "is_process_running", lambda pid: True)
    monkeypatch.setattr(runner, "kill_pid", lambda pid: killed.append(pid))
    result = runner.cleanup_tracked_child(4404)
    assert killed == [4404]
    assert result["leaked"] == [4404]


def test_cleanup_does_nothing_when_tracked_pid_already_exited(monkeypatch):
    killed = []
    monkeypatch.setattr(runner, "is_process_running", lambda pid: False)
    monkeypatch.setattr(runner, "kill_pid", lambda pid: killed.append(pid))
    result = runner.cleanup_tracked_child(4404)
    assert killed == []
    assert result["leaked"] == []


def test_cleanup_without_pid_never_scans_or_kills(monkeypatch):
    """PID alınamadıysa geniş tarama ile süreç öldürülmemeli."""
    def explode(*args, **kwargs):
        raise AssertionError("geniş process taraması yapılmamalı")

    monkeypatch.setattr(runner, "is_process_running", explode)
    monkeypatch.setattr(runner, "kill_pid", explode)
    result = runner.cleanup_tracked_child(None)
    assert result["leaked"] == []
    assert result["cleanup_error"] is None


def test_runner_has_no_broad_process_scan():
    """Runner artık tüm native_focus_child süreçlerini taramamalı."""
    with open(RUNNER_PATH, encoding="utf-8") as handle:
        source = handle.read()
    assert "stray_focus_children" not in source
    assert "Win32_Process" not in source


def test_base_matrix_default_never_opens_visible_classic_ui():
    names = [case["name"] for case in runner.base_matrix("video.mkv")]
    assert names == [
        "default_cinematic_novideo_nofocus",
        "default_cinematic_video_nofocus",
        "default_cinematic_novideo_focus",
        "default_cinematic_video_focus",
        "synthetic_cinematic_novideo",
        "synthetic_cinematic_video",
    ]


def test_matrix_can_no_longer_add_a_visible_classic_case():
    """Ürün kararı: eski kabuk hiçbir matris senaryosunda açılmaz."""
    import inspect

    assert "include_classic" not in inspect.signature(
        runner.base_matrix).parameters
    cases = runner.base_matrix("video.mkv")
    names = [case["name"] for case in cases]
    assert "diagnostic_classic_video_focus" not in names
    assert not [case for case in cases if case.get("ui") == "classic"]
    assert len(cases) == 6, f"sinematik matris 6 senaryo olmalı: {names}"


def test_cinematic_cases_do_not_set_the_classic_diagnostic_flag(monkeypatch):
    monkeypatch.setenv("MLCPLAYER_CLASSIC_UI", "1")
    captured = {}

    def fake_run(argv, env=None, **kwargs):
        captured["env"] = env
        raise AssertionError("stop-before-launch")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    case = runner.base_matrix("")[0]
    with pytest.raises(AssertionError):
        runner.run_case(case, os.path.dirname(os.path.dirname(__file__)), 5)
    assert "MLCPLAYER_CLASSIC_UI" not in captured["env"]
    assert "MLCPLAYER_OVERLAY_PREVIEW" not in captured["env"]


def test_every_case_clears_the_classic_env(monkeypatch):
    """Kullanıcı ortamında legacy anahtar olsa bile matris onu temizler."""
    monkeypatch.setenv("MLCPLAYER_CLASSIC_UI", "1")
    root = os.path.dirname(os.path.dirname(__file__))

    for case in runner.base_matrix("v.mkv"):
        captured = {}

        def fake_run(argv, env=None, **kwargs):
            captured["env"] = env
            raise AssertionError("stop-before-launch")

        monkeypatch.setattr(runner.subprocess, "run", fake_run)
        with pytest.raises(AssertionError):
            runner.run_case(case, root, 5)
        assert "MLCPLAYER_CLASSIC_UI" not in captured["env"], (
            f"{case['name']} klasik kabuğu açabiliyor")


def test_native_smoke_child_never_opens_the_classic_shell():
    """Child hiçbir yerde klasik kabuğu açan env'i AYARLAMAMALI."""
    with open(SMOKE_CHILD_PATH, encoding="utf-8") as handle:
        source = handle.read()
    assert 'env["MLCPLAYER_CLASSIC_UI"] = "1"' not in source
    assert 'os.environ["MLCPLAYER_CLASSIC_UI"] = "1"' not in source


def test_native_smoke_child_uses_the_canonical_product_shutdown_path():
    """MPV, ürün timer/observer temizliğinden önce elle sonlandırılmamalı."""
    with open(SMOKE_CHILD_PATH, encoding="utf-8") as handle:
        source = handle.read()

    shutdown = source.split("def step_shutdown():", 1)[1].split(
        "\ndef step_", 1)[0]
    assert "player.close()" in shutdown
    assert "player.mpv_player.stop()" not in shutdown
    assert "player.mpv_player.terminate()" not in shutdown
    assert "QTimer.singleShot(300, step_close)" not in shutdown
    assert shutdown.index("player.close()") < shutdown.index('mark("MARK_STOP")')
    assert shutdown.index('mark("MARK_STOP")') < shutdown.index(
        'mark("MARK_TERMINATE")')
    assert shutdown.index('mark("MARK_TERMINATE")') < shutdown.index(
        'mark("MARK_CLOSE")')


def test_results_line_is_parsed_into_typed_fields():
    stdout = (
        "MARK_BUTTONS t=1.0\n"
        "RESULTS: ui=cinematic video=True focus_handoff=True "
        "overlay_hidden_on_deactivate=False "
        "overlay_visible_after_return=True\n"
        "MARK_DONE t=2.0\n"
    )
    assert runner.parse_results_fields(stdout) == {
        "ui": "cinematic",
        "video": True,
        "focus_handoff": True,
        "overlay_hidden_on_deactivate": False,
        "overlay_visible_after_return": True,
    }


@pytest.mark.parametrize("fields, expected_reason", [
    ({"ui": "cinematic", "overlay_hidden_on_deactivate": False,
      "overlay_visible_after_return": True},
     "overlay_not_hidden_on_deactivate"),
    ({"ui": "cinematic", "overlay_hidden_on_deactivate": True,
      "overlay_visible_after_return": False},
     "overlay_not_restored_after_return"),
])
def test_cinematic_focus_behavior_must_hide_and_restore(fields, expected_reason):
    case = {"name": "focus", "ui": "cinematic", "focus": True,
            "synthetic": True}
    assert expected_reason in runner.evaluate_behavior(case, fields)


def test_diagnostic_classic_result_must_really_be_classic():
    case = {"name": "classic", "ui": "classic", "focus": True}
    reasons = runner.evaluate_behavior(case, {"ui": "cinematic"})
    assert "ui_mismatch_expected_classic_got_cinematic" in reasons


def test_clean_cinematic_focus_behavior_has_no_failure():
    case = {"name": "focus", "ui": "cinematic", "focus": True,
            "synthetic": False}
    fields = {
        "ui": "cinematic",
        "focus_foreground_confirmed": True,
        "overlay_hidden_on_deactivate": True,
        "overlay_visible_after_return": True,
    }
    assert runner.evaluate_behavior(case, fields) == []


def test_real_focus_case_requires_native_foreground_confirmation():
    case = {"name": "focus", "ui": "cinematic", "focus": True,
            "synthetic": False}
    fields = {
        "ui": "cinematic",
        "focus_foreground_confirmed": False,
        "overlay_hidden_on_deactivate": True,
        "overlay_visible_after_return": True,
    }
    assert "focus_child_not_foreground" in runner.evaluate_behavior(case, fields)
