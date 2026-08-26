# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Fiziksel ses/altyazi parcasi degistirme kabul sozlesmesi.

Bu testler Qt/MPV veya native pencere baslatmaz. Yeni ``tracks`` grubunun
fail-closed kayit, dinamik track kimligi ve gercek menu girdisi sinirlarini
kaynak sozlesmesi olarak korur.
"""
from pathlib import Path

from physical_tracks_contract import (
    StableSelection,
    alternate_track_id,
    fixture_block_code,
    fixture_problems,
    normalise_track_id,
    selected_track_matches,
    track_snapshot,
    unique_target_index,
)


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tests" / "run_physical_acceptance.py"
CHILD = ROOT / "tests" / "native_physical_acceptance_child.py"


def source(path):
    return path.read_text(encoding="utf-8", errors="replace")


def function_body(text, name, next_name):
    start = text.index(f"def {name}(")
    end = text.index(f"\ndef {next_name}(", start)
    return text[start:end]


def test_tracks_group_is_registered_and_dispatched():
    runner = source(RUNNER)
    child = source(CHILD)

    assert '("13", "tracks",' in runner
    assert 'elif GROUP == "tracks":' in child
    assert "group_tracks()" in child


def test_tracks_group_requires_two_real_audio_and_subtitle_tracks():
    child = source(CHILD)
    body = function_body(child, "group_tracks", "group_zorder")

    assert 'len(audio_tracks) < 2' in body
    assert 'len(subtitle_tracks) < 2' in body
    assert "_stable_track_inventory" in body
    assert "fixture_block_code(" in body
    assert "MULTI_TRACK_MEDIA_REQUIRED" in body


def test_tracks_group_uses_dynamic_ids_and_physical_menu_input():
    child = source(CHILD)
    body = function_body(child, "group_tracks", "group_zorder")

    assert 'inventory["audio"]["current"]' in body
    assert "alternate_track_id(" in body
    assert "physical_menu_action(" in body
    assert "PLAYER.select_audio_track(" not in body
    assert "PLAYER.select_subtitle_language(" not in body
    assert "mpv.aid =" not in body
    assert "mpv.sid =" not in body

    helper = function_body(child, "physical_menu_action", "physical_drag")
    assert ".trigger(" not in helper
    assert "select_audio_track(" not in helper
    assert "select_subtitle_language(" not in helper
    assert ".aid =" not in helper
    assert ".sid =" not in helper


def test_tracks_group_reads_back_property_selected_flag_and_menu_check():
    child = source(CHILD)
    body = function_body(child, "group_tracks", "group_zorder")

    assert "_wait_track_selection(" in body
    assert "_checked_after_reopen(" in body
    assert "action.isChecked()" in child
    assert "mpv.sub_visibility" in body
    assert 'record("audio_track_switch"' in body
    assert 'record("subtitle_track_switch_1"' in body
    assert 'record("subtitle_track_switch_2"' in body
    assert "subtitle_s1 != subtitle_s2" in body
    assert "subtitle_s2 != subtitle_s1" in body
    assert 'getattr(mpv, "current_ao", None)' in body


def test_track_ids_are_dynamic_and_canonical():
    assert normalise_track_id(42) == 42
    assert normalise_track_id("42") == 42
    assert normalise_track_id(None) is None
    assert normalise_track_id(False) is None
    assert normalise_track_id("auto") is None

    snapshot = track_snapshot(
        [{"type": "audio", "id": 7, "selected": True},
         {"type": "audio", "id": 42, "selected": False}],
        "audio", "7")
    assert alternate_track_id(snapshot) == 42
    assert isinstance(hash(snapshot["signature"]), int)
    assert unique_target_index([7, 42], 42) == 1
    assert unique_target_index([7, 7], 7) is None


def test_fixture_contract_fails_closed_for_ids_and_selected_state():
    good_audio = track_snapshot(
        [{"type": "audio", "id": 7, "selected": True},
         {"type": "audio", "id": 42}], "audio", 7)
    good_sub = track_snapshot(
        [{"type": "sub", "id": 3, "selected": True},
         {"type": "sub", "id": 99}], "sub", 3, True)
    assert fixture_problems(good_audio, good_sub, 1, 10.0) == []

    duplicate = track_snapshot(
        [{"type": "audio", "id": 7, "selected": True},
         {"type": "audio", "id": "7"}], "audio", 7)
    assert "audio_duplicate_id" in fixture_problems(
        duplicate, good_sub, 1, 10.0)

    none_selected = track_snapshot(
        [{"type": "audio", "id": 7},
         {"type": "audio", "id": 42}], "audio", 7)
    assert "audio_selected_mismatch" in fixture_problems(
        none_selected, good_sub, 1, 10.0)

    one_audio = track_snapshot(
        [{"type": "audio", "id": 7, "selected": True}], "audio", 7)
    assert "audio_needs_two_tracks" in fixture_problems(
        one_audio, good_sub, 1, 10.0)
    one_sub = track_snapshot(
        [{"type": "sub", "id": 3, "selected": True}], "sub", 3, True)
    assert "sub_needs_two_tracks" in fixture_problems(
        good_audio, one_sub, 1, 10.0)
    invalid = track_snapshot(
        [{"type": "audio", "id": None, "selected": True},
         {"type": "audio", "id": 42}], "audio", 42)
    assert "audio_invalid_id" in fixture_problems(
        invalid, good_sub, 1, 10.0)
    missing_current = track_snapshot(
        [{"type": "audio", "id": 7, "selected": True},
         {"type": "audio", "id": 42}], "audio", 99)
    assert "audio_current_missing" in fixture_problems(
        missing_current, good_sub, 1, 10.0)
    multiple = track_snapshot(
        [{"type": "audio", "id": 7, "selected": True},
         {"type": "audio", "id": 42, "selected": True}], "audio", 7)
    assert "audio_selected_mismatch" in fixture_problems(
        multiple, good_sub, 1, 10.0)


def test_selection_requires_property_exact_selected_and_visibility():
    tracks = [{"type": "sub", "id": 3},
              {"type": "sub", "id": 99, "selected": True}]
    assert selected_track_matches(
        track_snapshot(tracks, "sub", 99, True), 99, True)
    assert not selected_track_matches(
        track_snapshot(tracks, "sub", 3, True), 99, True)
    assert not selected_track_matches(
        track_snapshot(tracks, "sub", 99, False), 99, True)


def test_selection_must_be_stable_for_three_identical_samples():
    snapshot = track_snapshot(
        [{"type": "audio", "id": 7},
         {"type": "audio", "id": 42, "selected": True}],
        "audio", 42)
    stable = StableSelection(42, required=3, expected_ids=(7, 42))
    assert stable.observe(snapshot) is False

    dropped = track_snapshot(
        [{"type": "audio", "id": 42, "selected": True}], "audio", 42)
    assert stable.observe(dropped) is False
    assert stable.observe(snapshot) is False
    assert stable.observe(snapshot) is False
    assert stable.observe(snapshot) is True

    mismatch = track_snapshot(
        [{"type": "audio", "id": 7, "selected": True},
         {"type": "audio", "id": 42}], "audio", 7)
    assert stable.observe(mismatch) is False
    assert stable.observe(snapshot) is False


def test_menu_failure_classification_separates_product_from_harness():
    child = source(CHILD)
    assert '"root_action_missing_or_ambiguous"' in child
    assert '"target_action_missing_or_ambiguous"' in child
    assert "return False if reason in PRODUCT_MENU_FAILURES else None" in child


def test_fixture_block_reason_preserves_the_root_cause():
    assert fixture_block_code(["current_ao=wasapi"]) == "AUDIO_ISOLATION"
    assert fixture_block_code(
        ["TRACK_INVENTORY_UNSTABLE"]) == "TRACK_INVENTORY_UNSTABLE"
    assert fixture_block_code(
        ["MULTI_TRACK_MEDIA_REQUIRED"]) == "MULTI_TRACK_MEDIA_REQUIRED"
    assert fixture_block_code(
        ["audio_duplicate_id"]) == "TRACK_ID_SELECTED_CONTRACT"
    assert fixture_block_code(["duration_not_positive"]) == "MEDIA_FIXTURE"
