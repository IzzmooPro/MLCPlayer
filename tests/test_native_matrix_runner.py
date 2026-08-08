"""Native matrix runner'ın güvenilirlik regresyon testleri.

Bu testler ürün koduna (app/) dokunmaz ve hiçbir native MPV/Qt süreci
başlatmaz; yalnızca tests/run_native_overlay_matrix.py içindeki karar
mantığını ölçer.
"""
import importlib.util
import os

import pytest

RUNNER_PATH = os.path.join(os.path.dirname(__file__), "run_native_overlay_matrix.py")


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
        ["run_native_overlay_matrix.py", "--only", "preview_on_novideo_nofocus"],
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
        ["run_native_overlay_matrix.py", "--only", "preview_on_novideo_nofocus"],
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
