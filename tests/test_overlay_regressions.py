# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, QPoint, QRect, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMainWindow, QSlider, QVBoxLayout, QWidget, QPushButton

from app.video_frame import VideoFrame


def make_video_window(monkeypatch, enabled):
    if enabled:
        monkeypatch.delenv("MLCPLAYER_CLASSIC_UI", raising=False)
    else:
        monkeypatch.setenv("MLCPLAYER_CLASSIC_UI", "1")
    app = QApplication.instance() or QApplication([])
    window = QMainWindow()
    window.central_widget = QWidget(window)
    window.setCentralWidget(window.central_widget)
    window.main_layout = QVBoxLayout(window.central_widget)
    window.current_file = "<test-video>"
    frame = VideoFrame(window)
    window.video_frame = frame
    window.main_layout.addWidget(frame)
    window.resize(900, 600)
    window.show()
    app.processEvents()
    return app, window, frame


def test_legacy_classic_env_still_creates_the_overlay(monkeypatch):
    """Ürün kararı: sinematik overlay her koşulda kurulur."""
    app, window, frame = make_video_window(monkeypatch, False)

    assert getattr(frame, "control_overlay", None) is not None
    window.close()
    app.processEvents()


def test_overlay_preview_is_owned_by_main_window(monkeypatch):
    app, window, frame = make_video_window(monkeypatch, True)

    overlay = frame.control_overlay
    assert overlay.parent() is window
    assert overlay.isWindow()
    assert overlay.isVisible()
    window.close()
    app.processEvents()


def test_overlay_aligns_to_video_bottom_and_follows_resize(monkeypatch):
    app, window, frame = make_video_window(monkeypatch, True)
    overlay = frame.control_overlay
    frame.update_overlay_geometry()
    first = overlay.geometry()

    frame.resize(1200, 700)
    app.processEvents()
    second = overlay.geometry()

    assert second.x() != first.x() or second.y() != first.y()
    assert second.bottom() <= frame.mapToGlobal(frame.rect().bottomRight()).y()
    window.close()
    app.processEvents()


def test_overlay_controls_call_existing_player_methods(monkeypatch):
    app, window, frame = make_video_window(monkeypatch, True)
    calls = []
    window.play_previous = lambda: calls.append("previous")
    window.play_pause = lambda: calls.append("play_pause")
    window.play_next = lambda: calls.append("next")
    window.toggle_fullscreen = lambda: calls.append("fullscreen")
    overlay = frame.control_overlay

    for name in ("overlayPrevious", "overlayPlayPause", "overlayNext",
                 "overlayFullscreen"):
        button = next(button for button in overlay.findChildren(QPushButton)
                      if button.objectName() == name)
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)

    assert calls == ["previous", "play_pause", "next", "fullscreen"]
    window.close()
    app.processEvents()


def test_overlay_follows_existing_fullscreen_flow(monkeypatch):
    app, window, frame = make_video_window(monkeypatch, True)
    frame.enter_fullscreen()
    app.processEvents()
    assert frame.control_overlay.isVisible()
    frame.exit_fullscreen()
    app.processEvents()
    assert frame.control_overlay.isVisible()
    window.close()
    app.processEvents()


def test_overlay_closes_with_main_window(monkeypatch):
    app, window, frame = make_video_window(monkeypatch, True)
    overlay = frame.control_overlay

    window.close()
    app.processEvents()

    assert not overlay.isVisible()


def _global_video_rect(frame):
    return QRect(frame.mapToGlobal(QPoint(0, 0)), frame.size())


def test_overlay_stays_inside_minimum_video_frame(monkeypatch):
    app, window, frame = make_video_window(monkeypatch, True)
    window.resize(400, 300)
    app.processEvents()
    frame.update_overlay_geometry()

    video_rect = _global_video_rect(frame)
    overlay_rect = frame.control_overlay.geometry()

    assert video_rect.contains(overlay_rect.topLeft())
    assert video_rect.contains(overlay_rect.bottomRight())
    window.close()
    app.processEvents()


def test_overlay_visibility_follows_minimize_hide_and_restore(monkeypatch):
    app, window, frame = make_video_window(monkeypatch, True)
    overlay = frame.control_overlay
    assert overlay.isVisible()

    window.showMinimized()
    app.processEvents()
    assert not overlay.isVisible()

    window.showNormal()
    window.show()
    app.processEvents()
    assert overlay.isVisible()

    window.hide()
    app.processEvents()
    assert not overlay.isVisible()

    window.show()
    app.processEvents()
    assert overlay.isVisible()
    assert _global_video_rect(frame).contains(overlay.geometry().topLeft())
    window.close()
    app.processEvents()


def test_overlay_fullscreen_geometry_stays_inside_video_frame(monkeypatch):
    app, window, frame = make_video_window(monkeypatch, True)
    frame.enter_fullscreen()
    app.processEvents()

    video_rect = _global_video_rect(frame)
    overlay_rect = frame.control_overlay.geometry()
    assert video_rect.contains(overlay_rect.topLeft())
    assert video_rect.contains(overlay_rect.bottomRight())

    frame.exit_fullscreen()
    window.close()
    app.processEvents()


def test_overlay_hides_on_normal_window_deactivation_and_restores(monkeypatch):
    app, window, frame = make_video_window(monkeypatch, True)
    other = QWidget()
    other.setWindowTitle("Other Window")
    other.show()
    app.processEvents()
    assert frame.control_overlay.isVisible()

    other.activateWindow()
    QApplication.setActiveWindow(other)
    QApplication.sendEvent(window, QEvent(QEvent.Type.WindowDeactivate))
    app.processEvents()
    assert not frame.control_overlay.isVisible()

    window.activateWindow()
    window.raise_()
    QApplication.setActiveWindow(window)
    QApplication.sendEvent(window, QEvent(QEvent.Type.WindowActivate))
    app.processEvents()
    assert frame.control_overlay.isVisible()
    other.close()
    window.close()
    app.processEvents()


def test_overlay_hides_on_fullscreen_deactivation_and_restores_clickable(monkeypatch):
    app, window, frame = make_video_window(monkeypatch, True)
    calls = []
    window.play_pause = lambda: calls.append("play_pause")
    frame.enter_fullscreen()
    app.processEvents()
    assert frame.control_overlay.isVisible()

    other = QWidget()
    other.setWindowTitle("Other Window")
    other.show()
    other.activateWindow()
    QApplication.setActiveWindow(other)
    frame._is_player_surface_active = lambda: False
    frame.eventFilter(frame, QEvent(QEvent.Type.WindowDeactivate))
    app.processEvents()
    assert not frame.control_overlay.isVisible()

    frame.activateWindow()
    frame.raise_()
    QApplication.setActiveWindow(frame)
    frame._is_player_surface_active = lambda: True
    frame.eventFilter(frame, QEvent(QEvent.Type.WindowActivate))
    app.processEvents()
    assert frame.control_overlay.isVisible()
    play_button = next(button for button in frame.control_overlay.findChildren(QPushButton)
                       if button.objectName() == "overlayPlayPause")
    QTest.mouseClick(play_button, Qt.MouseButton.LeftButton)
    assert calls == ["play_pause"]

    other.close()
    frame.exit_fullscreen()
    window.close()
    app.processEvents()
