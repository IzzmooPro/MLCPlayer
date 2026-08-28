# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Overlay kontrollerinin Win32 hit-test alfası regresyonları.

Kök neden (gerçek Windows ölçümüyle kanıtlandı): `control_overlay` üst
düzey penceresi `WA_TranslucentBackground` nedeniyle `WS_EX_LAYERED`'dır ve
Windows fare hedefini PİKSEL ALFASINA göre seçer. Alfa=0 boyanan kontrol
pikselleri alttaki mpv `wid` yüzeyine düşer; düğmeye hiç `MouseButtonPress`
gelmez.

Ölçülen minimum çalışan alfa 2/255'tir (bkz. `OVERLAY_HIT_ALPHA`).

NOT: Native z-order/hit kanıtı `tests/native_overlay_input_zorder_child.py`
içindedir; burada yalnız Qt tarafındaki değişmezler kilitlenir.
"""
import os
import re
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QImage, QRegion
from PyQt6.QtWidgets import (
    QApplication, QLabel, QMainWindow, QSlider, QVBoxLayout, QWidget)


INTERACTIVE = ("overlayTimeline", "overlayPrevious", "overlayPlayPause",
               "overlayNext", "overlaySubtitles", "overlaySettings",
               "overlayVolume", "overlayVolumeSlider", "overlayFullscreen")


@pytest.fixture
def frame_env():
    app = QApplication.instance() or QApplication([])
    created = []

    def factory():
        from app.video_frame import VideoFrame

        window = QMainWindow()
        window.central_widget = QWidget(window)
        window.setCentralWidget(window.central_widget)
        window.main_layout = QVBoxLayout(window.central_widget)
        window.duration = 600.0
        window.position = 0.0
        window.current_file = "C:/video.mkv"
        window.is_paused = False
        window.is_muted = False
        window.playlist = []
        window.current_playlist_index = 0
        window.loop_file = window.loop_playlist = window.shuffle = False
        window.recent_files = []
        window._updating_position_slider = False
        window._pending_subs = []
        window.volume_slider = QSlider(Qt.Orientation.Horizontal)
        window.position_slider = QSlider()
        window.current_time_label = QLabel()
        window.total_time_label = QLabel()
        window.play_button = SimpleNamespace(setIcon=lambda icon: None)
        window.play_icon = window.pause_icon = object()
        window.update_time_label = lambda: None
        window.mpv_player = SimpleNamespace(
            aid=1, sid=1, audio_device="auto", sub_visibility=False,
            speed=1.0, track_list=[], audio_device_list=[],
            command=lambda *a, **k: None)
        for name in ("open_file", "open_folder", "open_url", "open_path",
                     "play_pause", "stop", "play_previous", "play_next",
                     "show_playlist", "toggle_mute", "seek_position",
                     "toggle_subtitles", "toggle_fullscreen",
                     "take_screenshot", "setup_video_adjustments",
                     "seek_relative", "goto_time", "set_playback_speed"):
            setattr(window, name, lambda *a, **k: None)
        frame = VideoFrame(window)
        window.video_frame = frame
        window.resize(1200, 700)
        window.show()
        app.processEvents()
        created.append(window)
        return SimpleNamespace(frame=frame, window=window, app=app)

    yield factory

    for window in created:
        window.close()
        window.deleteLater()
    app.processEvents()


def control(frame, name):
    for child in frame.control_overlay.findChildren(QWidget):
        if child.objectName() == name:
            return child
    return None


def rendered_alpha(frame, widget, point):
    """Overlay'i SAYDAM görüntüye çizip gerçek ARGB alfasını okur."""
    overlay = frame.control_overlay
    image = QImage(overlay.size(), QImage.Format.Format_ARGB32)
    image.fill(0)
    overlay.render(image, overlay.rect().topLeft(), QRegion(overlay.rect()),
                   QWidget.RenderFlag.DrawChildren)
    local = widget.mapTo(overlay, point)
    if not (0 <= local.x() < image.width() and 0 <= local.y() < image.height()):
        return -1
    return (image.pixel(local.x(), local.y()) >> 24) & 0xFF


# =====================================================================
# 1. Merkezi sabit
# =====================================================================

def test_hit_alpha_constant_is_the_measured_minimum():
    from app.video_frame import OVERLAY_HIT_ALPHA, OVERLAY_HIT_BACKGROUND

    assert OVERLAY_HIT_ALPHA >= 2, "olculen minimum 2/255"
    assert OVERLAY_HIT_ALPHA <= 8, "gorunur kutu olusturacak kadar yuksek"
    assert f"{OVERLAY_HIT_ALPHA})" in OVERLAY_HIT_BACKGROUND


def test_overlay_controls_do_not_declare_transparent_background():
    """Interaktif kontroller `background: transparent` BIRAKMAMALI."""
    from app.video_frame import OVERLAY_HIT_BACKGROUND

    import app.video_frame as module
    source = open(module.__file__, encoding="utf-8").read()
    block = source[source.index("def _create_control_overlay"):
                   source.index("def _make_overlay_button")]
    for selector in ("QPushButton {", "QPushButton#overlayPlayPause {",
                     "QSlider#overlayTimeline {"):
        index = block.find(selector)
        assert index != -1, selector
        rule = block[index:index + 260]
        assert "background: transparent" not in rule, selector
    assert OVERLAY_HIT_BACKGROUND.split("(")[0] in block


# =====================================================================
# 2. Gerçek çizilen alfa (Qt tarafı)
# =====================================================================

@pytest.mark.parametrize("name", INTERACTIVE)
def test_every_interactive_control_paints_hittable_pixels(frame_env, name):
    """Kontrolün merkezi ve kenarları alfa>0 boyanmalı."""
    from app.video_frame import OVERLAY_HIT_ALPHA

    env = frame_env()
    widget = control(env.frame, name)
    assert widget is not None, name

    # NOT: yuvarlak kenarli dugmelerde KOSE pikselleri sekil disindadir;
    # ornekleme kontrolun ic alanindan yapilir.
    rect = widget.rect()
    inset_x = max(2, rect.width() // 5)
    inset_y = max(2, rect.height() // 5)
    centre = rect.center()
    points = (centre,
              QPoint(rect.left() + inset_x, centre.y()),
              QPoint(rect.right() - inset_x, centre.y()),
              QPoint(centre.x(), rect.top() + inset_y),
              QPoint(centre.x(), rect.bottom() - inset_y))
    for point in points:
        alpha = rendered_alpha(env.frame, widget, point)
        assert alpha >= OVERLAY_HIT_ALPHA, (name, point, alpha)


def test_osd_stays_input_transparent(frame_env):
    """OSD tiklama almamali: input-transparent kalmali."""
    env = frame_env()

    assert env.frame.osd_label.testAttribute(
        Qt.WidgetAttribute.WA_TransparentForMouseEvents)


def test_overlay_is_not_input_transparent(frame_env):
    """Overlay penceresi input-transparent BAYRAGI tasimamali."""
    env = frame_env()

    assert not env.frame.control_overlay.testAttribute(
        Qt.WidgetAttribute.WA_TransparentForMouseEvents)


def test_overlay_does_not_use_always_on_top(frame_env):
    """Cozum TOPMOST ile yapilmadi; overlay baska uygulamalarin ustunde kalmaz."""
    env = frame_env()

    flags = env.frame.control_overlay.windowFlags()
    assert not (flags & Qt.WindowType.WindowStaysOnTopHint)


def test_overlay_does_not_steal_focus(frame_env):
    env = frame_env()
    overlay = env.frame.control_overlay

    assert overlay.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    assert overlay.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus


def test_hidden_overlay_produces_no_action(frame_env):
    """Görünürlük kapısı offscreen'da platform penceresine bağlı değildir."""
    from app.video_frame import VideoFrame

    env = frame_env()
    calls = []
    probe = SimpleNamespace(
        control_overlay=SimpleNamespace(isVisible=lambda: False),
        show_overlay_for_interaction=lambda: calls.append("shown"))
    probe._overlay_action_allowed = lambda: VideoFrame._overlay_action_allowed(
        probe)

    VideoFrame._run_overlay_action(probe, lambda: calls.append("ran"))

    assert calls == []


def test_release_overlay_surfaces_still_works(frame_env):
    """Kapanis yolu bu turda bozulmadi."""
    env = frame_env()

    env.frame.release_overlay_surfaces()

    assert env.frame.control_overlay is None
    assert env.frame.osd_label is None
