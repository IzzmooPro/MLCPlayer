# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Sinematik overlay görsel yapısı regresyon testleri.

Testler gerçek widget geometrisini, gerçek QIcon içeriğini ve gerçek oynatma
state bağlantısını ölçer; sabit/sahte state assert'i kullanılmaz.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QEvent, QPoint, QRect, QSize, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget)

from app.video_frame import VideoFrame

BUTTON_NAMES = ("overlayPrevious", "overlayPlayPause", "overlayNext",
                "overlayFullscreen")

@pytest.fixture
def video_window(monkeypatch):
    """Test başarısız olsa da pencereleri kesin olarak yok eden fabrika.

    QApplication referansı fixture ömrü boyunca tutulur; aksi halde test
    gövdesi bitince çöp toplanır ve bütün top-level pencereler C++ tarafında
    yok edilerek teardown'da RuntimeError üretir.
    """
    created = []
    app_ref = []

    def qt_app():
        app = QApplication.instance() or QApplication([])
        if not app_ref:
            app_ref.append(app)
        return app

    def factory(enabled=True, size=(1280, 720)):
        if enabled:
            monkeypatch.delenv("MLCPLAYER_CLASSIC_UI", raising=False)
        else:
            monkeypatch.setenv("MLCPLAYER_CLASSIC_UI", "1")
        app = qt_app()
        window = QMainWindow()
        window.central_widget = QWidget(window)
        window.setCentralWidget(window.central_widget)
        window.main_layout = QVBoxLayout(window.central_widget)
        window.main_layout.setContentsMargins(0, 0, 0, 0)
        window.is_paused = True
        window.duration = 0
        window.position = 0
        window.current_file = "<test-video>"
        frame = VideoFrame(window)
        window.video_frame = frame
        window.main_layout.addWidget(frame)
        window.resize(*size)
        window.show()
        app.processEvents()
        frame.update_overlay_geometry()
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


def button_by_name(overlay, name):
    return next(b for b in overlay.findChildren(QPushButton)
                if b.objectName() == name)


def global_video_rect(frame):
    return QRect(frame.mapToGlobal(QPoint(0, 0)), frame.size())


# --- Yerleşim ve ölçüler ---

def test_overlay_spans_video_width_and_sits_flush_at_bottom(video_window):
    app, window, frame = video_window()
    overlay = frame.control_overlay
    video_rect = global_video_rect(frame)

    assert overlay.width() == video_rect.width()
    assert overlay.geometry().left() == video_rect.left()
    # Video alanının altına sıfır boşlukla oturmalı.
    assert overlay.geometry().bottom() == video_rect.bottom()



def test_overlay_height_is_in_cinematic_range(video_window):
    app, window, frame = video_window()
    assert 100 <= frame.control_overlay.height() <= 120


def test_timeline_keeps_a_visible_but_reduced_side_padding(video_window):
    app, window, frame = video_window()
    margins = frame.control_overlay.layout().contentsMargins()
    assert margins.left() == 20
    assert margins.right() == 20


def test_overlay_stays_inside_minimum_video_frame(video_window):
    app, window, frame = video_window(size=(400, 300))
    app.processEvents()
    frame.update_overlay_geometry()

    video_rect = global_video_rect(frame)
    overlay_rect = frame.control_overlay.geometry()
    assert video_rect.contains(overlay_rect.topLeft())
    assert video_rect.contains(overlay_rect.bottomRight())



def test_timeline_row_is_above_bottom_control_row(video_window):
    app, window, frame = video_window()
    overlay = frame.control_overlay
    timeline = frame.overlay_timeline
    play = button_by_name(overlay, "overlayPlayPause")

    timeline_bottom = timeline.mapTo(overlay, timeline.rect().bottomLeft()).y()
    play_top = play.mapTo(overlay, play.rect().topLeft()).y()
    current_top = frame.overlay_current_time_label.mapTo(
        overlay, frame.overlay_current_time_label.rect().topLeft()).y()

    assert timeline_bottom <= play_top
    assert timeline_bottom <= current_top


def test_timeline_spans_the_padded_width(video_window):
    app, window, frame = video_window()
    overlay = frame.control_overlay
    margins = overlay.layout().contentsMargins()
    expected = overlay.width() - margins.left() - margins.right()

    assert margins.left() == 20
    assert margins.right() == 20
    assert abs(frame.overlay_timeline.width() - expected) <= 2
    # NOT: Görsel groove 3 px kalır; widget yüksekliği gerçek kullanıcı
    # tıklamaları için genişletildi (bkz. test_overlay_timeline_hit_regressions).
    assert frame.overlay_timeline.height() <= 48


def test_longer_timeline_does_not_move_the_bottom_controls(video_window):
    app, window, frame = video_window()
    overlay = frame.control_overlay
    controls = frame._overlay_controls_row.contentsMargins()
    time_left = frame.overlay_time_container.mapTo(overlay, QPoint(0, 0)).x()

    assert controls.left() == 8 and controls.right() == 8
    assert time_left == 28


def test_center_play_button_is_larger_than_other_media_buttons(video_window):
    app, window, frame = video_window()
    overlay = frame.control_overlay
    play = button_by_name(overlay, "overlayPlayPause")
    previous = button_by_name(overlay, "overlayPrevious")
    next_button = button_by_name(overlay, "overlayNext")
    fullscreen = button_by_name(overlay, "overlayFullscreen")

    assert play.width() == 50 and play.height() == 50
    assert play.width() > previous.width()
    assert play.width() > next_button.width()
    assert play.width() > fullscreen.width()
    # Hit alanları büyütüldü (ikonlar 18 px aynı); play hâlâ en büyük.
    assert 36 <= previous.width() <= 40
    assert 36 <= next_button.width() <= 40
    assert 36 <= fullscreen.width() <= 40


def test_overlay_icons_and_time_text_use_the_approved_reference_scale(
        video_window):
    app, window, frame = video_window()
    overlay = frame.control_overlay
    assert button_by_name(overlay, "overlayPrevious").iconSize().width() == 30
    assert button_by_name(overlay, "overlayNext").iconSize().width() == 30
    assert button_by_name(overlay, "overlayPlayPause").iconSize().width() == 32
    for name in ("overlaySubtitles", "overlayVolume", "overlaySettings",
                 "overlayFullscreen"):
        assert button_by_name(overlay, name).iconSize().width() == 28, name
    assert frame._overlay_controls_row.spacing() == 0
    for label in (frame.overlay_current_time_label,
                  frame.overlay_time_separator,
                  frame.overlay_total_time_label):
        assert "font-size: 16px" in label.styleSheet()


def test_media_buttons_are_horizontally_centred_in_overlay(video_window):
    app, window, frame = video_window()
    overlay = frame.control_overlay
    play = button_by_name(overlay, "overlayPlayPause")
    play_centre = play.mapTo(overlay, play.rect().center()).x()

    assert abs(play_centre - overlay.width() // 2) <= 6


def test_previous_and_next_buttons_sit_directly_beside_play(video_window):
    app, window, frame = video_window()
    overlay = frame.control_overlay
    previous = button_by_name(overlay, "overlayPrevious")
    play = button_by_name(overlay, "overlayPlayPause")
    next_button = button_by_name(overlay, "overlayNext")

    assert play.geometry().left() - previous.geometry().right() == 1
    assert next_button.geometry().left() - play.geometry().right() == 1


# --- İkonlar, metin ve erişilebilirlik ---

def test_overlay_buttons_have_no_visible_text(video_window):
    app, window, frame = video_window()
    overlay = frame.control_overlay
    for name in BUTTON_NAMES:
        assert button_by_name(overlay, name).text() == ""


def test_overlay_buttons_keep_tooltip_and_accessible_name(video_window):
    app, window, frame = video_window()
    overlay = frame.control_overlay
    expected = {
        "overlayPrevious": "Önceki",
        "overlayPlayPause": "Oynat",
        "overlayNext": "Sonraki",
        "overlayFullscreen": "Tam Ekran",
    }
    for name, label in expected.items():
        button = button_by_name(overlay, name)
        assert button.toolTip() == label
        assert button.accessibleName() == label


def test_overlay_buttons_carry_non_null_icons(video_window):
    app, window, frame = video_window()
    overlay = frame.control_overlay
    for name in BUTTON_NAMES:
        button = button_by_name(overlay, name)
        assert not button.icon().isNull()
        assert not button.icon().pixmap(button.iconSize()).isNull()


def test_play_pause_icon_and_label_follow_real_is_paused_state(video_window):
    app, window, frame = video_window()
    button = button_by_name(frame.control_overlay, "overlayPlayPause")

    window.is_paused = True
    frame.update_overlay_play_state()
    paused_key = button.icon().pixmap(button.iconSize()).cacheKey()
    assert button.accessibleName() == "Oynat"
    assert button.toolTip() == "Oynat"

    window.is_paused = False
    frame.update_overlay_play_state()
    playing_key = button.icon().pixmap(button.iconSize()).cacheKey()
    assert button.accessibleName() == "Duraklat"
    assert button.toolTip() == "Duraklat"

    assert paused_key != playing_key
    assert button.text() == ""


# --- Yüzey görünümü ---

def test_overlay_surface_uses_gradient_without_capsule_border(video_window):
    app, window, frame = video_window()
    style = frame.control_overlay.styleSheet()

    assert "qlineargradient" in style
    assert "rgba(12, 12, 14, 220)" in style
    assert "border-radius" not in style.split("QPushButton")[0]
    assert "border: 1px solid" not in style


def test_timeline_uses_orange_accent_and_thin_groove(video_window):
    app, window, frame = video_window()
    style = frame.control_overlay.styleSheet().lower()

    assert "#f26a3d" in style
    assert "height: 3px" in style


def test_picture_in_picture_uses_only_a_compact_control_strip(video_window):
    app, window, frame = video_window()

    frame.set_picture_in_picture_mode(True)
    frame.update_overlay_geometry()

    assert frame.control_overlay.height() <= 56
    assert frame.overlay_timeline.height() == 18
    assert frame.overlay_play_pause_button.size() == QSize(32, 32)
    assert frame.overlay_previous_button.isVisible() is False
    assert frame.overlay_next_button.isVisible() is False
    assert frame.overlay_pip_exit_button.isVisible() is True
    assert frame.overlay_subtitles_button.isVisible() is False
    assert frame.overlay_volume_slider.isVisible() is False

    frame.set_picture_in_picture_mode(False)
    assert frame.overlay_timeline.height() == 48
    assert frame.overlay_play_pause_button.size() == QSize(50, 50)
    assert frame.overlay_previous_button.isVisible() is True
    assert frame.overlay_next_button.isVisible() is True
    assert frame.overlay_pip_exit_button.isVisible() is False


def test_picture_in_picture_play_border_is_visibly_round(video_window):
    app, window, frame = video_window()
    frame.set_picture_in_picture_mode(True)
    app.processEvents()

    image = frame.overlay_play_pause_button.grab().toImage()
    corner = image.pixelColor(1, 1)
    top_centre = image.pixelColor(image.width() // 2, 1)

    assert top_centre.red() > 200 and top_centre.green() < 150
    colour_distance = sum(abs(a - b) for a, b in zip(
        corner.getRgb()[:3], top_centre.getRgb()[:3]))
    assert colour_distance > 80


def test_picture_in_picture_restores_previously_open_playlist(video_window):
    app, window, frame = video_window()
    frame.playlist_panel.open_animated()
    frame.playlist_panel.finish_animation()
    assert frame.playlist_panel.is_open is True

    frame.set_picture_in_picture_mode(True)
    assert frame.playlist_panel.is_open is False
    assert frame.toggle_playlist_panel() is False

    frame.set_picture_in_picture_mode(False)
    app.processEvents()
    assert frame.playlist_panel.is_open is True


def test_picture_in_picture_video_press_starts_native_window_move(video_window):
    app, window, frame = video_window()
    calls = []
    frame.set_picture_in_picture_mode(True)
    frame._start_pip_system_move = lambda: calls.append("move") or True
    local = QPoint(200, 100)
    event = QMouseEvent(
        QEvent.Type.MouseButtonPress, local.toPointF(),
        frame.mapToGlobal(local).toPointF(), Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)

    frame.mousePressEvent(event)

    assert calls == ["move"]
    assert event.isAccepted()


def test_normal_video_press_does_not_start_window_move(video_window):
    app, window, frame = video_window()
    calls = []
    frame._start_pip_system_move = lambda: calls.append("move") or True
    local = QPoint(200, 100)
    event = QMouseEvent(
        QEvent.Type.MouseButtonPress, local.toPointF(),
        frame.mapToGlobal(local).toPointF(), Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)

    frame.mousePressEvent(event)

    assert calls == []


def test_time_labels_use_reference_colours(video_window):
    app, window, frame = video_window()

    assert "#F26A3D" in frame.overlay_current_time_label.styleSheet()
    assert frame.overlay_total_time_label.styleSheet() != ""


# --- Davranış korunumu ---

def test_overlay_controls_still_call_player_methods(video_window):
    app, window, frame = video_window()
    calls = []
    window.play_previous = lambda: calls.append("previous")
    window.play_pause = lambda: calls.append("play_pause")
    window.play_next = lambda: calls.append("next")
    window.toggle_fullscreen = lambda: calls.append("fullscreen")
    overlay = frame.control_overlay

    for name in BUTTON_NAMES:
        QTest.mouseClick(button_by_name(overlay, name), Qt.MouseButton.LeftButton)

    assert calls == ["previous", "play_pause", "next", "fullscreen"]


def test_legacy_classic_env_still_creates_the_overlay(video_window):
    """Ürün kararı: sinematik tasarım tek arayüz; overlay her zaman var."""
    app, window, frame = video_window(enabled=False)
    assert frame.control_overlay is not None
    assert hasattr(frame, "overlay_play_pause_button")
