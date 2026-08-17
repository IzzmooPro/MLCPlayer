# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Overlay göster/gizle geçişlerindeki fade animasyonu regresyon testleri.

Testler gerçek 2.5 sn beklemez; animasyon deterministik biçimde
setCurrentTime() ile sürülür veya kısa kontrollü event-loop beklemesi
kullanılır.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import (QAbstractAnimation, QEasingCurve, QElapsedTimer,
                          QEvent, QPoint, QPropertyAnimation, QSettings, Qt)
from PyQt6.QtGui import QEnterEvent, QMouseEvent
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QSlider, QVBoxLayout, QWidget)

from app.config import MAX_VOLUME
from app.video_frame import (OVERLAY_FADE_IN_MS, OVERLAY_FADE_OUT_MS,
                             VideoFrame)


@pytest.fixture
def video_window(monkeypatch, tmp_path):
    created = []
    app_ref = []

    def qt_app():
        app = QApplication.instance() or QApplication([])
        if not app_ref:
            app_ref.append(app)
        return app

    def factory(enabled=True, playing=True, size=(1280, 720)):
        if enabled:
            monkeypatch.delenv("MLCPLAYER_CLASSIC_UI", raising=False)
        else:
            monkeypatch.setenv("MLCPLAYER_CLASSIC_UI", "1")
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                          str(tmp_path))
        app = qt_app()
        window = QMainWindow()
        window.central_widget = QWidget(window)
        window.setCentralWidget(window.central_widget)
        window.main_layout = QVBoxLayout(window.central_widget)
        window.main_layout.setContentsMargins(0, 0, 0, 0)
        window.duration = 100.0
        window.position = 10.0
        window.is_muted = False
        window.is_paused = not playing
        window.current_file = "<test-video>" if playing else ""
        window.volume_slider = QSlider(Qt.Orientation.Horizontal)
        window.volume_slider.setRange(0, MAX_VOLUME)
        window.volume_slider.setValue(70)
        for name in ("play_previous", "play_next", "play_pause", "toggle_mute",
                     "toggle_subtitles", "toggle_fullscreen",
                     "setup_video_adjustments"):
            setattr(window, name, lambda: None)
        frame = VideoFrame(window)
        window.video_frame = frame
        window.main_layout.addWidget(frame)
        window.resize(*size)
        window.show()
        app.processEvents()
        frame.update_overlay_geometry()
        if frame.control_overlay is not None:
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


def finish_fade(app, frame, limit_ms=1500):
    """Çalışan fade'i deterministik biçimde sonuna kadar sürer."""
    animation = frame.overlay_fade
    if animation is None:
        return
    if animation.state() == QAbstractAnimation.State.Running:
        animation.setCurrentTime(animation.duration())
    clock = QElapsedTimer()
    clock.start()
    while (animation.state() == QAbstractAnimation.State.Running
           and clock.elapsed() < limit_ms):
        app.processEvents()
    app.processEvents()


def send_mouse_move(widget, app):
    centre = widget.rect().center()
    event = QMouseEvent(QEvent.Type.MouseMove, centre.toPointF(),
                        widget.mapToGlobal(centre).toPointF(),
                        Qt.MouseButton.NoButton, Qt.MouseButton.NoButton,
                        Qt.KeyboardModifier.NoModifier)
    app.sendEvent(widget, event)
    app.processEvents()


def send_enter(widget, app):
    centre = widget.rect().center().toPointF()
    event = QEnterEvent(centre, centre,
                        widget.mapToGlobal(widget.rect().center()).toPointF())
    app.sendEvent(widget, event)
    app.processEvents()


# --- Animasyon nesnesi ---

def test_fade_animation_exists_when_preview_enabled(video_window):
    app, window, frame = video_window()
    assert isinstance(frame.overlay_fade, QPropertyAnimation)
    assert frame.overlay_fade.propertyName() == b"windowOpacity"
    assert frame.overlay_fade.targetObject() is frame.control_overlay


def test_fade_animation_exists_even_with_legacy_classic_env(video_window):
    """Legacy klasik anahtar artık fade/overlay kurulumunu engellemez."""
    app, window, frame = video_window(enabled=False)
    assert frame.control_overlay is not None
    assert getattr(frame, "overlay_hide_timer", None) is not None


def test_fade_durations_match_constants(video_window):
    app, window, frame = video_window()
    assert OVERLAY_FADE_IN_MS == 140
    assert OVERLAY_FADE_OUT_MS == 180

    frame.fade_overlay_in()
    assert frame.overlay_fade.duration() == OVERLAY_FADE_IN_MS
    assert frame.overlay_fade.easingCurve().type() == QEasingCurve.Type.OutCubic
    finish_fade(app, frame)

    frame.fade_overlay_out()
    assert frame.overlay_fade.duration() == OVERLAY_FADE_OUT_MS
    assert frame.overlay_fade.easingCurve().type() == QEasingCurve.Type.InCubic
    finish_fade(app, frame)


def test_same_animation_object_is_reused(video_window):
    app, window, frame = video_window()
    first = frame.overlay_fade
    for _ in range(4):
        frame.fade_overlay_out()
        finish_fade(app, frame)
        frame.fade_overlay_in()
        finish_fade(app, frame)
    assert frame.overlay_fade is first


# --- Auto-hide fade-out ---

def test_inactivity_timeout_does_not_hide_immediately(video_window):
    app, window, frame = video_window()
    frame.hide_overlay_for_inactivity()
    app.processEvents()

    assert frame.control_overlay.isVisible()
    assert frame.overlay_fade.state() == QAbstractAnimation.State.Running
    assert frame._overlay_auto_hidden is True


def test_overlay_hides_when_fade_out_completes(video_window):
    app, window, frame = video_window()
    frame.hide_overlay_for_inactivity()
    finish_fade(app, frame)

    assert not frame.control_overlay.isVisible()
    assert frame._overlay_auto_hidden is True


def test_fade_out_opacity_decreases_monotonically(video_window):
    app, window, frame = video_window()
    frame.hide_overlay_for_inactivity()
    animation = frame.overlay_fade

    samples = []
    for step in (0, 45, 90, 135, OVERLAY_FADE_OUT_MS):
        animation.setCurrentTime(step)
        samples.append(round(frame.control_overlay.windowOpacity(), 4))

    assert samples[0] == pytest.approx(1.0, abs=0.01)
    assert samples == sorted(samples, reverse=True), samples
    assert samples[-1] == pytest.approx(0.0, abs=0.01)


def test_fade_in_opacity_increases_monotonically(video_window):
    app, window, frame = video_window()
    frame.hide_overlay_for_inactivity()
    finish_fade(app, frame)

    frame.fade_overlay_in()
    animation = frame.overlay_fade
    samples = []
    for step in (0, 35, 70, 105, OVERLAY_FADE_IN_MS):
        animation.setCurrentTime(step)
        samples.append(round(frame.control_overlay.windowOpacity(), 4))

    assert samples == sorted(samples), samples
    assert samples[-1] == pytest.approx(1.0, abs=0.01)


def test_final_opacity_is_normalised(video_window):
    app, window, frame = video_window()
    frame.fade_overlay_in()
    finish_fade(app, frame)
    assert frame.control_overlay.windowOpacity() == 1.0

    frame.hide_overlay_for_inactivity()
    finish_fade(app, frame)
    assert frame.control_overlay.windowOpacity() == 0.0


# --- Kesilme ---

def test_mouse_move_during_fade_out_reverses_without_hiding(video_window):
    app, window, frame = video_window()
    frame.hide_overlay_for_inactivity()
    animation = frame.overlay_fade
    animation.setCurrentTime(90)
    midway = frame.control_overlay.windowOpacity()
    assert 0.0 < midway < 1.0

    send_mouse_move(frame, app)

    assert frame.control_overlay.isVisible()
    assert frame.overlay_fade.endValue() == 1.0
    assert frame.control_overlay.windowOpacity() <= midway + 0.05
    finish_fade(app, frame)
    assert frame.control_overlay.isVisible()
    assert frame.control_overlay.windowOpacity() == 1.0


def test_fade_out_during_fade_in_starts_from_current_opacity(video_window):
    app, window, frame = video_window()
    frame.hide_overlay_for_inactivity()
    finish_fade(app, frame)

    frame.fade_overlay_in()
    frame.overlay_fade.setCurrentTime(35)
    midway = frame.control_overlay.windowOpacity()
    assert 0.0 < midway < 1.0

    frame.fade_overlay_out()
    assert frame.overlay_fade.startValue() == pytest.approx(midway, abs=0.02)
    assert frame.control_overlay.windowOpacity() <= midway + 0.02


# --- Anında gizlenmesi gereken durumlar ---

def test_minimize_hides_immediately_without_fade(video_window):
    app, window, frame = video_window()
    window.showMinimized()
    app.processEvents()

    assert not frame.control_overlay.isVisible()
    assert frame.overlay_fade.state() != QAbstractAnimation.State.Running


def test_owner_hide_hides_immediately_without_fade(video_window):
    app, window, frame = video_window()
    window.hide()
    app.processEvents()

    assert not frame.control_overlay.isVisible()
    assert frame.overlay_fade.state() != QAbstractAnimation.State.Running


def test_window_deactivate_hides_immediately_without_fade(video_window):
    app, window, frame = video_window()
    frame._is_player_surface_active = lambda: False
    frame.eventFilter(window, QEvent(QEvent.Type.WindowDeactivate))
    app.processEvents()

    assert not frame.control_overlay.isVisible()
    assert frame.overlay_fade.state() != QAbstractAnimation.State.Running
    assert frame._overlay_auto_hidden is False


def test_close_stops_animation_and_hides(video_window):
    app, window, frame = video_window()
    frame.fade_overlay_out()
    frame.close_control_overlay()
    app.processEvents()

    assert not frame.control_overlay.isVisible()
    assert frame.overlay_fade.state() != QAbstractAnimation.State.Running


# --- Oynatma state ---

def test_paused_fades_in_and_stops_timer(video_window):
    app, window, frame = video_window()
    frame.hide_overlay_for_inactivity()
    finish_fade(app, frame)

    window.is_paused = True
    frame.update_overlay_play_state()
    finish_fade(app, frame)

    assert frame.control_overlay.isVisible()
    assert frame.control_overlay.windowOpacity() == 1.0
    assert not frame.overlay_hide_timer.isActive()


def test_resume_restarts_auto_hide_timer(video_window):
    app, window, frame = video_window()
    window.is_paused = True
    frame.update_overlay_play_state()
    finish_fade(app, frame)

    window.is_paused = False
    frame.update_overlay_play_state()
    finish_fade(app, frame)

    assert frame.control_overlay.isVisible()
    assert frame.overlay_hide_timer.isActive()
    assert frame.overlay_hide_timer.interval() == 2500


# --- Hover ve slider ---

def test_hover_blocks_fade_out(video_window):
    app, window, frame = video_window()
    send_enter(frame.control_overlay, app)
    frame.hide_overlay_for_inactivity()
    app.processEvents()

    assert frame.control_overlay.isVisible()
    assert frame.overlay_fade.state() != QAbstractAnimation.State.Running


@pytest.mark.parametrize("slider_name", ("overlay_timeline", "overlay_volume_slider"))
def test_slider_press_blocks_fade_out(video_window, slider_name):
    app, window, frame = video_window()
    slider = getattr(frame, slider_name)
    slider.setSliderDown(True)

    frame.hide_overlay_for_inactivity()
    app.processEvents()

    assert frame.control_overlay.isVisible()
    assert frame.overlay_fade.state() != QAbstractAnimation.State.Running
    slider.setSliderDown(False)


def test_slider_press_during_fade_out_returns_to_fade_in(video_window):
    app, window, frame = video_window()
    frame.hide_overlay_for_inactivity()
    frame.overlay_fade.setCurrentTime(90)
    assert frame.overlay_fade.state() == QAbstractAnimation.State.Running

    slider = frame.overlay_timeline
    slider.setSliderDown(True)
    frame.show_overlay_for_interaction()
    app.processEvents()

    assert frame.overlay_fade.endValue() == 1.0
    finish_fade(app, frame)
    assert frame.control_overlay.isVisible()
    slider.setSliderDown(False)


# --- Geometri ve fullscreen ---

def test_resize_does_not_reveal_faded_out_overlay(video_window):
    app, window, frame = video_window()
    frame.hide_overlay_for_inactivity()
    finish_fade(app, frame)

    window.resize(1000, 640)
    app.processEvents()
    frame.update_overlay_geometry()
    app.processEvents()

    assert not frame.control_overlay.isVisible()


def test_fullscreen_enter_and_exit_fade_in(video_window):
    app, window, frame = video_window()
    frame.hide_overlay_for_inactivity()
    finish_fade(app, frame)

    frame.enter_fullscreen()
    finish_fade(app, frame)
    assert frame.control_overlay.isVisible()
    assert frame.control_overlay.windowOpacity() == 1.0

    frame.hide_overlay_for_inactivity()
    finish_fade(app, frame)
    assert not frame.control_overlay.isVisible()

    frame.exit_fullscreen()
    finish_fade(app, frame)
    assert frame.control_overlay.isVisible()
    assert frame.control_overlay.windowOpacity() == 1.0


def test_activation_fades_overlay_back_in(video_window):
    app, window, frame = video_window()
    frame._is_player_surface_active = lambda: False
    frame.eventFilter(window, QEvent(QEvent.Type.WindowDeactivate))
    app.processEvents()
    assert not frame.control_overlay.isVisible()

    frame._is_player_surface_active = lambda: True
    frame.eventFilter(window, QEvent(QEvent.Type.WindowActivate))
    finish_fade(app, frame)

    assert frame.control_overlay.isVisible()
    assert frame.control_overlay.windowOpacity() == 1.0
