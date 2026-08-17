# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Playlist'in BAĞIMSIZ PENCERE sözleşmesi (aşama 2).

`test_playlist_dock_embedding_regressions.py`nin yerini alır. O dosya
panelin `playlist_dock_host`un gerçek child'ı olmasını ölçüyordu; kullanıcı
kararıyla (17 Ağustos 2026) panel ana pencerenin YANINDA duran sahipli bir
top-level pencereye taşındı, dolayısıyla o dosyanın konusu ortadan kalktı.

ESKİ DOSYADAKİ HER GEÇERLİ SÖZLEŞME BURADA KORUNDU. Özellikle ikisi
gevşetilmedi, çünkü ikisi de gerçek kullanıcı hatasından doğmuştu:

1. **Panel `Tool` penceresi OLAMAZ.** Kullanıcı "başka uygulama öne
   gelince playlist kayboluyor" diye raporlamıştı; sebebi ayrı pencere
   olmak değil, `Qt.Tool` olmaktı (Qt'de `Tool` pencereleri uygulama
   odağı kaybedince gizlenir).
2. **Playlist ile video ASLA kesişmez.** Eskiden bu "yapısal olarak
   imkânsız"dı; artık ÖLÇÜLEREK korunur.

Çözülen iddialar ve karşılıkları:

    panel.parent() is playlist_dock_host  -> panel.parent() is window
    not panel.isWindow()                  -> panel.isWindow()
    panel.window() is window              -> panel.window() is panel
    panel dolduruyor host'u               -> panel ana pencerenin sağında
    host layout genişliği ayırıyor        -> video genişliği HİÇ değişmiyor
    panel.pos() == (0, 0)                 -> (küresel konum artık meşru)
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QMainWindow, QVBoxLayout, QWidget)

from app.media_controls import show_playlist
from app.video_frame import VideoFrame


@pytest.fixture
def player_window(monkeypatch):
    """Ürünün media_container yerleşimi — dock host YOK."""
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


def open_playlist(app, window, frame):
    show_playlist(window)
    app.processEvents()
    panel = frame.playlist_panel
    panel.finish_animation()
    app.processEvents()
    return panel


def global_rect(widget):
    return QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())


def window_type(widget):
    """Pencere TÜRÜ — bayrakları maskesiz `&` ile denetlemek YANILTIR.

    `Qt.WindowType.Tool` bileşik bir değerdir (`Window` bitini içerir), bu
    yüzden `flags & Tool` sıradan bir `Window` için de doğru çıkar. Tür
    karşılaştırması `WindowType_Mask` ile yapılır.
    """
    return widget.windowFlags() & Qt.WindowType.WindowType_Mask


# --- 1. Yapısal sahiplik ---------------------------------------------

def test_the_playlist_is_a_top_level_window(player_window):
    app, window, frame = player_window()

    panel = open_playlist(app, window, frame)

    assert panel.isWindow(), "playlist bagimsiz pencere degil"
    assert panel.window() is panel


def test_the_playlist_window_is_owned_by_the_main_window(player_window):
    """Sahiplik ŞART: sahipsiz pencere ana pencereyle birlikte inmez."""
    app, window, frame = player_window()

    panel = open_playlist(app, window, frame)

    assert panel.parent() is window, (
        "playlist penceresi ana pencereye ait degil; birlikte simge "
        "durumuna inmez ve arkasinda kalabilir")


def test_the_playlist_is_never_a_tool_window(player_window):
    """KORUNDU: `Tool`, odak kaybinda pencereyi GIZLER.

    Kullanicinin raporladigi "baska uygulama one gelince playlist
    kayboluyor" hatasinin gercek sebebi buydu.
    """
    app, window, frame = player_window()

    panel = open_playlist(app, window, frame)

    assert window_type(panel) != Qt.WindowType.Tool, (
        "playlist yine `Tool` penceresi; odak kaybinda kaybolur")
    assert window_type(panel) == Qt.WindowType.Window


def test_the_playlist_never_floats_above_other_applications(player_window):
    """KORUNDU: always-on-top kullanilmaz."""
    app, window, frame = player_window()

    panel = open_playlist(app, window, frame)

    assert not (panel.windowFlags()
                & Qt.WindowType.WindowStaysOnTopHint)


# --- 2. Videoyla kesismeme (ESKI DOSYANIN MERKEZI SOZLESMESI) --------

@pytest.mark.parametrize("size", [(1280, 720), (1024, 640), (860, 560),
                                  (760, 520), (640, 480)])
def test_the_playlist_and_the_video_never_intersect(player_window, size):
    app, window, frame = player_window(size)

    panel = open_playlist(app, window, frame)

    overlap = global_rect(panel).intersected(global_rect(frame))
    assert overlap.isEmpty(), (
        f"{size} boyutunda playlist video ile kesisiyor: {overlap}")


def test_opening_the_playlist_does_not_shrink_the_video_surface(player_window):
    """ESKISINDEN GUCLU: video yuzeyi artik HIC degismiyor.

    Eski mimaride host gercek layout genisligi ayiriyordu ve video
    daraliyordu (`test_host_reserves_real_layout_width_for_the_panel`).
    Bagimsiz pencerede video alanindan yer ALINMAZ.
    """
    app, window, frame = player_window()
    before = frame.width()

    panel = open_playlist(app, window, frame)

    assert frame.width() == before, (
        f"playlist acilinca video {before} -> {frame.width()} daraldi")
    assert panel.width() > 0


def test_closing_the_playlist_leaves_the_video_surface_untouched(player_window):
    app, window, frame = player_window()
    before = frame.width()

    panel = open_playlist(app, window, frame)
    panel.close_animated()
    panel.finish_animation()
    app.processEvents()

    assert frame.width() == before


# --- 3. Ana pencereyi izleme (bayat geometri) ------------------------

def test_moving_the_window_keeps_the_playlist_attached(player_window):
    """Panel taşımayı AYNI kadar izler; geride kalmaz.

    Ölçüm kenar aritmetiğiyle değil DELTA ile yapılır: `QRect.right()`
    kapsayıcıdır (`x + w - 1`) ve top-level pencerenin çerçeve payı
    platforma göre değişir; kenar karşılaştırması bu yüzden kırılgandır.
    Sözleşme "panel pencereyle birlikte gitti" ve "kesişme yok"tur.
    """
    app, window, frame = player_window()
    panel = open_playlist(app, window, frame)
    panel_before = panel.x()
    window_before = window.x()

    window.move(window_before + 140, window.y() + 90)
    app.processEvents()

    assert global_rect(panel).intersected(global_rect(frame)).isEmpty()
    assert panel.x() - panel_before == window.x() - window_before, (
        "playlist ana pencerenin tasinmasini izlemedi")


def test_resizing_the_window_does_not_leave_stale_playlist_geometry(
        player_window):
    app, window, frame = player_window()
    panel = open_playlist(app, window, frame)

    window.resize(980, 620)
    app.processEvents()

    overlap = global_rect(panel).intersected(global_rect(frame))
    assert overlap.isEmpty(), f"bayat geometri kesisme birakti: {overlap}"


def test_the_playlist_follows_the_owner_height(player_window):
    app, window, frame = player_window()
    panel = open_playlist(app, window, frame)

    window.resize(1100, 900)
    app.processEvents()

    assert abs(panel.height() - window.frameGeometry().height()) <= 2


# --- 4. Odak yasam dongusu (KORUNDU) ---------------------------------

def test_owner_deactivation_preserves_the_logical_open_state(player_window):
    app, window, frame = player_window()
    panel = open_playlist(app, window, frame)

    window.windowHandle().setVisible(True)
    app.processEvents()

    assert panel.is_open, "odak devrinde playlist acik durumu kayboldu"


def test_returning_focus_keeps_the_playlist_open_without_overlap(player_window):
    app, window, frame = player_window()
    panel = open_playlist(app, window, frame)
    width_before = panel.width()

    window.activateWindow()
    app.processEvents()

    assert panel.is_open
    assert panel.width() == width_before, "kullanici genisligi kayboldu"
    assert global_rect(panel).intersected(global_rect(frame)).isEmpty()


# --- 5. Ayirici (KORUNDU, anlami degisti) ----------------------------

def test_the_separator_stays_visible_and_draggable(player_window):
    app, window, frame = player_window()

    panel = open_playlist(app, window, frame)

    assert panel.resize_handle.isVisible()
    assert panel.resize_handle.width() > 0
    assert panel.resize_handle.height() == panel.height()


def test_the_separator_changes_the_width_in_both_directions(player_window):
    """Genislik artik ana pencereden yer CALMAZ; yalniz panelindir."""
    app, window, frame = player_window()
    panel = open_playlist(app, window, frame)
    start = panel.width()

    panel._placement.set_width(start + 120)
    panel.apply_panel_geometry()
    wider = panel.width()
    panel._placement.set_width(wider - 200)
    panel.apply_panel_geometry()
    narrower = panel.width()

    assert wider > start, f"genisletme calismadi: {start} -> {wider}"
    assert narrower < wider, f"daraltma calismadi: {wider} -> {narrower}"
    assert narrower >= 320, "alt sinir korunmadi"
    assert global_rect(panel).intersected(global_rect(frame)).isEmpty()


def test_widening_the_playlist_does_not_shrink_the_video(player_window):
    app, window, frame = player_window()
    panel = open_playlist(app, window, frame)
    video_before = frame.width()

    panel._placement.set_width(panel.width() + 200)
    panel.apply_panel_geometry()
    app.processEvents()

    assert frame.width() == video_before
