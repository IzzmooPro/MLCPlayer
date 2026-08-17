# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""`zorder_after_resize` degerlendirmesinin regresyonlari.

Eski satir `PLAYER.resize()` ile PROGRAMATIK boyut degistiriyor, sonucu
yalnizca metin olarak basiyor ve karari goz kontrolune birakip BLOCKED
kaliyordu. Karar artik saf `zorder_after_resize_problems()` ile verilir;
bu testler bozuk yerlesimlerin gercekten yakalandigini kilitler.
"""
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest

from physical_layout import resize_problems, zorder_after_resize_problems

# Saglikli anlik goruntu: 1270x790 pencere, 48 px baslik, 360 px playlist.
GOOD = {
    "client": (300, 200, 1270, 790),
    "title_bar": (300, 200, 1270, 48),
    "media_container": (300, 248, 1270, 742),
    "video_frame": (300, 248, 910, 742),
    "playlist_host": (1210, 248, 360, 742),
    "playlist_panel": (1210, 248, 360, 742),
    "control_overlay": (300, 880, 910, 110),
    "panel_is_top_level": False,
    "panel_inside_host_chain": True,
    "overlay_visible": True,
    "overlay_opacity": 1.0,
    "controls": {
        "overlayTimeline": (328, 900, 854, 20),
        "overlayPlayPause": (733, 930, 44, 44),
        "overlayFullscreen": (1150, 935, 34, 34),
    },
    "control_hits": {
        "overlayPlayPause": "overlay",
        "overlaySubtitles": "overlay",
        "overlayVolume": "overlay",
        "overlayFullscreen": "overlay",
    },
    "panel_hit": "own_process",
    "foreground_is_player": True,
}


def broken(**changes):
    snapshot = copy.deepcopy(GOOD)
    snapshot.update(changes)
    return snapshot


def test_healthy_snapshot_has_no_problems():
    assert zorder_after_resize_problems(GOOD) == []


# =====================================================================
# 1. Video / playlist bolunmesi
# =====================================================================

def test_panel_overlapping_video_is_caught():
    problems = zorder_after_resize_problems(
        broken(playlist_panel=(1100, 248, 360, 742)))

    assert any("panel_intersects_video" in p for p in problems), problems


def test_horizontal_gap_between_video_and_host_is_caught():
    problems = zorder_after_resize_problems(
        broken(playlist_host=(1250, 248, 320, 742),
               playlist_panel=(1250, 248, 320, 742)))

    assert any(p.startswith("split_gap=") for p in problems), problems


def test_panel_outside_host_is_caught():
    problems = zorder_after_resize_problems(
        broken(playlist_panel=(1150, 248, 460, 742)))

    assert "panel_outside_host" in problems, problems


def test_top_level_panel_is_caught():
    problems = zorder_after_resize_problems(broken(panel_is_top_level=True))

    assert "panel_is_top_level" in problems


def test_panel_outside_host_chain_is_caught():
    problems = zorder_after_resize_problems(
        broken(panel_inside_host_chain=False))

    assert "panel_not_in_host_chain" in problems


# =====================================================================
# 2. Ana yerlesim bosluklari
# =====================================================================

@pytest.mark.parametrize("container,expected", [
    ((310, 248, 1250, 742), "media_container_left_gap"),
    ((300, 248, 1250, 742), "media_container_right_gap"),
    ((300, 248, 1270, 700), "media_container_bottom_gap"),
])
def test_container_outer_gaps_are_caught(container, expected):
    problems = zorder_after_resize_problems(broken(media_container=container))

    assert expected in problems, problems


def test_gap_under_title_bar_is_caught():
    problems = zorder_after_resize_problems(
        broken(media_container=(300, 260, 1270, 730)))

    assert "media_container_gap_under_title_bar" in problems


# =====================================================================
# 3. Overlay
# =====================================================================

def test_overlay_outside_video_is_caught():
    problems = zorder_after_resize_problems(
        broken(control_overlay=(300, 880, 1270, 110)))

    assert "overlay_outside_video" in problems, problems


def test_overlay_left_at_old_width_is_caught():
    """Resize sonrasi overlay eski (dar) genislikte kalmamali."""
    problems = zorder_after_resize_problems(
        broken(control_overlay=(300, 880, 840, 110)))

    assert any(p.startswith("overlay_width=") for p in problems), problems


def test_overlay_not_bottom_aligned_is_caught():
    problems = zorder_after_resize_problems(
        broken(control_overlay=(300, 820, 910, 110)))

    assert "overlay_not_bottom_aligned" in problems, problems


def test_control_outside_overlay_is_caught():
    controls = dict(GOOD["controls"])
    controls["overlayFullscreen"] = (1150, 1000, 34, 34)
    problems = zorder_after_resize_problems(broken(controls=controls))

    assert "control_outside_overlay:overlayFullscreen" in problems


# =====================================================================
# 4. Native hit / foreground
# =====================================================================

def test_wrong_control_hit_is_caught():
    hits = dict(GOOD["control_hits"])
    hits["overlayPlayPause"] = "video_frame"
    problems = zorder_after_resize_problems(broken(control_hits=hits))

    assert "control_hit:overlayPlayPause=video_frame" in problems


def test_panel_centre_falling_to_video_is_caught():
    problems = zorder_after_resize_problems(broken(panel_hit="video_frame"))

    assert "panel_hit=video_frame" in problems


def test_panel_centre_owned_by_another_process_is_caught():
    problems = zorder_after_resize_problems(broken(panel_hit="other_process"))

    assert "panel_hit=other_process" in problems


@pytest.mark.parametrize("kind", ["own_process", "main_window", "playlist_host"])
def test_panel_centre_inside_own_process_is_accepted(kind):
    assert zorder_after_resize_problems(broken(panel_hit=kind)) == []


def test_lost_foreground_is_caught():
    problems = zorder_after_resize_problems(broken(foreground_is_player=False))

    assert "player_not_foreground" in problems


# =====================================================================
# 5. Fiziksel resize gercekten oldu mu?
# =====================================================================

EXPECTED = {"right": 70, "bottom": 70, "left": 0, "top": 0}


def test_missing_physical_resize_is_caught():
    before = (300, 200, 1200, 720)

    problems = resize_problems(before, before, EXPECTED)

    assert problems, "resize hic olmadigi halde sorun bulunmadi"


def test_correct_physical_resize_passes():
    before = (300, 200, 1200, 720)
    after = (300, 200, 1270, 790)

    assert resize_problems(before, after, EXPECTED) == []


def test_opposite_edges_must_stay_stable():
    before = (300, 200, 1200, 720)
    after = (230, 130, 1340, 860)  # sol/ust de kaymis

    problems = resize_problems(before, after, EXPECTED)

    assert any(p.startswith("left=") for p in problems), problems
    assert any(p.startswith("top=") for p in problems), problems
