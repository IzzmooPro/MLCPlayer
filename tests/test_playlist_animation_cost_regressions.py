# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Playlist açılış/kapanış GEÇİŞİNİN maliyeti ve görsel doğruluğu.

Bu dosya bir zamanlar gömülü dock mimarisini ölçüyordu: "host genişliği
kareler arasında sabit mi", "dock genişliği kaç kez uygulandı", "panel host
içinde kayıyor mu". Panel 17 Ağustos 2026'da kullanıcı kararıyla ana
pencerenin YANINDA duran bağımsız pencereye taşındı; host da, dock genişliği
de, kaydırma da artık YOK.

SÖZLEŞMELER GEVŞETİLMEDİ, GÜÇLENDİ. Eskiden geçiş başına video yüzeyinin
EN FAZLA BİR KEZ yeniden boyutlanması kabul ediliyordu; bağımsız pencerede
video yüzeyi HİÇ boyutlanmamalıdır.

Karşılıklar:

    video en fazla 1 kez resize   -> video HİÇ resize olmaz
    host genişliği sabit          -> video genişliği sabit
    panel host içinde kayıyor     -> geçiş opaklıkla yapılıyor
    kesişme yok (her karede)      -> KORUNDU
    içerik yeniden kurulmuyor     -> KORUNDU
    hızlı aç/kapat doğru bitiyor  -> KORUNDU
    kullanıcı genişliği kalıcı    -> KORUNDU
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QMainWindow, QVBoxLayout, QWidget)

from app.media_controls import show_playlist
from app.video_frame import VideoFrame


@pytest.fixture
def player_window(monkeypatch):
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
        window.add_to_playlist = lambda: None
        window.remove_from_playlist = lambda index: None
        window.clear_playlist = lambda: None

        central = QWidget(window)
        window.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        window.media_container = QWidget(central)
        media_layout = QHBoxLayout(window.media_container)
        media_layout.setContentsMargins(0, 0, 0, 0)
        media_layout.setSpacing(0)
        frame = VideoFrame(window)
        frame.setMinimumSize(200, 120)
        window.video_frame = frame
        media_layout.addWidget(frame, 1)
        root.addWidget(window.media_container, 1)
        window.resize(*size)
        window.show()
        app.processEvents()
        created.append((window, frame))
        return app, window, frame

    yield factory

    for window, frame in created:
        panel = frame.playlist_panel
        if panel is not None:
            panel.close()
        frame.close_control_overlay()
        window.close()
        window.deleteLater()
    app.processEvents()


def global_rect(widget):
    return QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())


class CostRecorder:
    """Geçiş boyunca video yüzeyinin yeniden boyutlanma sayısı."""

    def __init__(self, monkeypatch, frame):
        self.video_resizes = 0
        self.frames = []
        original_resize = VideoFrame.resizeEvent

        def counting_resize(inner_self, event):
            if inner_self is frame:
                self.video_resizes += 1
            return original_resize(inner_self, event)

        monkeypatch.setattr(VideoFrame, "resizeEvent", counting_resize)

    def reset(self):
        self.video_resizes = 0
        self.frames = []


def step_animation(app, panel, recorder, window, frame, steps=12):
    """Geçişi deterministik adımlarla ilerletir, her karede ölçüm alır."""
    animation = panel.animation
    duration = max(1, animation.duration())
    for index in range(steps + 1):
        animation.setCurrentTime(int(duration * index / steps))
        app.processEvents()
        recorder.frames.append({
            "panel_rect": global_rect(panel),
            "video_rect": global_rect(frame),
            "video_width": frame.width(),
            "opacity": panel.windowOpacity(),
        })


def open_panel(app, window, frame):
    show_playlist(window)
    app.processEvents()
    return frame.playlist_panel


# --- 1. Maliyet: video yüzeyi HİÇ yeniden boyutlanmamalı --------------

def test_opening_the_playlist_never_resizes_the_video_surface(
        player_window, monkeypatch):
    app, window, frame = player_window()
    panel = open_panel(app, window, frame)
    recorder = CostRecorder(monkeypatch, frame)

    step_animation(app, panel, recorder, window, frame)

    assert recorder.video_resizes == 0, (
        f"acilista video yuzeyi {recorder.video_resizes} kez boyutlandi; "
        "bagimsiz pencere video alanindan yer ALMAZ")


def test_closing_the_playlist_never_resizes_the_video_surface(
        player_window, monkeypatch):
    app, window, frame = player_window()
    panel = open_panel(app, window, frame)
    panel.finish_animation()
    recorder = CostRecorder(monkeypatch, frame)

    panel.close_animated()
    step_animation(app, panel, recorder, window, frame)

    assert recorder.video_resizes == 0


def test_the_video_width_is_constant_during_the_transition(
        player_window, monkeypatch):
    app, window, frame = player_window()
    panel = open_panel(app, window, frame)
    recorder = CostRecorder(monkeypatch, frame)

    step_animation(app, panel, recorder, window, frame)

    widths = {sample["video_width"] for sample in recorder.frames}
    assert len(widths) == 1, f"video genisligi kareler arasinda degisti: {widths}"


# --- 2. Görsel doğruluk: hiçbir karede kesişme olmamalı ---------------

def test_panel_never_intersects_video_during_the_transition(
        player_window, monkeypatch):
    app, window, frame = player_window()
    panel = open_panel(app, window, frame)
    recorder = CostRecorder(monkeypatch, frame)

    step_animation(app, panel, recorder, window, frame)

    for index, sample in enumerate(recorder.frames):
        overlap = sample["panel_rect"].intersected(sample["video_rect"])
        assert overlap.isEmpty(), (
            f"kare #{index}: panel {sample['panel_rect']} video "
            f"{sample['video_rect']} ile kesisiyor -> {overlap}")


def test_the_transition_animates_the_window_opacity(
        player_window, monkeypatch):
    """Geçiş artık KAYDIRMA değil opaklıktır.

    Top-level bir pencereyi her karede taşımak Windows'ta titrer ve ana
    pencereyle senkron kalmaz; konum geçiş boyunca sabit tutulur.
    """
    app, window, frame = player_window()
    panel = open_panel(app, window, frame)
    recorder = CostRecorder(monkeypatch, frame)

    step_animation(app, panel, recorder, window, frame)

    opacities = [sample["opacity"] for sample in recorder.frames]
    lefts = {sample["panel_rect"].left() for sample in recorder.frames}
    assert len(set(opacities)) > 1, f"opaklik degismedi: {set(opacities)}"
    assert opacities[0] < opacities[-1], "acilis saydamdan opaka gitmeli"
    assert abs(opacities[-1] - 1.0) <= 0.01
    assert len(lefts) == 1, f"panel gecis sirasinda tasindi: {lefts}"


# --- 3. İçerik geçiş sırasında yeniden oluşturulmamalı ----------------

def test_rows_thumbnails_and_search_survive_the_transition(
        player_window, monkeypatch):
    app, window, frame = player_window()
    panel = open_panel(app, window, frame)
    recorder = CostRecorder(monkeypatch, frame)

    search_id = id(panel.search_field)
    view_id = id(panel.playlist_view)
    row_ids = [id(panel.row_widget(row))
               for row in range(panel.playlist_view.count())]
    thumb_ids = [id(panel.row_widget(row).thumbnail_label)
                 for row in range(panel.playlist_view.count())]
    assert row_ids, "test anlamli olsun diye en az bir satir olmali"

    step_animation(app, panel, recorder, window, frame)

    assert id(panel.search_field) == search_id
    assert id(panel.playlist_view) == view_id
    assert [id(panel.row_widget(row))
            for row in range(panel.playlist_view.count())] == row_ids
    assert [id(panel.row_widget(row).thumbnail_label)
            for row in range(panel.playlist_view.count())] == thumb_ids


# --- 4. Hızlı aç/kapat ve kullanıcı genişliği -------------------------

def test_rapid_open_close_open_ends_in_the_correct_state(player_window):
    app, window, frame = player_window()
    panel = open_panel(app, window, frame)

    for _ in range(3):
        frame.toggle_playlist_panel()
        app.processEvents()
        frame.toggle_playlist_panel()
        app.processEvents()

    panel.finish_animation()
    app.processEvents()

    assert panel.is_open
    assert panel.isVisible()
    assert panel.width() >= 320
    assert global_rect(panel).intersected(global_rect(frame)).isEmpty()


def test_reversing_mid_transition_continues_from_the_current_opacity(
        player_window):
    """Yarıda tersine çevirme sıçrama yapmamalı."""
    app, window, frame = player_window()
    panel = open_panel(app, window, frame)
    animation = panel.animation
    animation.setCurrentTime(animation.duration() // 2)
    app.processEvents()
    midway = panel.windowOpacity()

    panel.close_animated()
    app.processEvents()
    after_reverse = panel.windowOpacity()

    assert abs(after_reverse - midway) <= 0.05, (
        f"tersine cevirmede sicrama: {midway} -> {after_reverse}")


def test_user_selected_width_survives_open_close_cycles(player_window):
    app, window, frame = player_window(size=(1400, 800))
    panel = open_panel(app, window, frame)
    panel.finish_animation()
    app.processEvents()

    panel.set_panel_width(panel.width() + 110)
    app.processEvents()
    chosen = panel.width()

    frame.toggle_playlist_panel()
    panel.finish_animation()
    app.processEvents()
    frame.toggle_playlist_panel()
    panel.finish_animation()
    app.processEvents()

    assert panel.width() == chosen, (
        f"kullanici genisligi kayboldu: {chosen} -> {panel.width()}")
