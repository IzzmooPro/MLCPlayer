# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Fiziksel buttons kabulunun fail-closed onkosul regresyonlari.

Gercek MP4 tek playlist ogesi ve altyazi track'i olmadan kosuldugunda eski
harness once CC icin sahte urun FAIL'i yazdi, sonra "Sonraki" tiklamasinin
actigi modalda 600 saniyelik grup timeout'unu bekledi. Bu testler Qt, MPV veya
native SendInput baslatmadan o iki acigi kapatir.
"""
import os

from physical_buttons_contract import (
    BUTTONS_GROUP_TIMEOUT_SECONDS,
    FULLSCREEN_GROUP_TIMEOUT_SECONDS,
    MODAL_DISMISS_DELAY_MS,
    TIMELINE_GROUP_TIMEOUT_SECONDS,
    WINDOW_RESIZE_GROUP_TIMEOUT_SECONDS,
    arm_modal_dismissal,
    has_subtitle_track,
    playlist_step_available,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHILD = os.path.join(ROOT, "tests", "native_physical_acceptance_child.py")
RUNNER = os.path.join(ROOT, "tests", "run_physical_acceptance.py")


def read(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def buttons_source():
    source = read(CHILD)
    return source[source.index("def group_buttons("):
                  source.index("# ================= GRUP 2")]


def test_buttons_group_budget_is_three_minutes_or_less():
    assert 0 < BUTTONS_GROUP_TIMEOUT_SECONDS <= 180
    assert '("1", "buttons", BUTTONS_GROUP_TIMEOUT_SECONDS)' in read(RUNNER)


def test_selected_physical_package_has_bounded_group_budgets():
    source = read(RUNNER)
    expected = {
        "buttons": (BUTTONS_GROUP_TIMEOUT_SECONDS, 180),
        "timeline": (TIMELINE_GROUP_TIMEOUT_SECONDS, 300),
        "window_resize": (WINDOW_RESIZE_GROUP_TIMEOUT_SECONDS, 180),
        "fullscreen": (FULLSCREEN_GROUP_TIMEOUT_SECONDS, 120),
    }

    for name, (actual, maximum) in expected.items():
        assert 0 < actual <= maximum, (name, actual)
        constant = name.upper() + "_GROUP_TIMEOUT_SECONDS"
        assert f'"{name}", {constant})' in source


def test_subtitle_track_precondition_is_explicit_and_strict():
    assert has_subtitle_track([]) is False
    assert has_subtitle_track([{"type": "audio"}, {"type": "video"}]) is False
    assert has_subtitle_track([{"type": "sub"}]) is True
    assert has_subtitle_track([None, "sub", {"type": "sub"}]) is True


def test_cc_click_is_forbidden_when_subtitle_precondition_fails():
    source = buttons_source()

    guard = source.index("if not subtitle_tracks_ready:")
    blocked = source.index("BLOCKED: SUBTITLE_TRACK", guard)
    first_cc_click = source.index("physical_click(ready[0], ready[1]", guard)

    assert guard < blocked < first_cc_click


def test_single_item_playlist_has_no_next_or_previous_step():
    assert playlist_step_available(1, 0, 1) is False
    assert playlist_step_available(1, 0, -1) is False
    assert playlist_step_available(2, 0, 1) is True
    assert playlist_step_available(2, 1, -1) is True
    assert playlist_step_available(2, 1, 1) is False


def test_playlist_boundary_is_recorded_without_clicking():
    source = buttons_source()

    next_guard = source.index("if not next_available:")
    next_blocked = source.index("BLOCKED: PLAYLIST_NEXT_ITEM", next_guard)
    next_click = source.index("physical_click(ready[0], ready[1]", next_guard)
    assert next_guard < next_blocked < next_click


def test_modal_dismissal_is_armed_with_a_short_bound():
    calls = []
    callback = lambda: None

    delay = arm_modal_dismissal(
        lambda milliseconds, callback: calls.append((milliseconds, callback)),
        callback,
    )

    assert 0 < MODAL_DISMISS_DELAY_MS <= 1200
    assert delay == MODAL_DISMISS_DELAY_MS
    assert calls == [(MODAL_DISMISS_DELAY_MS, callback)]
    assert buttons_source().count("arm_modal_dismissal(") >= 2
