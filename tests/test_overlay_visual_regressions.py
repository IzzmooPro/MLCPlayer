"""Sinematik overlay görsel yapısı regresyon testleri.

Testler gerçek widget geometrisini, gerçek QIcon içeriğini ve gerçek oynatma
state bağlantısını ölçer; sabit/sahte state assert'i kullanılmaz.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QPoint, QRect, Qt
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


def test_overlay_content_has_side_padding(video_window):
    app, window, frame = video_window()
    margins = frame.control_overlay.layout().contentsMargins()
    assert 24 <= margins.left() <= 32
    assert 24 <= margins.right() <= 32


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

    assert abs(frame.overlay_timeline.width() - expected) <= 2
    # NOT: Görsel groove 3 px kalır; widget yüksekliği gerçek kullanıcı
    # tıklamaları için genişletildi (bkz. test_overlay_timeline_hit_regressions).
    assert frame.overlay_timeline.height() <= 48


def test_center_play_button_is_larger_than_other_media_buttons(video_window):
    app, window, frame = video_window()
    overlay = frame.control_overlay
    play = button_by_name(overlay, "overlayPlayPause")
    previous = button_by_name(overlay, "overlayPrevious")
    next_button = button_by_name(overlay, "overlayNext")
    fullscreen = button_by_name(overlay, "overlayFullscreen")

    assert 40 <= play.width() <= 48 and 40 <= play.height() <= 48
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
    assert button_by_name(overlay, "overlayPrevious").iconSize().width() == 25
    assert button_by_name(overlay, "overlayNext").iconSize().width() == 25
    assert button_by_name(overlay, "overlayPlayPause").iconSize().width() == 27
    for name in ("overlaySubtitles", "overlayVolume", "overlaySettings",
                 "overlayFullscreen"):
        assert button_by_name(overlay, name).iconSize().width() == 22, name
    assert frame._overlay_controls_row.spacing() == 8
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
