"""Sinematik pencerede görünür dış boşluk olmamalı (A).

`main_layout` sinematik modda dört kenara da RESIZE_MARGIN (12 px) iç boşluk
uyguluyordu. Bu değer bir hit-test toleransıdır; görünür içerik marjına
dönüştüğü için video ve playlist pencere kenarlarına sıfır oturmuyor, sağda,
solda ve altta ince koyu bir çerçeve görünüyordu.

RESIZE_MARGIN yalnızca `app/title_bar.py::resize_edges_at` ve
`FramelessResizeFilter` yolunda kalmalıdır.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QMainWindow, QVBoxLayout, QWidget)

from app.media_controls import show_playlist
from app.player import CINEMATIC_CONTENT_MARGINS
from app.title_bar import RESIZE_MARGIN, resize_edges_at
from app.video_frame import VideoFrame


@pytest.fixture
def cinematic_window(monkeypatch):
    monkeypatch.delenv("MLCPLAYER_CLASSIC_UI", raising=False)
    monkeypatch.setattr("app.media_controls.QDialog.exec", lambda self: 0)
    monkeypatch.setattr(
        "app.media_controls.QMessageBox.information", lambda *args: 0)
    app = QApplication.instance() or QApplication([])
    created = []

    def factory(size=(1280, 720)):
        window = QMainWindow()
        window.cinematic_ui_enabled = True
        window.playlist = [r"C:\media\first.mkv"]
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
        # Marj kararı ürünün KENDİ sabitinden gelir; test kendi değerini
        # uydurmaz, böylece ürün geri alınırsa bu testler de kırmızıya döner.
        window.main_layout.setContentsMargins(*CINEMATIC_CONTENT_MARGINS)
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
        frame.close_control_overlay()
        window.close()
    app.processEvents()


def global_rect(widget):
    return QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())


# --- Ürün kaynağı: sinematik main_layout marjları ---

def test_product_cinematic_layout_uses_zero_visible_margins():
    """Ürün kodu sinematik modda görünür marj UYGULAMAMALI."""
    import inspect

    from app import player as player_module

    assert player_module.CINEMATIC_CONTENT_MARGINS == (0, 0, 0, 0), (
        "sinematik içerik marjları sıfır değil: "
        f"{player_module.CINEMATIC_CONTENT_MARGINS}")
    source = inspect.getsource(player_module.MPVPlayer.__init__)
    assert "setContentsMargins(\n                RESIZE_MARGIN" not in source, (
        "main_layout hâlâ RESIZE_MARGIN'i görünür iç boşluk olarak kullanıyor")
    assert "setContentsMargins(*CINEMATIC_CONTENT_MARGINS)" in source


def test_resize_margin_constant_is_still_available_for_hit_testing():
    """RESIZE_MARGIN kaldırılmamalı; yalnızca hit-test toleransı olmalı."""
    assert RESIZE_MARGIN == 12


# --- Görünür yerleşim: içerik kenarlara sıfır oturmalı ---

def test_media_row_spans_the_whole_window_width(cinematic_window):
    app, window, frame = cinematic_window()
    container = window.media_container

    assert container.geometry().left() == 0
    assert container.width() == window.width(), (
        f"içerik satırı {container.width()} px, pencere {window.width()} px")


def test_video_touches_left_and_bottom_edges_without_gap(cinematic_window):
    app, window, frame = cinematic_window()
    window_rect = global_rect(window)
    video_rect = global_rect(frame)

    assert video_rect.left() == window_rect.left(), (
        f"solda {video_rect.left() - window_rect.left()} px boşluk var")
    assert video_rect.bottom() == window_rect.bottom(), (
        f"altta {window_rect.bottom() - video_rect.bottom()} px boşluk var")


def test_video_touches_the_right_edge_when_playlist_is_closed(cinematic_window):
    app, window, frame = cinematic_window()
    window_rect = global_rect(window)
    video_rect = global_rect(frame)

    assert video_rect.right() == window_rect.right(), (
        f"sağda {window_rect.right() - video_rect.right()} px boşluk var")


def test_playlist_touches_the_right_edge_when_open(cinematic_window):
    app, window, frame = cinematic_window()
    show_playlist(window)
    app.processEvents()
    panel = frame.playlist_panel
    panel.finish_animation()
    app.processEvents()

    window_rect = global_rect(window)
    panel_rect = global_rect(panel)

    assert panel_rect.right() == window_rect.right(), (
        f"playlist sağında {window_rect.right() - panel_rect.right()} px boşluk")
    assert panel_rect.bottom() == window_rect.bottom()
    assert global_rect(frame).left() == window_rect.left()


def test_no_outer_frame_remains_after_fullscreen_round_trip(cinematic_window):
    app, window, frame = cinematic_window()
    frame.enter_fullscreen()
    app.processEvents()
    frame.exit_fullscreen()
    app.processEvents()

    margins = window.main_layout.contentsMargins()
    assert (margins.left(), margins.right(), margins.bottom()) == (0, 0, 0)
    window_rect = global_rect(window)
    video_rect = global_rect(frame)
    assert video_rect.left() == window_rect.left()
    assert video_rect.bottom() == window_rect.bottom()


# --- Hit-test toleransı korunmalı ---

@pytest.mark.parametrize("point, expected", (
    ((2, 300), Qt.Edge.LeftEdge),
    ((1278, 300), Qt.Edge.RightEdge),
    ((600, 718), Qt.Edge.BottomEdge),
    ((2, 718), Qt.Edge.LeftEdge | Qt.Edge.BottomEdge),
    ((1278, 718), Qt.Edge.RightEdge | Qt.Edge.BottomEdge),
    ((2, 2), Qt.Edge.LeftEdge | Qt.Edge.TopEdge),
    ((1278, 2), Qt.Edge.RightEdge | Qt.Edge.TopEdge),
))
def test_resize_hit_test_still_covers_edges_and_corners(point, expected):
    rect = QRect(0, 0, 1280, 720)
    assert resize_edges_at(rect, QPoint(*point)) == expected


def test_hit_test_tolerance_is_independent_of_visible_margins():
    """Marj 0 olsa da kenardan 12 px içeride hâlâ resize bölgesi olmalı."""
    rect = QRect(0, 0, 1280, 720)
    assert resize_edges_at(rect, QPoint(RESIZE_MARGIN, 300)) == Qt.Edge.LeftEdge
    assert resize_edges_at(rect, QPoint(RESIZE_MARGIN + 1, 300)) == Qt.Edge(0)
