# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Playlist panelinin gerçek dock child'ı olmasını doğrulayan regresyonlar.

Kullanıcı kanıtı (iki gerçek Windows ekran görüntüsü):

1. Başka uygulama öne geldiğinde playlist kayboluyor, alt kontrol yüzeyi
   kalabiliyor -> iki yüzeyin ortak görünürlük yaşam döngüsü yok.
2. Native taşıma/boyutlandırma sonrası playlist bayat global geometriyle
   videonun ÜSTÜNE biniyor.

Kök neden: `PlaylistPanel` ayrı bir top-level `Tool` penceresidir ve
`playlist_dock_host` yalnızca genişlik ayıran boş bir yer tutucudur. Panel
global ekran koordinatlarıyla konumlandığı için Windows onu bağımsız
sıralayabilir, gizleyebilir veya bayat konumda bırakabilir.

Bu dosya paneli host'un gerçek child'ı yapan mimariyi ölçer; kesişme
yapısal olarak imkânsız hale gelmelidir.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QEvent, QPoint, QRect, Qt
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QMainWindow, QVBoxLayout, QWidget)

from app.media_controls import show_playlist
from app.video_frame import VideoFrame


@pytest.fixture
def dock_window(monkeypatch):
    """Ürünün media_container + playlist_dock_host yerleşimini kurar."""
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
        frame.close_control_overlay()
        window.close()
        window.deleteLater()
    app.processEvents()


def open_playlist(app, window, frame):
    show_playlist(window)
    app.processEvents()
    panel = frame.playlist_panel
    panel.finish_animation()
    app.processEvents()
    return panel


def global_rect(widget):
    return QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())


def settle(app, window, frame):
    """Layout ve geometri akışını deterministik biçimde oturtur."""
    app.processEvents()
    window.media_container.layout().activate()
    frame.update_playlist_panel_geometry()
    app.processEvents()


# --- 1. Yapısal sahiplik: panel gerçek bir child olmalı ---

def test_playlist_panel_is_a_child_of_the_dock_host(dock_window):
    app, window, frame = dock_window()
    panel = open_playlist(app, window, frame)

    assert panel.parent() is window.playlist_dock_host, (
        f"panel {panel.parent()!r} altında; playlist_dock_host bekleniyordu")


def test_playlist_panel_is_not_a_top_level_window(dock_window):
    app, window, frame = dock_window()
    panel = open_playlist(app, window, frame)

    assert not panel.isWindow(), (
        "panel hâlâ top-level pencere; Windows onu bağımsız sıralayabilir")


def test_playlist_panel_has_no_tool_window_flag(dock_window):
    app, window, frame = dock_window()
    panel = open_playlist(app, window, frame)

    assert not (panel.windowFlags() & Qt.WindowType.Tool), (
        "Tool bayrağı ayrı HWND üretir; embedding sonrası kalmamalı")


def test_playlist_panel_shares_the_main_window_native_surface(dock_window):
    app, window, frame = dock_window()
    panel = open_playlist(app, window, frame)

    assert panel.window() is window, (
        "panel ana pencerenin native yüzeyine ait değil")


# --- 2. Yerel koordinat ve host'a sığma ---

def test_open_playlist_fills_its_host_in_local_coordinates(dock_window):
    app, window, frame = dock_window()
    panel = open_playlist(app, window, frame)
    host = window.playlist_dock_host
    settle(app, window, frame)

    assert host.isVisible() and host.width() > 0
    assert global_rect(panel) == global_rect(host), (
        f"panel {global_rect(panel)} host {global_rect(host)} ile örtüşmüyor")


def test_host_reserves_real_layout_width_for_the_panel(dock_window):
    app, window, frame = dock_window()
    panel = open_playlist(app, window, frame)
    settle(app, window, frame)

    assert window.playlist_dock_host.width() >= 320
    assert panel.width() == window.playlist_dock_host.width()


# --- 3. Playlist ve video asla kesişmemeli (2. ekran görüntüsü) ---

@pytest.mark.parametrize("size", ((1280, 720), (1600, 900), (960, 600)))
def test_playlist_and_video_never_intersect(dock_window, size):
    app, window, frame = dock_window(size=size)
    panel = open_playlist(app, window, frame)
    settle(app, window, frame)

    overlap = global_rect(panel).intersected(global_rect(frame))
    assert overlap.isEmpty(), (
        f"{size} boyutunda playlist {global_rect(panel)} video "
        f"{global_rect(frame)} ile kesişiyor: {overlap}")


def test_resizing_the_window_does_not_leave_stale_playlist_geometry(dock_window):
    """2. ekran görüntüsündeki tam senaryo: aç, sonra pencereyi küçült."""
    app, window, frame = dock_window(size=(1600, 900))
    panel = open_playlist(app, window, frame)
    settle(app, window, frame)

    window.resize(980, 620)
    settle(app, window, frame)

    overlap = global_rect(panel).intersected(global_rect(frame))
    assert overlap.isEmpty(), (
        f"küçültme sonrası bayat geometri: playlist {global_rect(panel)} "
        f"video {global_rect(frame)} ile kesişiyor: {overlap}")
    assert global_rect(window).contains(global_rect(panel)), (
        "panel ana pencerenin dışına taştı")


def test_moving_the_window_keeps_the_playlist_attached(dock_window):
    app, window, frame = dock_window()
    panel = open_playlist(app, window, frame)
    settle(app, window, frame)
    before = global_rect(panel).topLeft() - global_rect(window).topLeft()

    window.move(window.x() + 180, window.y() + 120)
    settle(app, window, frame)
    after = global_rect(panel).topLeft() - global_rect(window).topLeft()

    assert before == after, (
        f"taşıma sonrası panel ofseti değişti: {before} -> {after}")
    assert global_rect(panel).intersected(global_rect(frame)).isEmpty()


# --- 4. Odak devrinde açık durum korunmalı (1. ekran görüntüsü) ---

def test_owner_deactivation_preserves_the_logical_open_state(dock_window):
    app, window, frame = dock_window()
    panel = open_playlist(app, window, frame)

    app.sendEvent(window, QEvent(QEvent.Type.WindowDeactivate))
    app.processEvents()

    assert panel.is_open, "odak devrinde playlist açık durumu kayboldu"


def test_returning_focus_restores_the_open_playlist_without_overlap(dock_window):
    app, window, frame = dock_window()
    panel = open_playlist(app, window, frame)
    settle(app, window, frame)
    width_before = panel.width()

    app.sendEvent(window, QEvent(QEvent.Type.WindowDeactivate))
    app.processEvents()
    app.sendEvent(window, QEvent(QEvent.Type.WindowActivate))
    settle(app, window, frame)

    assert panel.is_open
    assert panel.isVisible()
    assert panel.width() == width_before, "kullanıcı genişliği kayboldu"
    assert global_rect(panel).intersected(global_rect(frame)).isEmpty()


# --- 5. Embedding sonrası ölü kalan owner mekanizması ---

def test_obsolete_owner_hide_restore_hooks_are_gone(dock_window):
    """Embedding'den sonra owner gizle/geri yükle makyajı kalmamalı."""
    app, window, frame = dock_window()
    panel = open_playlist(app, window, frame)

    for name in ("hide_for_owner", "restore_for_owner"):
        assert not hasattr(panel, name), (
            f"{name} embedding sonrası gereksiz; kaldırılmalı")


def test_playlist_geometry_does_not_depend_on_global_mapping(dock_window):
    """Panel host'a göre yerel konumlanmalı; global eşleme kullanılmamalı."""
    app, window, frame = dock_window()
    panel = open_playlist(app, window, frame)
    settle(app, window, frame)

    # Host child'ı olarak panelin yerel konumu (0,0) olmalıdır.
    assert panel.pos() == QPoint(0, 0), (
        f"panel host içinde yerel (0,0) değil: {panel.pos()}")


# --- 6. Kullanıcı genişliği ve ayraç korunumu ---

def test_separator_drag_changes_width_in_both_directions(dock_window):
    app, window, frame = dock_window(size=(1400, 800))
    panel = open_playlist(app, window, frame)
    settle(app, window, frame)
    start = panel.width()

    frame.set_playlist_panel_width(start + 120)
    settle(app, window, frame)
    wider = panel.width()

    frame.set_playlist_panel_width(start - 60)
    settle(app, window, frame)
    narrower = panel.width()

    assert wider > start, f"sağa/sola genişletme çalışmadı: {start} -> {wider}"
    assert narrower < wider, f"daraltma çalışmadı: {wider} -> {narrower}"
    assert narrower >= 320
    assert global_rect(panel).intersected(global_rect(frame)).isEmpty()


def test_separator_stays_visible_and_draggable_after_embedding(dock_window):
    app, window, frame = dock_window(size=(1400, 800))
    panel = open_playlist(app, window, frame)
    settle(app, window, frame)

    assert panel.resize_handle.isVisible()
    assert panel.resize_handle.width() > 0
    assert panel.resize_handle.height() == panel.height()
