# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Gerçek MPVPlayer kabuğunda başlık çubuğu entegrasyon testleri."""
import json
import os
import subprocess
import sys

import pytest
from PyQt6.QtCore import QRect

CHILD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "title_bar_child.py")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_child(preview, settings_dir):
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["MLC_TITLEBAR_SETTINGS"] = str(settings_dir)
    if preview:
        env.pop("MLCPLAYER_CLASSIC_UI", None)
    else:
        env["MLCPLAYER_CLASSIC_UI"] = "1"
    proc = subprocess.run([sys.executable, CHILD], env=env, cwd=PROJECT_ROOT,
                          capture_output=True, text=True, timeout=180)
    line = next((l for l in proc.stdout.splitlines()
                 if l.startswith("TITLEBAR_JSON ")), None)
    if line is None:
        raise AssertionError(
            f"Ölçüm alınamadı (exit={proc.returncode})\n"
            f"stdout:\n{proc.stdout[-3000:]}\nstderr:\n{proc.stderr[-3000:]}")
    return json.loads(line[len("TITLEBAR_JSON "):])


@pytest.fixture(scope="module")
def preview_on(tmp_path_factory):
    return run_child(True, tmp_path_factory.mktemp("titlebar-on"))


@pytest.fixture(scope="module")
def preview_off(tmp_path_factory):
    return run_child(False, tmp_path_factory.mktemp("titlebar-off"))


def rect(values):
    return QRect(*values)


# --- Preview açık ---

def test_preview_window_is_frameless(preview_on):
    assert preview_on["frameless"] is True


def test_preview_hides_the_classic_menu_bar(preview_on):
    assert preview_on["menu_bar_visible"] is False


def test_preview_creates_the_custom_title_bar(preview_on):
    assert preview_on["has_title_bar"] is True
    assert preview_on["title_bar_height"] == 40
    assert preview_on["title_bar_visible"] is True


def test_classic_menu_actions_stay_alive_in_overflow(preview_on):
    assert preview_on["menu_bar_action_count"] == 9
    assert preview_on["overflow_titles"] == [
        "Ortam", "Oynatma", "Ses", "Görüntü", "Alt Yazı",
        "Araçlar", "Gezinim", "Görünüm", "Yardım"]


# --- Legacy klasik anahtar: artık eski kabuğu GERİ GETİRMEZ ---
#
# Bu blok eskiden klasik kabuğun korunduğunu doğruluyordu. Kullanıcı eski
# pencereyi gerçek Windows'ta gördüğü için ürün kararı değişti: sinematik
# tasarım tek arayüzdür.

def test_legacy_env_still_yields_a_frameless_window(preview_off):
    assert preview_off["frameless"] is True


def test_legacy_env_keeps_the_classic_menu_bar_hidden(preview_off):
    assert preview_off["menu_bar_visible"] is False


def test_legacy_env_still_creates_the_modern_title_bar(preview_off):
    assert preview_off["has_title_bar"] is True
    assert preview_off["overlay_created"] is True


def test_legacy_env_fullscreen_never_reveals_the_menu_bar(preview_off):
    assert preview_off["window_is_fullscreen"] is True
    assert preview_off["menu_visible_fullscreen"] is False
    assert preview_off["window_is_fullscreen_after_exit"] is False
    assert preview_off["menu_visible_after_exit"] is False


# --- Minimum boyut ---

def test_main_window_keeps_its_400x300_minimum(preview_on):
    assert preview_on["window_minimum"] == [400, 300]


def test_title_bar_controls_fit_inside_minimum_window(preview_on):
    window = rect(preview_on["window_rect_at_min"])
    bar = rect(preview_on["title_rect_at_min"])
    assert window.contains(bar)

    buttons = preview_on["title_buttons_at_min"]
    assert buttons, "başlık düğmeleri ölçülemedi"
    for name, values in buttons.items():
        assert window.contains(rect(values)), f"{name} pencere dışına taştı"


def test_video_area_still_fits_at_minimum_window(preview_on):
    window = rect(preview_on["window_rect_at_min"])
    assert window.contains(rect(preview_on["video_rect_at_min"]))


# --- Fullscreen ---

def test_title_bar_is_hidden_during_fullscreen(preview_on):
    assert preview_on["window_is_fullscreen"] is True
    assert preview_on["title_bar_visible_fullscreen"] is False


def test_title_bar_returns_after_fullscreen(preview_on):
    assert preview_on["window_is_fullscreen_after_exit"] is False
    assert preview_on["title_bar_visible_after_exit"] is True


def test_classic_menu_bar_stays_hidden_after_fullscreen_in_preview(preview_on):
    assert preview_on["menu_visible_fullscreen"] is False
    assert preview_on["menu_visible_after_exit"] is False


def test_bottom_overlay_is_untouched_in_preview(preview_on):
    assert preview_on["overlay_created"] is True


# --- Z-order dayanıklılığı ---

def test_player_exposes_a_single_ensure_helper(preview_on):
    assert preview_on["has_ensure_helper"] is True


def test_title_bar_is_on_top_after_returning_from_fullscreen(preview_on):
    assert preview_on["title_bar_visible_after_exit"] is True
    assert preview_on["title_bar_last_in_child_order_after_exit"] is True


def test_ensure_helper_raises_and_shows_the_title_bar(preview_on):
    assert preview_on["title_bar_on_top_after_helper"] is True
    assert preview_on["title_bar_visible_after_helper"] is True


def test_legacy_env_still_does_title_bar_z_order_work(preview_off):
    assert preview_off["has_ensure_helper"] is True
    assert preview_off["has_title_bar"] is True


def test_playback_start_raises_title_bar_exactly_once(preview_on):
    assert preview_on["has_raise_pending_flag"] is True
    assert preview_on["mark_sets_pending"] is True
    assert preview_on["raise_pending_cleared_after_one_update"] is True
    assert preview_on["raise_pending_stays_cleared"] is True
    # 5 + 1 update_ui turunda raise yalnızca bir kez olmalı.
    assert preview_on["ensure_calls_for_one_playback"] == 1
    assert preview_on["ensure_calls_after_extra_updates"] == 1


def test_legacy_env_mark_helper_still_sets_pending(preview_off):
    """Sinematik kabuk her koşulda kurulduğu için bayrak da çalışır."""
    assert preview_off["mark_sets_pending"] is True
