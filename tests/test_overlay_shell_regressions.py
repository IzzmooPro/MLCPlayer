"""Gerçek MPVPlayer kabuğu için görsel/düzen regresyon testleri.

Ölçümler ayrı child süreçte gerçek ürün düzeninden alınır (bkz. layout_child.py);
sabit ekran koordinatı veya sahte state kullanılmaz.
"""
import json
import os
import subprocess
import sys

import pytest

from PyQt6.QtCore import QRect

CHILD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "layout_child.py")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_child(preview, settings_dir):
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["MLC_LAYOUT_SETTINGS"] = str(settings_dir)
    if preview:
        env["MLCPLAYER_OVERLAY_PREVIEW"] = "1"
    else:
        env.pop("MLCPLAYER_OVERLAY_PREVIEW", None)
    proc = subprocess.run([sys.executable, CHILD], env=env, cwd=PROJECT_ROOT,
                          capture_output=True, text=True, timeout=180)
    line = next((l for l in proc.stdout.splitlines()
                 if l.startswith("LAYOUT_JSON ")), None)
    if line is None:
        raise AssertionError(
            f"Ölçüm alınamadı (exit={proc.returncode})\n"
            f"stdout:\n{proc.stdout[-3000:]}\nstderr:\n{proc.stderr[-3000:]}")
    return json.loads(line[len("LAYOUT_JSON "):])


@pytest.fixture(scope="module")
def preview_on(tmp_path_factory):
    return run_child(True, tmp_path_factory.mktemp("layout-preview-on"))


@pytest.fixture(scope="module")
def preview_off(tmp_path_factory):
    return run_child(False, tmp_path_factory.mktemp("layout-preview-off"))


def rect(values):
    return QRect(*values)


# --- 1. Preview açıkken klasik kontrol paneli gizlenmeli ---

def test_classic_panel_is_hidden_when_preview_is_on(preview_on):
    assert preview_on["overlay_created"] is True
    assert preview_on["has_control_container"] is True
    assert preview_on["control_container_visible_normal"] is False


def test_classic_panel_takes_no_layout_height_when_preview_is_on(preview_on):
    assert preview_on["control_container_height_normal"] == 0


def test_classic_panel_is_visible_when_preview_is_off(preview_off):
    assert preview_off["overlay_created"] is False
    assert preview_off["control_container_visible_normal"] is True
    assert preview_off["control_container_height_normal"] == 54


def test_product_control_objects_survive_with_preview_on(preview_on):
    """Gizleme ürün nesnelerini ve mevcut akışları bozmamalı."""
    assert preview_on["has_position_slider"] is True
    assert preview_on["has_play_button"] is True


# --- 2. Gerçek 400x300 pencerede taşma olmamalı ---

def test_video_frame_fits_inside_real_minimum_window(preview_on):
    window = rect(preview_on["window_rect_at_min"])
    video = rect(preview_on["video_rect_at_min"])
    assert window.contains(video), f"video {video} pencere {window} dışına taşıyor"


def test_main_window_keeps_its_400x300_minimum(preview_on):
    assert preview_on["window_minimum"] == [400, 300]


def test_video_frame_minimum_is_smaller_than_window_minimum(preview_on):
    """VideoFrame minimumu menü + panel yüksekliğini hesaba katmalı."""
    assert preview_on["video_minimum"][1] < 300


def test_overlay_and_its_controls_stay_inside_minimum_window(preview_on):
    window = rect(preview_on["window_rect_at_min"])
    video = rect(preview_on["video_rect_at_min"])
    overlay = rect(preview_on["overlay_rect_at_min"])

    assert video.contains(overlay), f"overlay {overlay} video {video} dışında"
    assert window.contains(overlay), f"overlay {overlay} pencere {window} dışında"
    for key in ("overlay_timeline_rect_at_min", "overlay_play_rect_at_min",
                "overlay_current_label_rect_at_min",
                "overlay_fullscreen_rect_at_min"):
        child = rect(preview_on[key])
        assert window.contains(child), f"{key} {child} pencere dışına taşıyor"


def test_hidden_classic_panel_does_not_overlap_overlay_at_minimum(preview_on):
    assert preview_on["control_container_visible_at_min"] is False
    assert preview_on["control_container_height_at_min"] == 0


# --- 3. Fullscreen'de ikinci pencere kalmamalı ---

def test_fullscreen_uses_the_main_window(preview_on):
    assert preview_on["fullscreen_flag"] is True
    assert preview_on["window_is_fullscreen"] is True


def test_no_second_window_is_visible_during_fullscreen(preview_on):
    visible = preview_on["visible_top_levels_fullscreen"]
    assert len(visible) == 1, f"fullscreen sırasında fazladan pencere: {visible}"


def test_menu_and_classic_panel_are_hidden_during_fullscreen(preview_on):
    assert preview_on["menu_visible_fullscreen"] is False
    assert preview_on["control_container_visible_fullscreen"] is False


def test_video_fills_the_screen_during_fullscreen(preview_on):
    screen = rect(preview_on["screen_rect"])
    video = rect(preview_on["video_rect_fullscreen"])
    assert video.width() == screen.width()
    assert video.height() >= screen.height() - 2


def test_overlay_stays_owned_and_positioned_during_fullscreen(preview_on):
    assert preview_on["overlay_owner_is_main_window_fullscreen"] is True
    video = rect(preview_on["video_rect_fullscreen"])
    overlay = rect(preview_on["overlay_rect_fullscreen"])
    assert video.contains(overlay)
    assert overlay.bottom() == video.bottom()


def test_exiting_fullscreen_restores_window_and_menu(preview_on):
    assert preview_on["fullscreen_flag_after_exit"] is False
    assert preview_on["window_is_fullscreen_after_exit"] is False
    assert preview_on["menu_visible_after_exit"] is True
    assert preview_on["geometry_after_exit"] == \
        preview_on["geometry_before_fullscreen"]
    assert len(preview_on["visible_top_levels_after_exit"]) == 1


def test_classic_panel_stays_hidden_after_fullscreen_with_preview_on(preview_on):
    assert preview_on["control_container_visible_after_exit"] is False


def test_classic_panel_returns_after_fullscreen_with_preview_off(preview_off):
    assert preview_off["window_is_fullscreen_after_exit"] is False
    assert preview_off["menu_visible_after_exit"] is True
    assert preview_off["control_container_visible_after_exit"] is True
