"""Dar pencerede overlay süre bloğunun davranışı.

400x300'de yarım/kırpık süre metni gösterilmemeli; blok tamamen gizlenmeli.
Geniş pencerede geri gelmeli. Ölçümler gerçek widget görünürlüğü ve
geometrisi üzerinden yapılır.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QPoint, QRect, QSettings, Qt
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QSlider, QVBoxLayout, QWidget)

from app.config import MAX_VOLUME
from app.video_frame import VideoFrame

RIGHT_CONTROLS = ("overlaySubtitles", "overlaySettings", "overlayVolume",
                  "overlayVolumeSlider", "overlayFullscreen")


@pytest.fixture
def video_window(monkeypatch, tmp_path):
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
        window.is_paused = True
        window.is_muted = False
        window.duration = 3661.0
        window.position = 65.0
        window.volume_slider = QSlider(Qt.Orientation.Horizontal)
        window.volume_slider.setRange(0, MAX_VOLUME)
        window.volume_slider.setValue(70)
        frame = VideoFrame(window)
        window.video_frame = frame
        window.main_layout.addWidget(frame)
        window.resize(*size)
        window.show()
        app.processEvents()
        frame.update_overlay_geometry()
        frame.update_overlay_state()
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


def resize_to(app, window, frame, width, height):
    window.resize(width, height)
    app.processEvents()
    frame.update_overlay_geometry()
    frame.update_overlay_state()
    app.processEvents()


def widget_by_name(overlay, name):
    return next(w for w in overlay.findChildren(QWidget)
                if w.objectName() == name)


def global_rect(widget):
    return QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())


def time_widgets(frame):
    return (frame.overlay_current_time_label,
            frame.overlay_time_separator,
            frame.overlay_total_time_label)


# --- 1. 400 px genişlik ---

def test_time_block_is_fully_hidden_at_minimum_width(video_window):
    app, window, frame = video_window(size=(400, 300))
    for widget in time_widgets(frame):
        assert not widget.isVisible()


def test_right_controls_stay_visible_at_minimum_width(video_window):
    app, window, frame = video_window(size=(400, 300))
    overlay = frame.control_overlay
    for name in RIGHT_CONTROLS:
        widget = widget_by_name(overlay, name)
        assert widget.isVisible(), f"{name} gizlendi"
        assert widget.width() > 0 and widget.height() > 0


def test_timeline_and_media_buttons_stay_visible_at_minimum_width(video_window):
    app, window, frame = video_window(size=(400, 300))
    overlay = frame.control_overlay
    assert frame.overlay_timeline.isVisible()
    for name in ("overlayPrevious", "overlayPlayPause", "overlayNext"):
        assert widget_by_name(overlay, name).isVisible()


def test_no_control_is_clipped_outside_overlay_at_minimum_width(video_window):
    app, window, frame = video_window(size=(400, 300))
    overlay = frame.control_overlay
    overlay_rect = overlay.geometry()
    names = RIGHT_CONTROLS + ("overlayPrevious", "overlayPlayPause",
                              "overlayNext", "overlayTimeline")
    for name in names:
        rect = global_rect(widget_by_name(overlay, name))
        assert overlay_rect.contains(rect), f"{name} {rect} overlay dışında"


# --- 2. 1280 px genişlik ---

def test_time_block_is_visible_at_wide_width(video_window):
    app, window, frame = video_window(size=(1280, 720))
    for widget in time_widgets(frame):
        assert widget.isVisible()


def test_time_texts_are_correct_at_wide_width(video_window):
    app, window, frame = video_window(size=(1280, 720))
    assert frame.overlay_current_time_label.text() == "01:05"
    assert frame.overlay_total_time_label.text() == "1:01:01"
    assert frame.overlay_time_separator.text() == "/"


def test_centre_play_button_stays_centred_at_wide_width(video_window):
    app, window, frame = video_window(size=(1280, 720))
    overlay = frame.control_overlay
    play = widget_by_name(overlay, "overlayPlayPause")
    centre = play.mapTo(overlay, play.rect().center()).x()
    assert abs(centre - overlay.width() // 2) <= 6


# --- 3. Aynı pencerede küçült / büyüt ---

def test_time_block_hides_and_returns_on_resize(video_window):
    app, window, frame = video_window(size=(1280, 720))
    assert all(widget.isVisible() for widget in time_widgets(frame))

    resize_to(app, window, frame, 400, 300)
    assert not any(widget.isVisible() for widget in time_widgets(frame))

    resize_to(app, window, frame, 1280, 720)
    assert all(widget.isVisible() for widget in time_widgets(frame))
    assert frame.overlay_current_time_label.text() == "01:05"
    assert frame.overlay_total_time_label.text() == "1:01:01"


def test_right_controls_survive_the_resize_cycle(video_window):
    app, window, frame = video_window(size=(1280, 720))
    resize_to(app, window, frame, 400, 300)
    resize_to(app, window, frame, 1280, 720)
    overlay = frame.control_overlay
    for name in RIGHT_CONTROLS:
        assert widget_by_name(overlay, name).isVisible()
