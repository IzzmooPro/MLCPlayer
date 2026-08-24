# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dar WIN-P0-04 fiziksel olcum grubunun kaynak sozlesmesi."""
import os

from physical_buttons_contract import PLAYBACK_SEEK_GROUP_TIMEOUT_SECONDS


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHILD = os.path.join(ROOT, "tests", "native_physical_acceptance_child.py")
RUNNER = os.path.join(ROOT, "tests", "run_physical_acceptance.py")
MATRIX = os.path.join(ROOT, "docs", "WINDOWS_ACCEPTANCE_MATRIX.md")


def read(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def playback_seek_source():
    source = read(CHILD)
    return source[source.index("def group_playback_seek("):
                  source.index("def group_timeline(")]


def test_playback_seek_group_has_a_90_second_hard_bound():
    assert PLAYBACK_SEEK_GROUP_TIMEOUT_SECONDS == 90
    runner = read(RUNNER)
    assert "PLAYBACK_SEEK_GROUP_TIMEOUT_SECONDS" in runner
    assert '("12", "playback_seek", PLAYBACK_SEEK_GROUP_TIMEOUT_SECONDS)' in runner


def test_playback_seek_group_is_dispatched_by_the_child():
    source = read(CHILD)
    assert 'elif GROUP == "playback_seek":' in source
    assert "group_playback_seek()" in source


def test_playback_seek_scope_is_narrow_and_reads_real_state():
    block = playback_seek_source()

    assert "overlayPlayPause" in block
    assert block.count("physical_click(") >= 3
    assert "mpv.pause" in block
    assert "PLAYER.is_paused" in block
    assert "mpv.time_pos" in block
    assert "(0.10, 0.50, 0.90)" in block
    assert "threaded_drag(" in block
    assert "input_contract_problems(" in block
    assert "slider_value_tolerance(" in block
    assert "seek_time_tolerance(" in block

    for unrelated in (
            "overlaySubtitles", "overlayVolume", "overlaySettings",
            "overlayPlaylist", "overlayFullscreen"):
        assert unrelated not in block


def test_win_p0_04_matrix_routes_to_the_narrow_group_only():
    matrix = read(MATRIX)
    section = matrix[matrix.index("### WIN-P0-04"):
                     matrix.index("### WIN-P0-05")]
    assert "run_physical_acceptance.py playback_seek" in section
    assert "buttons,timeline" not in section
    assert "NOT_RUN" in section
