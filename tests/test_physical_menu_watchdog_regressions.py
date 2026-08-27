# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Nested QMenu kapanisinin bounded ve fail-closed davranis regresyonlari."""
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
CHILD = TESTS / "native_physical_acceptance_child.py"
sys.path.insert(0, str(TESTS))
from physical_menu_watchdog import popup_completion_decision  # noqa: E402


PROBE = textwrap.dedent(
    r"""
    import os
    import sys
    import time

    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    sys.path.insert(0, os.environ["MLC_TESTS_DIR"])

    from PyQt6.QtCore import QPoint, QTimer
    from PyQt6.QtWidgets import QApplication, QMenu
    from physical_menu_watchdog import PopupChainWatchdog

    mode = sys.argv[1]
    app = QApplication(sys.argv)
    root = QMenu("root")
    middle = root.addMenu("middle")
    leaf = middle.addMenu("leaf")
    leaf.addAction("target")
    menus = [root, middle, leaf]
    state = {"escapes": 0, "close_calls": 0, "closed": None, "forced": None,
             "timeout": 0, "markers": []}

    def active_popup():
        return next((menu for menu in reversed(menus) if menu.isVisible()), None)

    def send_escape():
        state["escapes"] += 1
        if mode == "escape":
            popup = active_popup()
            if popup is not None:
                popup.hide()

    def close_visible():
        state["close_calls"] += 1
        count = 0
        for menu in reversed(menus):
            if menu.isVisible():
                count += 1
                menu.close()
        return count

    def marker(name, **fields):
        state["markers"].append(name)
        print("PROBE_PHASE " + name + " " +
              " ".join(f"{key}={value}" for key, value in fields.items()),
              flush=True)

    watchdog = PopupChainWatchdog(
        active_popup=active_popup,
        send_escape=send_escape,
        close_visible=close_visible,
        marker=marker,
        timeout_ms=80 if mode == "fallback" else (60 if mode == "cancel" else 1000),
        escape_interval_ms=20,
        max_escapes=4 if mode == "escape" else 2,
    )

    def completed(closed, forced):
        state["closed"] = closed
        state["forced"] = forced
        print(f"PROBE_COMPLETE closed={closed} forced={forced}", flush=True)

    def open_chain():
        middle.popup(QPoint(20, 20))
        leaf.popup(QPoint(40, 40))
        if mode == "escape":
            watchdog.dismiss(completed)

    if mode == "cancel":
        watchdog.arm(
            lambda: state.__setitem__("timeout", state["timeout"] + 1),
            completed)
        watchdog.cancel()
        root.popup(QPoint(0, 0))
        deadline = time.monotonic() + 0.25
        while time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.005)
        visible = root.isVisible()
        print(f"PROBE_CANCEL visible={visible} escapes={state['escapes']} "
              f"close_calls={state['close_calls']} timeout={state['timeout']} "
              f"closed={state['closed']}", flush=True)
        root.close()
        raise SystemExit(0 if visible and state["escapes"] == 0 and
                         state["close_calls"] == 0 and state["timeout"] == 0
                         and state["closed"] is None else 4)

    watchdog.arm(lambda: state.__setitem__("timeout", state["timeout"] + 1),
                 completed)
    QTimer.singleShot(0, open_chain)
    root.exec(QPoint(0, 0))
    deadline = time.monotonic() + 1.0
    while state["closed"] is None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    print(f"PROBE_RETURN mode={mode} escapes={state['escapes']} "
          f"timeout={state['timeout']} closed={state['closed']} "
          f"forced={state['forced']}", flush=True)
    raise SystemExit(0 if state["closed"] is True else 3)
    """
)


def run_probe(tmp_path, mode):
    probe = tmp_path / "popup_watchdog_probe.py"
    probe.write_text(PROBE, encoding="utf-8")
    env = dict(os.environ)
    env["MLC_TESTS_DIR"] = str(TESTS)
    return subprocess.run(
        [sys.executable, str(probe), mode], cwd=ROOT, env=env,
        capture_output=True, text=True, timeout=10)


def test_three_level_exec_unwinds_with_bounded_physical_escapes(tmp_path):
    completed = run_probe(tmp_path, "escape")

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PROBE_COMPLETE closed=True forced=False" in completed.stdout
    assert "PROBE_RETURN mode=escape escapes=3 timeout=0 closed=True forced=False" in completed.stdout


def test_watchdog_forces_cleanup_but_reports_fail_closed(tmp_path):
    completed = run_probe(tmp_path, "fallback")

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PROBE_COMPLETE closed=True forced=True" in completed.stdout
    assert "PROBE_RETURN mode=fallback escapes=2 timeout=1 closed=True forced=True" in completed.stdout
    assert "PROBE_PHASE popup_cleanup_forced" in completed.stdout


def test_cancelled_watchdog_cannot_touch_a_later_popup(tmp_path):
    completed = run_probe(tmp_path, "cancel")

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert ("PROBE_CANCEL visible=True escapes=0 close_calls=0 timeout=0 "
            "closed=None") in completed.stdout


@pytest.mark.parametrize("values, expected_reason", [
    ({"forced": True}, "popup_chain_not_closed"),
    ({"timed_out": True}, "menu_sequence_timeout"),
    ({"closed": False}, "popup_chain_not_closed"),
    ({"root_closed": False}, "root_popup_not_closed"),
])
def test_popup_completion_failures_never_deliver(values, expected_reason):
    inputs = {"pending": ("click", "physical_action_click", True),
              "timed_out": False, "closed": True, "forced": False,
              "root_closed": True}
    inputs.update(values)

    assert popup_completion_decision(**inputs) == {
        "reason": expected_reason, "delivered": False, "checked": False}


@pytest.mark.parametrize("pending", [
    ("click", "physical_action_click", False),
    ("inspect", "checked_readback", True),
])
def test_popup_completion_delivers_only_closed_click_or_inspect(pending):
    assert popup_completion_decision(
        pending=pending, timed_out=False, closed=True, forced=False,
        root_closed=True) == {
            "reason": pending[1], "delivered": True,
            "checked": bool(pending[2])}


def test_physical_menu_arms_watchdog_before_risky_right_click():
    source = CHILD.read_text(encoding="utf-8", errors="replace")
    start = source.index("def physical_menu_action(")
    end = source.index("\ndef physical_drag(", start)
    body = source[start:end]

    assert body.index("watchdog.arm(") < body.index(
        "mouse_button(True, right=True)")
    assert 'phase("target_click_sent")' in body
    assert 'phase("checked_read"' in body
    assert 'phase("popup_cleanup_complete"' in body
    assert "root_popup_closed()" in body
    assert "popup_completion_decision(" in body
    assert 'delivered=decision["delivered"]' in body
    assert "watchdog.dismiss()" in body


def test_physical_menu_watchdog_does_not_bypass_product_selection():
    source = CHILD.read_text(encoding="utf-8", errors="replace")
    start = source.index("def physical_menu_action(")
    end = source.index("\ndef physical_drag(", start)
    body = source[start:end]

    for forbidden in (".trigger(", "select_audio_track(",
                      "select_subtitle_language(", ".aid =", ".sid ="):
        assert forbidden not in body

    failures_start = source.index("PRODUCT_MENU_FAILURES = {")
    failures_end = source.index("\n}\n", failures_start)
    product_failures = source[failures_start:failures_end]
    assert "menu_sequence_timeout" not in product_failures
    assert "popup_chain_not_closed" not in product_failures
    assert "root_popup_not_closed" not in product_failures
