# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""HDR tanisinin fail-closed, test-only ve urunden izole sozlesmesi."""
from pathlib import Path

from hdr_probe_contract import (
    CANDIDATE_PROFILE,
    CURRENT_PROFILE,
    HDR_CHILD_TIMEOUT_SECONDS,
    classify_input,
    hdr_probe_config,
    output_problems,
    parse_dxdiag_colorspace,
    report_problems,
)


ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "tests" / "run_hdr_acceptance.py"
CHILD = ROOT / "tests" / "native_hdr_probe_child.py"
MATRIX = ROOT / "docs" / "WINDOWS_ACCEPTANCE_MATRIX.md"


def read(path):
    return path.read_text(encoding="utf-8", errors="replace")


def test_probe_profiles_are_bounded_and_do_not_mutate_product_config():
    original = {"vo": "gpu", "hwdec": "auto-safe", "scale": "spline36"}

    current = hdr_probe_config(original, CURRENT_PROFILE)
    candidate = hdr_probe_config(original, CANDIDATE_PROFILE)

    assert original == {"vo": "gpu", "hwdec": "auto-safe",
                        "scale": "spline36"}
    assert current["vo"] == "gpu"
    assert candidate["vo"] == "gpu-next"
    assert candidate["gpu_api"] == "d3d11"
    assert candidate["gpu_context"] == "d3d11"
    assert candidate["target_colorspace_hint"] == "auto"
    assert candidate["target_colorspace_hint_mode"] == "target"
    assert 0 < HDR_CHILD_TIMEOUT_SECONDS <= 60


def test_hdr10_input_requires_pq_bt2020_and_ten_bit_pixels():
    assert classify_input({
        "primaries": "bt.2020", "gamma": "pq", "pixelformat": "p010",
        "max-cll": 1000, "max-fall": 400,
    }) == "hdr10"
    assert classify_input({
        "primaries": "bt.2020", "gamma": "pq", "pixelformat": "cuda",
        "hw-pixelformat": "p010",
    }) == "hdr10"
    assert classify_input({
        "primaries": "bt.2020", "gamma": "pq", "pixelformat": "nv12",
    }) == "invalid_hdr"
    assert classify_input({
        "primaries": "bt.709", "gamma": "bt.1886",
        "pixelformat": "yuv420p",
    }) == "sdr"


def test_hdr_output_requires_pq_bt2020_while_sdr_target_is_not_hdr_pass():
    assert output_problems(
        {"primaries": "bt.2020", "gamma": "pq", "pixelformat": "rgb10"},
        expected_hdr=True) == []
    assert output_problems(
        {"primaries": "bt.709", "gamma": "bt.1886",
         "pixelformat": "rgb8"}, expected_hdr=True)


def test_dxdiag_colorspace_parser_requires_explicit_active_value():
    assert parse_dxdiag_colorspace(
        "Display Color Space: DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020\n"
    ) == "DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020"
    assert parse_dxdiag_colorspace(
        "Display Color Space: DXGI_COLOR_SPACE_RGB_FULL_G22_NONE_P709\n"
    ) == "DXGI_COLOR_SPACE_RGB_FULL_G22_NONE_P709"
    assert parse_dxdiag_colorspace("HDR Support: Supported\n") == ""


def test_report_requires_exit_markers_shutdown_and_no_process_leak():
    good = {
        "profile": CANDIDATE_PROFILE,
        "exit_code": 0,
        "mark_done": True,
        "input_class": "hdr10",
        "input": {"primaries": "bt.2020", "gamma": "pq",
                  "pixelformat": "p010", "max-cll": 1000},
        "target": {"primaries": "bt.2020", "gamma": "pq",
                   "pixelformat": "rgb10"},
        "hwdec_current": "d3d11va",
        "stop_calls": 1,
        "terminate_calls": 1,
        "call_order": ["stop", "terminate"],
        "close_accepted": True,
        "cursor_restored": True,
        "captured": True,
        "leaked_processes": [],
        "stderr": "",
    }
    assert report_problems(good, expected_hdr=True) == []
    assert report_problems({**good, "mark_done": False}, expected_hdr=True)
    assert report_problems({**good, "leaked_processes": [123]},
                           expected_hdr=True)
    assert report_problems({**good, "close_accepted": False},
                           expected_hdr=True)
    assert report_problems({**good, "cursor_restored": False},
                           expected_hdr=True)


def test_runner_and_child_are_opt_in_and_product_config_stays_test_only():
    runner = read(RUNNER)
    child = read(CHILD)

    assert 'MLC_NATIVE_HDR_ACCEPTANCE") != "1"' in runner
    assert "MLC_HDR_TEST_VIDEO" in runner
    assert "HDR_CHILD_TIMEOUT_SECONDS" in runner
    assert "time.monotonic() + 20" in runner
    assert "CURRENT_PROFILE" in runner and "CANDIDATE_PROFILE" in runner
    assert "native_hdr_probe_child.py" in runner

    assert 'MLC_NATIVE_HDR_ACCEPTANCE") != "1"' in child
    assert "player_module.MPV_CONFIG = hdr_probe_config(" in child
    assert "mpv_player._get_property(name)" in child
    assert 'get_property(mpv_player, "video-params"' in child
    assert 'get_property(mpv_player, "video-target-params"' in child
    assert 'get_property(mpv_player, "hwdec-current"' in child
    assert "player.close()" in child
    assert "restore_cursor_position(initial_cursor)" in child
    assert "os._exit(exit_code)" in child


def test_p2_hdr_matrix_routes_to_probe_but_remains_blocked_until_native_run():
    matrix = read(MATRIX)
    section = matrix[matrix.index("## P2"):]
    assert "tests/run_hdr_acceptance.py" in section
    assert "video-target-params" in section
    assert "G2084_NONE_P2020" in section
    assert "| WIN-P2-01 |" in section and "| BLOCKED |" in section
