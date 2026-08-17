# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""OSD, kontrol katmanının ALTINA gizlenmemeli.

Fiziksel kabul kanıtı (`subtitles/no_subtitle_osd_layout`, gerçek pencere,
gerçek MKV):

    osd     = (736, 876, 128, 20)
    overlay = (100, 810, 1400, 110)
    overlay_overlap = True

Ekran görüntüsünde "Altyazı bulunamadı" yazısı oynat/duraklat düğmesinin
arkasında kalıyordu.

Kök neden: `_center_osd()` OSD'yi video alanının ALT kenarından yalnız
24 px yukarı koyuyordu; kontrol katmanı ise alttaki ~110 px'i kaplıyor.
Doğru kural: OSD'nin alt kenarı, kontrol katmanının GERÇEK üst kenarından
küçük bir boşlukla yukarıda olmalı. Kural tek bir mesaja değil,
`show_osd()` kullanan BÜTÜN bildirimlere uygulanır.
"""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QPoint, QRect, QSettings, Qt
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMainWindow, QSlider, QVBoxLayout,
    QWidget)

from app.config import MAX_VOLUME
from app.video_frame import VideoFrame

# Kabul toleransi: OSD ile katman arasindaki bosluk bu araliktaysa
# kullanici mesaji kontrollerin uzerinde ve okunur gorur.
MIN_GAP = 12
MAX_GAP = 16


@pytest.fixture
def player_window(monkeypatch, tmp_path):
    monkeypatch.delenv("MLCPLAYER_CLASSIC_UI", raising=False)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      str(tmp_path))
    app = QApplication.instance() or QApplication([])
    created = []

    def factory(size=(1400, 820)):
        window = QMainWindow()
        window.cinematic_ui_enabled = True
        window.playlist = [r"C:\media\first.mkv"]
        window.current_playlist_index = 0
        window.current_file = window.playlist[0]
        window.duration = 600.0
        window.position = 0.0
        window.is_paused = False
        window.is_muted = False
        window._updating_position_slider = False
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
        window.mpv_player = SimpleNamespace(time_pos=0.0, pause=False,
                                            track_list=[], sub_visibility=False,
                                            sid="no", stop=lambda: None)
        for name in ("play_previous", "play_next", "play_pause", "toggle_mute",
                     "toggle_subtitles", "toggle_fullscreen",
                     "setup_video_adjustments", "add_to_playlist",
                     "remove_from_playlist", "clear_playlist"):
            setattr(window, name, lambda *a: None)
        window.play_from_playlist = lambda index: None

        central = QWidget(window)
        window.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        window.media_container = QWidget(central)
        media_layout = QHBoxLayout(window.media_container)
        media_layout.setContentsMargins(0, 0, 0, 0)
        media_layout.setSpacing(0)
        window.playlist_dock_host = QWidget(window.media_container)
        window.playlist_dock_host.setFixedWidth(0)
        window.playlist_dock_host.hide()
        frame = VideoFrame(window)
        frame.setMinimumSize(200, 120)
        window.video_frame = frame
        media_layout.addWidget(frame, 1)
        media_layout.addWidget(window.playlist_dock_host, 0)
        root.addWidget(window.media_container, 1)
        window.resize(*size)
        window.show()
        app.processEvents()
        # Offscreen platformda gercek foreground kavrami yok; karar
        # dogrudan yamalanir (bkz. test_overlay_foreground_ownership).
        monkeypatch.setattr(type(frame), "_player_owns_foreground",
                            lambda self: True)
        frame.update_overlay_geometry()
        frame.show_overlay_for_interaction()
        finish_fade(app, frame)
        app.processEvents()
        created.append((window, frame))
        return app, window, frame

    yield factory

    QApplication.setActiveWindow(None)
    app.processEvents()
    for window, frame in created:
        if frame.is_video_fullscreen:
            frame.exit_fullscreen()
        fade = getattr(frame, "overlay_fade", None)
        if fade is not None:
            fade.stop()
        panel = getattr(frame, "playlist_panel", None)
        if panel is not None:
            panel.animation.stop()
        frame.close_control_overlay()
        window.close()
        app.processEvents()
        window.deleteLater()
    app.processEvents()


def finish_fade(app, frame):
    animation = getattr(frame, "overlay_fade", None)
    if animation is not None and animation.state().name == "Running":
        animation.setCurrentTime(animation.duration())
    app.processEvents()


def global_rect(widget):
    """Ust duzey Tool yuzeyleri icin de dogru global dikdortgen."""
    if widget.isWindow():
        return QRect(widget.geometry())
    return QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())


def osd_rect(frame):
    return global_rect(frame.osd_label)


def overlay_band(frame):
    """Kontrol katmaninin AYRILMIS bandi (gorunur olmasa da gecerli)."""
    return global_rect(frame.control_overlay)


def show(app, frame, text="Altyazı bulunamadı"):
    frame.show_osd(text)
    app.processEvents()
    return osd_rect(frame)


# --- 1. Kanitlanan hata: OSD kontrol katmaninin icine yerlesiyor ---

def test_osd_never_intersects_the_control_overlay(player_window):
    app, window, frame = player_window()

    rect = show(app, frame)

    assert not rect.intersects(overlay_band(frame)), (
        f"OSD kontrol katmaninin icinde: osd={rect.getRect()} "
        f"overlay={overlay_band(frame).getRect()}")


def test_osd_sits_just_above_the_control_overlay(player_window):
    app, window, frame = player_window()

    rect = show(app, frame)

    gap = overlay_band(frame).top() - rect.bottom()
    assert MIN_GAP <= gap <= MAX_GAP, (
        f"OSD ile kontrol katmani arasindaki bosluk {gap}px; "
        f"beklenen {MIN_GAP}-{MAX_GAP}px")


def test_osd_stays_horizontally_centred_and_inside_the_video_area(
        player_window):
    app, window, frame = player_window()

    rect = show(app, frame)

    video = global_rect(frame)
    assert video.contains(rect), (
        f"OSD video alanindan tasti: osd={rect.getRect()} "
        f"video={video.getRect()}")
    assert abs(rect.center().x() - video.center().x()) <= 2


# --- 2. Kural tek mesaja ozel degil ---

@pytest.mark.parametrize("text", ["Sessiz", "Ses: %70", "Altyazı eklendi",
                                  "Bölüm 02", "Altyazı bulunamadı"])
def test_every_osd_message_uses_the_same_safe_region(player_window, text):
    app, window, frame = player_window()

    rect = show(app, frame, text)

    assert not rect.intersects(overlay_band(frame)), (
        f"{text!r} mesaji kontrol katmaninin icinde kaldi")


# --- 3. Playlist acikken video alani daralir ---

def test_osd_follows_the_video_area_when_the_playlist_takes_width(
        player_window):
    app, window, frame = player_window()
    window.playlist_dock_host.setFixedWidth(320)
    window.playlist_dock_host.show()
    app.processEvents()
    frame.update_overlay_geometry()
    app.processEvents()

    rect = show(app, frame)

    video = global_rect(frame)
    assert abs(rect.center().x() - video.center().x()) <= 2, (
        "OSD playlist alanina dogru kaydi")
    assert video.contains(rect)
    assert not rect.intersects(overlay_band(frame))


# --- 4. Tam ekran ---

def test_osd_stays_above_the_overlay_in_fullscreen(player_window):
    app, window, frame = player_window()
    frame.enter_fullscreen()
    app.processEvents()
    frame.update_overlay_geometry()
    finish_fade(app, frame)
    app.processEvents()

    rect = show(app, frame)

    assert global_rect(frame).contains(rect)
    assert not rect.intersects(overlay_band(frame))


# --- 5. Kucuk pencere ---

def test_osd_stays_inside_a_small_video_area(player_window):
    app, window, frame = player_window(size=(400, 300))
    app.processEvents()

    rect = show(app, frame)

    video = global_rect(frame)
    assert video.contains(rect), (
        f"kucuk pencerede OSD tasti: osd={rect.getRect()} "
        f"video={video.getRect()}")
    assert not rect.intersects(overlay_band(frame))


def test_osd_is_clamped_inside_a_very_short_video_area(player_window):
    app, window, frame = player_window()
    frame.setMinimumSize(200, 90)
    window.resize(360, 150)
    app.processEvents()

    rect = show(app, frame)

    video = global_rect(frame)
    assert video.contains(rect), (
        f"cok kisa alanda OSD tasti: osd={rect.getRect()} "
        f"video={video.getRect()}")


# --- 6. Resize sirasi ---

def test_overlay_and_osd_follow_the_new_geometry_together_after_resize(
        player_window):
    app, window, frame = player_window()
    show(app, frame)

    window.resize(1000, 640)
    app.processEvents()
    frame.update_overlay_geometry()
    app.processEvents()

    rect = osd_rect(frame)
    band = overlay_band(frame)
    video = global_rect(frame)
    assert not rect.intersects(band), (
        f"resize sonrasi OSD katmanin icinde: osd={rect.getRect()} "
        f"overlay={band.getRect()}")
    assert video.contains(rect)
    assert abs(rect.center().x() - video.center().x()) <= 2


def test_resize_updates_the_overlay_before_placing_the_osd(player_window):
    """Eski katman geometrisiyle yerlestirme yapilmamali."""
    app, window, frame = player_window()
    show(app, frame)
    order = []
    real_center = type(frame)._center_osd
    real_overlay = type(frame).update_overlay_geometry

    def center(self):
        order.append("osd")
        return real_center(self)

    def overlay(self):
        order.append("overlay")
        return real_overlay(self)

    type(frame)._center_osd = center
    type(frame).update_overlay_geometry = overlay
    try:
        window.resize(1180, 700)
        app.processEvents()
    finally:
        type(frame)._center_osd = real_center
        type(frame).update_overlay_geometry = real_overlay

    assert "osd" in order and "overlay" in order
    assert order.index("overlay") < order.index("osd"), (
        f"OSD, katman geometrisinden ONCE yerlestirildi: {order}")


# --- 7. Katman gizliyken bile bant korunur ---

def test_hidden_overlay_still_reserves_its_band(player_window):
    app, window, frame = player_window()
    band = overlay_band(frame)
    frame.hide_overlay_immediately()
    app.processEvents()

    rect = show(app, frame)

    assert not rect.intersects(band), (
        "katman auto-hide durumundayken OSD, katmanin geri donecegi alani "
        f"isgal etti: osd={rect.getRect()} band={band.getRect()}")


def test_transparent_overlay_still_reserves_its_band(player_window):
    app, window, frame = player_window()
    band = overlay_band(frame)
    frame.control_overlay.setWindowOpacity(0.0)
    app.processEvents()

    rect = show(app, frame)

    assert not rect.intersects(band)


# --- 8. Uzun metin ---

def test_long_osd_text_never_exceeds_the_video_width(player_window):
    app, window, frame = player_window(size=(560, 420))

    rect = show(app, frame, "Altyazı bulunamadı " * 12)

    video = global_rect(frame)
    assert rect.width() <= video.width(), (
        f"uzun metin video genisligini asti: osd={rect.width()} "
        f"video={video.width()}")
    assert video.contains(rect)
    assert not rect.intersects(overlay_band(frame))


# --- 9. Davranis sozlesmesi degismedi ---

def test_message_text_timer_and_mouse_transparency_are_unchanged(
        player_window):
    app, window, frame = player_window()

    frame.show_osd("Altyazı bulunamadı", duration=1800)
    app.processEvents()

    assert frame.osd_label.isVisible()
    assert frame.osd_label.text() == "Altyazı bulunamadı"
    assert frame.osd_timer.isSingleShot()
    assert frame.osd_timer.isActive()
    assert frame.osd_label.testAttribute(
        Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert frame.osd_label.windowFlags() & Qt.WindowType.Tool
