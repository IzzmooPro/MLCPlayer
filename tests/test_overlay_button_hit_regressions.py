# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Overlay düğmelerinin tıklama güvenilirliği: hit alanı + fade yaşam döngüsü.

A) Görünür overlay üzerinde her düğmenin beş noktasında gerçek tıklama.
B) Fade-in / fade-out / tamamen gizli durumlarında tıklama davranışı.
"""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import (QAbstractAnimation, QEvent, QPoint, QRect, QSettings,
                          Qt)
from PyQt6.QtGui import QContextMenuEvent, QMouseEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import (
    QApplication, QLabel, QMainWindow, QPushButton, QSlider, QVBoxLayout,
    QWidget)

from app.config import MAX_VOLUME
from app.video_frame import VideoFrame

# Düğme -> tetiklemesi beklenen gerçek player metodu
BUTTON_METHODS = {
    "overlaySubtitles": "toggle_subtitles",
    "overlayVolume": "toggle_mute",
    "overlaySettings": "setup_video_adjustments",
    "overlayFullscreen": "toggle_fullscreen",
    "overlayPrevious": "play_previous",
    "overlayNext": "play_next",
    "overlayPlayPause": "play_pause",
}

# Kullanıcı için rahat kabul edilen minimum hit alanı
MIN_BUTTON_SIDE = 40


@pytest.fixture
def product_window(monkeypatch, tmp_path):
    created = []
    app_ref = []

    def qt_app():
        app = QApplication.instance() or QApplication([])
        if not app_ref:
            app_ref.append(app)
        return app

    def factory(size=(1280, 720)):
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
        window.position = 10.0
        window.is_paused = False
        window.is_muted = False
        window.current_file = "<test-video>"
        window._updating_position_slider = False
        window.volume_slider = QSlider(Qt.Orientation.Horizontal)
        window.volume_slider.setRange(0, MAX_VOLUME)
        window.volume_slider.setValue(70)
        window.position_slider = QSlider()
        window.current_time_label = QLabel()
        window.total_time_label = QLabel()
        window.play_button = SimpleNamespace(setIcon=lambda icon: None)
        window.play_icon = object()
        window.pause_icon = object()
        window.update_time_label = lambda: None
        window.mpv_player = SimpleNamespace(
            time_pos=0.0, pause=False, sub_visibility=False, sid=None,
            track_list=[{"id": 1, "type": "sub"}], stop=lambda: None)
        window.seek_position = lambda value: None
        window.calls = []
        for name in set(BUTTON_METHODS.values()):
            setattr(window, name,
                    lambda name=name: window.calls.append(name))

        frame = VideoFrame(window)
        window.video_frame = frame
        window.main_layout.addWidget(frame)
        window.resize(*size)
        window.show()
        app.processEvents()
        frame.update_overlay_geometry()
        frame.show_overlay_for_interaction()
        finish_fade(app, frame)
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


def finish_fade(app, frame):
    animation = getattr(frame, "overlay_fade", None)
    if animation is None:
        return
    if animation.state() == QAbstractAnimation.State.Running:
        animation.setCurrentTime(animation.duration())
    app.processEvents()


def button_by_name(frame, name):
    return next(b for b in frame.control_overlay.findChildren(QPushButton)
                if b.objectName() == name)


def hit_points(button, inset=3):
    """Merkez + dört köşeden `inset` px içeri."""
    width, height = button.width(), button.height()
    return {
        "centre": QPoint(width // 2, height // 2),
        "top_left": QPoint(inset, inset),
        "top_right": QPoint(width - 1 - inset, inset),
        "bottom_left": QPoint(inset, height - 1 - inset),
        "bottom_right": QPoint(width - 1 - inset, height - 1 - inset),
    }


def product_surface_widget_at(frame, global_point):
    """Platformun desteklediği en güçlü hit-test sonucunu döndürür.

    Gerçek Qt/Windows oturumunda sistem çapındaki ``widgetAt`` kullanılır.
    Offscreen eklentisi onu uygulamadığından aynı global nokta overlay'in
    koordinatına çevrilip Qt çocuk ağacında çözülür. İkinci yol geometri,
    görünürlük ve kardeş-widget örtüşmesini kanıtlar; native HWND z-order
    kanıtı değildir.
    """
    if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
        return QApplication.widgetAt(global_point)
    overlay = frame.control_overlay
    return overlay.childAt(overlay.mapFromGlobal(global_point))


def test_fullscreen_and_other_overlay_buttons_use_pointing_hand_cursor(
        product_window):
    app, window, frame = product_window()

    for name in BUTTON_METHODS:
        assert button_by_name(frame, name).cursor().shape() == (
            Qt.CursorShape.PointingHandCursor), name


def test_double_click_on_noninteractive_overlay_surface_toggles_fullscreen(
        product_window):
    app, window, frame = product_window()
    overlay = frame.control_overlay
    point = QPoint(overlay.width() // 2, 4)
    event = QMouseEvent(
        QEvent.Type.MouseButtonDblClick, point.toPointF(),
        overlay.mapToGlobal(point).toPointF(), Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)

    QApplication.sendEvent(overlay, event)
    app.processEvents()

    assert window.calls == ["toggle_fullscreen"]
    assert event.isAccepted()


def test_right_click_on_noninteractive_overlay_surface_opens_video_menu(
        product_window):
    app, window, frame = product_window()
    overlay = frame.control_overlay
    opened = []
    fake_menu = SimpleNamespace(exec=lambda point: opened.append(QPoint(point)))
    frame.build_context_menu = lambda: fake_menu
    point = QPoint(overlay.width() // 2, 4)
    global_point = overlay.mapToGlobal(point)
    event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, point,
                              global_point)

    QApplication.sendEvent(overlay, event)
    app.processEvents()

    assert opened == [global_point]
    assert event.isAccepted()


# --- A. Görünür overlay üzerinde hit alanı ---

@pytest.mark.parametrize("name", list(BUTTON_METHODS))
def test_every_corner_click_reaches_the_player_method(product_window, name):
    app, window, frame = product_window()
    button = button_by_name(frame, name)
    expected = BUTTON_METHODS[name]

    for label, point in hit_points(button).items():
        window.calls.clear()
        QTest.mouseClick(button, Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier(0), point)
        app.processEvents()
        assert window.calls == [expected], (
            f"{name} {label} noktası: {window.calls}")


@pytest.mark.parametrize("name", list(BUTTON_METHODS))
def test_product_surface_hit_test_resolves_to_the_button(product_window, name):
    app, window, frame = product_window()
    button = button_by_name(frame, name)

    for label, point in hit_points(button).items():
        target = product_surface_widget_at(frame, button.mapToGlobal(point))
        assert target is not None, f"{name} {label}: hit-test boş"
        assert target is button or target.isAncestorOf(button) is False, (
            f"{name} {label}: {target.objectName() or type(target).__name__}")
        assert target is button, (
            f"{name} {label} tıklaması {target.objectName() or type(target).__name__} "
            "üzerine düşüyor")


def test_repeated_resize_keeps_visible_button_hits_and_clicks(product_window):
    app, window, frame = product_window()
    sizes = ((480, 300), (760, 430), (1280, 720), (560, 340),
             (1600, 900), (480, 300), (1280, 720))

    for width, height in sizes:
        window.resize(width, height)
        app.processEvents()
        frame.update_overlay_geometry()
        frame.show_overlay_for_interaction()
        finish_fade(app, frame)
        app.processEvents()

        visible = [button_by_name(frame, name) for name in BUTTON_METHODS
                   if button_by_name(frame, name).isVisible()]
        assert button_by_name(frame, "overlayPlayPause").isVisible()
        assert visible
        for button in visible:
            expected = BUTTON_METHODS[button.objectName()]
            point = button.rect().center()
            assert product_surface_widget_at(
                frame, button.mapToGlobal(point)) is button
            window.calls.clear()
            QTest.mouseClick(button, Qt.MouseButton.LeftButton,
                             Qt.KeyboardModifier(0), point)
            app.processEvents()
            assert window.calls == [expected], (
                width, height, button.objectName(), window.calls)


@pytest.mark.parametrize("name", ("overlaySubtitles", "overlayVolume",
                                  "overlaySettings", "overlayFullscreen"))
def test_right_group_buttons_have_a_comfortable_hit_area(product_window, name):
    app, window, frame = product_window()
    button = button_by_name(frame, name)
    assert button.width() >= MIN_BUTTON_SIDE, (
        f"{name} genişliği {button.width()} px, en az {MIN_BUTTON_SIDE} olmalı")
    assert button.height() >= MIN_BUTTON_SIDE


@pytest.mark.parametrize("name", ("overlayPrevious", "overlayNext"))
def test_skip_buttons_have_a_comfortable_hit_area(product_window, name):
    app, window, frame = product_window()
    button = button_by_name(frame, name)
    assert button.width() >= 36
    assert button.height() >= 36


def test_icon_sizes_match_the_approved_reference_scale(product_window):
    app, window, frame = product_window()
    for name in ("overlaySubtitles", "overlayVolume", "overlaySettings",
                 "overlayFullscreen"):
        button = button_by_name(frame, name)
        assert button.iconSize().width() == 22, name
    assert button_by_name(frame, "overlayPrevious").iconSize().width() == 25
    assert button_by_name(frame, "overlayNext").iconSize().width() == 25
    assert button_by_name(frame, "overlayPlayPause").iconSize().width() == 27


def test_button_hit_areas_do_not_overlap_each_other(product_window):
    app, window, frame = product_window()
    rects = []
    for name in BUTTON_METHODS:
        button = button_by_name(frame, name)
        rects.append((name, QRect(button.mapToGlobal(QPoint(0, 0)),
                                  button.size())))
    for index, (name_a, rect_a) in enumerate(rects):
        for name_b, rect_b in rects[index + 1:]:
            assert not rect_a.intersects(rect_b), f"{name_a} ↔ {name_b}"


def test_button_hit_areas_do_not_touch_the_timeline(product_window):
    app, window, frame = product_window()
    timeline_rect = QRect(frame.overlay_timeline.mapToGlobal(QPoint(0, 0)),
                          frame.overlay_timeline.size())
    for name in BUTTON_METHODS:
        button = button_by_name(frame, name)
        rect = QRect(button.mapToGlobal(QPoint(0, 0)), button.size())
        assert not timeline_rect.intersects(rect), name


def test_minimum_window_keeps_buttons_inside_the_overlay(product_window):
    app, window, frame = product_window(size=(400, 300))
    app.processEvents()
    frame.update_overlay_geometry()
    overlay_rect = frame.control_overlay.geometry()

    for name in BUTTON_METHODS:
        button = button_by_name(frame, name)
        rect = QRect(button.mapToGlobal(QPoint(0, 0)), button.size())
        assert overlay_rect.contains(rect), f"{name} taştı: {rect}"


def test_minimum_window_keeps_a_usable_volume_slider(product_window):
    app, window, frame = product_window(size=(400, 300))
    app.processEvents()
    frame.update_overlay_geometry()
    assert frame.overlay_volume_slider.width() >= 30


# --- B. Fade yaşam döngüsü ---

def test_click_works_while_fully_visible(product_window):
    app, window, frame = product_window()
    assert frame.control_overlay.windowOpacity() == 1.0
    QTest.mouseClick(button_by_name(frame, "overlayVolume"),
                     Qt.MouseButton.LeftButton)
    app.processEvents()
    assert window.calls == ["toggle_mute"]


@pytest.mark.parametrize("progress", (0.3, 0.55, 0.8))
def test_click_works_during_fade_in(product_window, progress):
    app, window, frame = product_window()
    frame.hide_overlay_for_inactivity()
    finish_fade(app, frame)

    frame.fade_overlay_in()
    animation = frame.overlay_fade
    animation.setCurrentTime(int(animation.duration() * progress))
    app.processEvents()
    assert 0.0 < frame.control_overlay.windowOpacity() < 1.0

    window.calls.clear()
    QTest.mouseClick(button_by_name(frame, "overlaySettings"),
                     Qt.MouseButton.LeftButton)
    app.processEvents()

    assert window.calls == ["setup_video_adjustments"]


def test_click_during_fade_out_reverses_and_fires_once(product_window):
    app, window, frame = product_window()
    frame.hide_overlay_for_inactivity()
    animation = frame.overlay_fade
    animation.setCurrentTime(int(animation.duration() * 0.5))
    app.processEvents()
    assert frame.control_overlay.isVisible()

    window.calls.clear()
    QTest.mouseClick(button_by_name(frame, "overlayFullscreen"),
                     Qt.MouseButton.LeftButton)
    app.processEvents()

    assert window.calls == ["toggle_fullscreen"]
    assert frame.control_overlay.isVisible()
    assert frame.overlay_fade.endValue() == 1.0


def test_hidden_overlay_produces_no_button_action(product_window):
    app, window, frame = product_window()
    frame.hide_overlay_for_inactivity()
    finish_fade(app, frame)
    assert not frame.control_overlay.isVisible()

    window.calls.clear()
    button = button_by_name(frame, "overlayVolume")
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    app.processEvents()

    assert window.calls == []


def test_first_click_after_becoming_visible_is_not_swallowed(product_window):
    app, window, frame = product_window()
    frame.hide_overlay_for_inactivity()
    finish_fade(app, frame)

    # Fare hareketi overlay'i geri getirir
    frame.show_overlay_for_interaction()
    finish_fade(app, frame)
    assert frame.control_overlay.isVisible()

    window.calls.clear()
    QTest.mouseClick(button_by_name(frame, "overlaySubtitles"),
                     Qt.MouseButton.LeftButton)
    app.processEvents()

    assert window.calls == ["toggle_subtitles"], "ilk tıklama kayboldu"


def test_click_is_not_delivered_twice(product_window):
    app, window, frame = product_window()
    window.calls.clear()
    QTest.mouseClick(button_by_name(frame, "overlayNext"),
                     Qt.MouseButton.LeftButton)
    app.processEvents()
    assert window.calls == ["play_next"]


def test_button_press_keeps_overlay_visible(product_window):
    app, window, frame = product_window()
    button = button_by_name(frame, "overlayVolume")
    QTest.mousePress(button, Qt.MouseButton.LeftButton)
    app.processEvents()
    assert frame.control_overlay.isVisible()
    assert frame._overlay_auto_hidden is False
    QTest.mouseRelease(button, Qt.MouseButton.LeftButton)
    app.processEvents()
