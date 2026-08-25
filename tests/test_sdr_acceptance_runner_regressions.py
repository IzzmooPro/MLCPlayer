# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Tek senaryolu SDR native kabul kosucusunun fail-closed sozlesmesi."""
import importlib.util
import os
import sys

import pytest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTRACT_PATH = os.path.join(ROOT, "tests", "sdr_probe_contract.py")


@pytest.fixture(scope="module")
def contract():
    spec = importlib.util.spec_from_file_location(
        "mlc_sdr_probe_contract", CONTRACT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def passing_report():
    return {
        "profile": "current_product",
        "exit_code": 0,
        "mark_done": True,
        "captured": True,
        "input_class": "sdr_bt709",
        "input": {"primaries": "bt.709", "gamma": "bt.1886"},
        "target": {"primaries": "bt.709", "gamma": "bt.1886"},
        "duration": 3.0,
        "max_time_pos": 1.2,
        "frame_drops": {
            "decoder-frame-drop-count": 0,
            "frame-drop-count": 0,
        },
        "stop_calls": 1,
        "terminate_calls": 1,
        "call_order": ["stop", "terminate"],
        "close_accepted": True,
        "cursor_restored": True,
        "leaked_processes": [],
        "stderr": "",
        "timed_out": False,
    }


def test_exact_passing_report_has_no_problems(contract):
    assert contract.report_problems(passing_report()) == []


@pytest.mark.parametrize("field,value", [
    ("exit_code", 1),
    ("mark_done", False),
    ("captured", False),
    ("input_class", "hdr10"),
    ("duration", 0.0),
    ("max_time_pos", 0.0),
    ("call_order", ["terminate", "stop"]),
    ("close_accepted", False),
    ("cursor_restored", False),
    ("timed_out", True),
])
def test_each_required_gate_fails_closed(contract, field, value):
    report = passing_report()
    report[field] = value
    assert contract.report_problems(report)


def test_frame_drop_and_process_leak_fail_closed(contract):
    report = passing_report()
    report["frame_drops"]["frame-drop-count"] = 1
    report["leaked_processes"] = [1234]
    problems = contract.report_problems(report)
    assert any("frame drop" in item for item in problems)
    assert any("surec sizintisi" in item for item in problems)


def test_missing_drop_counter_is_not_silently_zero(contract):
    report = passing_report()
    report["frame_drops"]["frame-drop-count"] = None
    assert contract.report_problems(report)


def test_complete_known_luajit_trace_is_diagnostic_not_a_crash(contract):
    report = passing_report()
    report["stderr"] = (
        "Windows fatal exception: code 0xe24c4a02\n\n"
        "Thread 0x1234 (most recent call first):\n"
        "  File \"mpv.py\", line 1 in _loop\n"
        "Current thread's C stack trace (most recent call first):\n"
        "  <cannot get C stack on this system>\n")
    assert contract.report_problems(report) == []


def test_truncated_luajit_trace_still_fails(contract):
    report = passing_report()
    report["stderr"] = "Windows fatal exception: code 0xe24c4a02\n"
    assert contract.report_problems(report)


def test_sdr_display_contract_is_exact(contract):
    assert contract.display_problems(
        contract.SDR_COLORSPACE, contract.SDR_COLORSPACE) == []
    assert contract.display_problems("", contract.SDR_COLORSPACE)
    assert contract.display_problems(
        "DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020",
        "DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020")


def test_timeout_never_exceeds_format_plan_limit(contract):
    assert 0 < contract.SDR_CHILD_TIMEOUT_SECONDS <= 60


def test_diagnostic_profile_is_test_only_and_does_not_mutate_product_config(
        contract):
    original = {"video_latency_hacks": "yes", "vo": "gpu"}
    current = contract.sdr_probe_config(original, contract.CURRENT_PROFILE)
    diagnostic = contract.sdr_probe_config(
        original, contract.NO_LATENCY_HACKS_PROFILE)
    assert original == {"video_latency_hacks": "yes", "vo": "gpu"}
    assert current["video_latency_hacks"] == "yes"
    assert diagnostic["video_latency_hacks"] == "no"
    assert diagnostic["vo"] == "gpu"


def test_unknown_profile_is_rejected(contract):
    with pytest.raises(ValueError):
        contract.sdr_probe_config({}, "unknown")


def test_product_uses_mpv_safe_default_for_video_latency_hacks():
    from app.config import MPV_CONFIG

    assert "video_latency_hacks" not in MPV_CONFIG


@pytest.mark.parametrize("value,expected", [
    ("", 0.0),
    ("0", 0.0),
    ("10", 10.0),
    ("15", 15.0),
])
def test_visual_hold_is_bounded(contract, value, expected):
    assert contract.visual_hold_seconds(value) == expected


@pytest.mark.parametrize("value", ["-1", "15.1", "nan", "bad"])
def test_visual_hold_rejects_unsafe_values(contract, value):
    with pytest.raises(ValueError):
        contract.visual_hold_seconds(value)
