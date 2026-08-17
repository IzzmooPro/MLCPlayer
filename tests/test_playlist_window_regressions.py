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
from PyQt6.QtCore import QPoint, QRect, QSize, Qt
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QMainWindow, QVBoxLayout, QWidget)

from app.config import WINDOW_BACKGROUND
from app.media_controls import show_playlist
from app.title_bar import TITLE_BAR_SIDE_MARGIN, TITLE_BUTTON_SIZE
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


# --- 1b. Ana pencereyle AYNI tasarim dili ----------------------------

def test_the_playlist_uses_the_main_window_background(player_window):
    """Kullanıcı bildirdi (17 Ağustos 2026): renk ana pencereden farklıydı.

    Panel gömülüyken kendi nötr rengi (#131416) vardı ve video üstünde
    yüzdüğü için mantıklıydı. Ayrı pencereye taşınınca ana pencerenin
    yanına gelip farklı tonda durmaya başladı. Renk TEK kaynaktan gelir.
    """
    app, window, frame = player_window()

    panel = open_playlist(app, window, frame)

    assert WINDOW_BACKGROUND.lower() in panel.styleSheet().lower(), (
        "playlist ana pencerenin yuzey rengini kullanmiyor")
    assert "rgba(19, 20, 22" not in panel.styleSheet(), (
        "eski gomulu panel rengi duruyor")


def test_the_playlist_has_no_native_title_bar(player_window):
    """Ana pencere frameless; playlist de öyle olmalı.

    ÖLÇÜLDÜ: bayraksız `Qt.Window` Windows'ta 31 px'lik native başlık
    çubuğu çiziyordu. Panelin ZATEN kendi başlığı ve kapatma düğmesi var,
    yani kullanıcı iki başlık birden görüyordu ve üstteki uygulamanın
    tasarımına hiç uymuyordu.
    """
    app, window, frame = player_window()

    panel = open_playlist(app, window, frame)

    assert panel.windowFlags() & Qt.WindowType.FramelessWindowHint, (
        "playlist penceresinde native baslik cubugu var")


def test_the_playlist_can_be_dragged_by_its_header(player_window):
    """Frameless pencere native başlıktan taşınamaz; başlık alanı taşır.

    Bu olmadan panel frameless yapılınca HİÇ taşınamaz hâle gelirdi.
    """
    app, window, frame = player_window()
    panel = open_playlist(app, window, frame)
    before = panel.pos()

    # API GLOBAL nokta alir -- gercek fare olayindaki gibi.
    press = panel.mapToGlobal(QPoint(140, 18))
    panel.begin_header_drag(press)
    panel.continue_header_drag(press + QPoint(60, 25))
    panel.end_header_drag()
    app.processEvents()

    assert panel.pos().x() == before.x() + 60
    assert panel.pos().y() == before.y() + 25


def test_the_playlist_styles_its_tooltips_like_the_rest_of_the_app(
        player_window):
    """Kullanıcı bildirdi: "Kapat (Esc)" ipucu kocaman çıkıyordu.

    `APP_STYLE` ana pencereye kuruludur, `QApplication`a değil. Playlist
    AYRI bir top-level pencere olduğu için ipucu ürünün stilini almıyor,
    sistem varsayılanına düşüyordu.
    """
    app, window, frame = player_window()

    panel = open_playlist(app, window, frame)

    assert "QToolTip" in panel.styleSheet(), (
        "playlist ipuclari urunun stilini almiyor")


def test_the_playlist_close_button_matches_the_title_bar_one(player_window):
    """Kapatma düğmesi ana pencerenin başlık çubuğundakiyle AYNI olmalı.

    Panel ayrı bir penceredir; kendi ölçüsünü uydurması onu yabancı
    gösteriyordu (36x36 metin "×" vs 34x34 ikon).
    """
    app, window, frame = player_window()
    panel = open_playlist(app, window, frame)
    button = panel.close_button

    assert button.size() == QSize(TITLE_BUTTON_SIZE, TITLE_BUTTON_SIZE), (
        f"kapat dugmesi {button.size()} != baslik cubugu "
        f"{TITLE_BUTTON_SIZE}x{TITLE_BUTTON_SIZE}")
    assert button.text() == "", "metin '×' yerine ikon kullanilmali"
    assert not button.icon().isNull(), "kapat ikonu yok"
    # Sag kenar payi baslik cubugununkiyle ayni.
    assert panel.width() - (button.x() + button.width()) == TITLE_BAR_SIDE_MARGIN


def test_the_resize_filter_does_not_drive_the_main_window_from_the_playlist(
        player_window):
    """Kullanıcı bildirdi: playlist'te her yerde yatay resize imleci çıkıyor.

    `FramelessResizeFilter` panel ANA PENCERENİN İÇİNDE bir yüzeyken
    kuruluyordu; kenar olayları ona düşebiliyordu. Panel artık AYRI bir
    penceredir ve koordinatları ana pencereye eşlenince anlamsız kenarlar
    üretiyor, imleç her yerde resize'a dönüyordu.
    """
    from app.title_bar import FramelessResizeFilter

    app, window, frame = player_window()
    panel = open_playlist(app, window, frame)

    # Fixture'in penceresi DEGISTIRILMEZ. Onceki surum burada
    # `window.title_bar = None` yapip `central_widget`i degistiriyordu;
    # fixture teardown'i bozuluyor ve surec SESSIZCE cokuyordu (10 test
    # sonrasi ozet hic basilmadi). Filtre kendi tek kullanimlik
    # penceresine kurulur.
    # Probe KENDI widget'larini kullanir. Onceki surum buraya fixture'in
    # gercek `frame`ini veriyordu; filtre o cerceveye kuruluyor, probe
    # silinince SARKAN bir olay filtresi kaliyor ve SONRAKI test sessizce
    # cokuyordu (10 test sonrasi ozet hic basilmadi).
    probe = QMainWindow()
    probe.central_widget = QWidget(probe)
    probe.title_bar = None
    probe.media_container = QWidget(probe)
    probe_frame = QWidget(probe)
    probe_frame.control_overlay = None
    probe_frame.playlist_panel = panel
    probe.video_frame = probe_frame
    filt = FramelessResizeFilter(probe, None)
    try:
        filt.install()
        assert not any(target is panel for target in filt.targets), (
            "resize filtresi hala playlist penceresine kurulu")
    finally:
        # Ne olursa olsun hicbir hedefte filtre BIRAKILMAZ.
        for target in list(filt.targets):
            try:
                target.removeEventFilter(filt)
            except Exception:
                pass
        probe.close()
        probe.deleteLater()
        app.processEvents()


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
