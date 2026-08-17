# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Overlay CC (altyazı) durum göstergesi regresyon testleri.

Gerçek durum kaynağı MPV'dir: sub_visibility + sid/track_list. Düğmeye
basılmış olmak state olarak saklanmaz; klavye, menü, dil seçimi veya harici
altyazı yükleme sonrası da doğru renk gösterilmelidir.
"""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QPoint, QSettings, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import (
    QApplication, QLabel, QMainWindow, QPushButton, QSlider, QVBoxLayout,
    QWidget)

from app import media_controls
from app.config import MAX_VOLUME
from app.video_frame import OVERLAY_ACCENT, VideoFrame

ACTIVE_LABEL = "Altyazıları Kapat"
INACTIVE_LABEL = "Altyazıları Aç"


@pytest.fixture
def product_window(monkeypatch, tmp_path):
    created = []
    app_ref = []

    def qt_app():
        app = QApplication.instance() or QApplication([])
        if not app_ref:
            app_ref.append(app)
        return app

    def factory(classic=False, sub_visibility=False, sid=None, tracks=None):
        if classic:
            monkeypatch.setenv("MLCPLAYER_CLASSIC_UI", "1")
        else:
            monkeypatch.delenv("MLCPLAYER_CLASSIC_UI", raising=False)
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                          str(tmp_path))
        app = qt_app()
        window = QMainWindow()
        window.central_widget = QWidget(window)
        window.setCentralWidget(window.central_widget)
        window.main_layout = QVBoxLayout(window.central_widget)
        window.main_layout.setContentsMargins(0, 0, 0, 0)
        window.duration = 600.0
        window.position = 0.0
        window.is_paused = False
        window.is_muted = False
        window.current_file = "<test-video>"
        window._updating_position_slider = False
        window._pending_subs = []
        window.volume_slider = QSlider(Qt.Orientation.Horizontal)
        window.volume_slider.setRange(0, MAX_VOLUME)
        window.volume_slider.setValue(70)
        window.position_slider = QSlider()
        window.position_slider.setRange(0, 1000)
        window.current_time_label = QLabel()
        window.total_time_label = QLabel()
        window.play_button = SimpleNamespace(setIcon=lambda icon: None)
        window.play_icon = object()
        window.pause_icon = object()
        window.update_time_label = lambda: None
        window.mpv_player = SimpleNamespace(
            time_pos=0.0, pause=False, sub_visibility=sub_visibility,
            sid=sid, track_list=tracks if tracks is not None else [
                {"id": 1, "type": "sub", "lang": "eng"}],
            stop=lambda: None)
        window.seek_position = lambda value: None
        for name in ("play_previous", "play_next", "play_pause", "toggle_mute",
                     "toggle_fullscreen", "setup_video_adjustments"):
            setattr(window, name, lambda: None)
        window.toggle_subtitles = lambda: media_controls.toggle_subtitles(window)

        frame = VideoFrame(window)
        window.video_frame = frame
        window.main_layout.addWidget(frame)
        window.resize(1280, 720)
        window.show()
        app.processEvents()
        frame.update_overlay_geometry()
        if frame.control_overlay is not None:
            frame.show_overlay_for_interaction()
            animation = frame.overlay_fade
            if animation is not None:
                animation.setCurrentTime(animation.duration())
        app.processEvents()
        created.append((window, frame))
        return app, window, frame

    yield factory

    app = qt_app()
    for window, frame in created:
        if frame.is_video_fullscreen:
            frame.exit_fullscreen()
        frame.close_control_overlay()
        window.close()
        window.deleteLater()
    app.processEvents()


def cc_button(frame):
    return frame.overlay_subtitles_button


def icon_key(button):
    return button.icon().pixmap(button.iconSize()).cacheKey()


# --- 1/2/3. Gerçek MPV durumu ikona yansımalı ---

def test_hidden_subtitles_use_the_inactive_appearance(product_window):
    app, window, frame = product_window(sub_visibility=False, sid=1)
    frame.update_overlay_state()
    button = cc_button(frame)
    assert button.accessibleName() == INACTIVE_LABEL
    assert frame.overlay_subtitles_active is False


def test_visible_subtitles_with_a_track_turn_the_icon_orange(product_window):
    app, window, frame = product_window(sub_visibility=True, sid=1)
    frame.update_overlay_state()
    button = cc_button(frame)
    assert frame.overlay_subtitles_active is True
    assert button.accessibleName() == ACTIVE_LABEL
    assert button.toolTip() == ACTIVE_LABEL


def test_visible_but_no_selected_track_stays_inactive(product_window):
    app, window, frame = product_window(sub_visibility=True, sid=False)
    frame.update_overlay_state()
    assert frame.overlay_subtitles_active is False
    assert cc_button(frame).accessibleName() == INACTIVE_LABEL


def test_active_and_inactive_icons_differ(product_window):
    app, window, frame = product_window(sub_visibility=False, sid=1)
    frame.update_overlay_state()
    inactive = icon_key(cc_button(frame))

    window.mpv_player.sub_visibility = True
    frame.update_overlay_state()
    active = icon_key(cc_button(frame))

    assert inactive != active
    assert OVERLAY_ACCENT == "#F26A3D"


# --- 4/5. Overlay CC düğmesi ---

def test_clicking_cc_button_turns_the_icon_orange(product_window):
    app, window, frame = product_window(sub_visibility=False, sid=1)
    frame.update_overlay_state()

    QTest.mouseClick(cc_button(frame), Qt.MouseButton.LeftButton)
    app.processEvents()

    assert window.mpv_player.sub_visibility is True
    assert frame.overlay_subtitles_active is True
    assert cc_button(frame).accessibleName() == ACTIVE_LABEL


def test_clicking_cc_button_again_returns_to_inactive(product_window):
    app, window, frame = product_window(sub_visibility=True, sid=1)
    frame.update_overlay_state()

    QTest.mouseClick(cc_button(frame), Qt.MouseButton.LeftButton)
    app.processEvents()

    assert window.mpv_player.sub_visibility is False
    assert frame.overlay_subtitles_active is False
    assert cc_button(frame).accessibleName() == INACTIVE_LABEL


def test_clicking_cc_without_any_subtitle_shows_bottom_centre_osd(
        product_window):
    app, window, frame = product_window(
        sub_visibility=False, sid=False, tracks=[])
    frame.update_overlay_state()

    QTest.mouseClick(cc_button(frame), Qt.MouseButton.LeftButton)
    app.processEvents()

    assert window.mpv_player.sub_visibility is False
    assert frame.osd_label.isVisible()
    assert frame.osd_label.text() == "Altyazı bulunamadı"
    video_origin = frame.mapToGlobal(QPoint(0, 0))
    osd_centre = frame.osd_label.geometry().center()
    assert abs(osd_centre.x() - (video_origin.x() + frame.width() // 2)) <= 2
    assert frame.osd_label.geometry().bottom() < video_origin.y() + frame.height()
    # Mesaj alt bolgede durur ama kontrol katmaninin AYRILMIS bandina
    # girmez (bkz. tests/test_osd_layout_regressions.py).
    band_top = (video_origin.y() + frame.height()
                - frame.control_overlay.geometry().height())
    assert frame.osd_label.geometry().bottom() < band_top
    assert osd_centre.y() > video_origin.y() + frame.height() // 2


def test_missing_subtitle_osd_uses_the_same_timed_osd_channel(product_window):
    app, window, frame = product_window(
        sub_visibility=False, sid=None, tracks=[])

    media_controls.toggle_subtitles(window)
    app.processEvents()

    assert frame.osd_timer.isActive()
    assert frame.osd_timer.remainingTime() > 0
    assert frame.overlay_subtitles_active is False


# --- 6/7. Klavye ve menü yolları ---

def test_keyboard_toggle_updates_the_icon(product_window):
    app, window, frame = product_window(sub_visibility=False, sid=1)
    frame.update_overlay_state()

    media_controls.toggle_subtitles(window)
    app.processEvents()

    assert frame.overlay_subtitles_active is True


def test_menu_toggle_updates_the_icon(product_window):
    app, window, frame = product_window(sub_visibility=True, sid=1)
    frame.update_overlay_state()

    window.toggle_subtitles()
    app.processEvents()

    assert frame.overlay_subtitles_active is False


# --- 8/9. Dil seçimi ve harici altyazı ---

def test_selecting_a_subtitle_language_turns_the_icon_orange(product_window):
    app, window, frame = product_window(
        sub_visibility=True, sid=False,
        tracks=[{"id": 1, "type": "sub"}, {"id": 2, "type": "sub"}])
    frame.update_overlay_state()
    assert frame.overlay_subtitles_active is False

    media_controls.select_subtitle_language(window, 2)
    app.processEvents()

    assert window.mpv_player.sid == 2
    assert frame.overlay_subtitles_active is True


def test_loading_an_external_subtitle_updates_the_icon(product_window,
                                                       tmp_path, monkeypatch):
    app, window, frame = product_window(sub_visibility=False, sid=False)
    frame.update_overlay_state()

    subtitle = tmp_path / "movie.srt"
    subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\nmerhaba\n",
                        encoding="utf-8")

    def sub_add(path):
        window.mpv_player.track_list = list(window.mpv_player.track_list) + [
            {"id": 3, "type": "sub", "external": True}]
        window.mpv_player.sid = 3
        window.mpv_player.sub_visibility = True

    window.mpv_player.sub_add = sub_add
    monkeypatch.setattr(
        "app.media_controls.QFileDialog.getOpenFileName",
        staticmethod(lambda *args, **kwargs: (str(subtitle), "")))

    media_controls.open_subtitle(window)
    app.processEvents()

    assert frame.overlay_subtitles_active is True


# --- 10/11. Periyodik güncelleme ve gereksiz setIcon ---

def test_external_change_is_picked_up_by_update_overlay_state(product_window):
    app, window, frame = product_window(sub_visibility=False, sid=1)
    frame.update_overlay_state()
    assert frame.overlay_subtitles_active is False

    # Ürün dışından (ör. mpv tarafında) değişti
    window.mpv_player.sub_visibility = True
    frame.update_overlay_state()

    assert frame.overlay_subtitles_active is True


def test_repeated_updates_do_not_rebuild_the_icon(product_window):
    app, window, frame = product_window(sub_visibility=True, sid=1)
    frame.update_overlay_state()
    button = cc_button(frame)
    calls = []
    original = button.setIcon
    button.setIcon = lambda icon: (calls.append(1), original(icon))[1]

    for _ in range(5):
        frame.update_overlay_state()

    assert calls == [], "durum değişmeden ikon yeniden üretildi"
    button.setIcon = original


# --- 12. Diagnostic klasik mod ---

def test_legacy_classic_env_keeps_the_cc_button(product_window):
    """Legacy anahtar verilse bile CC göstergesi sinematik overlay'de kalır."""
    app, window, frame = product_window(classic=True, sub_visibility=True, sid=1)
    assert frame.control_overlay is not None
    assert hasattr(frame, "overlay_subtitles_button")
    frame.update_overlay_state()


# --- 13. Düğme kimliği değişmemeli ---

def test_cc_button_keeps_its_identity_and_position(product_window):
    app, window, frame = product_window(sub_visibility=True, sid=1)
    frame.update_overlay_state()
    overlay = frame.control_overlay
    button = cc_button(frame)

    assert button.objectName() == "overlaySubtitles"
    # Hit alanı 30 -> 40 px büyütüldü (ikon 18 px aynı kaldı).
    assert button.size().width() == 40 and button.size().height() == 40
    assert button.text() == ""

    order = ["overlaySubtitles", "overlaySettings", "overlayVolume",
             "overlayVolumeSlider", "overlayFullscreen"]
    positions = []
    for name in order:
        widget = next(w for w in overlay.findChildren(QWidget)
                      if w.objectName() == name)
        positions.append(widget.mapTo(overlay, widget.rect().center()).x())
    assert positions == sorted(positions)


def test_cc_button_click_still_reaches_toggle_subtitles(product_window):
    app, window, frame = product_window(sub_visibility=False, sid=1)
    calls = []
    window.toggle_subtitles = lambda: calls.append("toggle_subtitles")

    QTest.mouseClick(cc_button(frame), Qt.MouseButton.LeftButton)
    app.processEvents()

    assert calls == ["toggle_subtitles"]


# --- Sınır durumları: seçili altyazı yokken turuncu olmamalı ---

@pytest.mark.parametrize("sid", ("no", "none", "", 0, "0", None, False))
def test_empty_or_disabled_sid_values_stay_inactive(product_window, sid):
    app, window, frame = product_window(sub_visibility=True, sid=sid)
    frame.update_overlay_state()
    assert frame.overlay_subtitles_active is False, f"sid={sid!r} aktif sayıldı"
    assert cc_button(frame).accessibleName() == INACTIVE_LABEL


def test_auto_sid_without_a_selected_track_is_inactive(product_window):
    app, window, frame = product_window(
        sub_visibility=True, sid="auto",
        tracks=[{"id": 1, "type": "sub", "selected": False},
                {"id": 2, "type": "audio", "selected": True}])
    frame.update_overlay_state()
    assert frame.overlay_subtitles_active is False


def test_auto_sid_with_a_selected_subtitle_track_is_active(product_window):
    app, window, frame = product_window(
        sub_visibility=True, sid="auto",
        tracks=[{"id": 1, "type": "sub", "selected": True},
                {"id": 2, "type": "audio", "selected": True}])
    frame.update_overlay_state()
    assert frame.overlay_subtitles_active is True
    assert cc_button(frame).accessibleName() == ACTIVE_LABEL


def test_numeric_sid_matching_a_subtitle_track_is_active(product_window):
    app, window, frame = product_window(
        sub_visibility=True, sid=4,
        tracks=[{"id": 3, "type": "audio"}, {"id": 4, "type": "sub"}])
    frame.update_overlay_state()
    assert frame.overlay_subtitles_active is True


def test_numeric_sid_without_a_matching_track_is_inactive(product_window):
    app, window, frame = product_window(
        sub_visibility=True, sid=4,
        tracks=[{"id": 1, "type": "sub"}, {"id": 4, "type": "audio"}])
    frame.update_overlay_state()
    assert frame.overlay_subtitles_active is False


@pytest.mark.parametrize("sid", (4, "auto", 1))
def test_hidden_subtitles_are_inactive_regardless_of_sid(product_window, sid):
    app, window, frame = product_window(
        sub_visibility=False, sid=sid,
        tracks=[{"id": 1, "type": "sub", "selected": True},
                {"id": 4, "type": "sub"}])
    frame.update_overlay_state()
    assert frame.overlay_subtitles_active is False


def test_track_list_read_error_falls_back_to_inactive(product_window):
    app, window, frame = product_window(sub_visibility=True, sid=4)

    class Exploding:
        def __get__(self, obj, owner=None):
            raise RuntimeError("mpv property unavailable")

    class Player:
        sub_visibility = True
        sid = 4
        track_list = Exploding()

    window.mpv_player = Player()
    frame.update_overlay_state()
    assert frame.overlay_subtitles_active is False


def test_real_embedded_subtitle_scenario_stays_active(product_window):
    """Gerçek smoke'taki durum: sid=4, gömülü altyazı parçası mevcut."""
    app, window, frame = product_window(
        sub_visibility=True, sid=4,
        tracks=[{"id": 1, "type": "video"},
                {"id": 2, "type": "audio", "lang": "hin"},
                {"id": 3, "type": "audio", "lang": "eng"},
                {"id": 4, "type": "sub", "lang": "eng", "selected": True}])
    frame.update_overlay_state()
    assert frame.overlay_subtitles_active is True
    assert cc_button(frame).accessibleName() == ACTIVE_LABEL


def test_missing_track_list_property_falls_back_to_inactive(product_window):
    app, window, frame = product_window(sub_visibility=True, sid=4)
    delattr(window.mpv_player, "track_list")
    frame.update_overlay_state()
    assert frame.overlay_subtitles_active is False
