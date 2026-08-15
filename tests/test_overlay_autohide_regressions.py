"""Sinematik overlay otomatik gizlenme regresyon testleri.

Testler 2500 ms gerçek bekleme kullanmaz; timer slotu deterministik biçimde
çalıştırılır. Gerçek süre ölçümü ayrı Windows smoke testinde yapılır.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import (QAbstractAnimation, QElapsedTimer, QEvent,
                          QPoint, QSettings, Qt)
from PyQt6.QtGui import QEnterEvent, QMouseEvent
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QSlider, QVBoxLayout, QWidget)

from app.config import MAX_VOLUME
from app.video_frame import OVERLAY_AUTO_HIDE_MS, VideoFrame


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
    """Fade animasyonunu deterministik biçimde sonuna kadar sürer.

    Auto-hide artık anında gizlemez; 180 ms fade-out sonunda gizler.
    """
    animation = getattr(frame, "overlay_fade", None)
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
    event = QMouseEvent(QEvent.Type.MouseMove, widget.rect().center().toPointF(),
                        widget.mapToGlobal(widget.rect().center()).toPointF(),
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


def send_leave(widget, app):
    app.sendEvent(widget, QEvent(QEvent.Type.Leave))
    app.processEvents()


def send_mouse_button(widget, app, event_type):
    centre = widget.rect().center().toPointF()
    event = QMouseEvent(event_type, centre,
                        widget.mapToGlobal(widget.rect().center()).toPointF(),
                        Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton,
                        Qt.KeyboardModifier.NoModifier)
    app.sendEvent(widget, event)
    app.processEvents()


# --- 1. Preview açık, video oynuyor ---

def test_auto_hide_timer_exists_and_is_single_shot(video_window):
    app, window, frame = video_window()
    timer = frame.overlay_hide_timer
    assert timer is not None
    assert timer.isSingleShot()
    assert timer.interval() == OVERLAY_AUTO_HIDE_MS == 2500


def test_timer_is_active_while_video_plays(video_window):
    app, window, frame = video_window()
    assert frame.overlay_hide_timer.isActive()


def test_timeout_hides_overlay_while_video_plays(video_window):
    app, window, frame = video_window()
    assert frame.control_overlay.isVisible()

    frame.hide_overlay_for_inactivity()
    finish_fade(app, frame)

    assert not frame.control_overlay.isVisible()


# --- 2. Preview kapalı ---

def test_auto_hide_timer_exists_even_with_legacy_classic_env(video_window):
    """Legacy klasik anahtar artık sinematik overlay'i kapatamaz."""
    app, window, frame = video_window(enabled=False)
    assert frame.control_overlay is not None
    assert getattr(frame, "overlay_hide_timer", None) is not None


def test_helpers_are_safe_with_legacy_classic_env(video_window):
    app, window, frame = video_window(enabled=False)
    frame.show_overlay_for_interaction()
    frame.schedule_overlay_hide()
    frame.cancel_overlay_hide()
    frame.hide_overlay_for_inactivity()
    assert frame.control_overlay is not None


# --- 3. Video yok ---

def test_timeout_does_not_hide_overlay_without_media(video_window):
    app, window, frame = video_window(playing=False)
    window.current_file = ""
    frame.hide_overlay_for_inactivity()
    app.processEvents()
    assert frame.control_overlay.isVisible()


def test_timer_is_not_scheduled_without_media(video_window):
    app, window, frame = video_window(playing=False)
    window.current_file = ""
    frame.schedule_overlay_hide()
    assert not frame.overlay_hide_timer.isActive()


# --- 4. Duraklatılmış ---

def test_timeout_does_not_hide_overlay_when_paused(video_window):
    app, window, frame = video_window()
    window.is_paused = True
    frame.hide_overlay_for_inactivity()
    app.processEvents()
    assert frame.control_overlay.isVisible()


def test_timer_is_cancelled_when_paused(video_window):
    app, window, frame = video_window()
    window.is_paused = True
    frame.update_overlay_play_state()
    assert not frame.overlay_hide_timer.isActive()
    assert frame.control_overlay.isVisible()


# --- 5. Mouse hareketi ---

def test_mouse_move_on_video_frame_restores_hidden_overlay(video_window):
    app, window, frame = video_window()
    frame.hide_overlay_for_inactivity()
    finish_fade(app, frame)
    assert not frame.control_overlay.isVisible()

    send_mouse_move(frame, app)
    finish_fade(app, frame)

    assert frame.control_overlay.isVisible()
    assert frame.overlay_hide_timer.isActive()


def test_mouse_move_keeps_cursor_behaviour(video_window):
    """Mevcut cursor davranışı bozulmamalı."""
    app, window, frame = video_window()
    frame.enter_fullscreen()
    app.processEvents()
    frame.setCursor(Qt.CursorShape.BlankCursor)
    send_mouse_move(frame, app)
    assert frame.cursor().shape() == Qt.CursorShape.ArrowCursor
    assert frame.cursor_timer.isActive()


# --- 6. Overlay hover ---

def test_overlay_enter_cancels_the_hide_timer(video_window):
    app, window, frame = video_window()
    send_enter(frame.control_overlay, app)
    assert not frame.overlay_hide_timer.isActive()


def test_timeout_does_not_hide_overlay_while_hovered(video_window):
    app, window, frame = video_window()
    send_enter(frame.control_overlay, app)
    frame.hide_overlay_for_inactivity()
    app.processEvents()
    assert frame.control_overlay.isVisible()


def test_overlay_leave_reschedules_hide_while_playing(video_window):
    app, window, frame = video_window()
    send_enter(frame.control_overlay, app)
    assert not frame.overlay_hide_timer.isActive()

    send_leave(frame.control_overlay, app)
    assert frame.overlay_hide_timer.isActive()


# --- 7. Timeline ve ses slider'ı ---

@pytest.mark.parametrize("slider_name", ("overlay_timeline", "overlay_volume_slider"))
def test_timeout_does_not_hide_overlay_while_slider_is_pressed(video_window,
                                                               slider_name):
    app, window, frame = video_window()
    slider = getattr(frame, slider_name)
    slider.setSliderDown(True)

    frame.hide_overlay_for_inactivity()
    app.processEvents()

    assert frame.control_overlay.isVisible()
    slider.setSliderDown(False)


@pytest.mark.parametrize("slider_name", ("overlay_timeline", "overlay_volume_slider"))
def test_slider_release_reschedules_hide(video_window, slider_name):
    app, window, frame = video_window()
    slider = getattr(frame, slider_name)
    slider.setSliderDown(True)
    frame.cancel_overlay_hide()
    assert not frame.overlay_hide_timer.isActive()

    slider.setSliderDown(False)
    send_mouse_button(slider, app, QEvent.Type.MouseButtonRelease)

    assert frame.overlay_hide_timer.isActive()


# --- 8. Oynatma state entegrasyonu ---

def test_pause_keeps_overlay_visible_and_stops_timer(video_window):
    app, window, frame = video_window()
    frame.hide_overlay_for_inactivity()
    finish_fade(app, frame)

    window.is_paused = True
    frame.update_overlay_play_state()
    app.processEvents()

    assert frame.control_overlay.isVisible()
    assert not frame.overlay_hide_timer.isActive()


def test_resume_shows_overlay_and_starts_timer(video_window):
    app, window, frame = video_window()
    window.is_paused = True
    frame.update_overlay_play_state()

    window.is_paused = False
    frame.update_overlay_play_state()
    app.processEvents()

    assert frame.control_overlay.isVisible()
    assert frame.overlay_hide_timer.isActive()


def test_stop_keeps_overlay_visible_and_stops_timer(video_window):
    app, window, frame = video_window()
    window.is_paused = True
    window.current_file = ""
    frame.update_overlay_play_state()
    app.processEvents()

    assert frame.control_overlay.isVisible()
    assert not frame.overlay_hide_timer.isActive()


def test_periodic_state_update_does_not_restart_the_timer(video_window):
    """update_ui 100 ms'de bir çalışırken timer sürekli yeniden başlamamalı."""
    app, window, frame = video_window()
    frame.cancel_overlay_hide()

    for _ in range(5):
        frame.update_overlay_state()
    app.processEvents()

    assert not frame.overlay_hide_timer.isActive()


# --- 9. Resize / move ---

def test_resize_does_not_reveal_auto_hidden_overlay(video_window):
    app, window, frame = video_window()
    frame.hide_overlay_for_inactivity()
    finish_fade(app, frame)

    window.resize(1000, 640)
    app.processEvents()
    frame.update_overlay_geometry()
    app.processEvents()

    assert not frame.control_overlay.isVisible()


def test_geometry_is_updated_while_auto_hidden_and_correct_on_return(video_window):
    app, window, frame = video_window()
    frame.hide_overlay_for_inactivity()
    finish_fade(app, frame)

    window.resize(1000, 640)
    app.processEvents()
    frame.update_overlay_geometry()
    app.processEvents()

    send_mouse_move(frame, app)

    overlay = frame.control_overlay
    assert overlay.isVisible()
    assert overlay.width() == frame.width()
    assert overlay.geometry().bottom() == \
        frame.mapToGlobal(QPoint(0, 0)).y() + frame.height() - 1


# --- 10. Fullscreen ---

def test_fullscreen_entry_shows_overlay_and_schedules_hide(video_window):
    app, window, frame = video_window()
    frame.hide_overlay_for_inactivity()
    finish_fade(app, frame)

    frame.enter_fullscreen()
    app.processEvents()

    assert frame.control_overlay.isVisible()
    assert frame.overlay_hide_timer.isActive()


def test_fullscreen_hide_and_restore_cycle(video_window):
    app, window, frame = video_window()
    frame.enter_fullscreen()
    app.processEvents()

    frame.hide_overlay_for_inactivity()
    finish_fade(app, frame)
    assert not frame.control_overlay.isVisible()

    send_mouse_move(frame, app)
    finish_fade(app, frame)
    assert frame.control_overlay.isVisible()

    frame.exit_fullscreen()
    app.processEvents()
    assert frame.control_overlay.isVisible()


# --- 11. Alt+Tab ---

def test_overlay_hides_on_deactivate_and_returns_on_activate(video_window):
    app, window, frame = video_window()
    other = QWidget()
    other.setWindowTitle("Other")
    other.show()
    app.processEvents()

    QApplication.setActiveWindow(other)
    frame._is_player_surface_active = lambda: False
    frame.eventFilter(window, QEvent(QEvent.Type.WindowDeactivate))
    app.processEvents()
    assert not frame.control_overlay.isVisible()

    QApplication.setActiveWindow(window)
    frame._is_player_surface_active = lambda: True
    frame.eventFilter(window, QEvent(QEvent.Type.WindowActivate))
    app.processEvents()

    assert frame.control_overlay.isVisible()
    assert frame.overlay_hide_timer.isActive()
    other.close()


def test_owner_deactivation_is_not_confused_with_auto_hide(video_window):
    """Deactivate ile gizlenme auto-hidden state'i işaretlememeli."""
    app, window, frame = video_window()
    frame._is_player_surface_active = lambda: False
    frame.eventFilter(window, QEvent(QEvent.Type.WindowDeactivate))
    app.processEvents()

    assert not frame.control_overlay.isVisible()
    assert frame._overlay_auto_hidden is False
