# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Tek komutluk ana pencere kabul runner sözleşmesi."""
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tests" / "run_main_window_acceptance.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("main_window_acceptance", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runner_is_opt_in_bounded_and_fail_closed():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'MLC_NATIVE_SMOKE' in source
    assert "1 <= args.repeat <= 5" in source
    assert "first_failed_cycle" in source
    assert "all_passed" in source
    assert "MARK_DONE main_window_acceptance" in source


def test_runner_defaults_to_three_clean_cycles():
    runner = load_runner()
    assert runner.parse_args([]).repeat == 3
    assert runner.parse_args(["--repeat", "2"]).repeat == 2


def test_physical_buttons_establishes_subtitle_off_precondition():
    source = (ROOT / "tests" / "native_physical_acceptance_child.py").read_text(
        encoding="utf-8")
    marker = "# --- CC ONCE olculur"
    block = source[source.index(marker):source.index("# --- Play / pause", source.index(marker))]
    assert "mpv.sub_visibility = False" in block
    assert "wait_for(lambda: bool(mpv.sub_visibility) is False" in block


def test_physical_resize_respects_snapped_playlist_boundary_policy():
    source = (ROOT / "tests" / "native_physical_acceptance_child.py").read_text(
        encoding="utf-8")
    marker = 'if name == "right":\n            expectations'
    assert marker in source
    assert 'expectations = {"right": 0, "left": 0}' in source
    assert 'expectations = {"right": delta[0], "top": delta[1]' in source
    assert 'expectations = {"right": delta[0], "bottom": delta[1]' in source
