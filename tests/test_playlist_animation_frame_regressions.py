# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Playlist açılış/kapanış animasyonunun HER ara karesinde kesişme olmamalı.

Kabul edilen düzeltme, dock genişliği değiştikten sonra
`layout.invalidate() + activate()` çağırmaya dayanır. Bu olmadan host, yeni
genişlikle ama ESKİ x konumunda kalıyor ve panel videoyla kesişiyordu.

Son durum testleri bu hatayı kaçırır: animasyon biterken layout zaten
oturmuş olur. Bu dosya kesişmeyi ara karelerde, animasyonun kendi
`valueChanged` yolundan örnekleyerek ölçer.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QMainWindow, QVBoxLayout, QWidget)

from app.media_controls import show_playlist
from app.playlist_panel import PANEL_ANIMATION_MS
from app.video_frame import VideoFrame


@pytest.fixture
def dock_window(monkeypatch):
    monkeypatch.delenv("MLCPLAYER_CLASSIC_UI", raising=False)
    monkeypatch.setattr("app.media_controls.QDialog.exec", lambda self: 0)
    monkeypatch.setattr(
        "app.media_controls.QMessageBox.information", lambda *args: 0)
    app = QApplication.instance() or QApplication([])
    created = []

    def factory(size=(1280, 720)):
        window = QMainWindow()
        window.cinematic_ui_enabled = True
        window.playlist = [r"C:\media\first.mkv", r"C:\media\second.mp4"]
        window.current_playlist_index = 0
        window.current_file = window.playlist[0]
        window.is_paused = True
        window.play_from_playlist = lambda index: None
        for name in ("add_to_playlist", "remove_from_playlist",
                     "clear_playlist"):
            setattr(window, name, lambda *a: None)

        central = QWidget(window)
        window.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        window.media_container = QWidget(central)
        media_layout = QHBoxLayout(window.media_container)
        media_layout.setContentsMargins(0, 0, 0, 0)
        media_layout.setSpacing(0)
        window.playlist_dock_host = QWidget(window.media_container)
        window.playlist_dock_host.setObjectName("playlistDockHost")
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
        created.append((window, frame))
        return app, window, frame

    yield factory

    for window, frame in created:
        # NOT: Hâlâ çalışan/duraklatılmış bir animasyon, hedef widget yok
        # edildikten sonra yorumlayıcı kapanışında native abort (0xC0000409)
        # üretiyordu. Animasyonlar widget'lardan ÖNCE durdurulur.
        panel = getattr(frame, "playlist_panel", None)
        if panel is not None:
            panel.animation.stop()
        fade = getattr(frame, "overlay_fade", None)
        if fade is not None:
            fade.stop()
        frame.close_control_overlay()
        window.close()
        app.processEvents()
        window.deleteLater()
    app.processEvents()


def global_rect(widget):
    return QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())


class FrameRecorder:
    """Animasyonun kendi valueChanged yolundan ara kare örnekler."""

    def __init__(self, app, window, frame, panel):
        self.app = app
        self.window = window
        self.frame = frame
        self.panel = panel
        self.samples = []

    def __call__(self, value):
        host = self.window.playlist_dock_host
        # Ürünün layout akışı bu noktada zaten uygulanmış olmalıdır.
        self.samples.append({
            "value": int(value),
            "host_width": host.width(),
            "panel_width": self.panel.width(),
            "panel_visible": self.panel.isVisible(),
            "panel_rect": global_rect(self.panel),
            "video_rect": global_rect(self.frame),
            "host_rect": global_rect(host),
        })

    def attach(self):
        self.panel.animation.valueChanged.connect(self)

    def detach(self):
        self.panel.animation.valueChanged.disconnect(self)


def drive_animation(app, panel, recorder, steps=12):
    """Animasyonu deterministik adımlarla ilerletir (duvar saati beklemez)."""
    animation = panel.animation
    duration = max(1, animation.duration())
    for index in range(steps + 1):
        animation.setCurrentTime(int(duration * index / steps))
        app.processEvents()
    return recorder.samples


def assert_frame_is_sane(sample, index, phase):
    """Kareyi GÖRÜNÜR (host tarafından kırpılmış) dikdörtgen üzerinden ölçer.

    Animasyon artık host genişliğini değil, panelin host içindeki yerel x
    konumunu değiştiriyor. Panel kapalıya doğru kayarken geometrisinin bir
    kısmı host'un dışında kalır; host child'ını clip ettiği için kullanıcının
    gördüğü şey kesişimdir. Ölçüm de bu yüzden kesişim üzerinden yapılır.
    """
    panel_rect = sample["panel_rect"]
    video_rect = sample["video_rect"]
    host_rect = sample["host_rect"]
    visible_rect = panel_rect.intersected(host_rect)

    overlap = panel_rect.intersected(video_rect)
    assert overlap.isEmpty(), (
        f"{phase} karesi #{index} (ofset={sample['value']}): playlist "
        f"{panel_rect} video {video_rect} ile kesişiyor -> {overlap}")
    if sample["panel_visible"] and sample["host_width"] > 0:
        if visible_rect.isEmpty():
            # Panel tamamen dışarı kaydı: kapanışın doğru son durumu.
            return
        assert host_rect.contains(visible_rect), (
            f"{phase} karesi #{index}: görünür panel {visible_rect} host "
            f"{host_rect} dışına taştı")
        assert sample["panel_width"] == sample["host_width"], (
            f"{phase} karesi #{index}: panel {sample['panel_width']} != host "
            f"{sample['host_width']}")


def test_opening_animation_never_intersects_the_video(dock_window):
    app, window, frame = dock_window()
    show_playlist(window)
    app.processEvents()
    panel = frame.playlist_panel

    recorder = FrameRecorder(app, window, frame, panel)
    recorder.attach()
    try:
        samples = drive_animation(app, panel, recorder)
    finally:
        recorder.detach()

    assert len(samples) >= 8, f"yeterli ara kare örneklenmedi: {len(samples)}"
    for index, sample in enumerate(samples):
        assert_frame_is_sane(sample, index, "açılış")

    # Açılış gerçekten genişleyen bir aralık taramalı (tek kareye çökmemeli).
    widths = [sample["value"] for sample in samples]
    assert min(widths) < max(widths)
    assert max(widths) >= 320


def test_closing_animation_never_intersects_the_video(dock_window):
    app, window, frame = dock_window()
    show_playlist(window)
    app.processEvents()
    panel = frame.playlist_panel
    panel.finish_animation()
    app.processEvents()
    video_width_open = frame.width()

    panel.close_animated()
    recorder = FrameRecorder(app, window, frame, panel)
    recorder.attach()
    try:
        samples = drive_animation(app, panel, recorder)
    finally:
        recorder.detach()

    assert len(samples) >= 8, f"yeterli ara kare örneklenmedi: {len(samples)}"
    for index, sample in enumerate(samples):
        assert_frame_is_sane(sample, index, "kapanış")

    widths = [sample["value"] for sample in samples]
    assert min(widths) < max(widths), "kapanış tek genişlikte kaldı"

    # Kapanış: host genişliği 0, panel gizli, video eski genişliğine döner.
    panel.finish_animation()
    app.processEvents()
    assert window.playlist_dock_host.width() == 0
    assert not panel.isVisible()
    assert frame.width() > video_width_open


@pytest.mark.parametrize("size", ((1280, 720), (1600, 900), (1024, 640)))
def test_animation_frames_stay_clean_at_several_window_sizes(dock_window, size):
    app, window, frame = dock_window(size=size)
    show_playlist(window)
    app.processEvents()
    panel = frame.playlist_panel

    recorder = FrameRecorder(app, window, frame, panel)
    recorder.attach()
    try:
        samples = drive_animation(app, panel, recorder, steps=8)
    finally:
        recorder.detach()

    for index, sample in enumerate(samples):
        assert_frame_is_sane(sample, index, f"{size} açılış")


def test_resize_during_the_opening_animation_stays_clean(dock_window):
    """Animasyon sürerken pencere boyutu değişse de kesişme olmamalı."""
    app, window, frame = dock_window(size=(1600, 900))
    show_playlist(window)
    app.processEvents()
    panel = frame.playlist_panel
    animation = panel.animation
    duration = max(1, animation.duration())

    recorder = FrameRecorder(app, window, frame, panel)
    recorder.attach()
    try:
        animation.setCurrentTime(duration // 3)
        app.processEvents()
        window.resize(1040, 660)
        app.processEvents()
        frame.update_playlist_panel_geometry()
        app.processEvents()

        # Bu AN kritiktir: yeniden boyutlandırma dock genişliğini değiştirir
        # ama bir sonraki animasyon karesi henüz gelmemiştir. Layout burada
        # konumlarıyla birlikte tazelenmezse host yeni genişlikte ama eski
        # x konumunda kalır ve panel videoyla kesişir.
        mid = {
            "value": window.playlist_dock_host.width(),
            "host_width": window.playlist_dock_host.width(),
            "panel_width": panel.width(),
            "panel_visible": panel.isVisible(),
            "panel_rect": global_rect(panel),
            "video_rect": global_rect(frame),
            "host_rect": global_rect(window.playlist_dock_host),
        }
        assert_frame_is_sane(mid, "resize-ani", "animasyon içi yeniden boyutlandırma")

        for index in range(4, 13):
            animation.setCurrentTime(int(duration * index / 12))
            app.processEvents()
    finally:
        recorder.detach()

    for index, sample in enumerate(recorder.samples):
        assert_frame_is_sane(sample, index, "boyutlanan açılış")


def test_animation_duration_is_still_the_approved_value(dock_window):
    app, window, frame = dock_window()
    show_playlist(window)
    app.processEvents()

    assert frame.playlist_panel.animation.duration() == PANEL_ANIMATION_MS
