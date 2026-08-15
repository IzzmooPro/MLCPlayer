"""Playlist açma/kapatma animasyonunun MALİYETİ (B).

Kasmanın kök nedeni ölçülebilir olmalıdır: eski animasyon her karede host
genişliğini değiştirip `apply_playlist_dock_width()` üzerinden
`layout.invalidate()/activate()` çağırıyordu. Bu, `VideoFrame`'i ve dolayısıyla
MPV native `wid` yüzeyini her karede yeniden boyutlandırıyordu.

Hedef mimari: host genişliği açılışta BİR KEZ ayrılır (video/MPV tek kez
yeniden boyutlanır); görsel animasyon panelin host içindeki YEREL x konumu
üzerinden yapılır ve host paneli clip eder.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QMainWindow, QVBoxLayout, QWidget)

from app.media_controls import show_playlist
from app.video_frame import VideoFrame

# Açılış/kapanış boyunca video yüzeyi kaç kez yeniden boyutlanabilir?
# Tek bir yer ayırma (ve kapanışta tek bir geri verme) beklenir; küçük bir
# tolerans Qt'nin kendi ara resize'ları içindir.
MAX_VIDEO_RESIZES_PER_TRANSITION = 3
MAX_DOCK_WIDTH_APPLICATIONS_PER_TRANSITION = 3


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
        window.main_layout = QVBoxLayout(central)
        window.main_layout.setContentsMargins(0, 0, 0, 0)
        window.main_layout.setSpacing(0)
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
        window.main_layout.addWidget(window.media_container, 1)
        window.resize(*size)
        window.show()
        app.processEvents()
        created.append((window, frame))
        return app, window, frame

    yield factory

    for window, frame in created:
        panel = getattr(frame, "playlist_panel", None)
        if panel is not None:
            panel.animation.stop()
        frame.close_control_overlay()
        window.close()
    app.processEvents()


def global_rect(widget):
    return QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())


class CostRecorder:
    """Animasyon boyunca video resize ve dock genişlik uygulama sayısı."""

    def __init__(self, monkeypatch, frame):
        self.video_resizes = 0
        self.dock_width_applications = 0
        self.frames = []
        self._frame = frame

        original_resize = VideoFrame.resizeEvent

        def counting_resize(inner_self, event):
            if inner_self is frame:
                self.video_resizes += 1
            return original_resize(inner_self, event)

        monkeypatch.setattr(VideoFrame, "resizeEvent", counting_resize)

        original_apply = VideoFrame.apply_playlist_dock_width

        def counting_apply(inner_self, width, minimum=0):
            if inner_self is frame:
                self.dock_width_applications += 1
            return original_apply(inner_self, width, minimum)

        monkeypatch.setattr(VideoFrame, "apply_playlist_dock_width",
                            counting_apply)

    def reset(self):
        self.video_resizes = 0
        self.dock_width_applications = 0
        self.frames = []


def step_animation(app, panel, recorder, window, frame, steps=12):
    """Animasyonu deterministik adımlarla ilerletir, her karede ölçüm alır."""
    animation = panel.animation
    duration = max(1, animation.duration())
    for index in range(steps + 1):
        animation.setCurrentTime(int(duration * index / steps))
        app.processEvents()
        recorder.frames.append({
            "panel_rect": global_rect(panel),
            "video_rect": global_rect(frame),
            "host_rect": global_rect(window.playlist_dock_host),
            "host_width": window.playlist_dock_host.width(),
            "video_width": frame.width(),
        })


def open_panel(app, window, frame):
    show_playlist(window)
    app.processEvents()
    return frame.playlist_panel


# --- 1. Maliyet: video/MPV yüzeyi her karede yeniden boyutlanmamalı ---

def test_opening_animation_resizes_the_video_surface_only_once(
        dock_window, monkeypatch):
    app, window, frame = dock_window()
    panel = open_panel(app, window, frame)
    recorder = CostRecorder(monkeypatch, frame)
    recorder.reset()

    step_animation(app, panel, recorder, window, frame)

    assert recorder.video_resizes <= MAX_VIDEO_RESIZES_PER_TRANSITION, (
        f"açılışta video yüzeyi {recorder.video_resizes} kez yeniden "
        f"boyutlandı; en fazla {MAX_VIDEO_RESIZES_PER_TRANSITION} olmalı")


def test_opening_animation_applies_dock_width_only_once(
        dock_window, monkeypatch):
    app, window, frame = dock_window()
    panel = open_panel(app, window, frame)
    recorder = CostRecorder(monkeypatch, frame)
    recorder.reset()

    step_animation(app, panel, recorder, window, frame)

    assert (recorder.dock_width_applications
            <= MAX_DOCK_WIDTH_APPLICATIONS_PER_TRANSITION), (
        f"açılışta dock genişliği {recorder.dock_width_applications} kez "
        f"uygulandı (her uygulama layout.invalidate/activate demektir)")


def test_closing_animation_resizes_the_video_surface_only_once(
        dock_window, monkeypatch):
    app, window, frame = dock_window()
    panel = open_panel(app, window, frame)
    panel.finish_animation()
    app.processEvents()
    recorder = CostRecorder(monkeypatch, frame)
    recorder.reset()

    panel.close_animated()
    step_animation(app, panel, recorder, window, frame)

    assert recorder.video_resizes <= MAX_VIDEO_RESIZES_PER_TRANSITION, (
        f"kapanışta video yüzeyi {recorder.video_resizes} kez yeniden "
        f"boyutlandı")


def test_host_width_is_constant_during_the_opening_animation(
        dock_window, monkeypatch):
    """Host genişliği açılışta bir kez ayrılır; kareler onu değiştirmez."""
    app, window, frame = dock_window()
    panel = open_panel(app, window, frame)
    recorder = CostRecorder(monkeypatch, frame)

    step_animation(app, panel, recorder, window, frame)

    widths = {sample["host_width"] for sample in recorder.frames}
    assert len(widths) == 1, f"host genişliği kareler arasında değişti: {widths}"
    video_widths = {sample["video_width"] for sample in recorder.frames}
    assert len(video_widths) == 1, (
        f"video genişliği kareler arasında değişti: {video_widths}")


# --- 2. Görsel doğruluk: hiçbir karede kesişme/taşma olmamalı ---

def test_panel_never_intersects_video_during_animation(dock_window, monkeypatch):
    app, window, frame = dock_window()
    panel = open_panel(app, window, frame)
    recorder = CostRecorder(monkeypatch, frame)

    step_animation(app, panel, recorder, window, frame)

    for index, sample in enumerate(recorder.frames):
        visible = sample["panel_rect"].intersected(sample["host_rect"])
        overlap = visible.intersected(sample["video_rect"])
        assert overlap.isEmpty(), (
            f"kare #{index}: görünür panel {visible} video "
            f"{sample['video_rect']} ile kesişiyor -> {overlap}")


def test_panel_slides_inside_the_host_instead_of_resizing_it(
        dock_window, monkeypatch):
    """Animasyon panelin host içindeki YEREL x konumunu değiştirmeli."""
    app, window, frame = dock_window()
    panel = open_panel(app, window, frame)
    recorder = CostRecorder(monkeypatch, frame)

    step_animation(app, panel, recorder, window, frame)

    offsets = [sample["panel_rect"].left() - sample["host_rect"].left()
               for sample in recorder.frames]
    assert len(set(offsets)) > 1, (
        f"panel host içinde kaymıyor; ofsetler sabit: {set(offsets)}")
    assert offsets[0] > offsets[-1], (
        f"açılış sağdan sola kaymalı: {offsets[0]} -> {offsets[-1]}")
    assert abs(offsets[-1]) <= 1, f"açılış x=0'da bitmeli, {offsets[-1]}"


# --- 3. İçerik animasyon sırasında yeniden oluşturulmamalı ---

def test_rows_thumbnails_and_search_survive_the_animation(
        dock_window, monkeypatch):
    app, window, frame = dock_window()
    panel = open_panel(app, window, frame)
    recorder = CostRecorder(monkeypatch, frame)

    search_id = id(panel.search_field)
    view_id = id(panel.playlist_view)
    row_ids = [id(panel.row_widget(row))
               for row in range(panel.playlist_view.count())]
    thumb_ids = [id(panel.row_widget(row).thumbnail_label)
                 for row in range(panel.playlist_view.count())]
    assert row_ids, "test anlamlı olsun diye en az bir satır olmalı"

    step_animation(app, panel, recorder, window, frame)

    assert id(panel.search_field) == search_id
    assert id(panel.playlist_view) == view_id
    assert [id(panel.row_widget(row))
            for row in range(panel.playlist_view.count())] == row_ids
    assert [id(panel.row_widget(row).thumbnail_label)
            for row in range(panel.playlist_view.count())] == thumb_ids


# --- 4. Hızlı aç/kapat ve tersine çevirme ---

def test_rapid_open_close_open_ends_in_the_correct_state(dock_window):
    app, window, frame = dock_window()
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
    assert window.playlist_dock_host.width() >= 320
    assert global_rect(panel).intersected(global_rect(frame)).isEmpty()


def test_reversing_mid_animation_continues_from_the_current_position(
        dock_window):
    """Yarıda tersine çevirme sıçrama yapmamalı."""
    app, window, frame = dock_window()
    panel = open_panel(app, window, frame)
    animation = panel.animation
    animation.setCurrentTime(animation.duration() // 2)
    app.processEvents()
    midway_offset = panel.pos().x()

    panel.close_animated()
    app.processEvents()
    after_reverse_offset = panel.pos().x()

    assert abs(after_reverse_offset - midway_offset) <= 6, (
        f"tersine çevirmede sıçrama: {midway_offset} -> {after_reverse_offset}")


def test_user_selected_width_survives_open_close_cycles(dock_window):
    app, window, frame = dock_window(size=(1400, 800))
    panel = open_panel(app, window, frame)
    panel.finish_animation()
    app.processEvents()

    frame.set_playlist_panel_width(panel.width() + 110)
    app.processEvents()
    chosen = panel.width()

    frame.toggle_playlist_panel()
    panel.finish_animation()
    app.processEvents()
    frame.toggle_playlist_panel()
    panel.finish_animation()
    app.processEvents()

    assert panel.width() == chosen, (
        f"kullanıcı genişliği korunmadı: {chosen} -> {panel.width()}")


# --- 5. Event loop animasyon sırasında cevap vermeli ---

def test_event_loop_stays_responsive_during_the_animation(dock_window):
    app, window, frame = dock_window()
    panel = open_panel(app, window, frame)
    animation = panel.animation
    duration = max(1, animation.duration())

    ticks = []
    from PyQt6.QtCore import QTimer
    timer = QTimer()
    timer.setSingleShot(False)
    timer.setInterval(0)
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start()
    try:
        for index in range(13):
            animation.setCurrentTime(int(duration * index / 12))
            app.processEvents()
    finally:
        timer.stop()

    assert ticks, "animasyon sırasında event loop hiç tick üretmedi"
