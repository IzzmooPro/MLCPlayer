# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
import ctypes
import os
import math
import threading

from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QMenu, QHBoxLayout,
                             QPushButton, QSizePolicy, QSlider, QVBoxLayout)
from PyQt6.QtGui import QAction, QActionGroup, QCursor
from PyQt6.QtCore import (Qt, QTimer, QPoint, QRect, QSize, QEvent,
                          QEasingCurve, QObject, QPropertyAnimation,
                          pyqtSignal)
from app.ui_components import ClickableSlider
from app.ui_icons import make_media_icon
from app.playlist_panel import PlaylistPanel
from app.utils import format_time
from app.config import APP_STYLE, cinematic_ui_enabled, MAX_VOLUME
from app import track_labels
from app.errors import safe_console
from app.menu_actions import populate_audio_device_menu, populate_recent_menu
from app.i18n import tr, tr_mark, translate_marked
from app.empty_state import EmptyStateOverlay

# Ana menüyle AYNI hız seçenekleri.
PLAYBACK_SPEEDS = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0)

# Video sahnesi üzerinde fare tekerleği: standart bir kademe 120 birimdir
# ve ses adımı ses çubuğunun kendi adımıyla (`VolumeSlider.wheelEvent`) aynıdır.
WHEEL_ANGLE_PER_STEP = 120
WHEEL_VOLUME_STEP = 5

# Sağ-tık menüsü ürünün KOYU temasını kullanır. Stil TEK yerde tanımlanır;
# alt menüler kök menüden miras alır (her alt menüye kopyalanmaz).
CONTEXT_MENU_STYLE = APP_STYLE

# --- Gerçek Windows foreground ölçümü ---
# İmzalar açıkça tanımlanır: varsayılan ctypes dönüş tipi C int'tir ve 64-bit
# HWND değerlerini kırpabilir. wintypes ile pointer-safe hale getirilir.
if os.name == "nt":
    from ctypes import wintypes

    _REAL_USER32 = ctypes.windll.user32
    _REAL_USER32.GetForegroundWindow.argtypes = []
    _REAL_USER32.GetForegroundWindow.restype = wintypes.HWND
    _REAL_USER32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    _REAL_USER32.GetWindowThreadProcessId.restype = wintypes.DWORD
else:  # pragma: no cover - ürün yalnızca Windows'ta çalışır
    wintypes = None
    _REAL_USER32 = None

# Testlerin ölçüm yolunu yamalayabilmesi için ayrı ad.
_user32 = _REAL_USER32


def _foreground_measurement_supported():
    """Gerçek foreground ölçümü bu platformda anlamlı mı?

    Offscreen Qt platformunda foreground kavramı yoktur; ölçüm devre dışıdır
    ve mevcut davranış korunur.
    """
    if os.name != "nt":
        return False
    app = QApplication.instance()
    return not (app is not None and app.platformName() == "offscreen")


def _measure_foreground_pid():
    """Foreground penceresinin PID'i; ölçülemezse None.

    Sıfır HWND, sıfır thread, sıfır PID ve her türlü Win32/ctypes hatası
    "ölçülemedi" sayılır. Çağıran taraf bunu GÜVENLİ yönde (yüzeyleri gizli
    tut) yorumlar.
    """
    if _user32 is None:
        return None
    try:
        hwnd = _user32.GetForegroundWindow()
        if not hwnd:
            return None
        pid = wintypes.DWORD(0)
        thread = _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not thread or not pid.value:
            return None
        return int(pid.value)
    except Exception:
        return None


# Sinematik kontrol katmanı ölçüleri (onaylanmış referans görsele göre).
OVERLAY_HEIGHT = 110
OVERLAY_SIDE_PADDING = 28
OVERLAY_NARROW_SIDE_PADDING = 8
OVERLAY_NARROW_WIDTH = 560
OVERLAY_ACCENT = "#F26A3D"
# PiP, normal kontrol panelini kucuk pencereye sikistirmaz. YouTube benzeri
# yalniz video deneyimi icin fareyle etkilesimde gorunen ince bir serit
# kullanir; oynatma sirasinda mevcut auto-hide kuraliyla tamamen kaybolur.
PIP_OVERLAY_HEIGHT = 54
PIP_OVERLAY_SIDE_PADDING = 12
PIP_OVERLAY_BOTTOM_PADDING = 4
PIP_TIMELINE_HIT_HEIGHT = 18
PIP_PLAY_BUTTON_SIZE = 32
# OSD, kontrol katmanının AYRILMIŞ bandının üstünde durur. Katman
# auto-hide veya opacity=0 olsa bile bant korunur; aksi halde katman geri
# geldiğinde mesaj düğmelerin arkasında kalıyordu.
OSD_OVERLAY_GAP = 14

# --- Altyazı için güvenli alt bant ---------------------------------------
#
# Ölçülen kusur (gerçek video, 1400x772 yüzey): `sub_pos=100` iken
# altyazı bbox'ı (333, 635, 1065, 739), kontrol katmanının üst kenarı
# 662 → altyazı bandın 77 px İÇİNE giriyor ve timeline ile kesişiyordu.
#
# Çözüm SABİT bir yüzde DEĞİLDİR: `sub_pos` kullanıcının tercihidir ve
# 0-100 aralığı, varsayılan %100 korunur. Bunun yerine MPV'ye gerçek
# ayrılmış banttan türetilen bir ALT MARJ verilir; böylece %100 "panele
# en yakın GÜVENLİ konum" olur ve daha küçük değerler altyazıyı yukarı
# taşımaya devam eder.
#
# NOT: bu libmpv'de (v0.36) `sub-margin-y-offset` YOKTUR; var olan
# özellik `sub-margin-y`dir ve `sub-scale-by-window=yes` iken 720 px
# referans yüksekliğine göre ölçeklenir.
SUBTITLE_BAND_GAP = 12
MPV_MARGIN_REFERENCE_HEIGHT = 720

# ASS altyazıda `sub-margin-y` ETKİSİZDİR (ölçüldü: marj 116 → 300'de
# altyazı 0 px hareket etti). Fakat `sub-pos` ÇALIŞIR (ölçüldü: 100 → 80
# arasında ~149 px yukarı hareket). Bu yüzden ASS metin altyazılarında
# güvenli bant, MPV'ye YALNIZ ÇALIŞMA ANINDA yazılan efektif bir
# `sub_pos` ile sağlanır. Kullanıcının kayıtlı tercihi (QSettings ve
# Altyazı Ayarları penceresi) DEĞİŞMEZ; düzeltme onun ÜZERİNE kontrollü
# bir ofset olarak uygulanır.
ASS_SUB_CODECS = frozenset({"ass", "ssa", "ass-text", "subst"})
# Metin tabanlı olup ASS OLMAYAN codec'ler `sub-margin-y` yolunu kullanır.
TEXT_SUB_CODECS = frozenset({"subrip", "srt", "text", "webvtt", "mov_text",
                             "microdvd", "subviewer", "sami", "eia_608"})
OSD_EDGE_MARGIN = 10
# Oynatma sürerken etkileşimsizlik sonrası overlay'in gizlenme süresi.
OVERLAY_AUTO_HIDE_MS = 2500
# Timeline'ın görünmez tıklama alanı. Görsel çizgi yine 3 px'tir;
# kullanıcı çizgiyi ~18 px yukarıdan/aşağıdan kaçırsa da seek çalışır.
OVERLAY_TIMELINE_HIT_HEIGHT = 48
#: Timeline'ın GÖRÜNEN çubuk (groove) yüksekliği; stylesheet ile aynı değer.
#: Hover'da 5 px'e çıkar, ama bant hesabı NORMAL hâli esas alır: hover
#: geçici bir durumdur ve altyazıyı oynatırken oynatmamalıdır.
OVERLAY_TIMELINE_GROOVE_HEIGHT = 3


def overlay_timeline_top_padding():
    """Timeline'ın ÇİZİLEN çubuğu ile tıklama alanının üstü arasındaki pay.

    ÖLÇÜLEN KUSUR (kullanıcı raporu, 16 Ağustos 2026): altyazı doğru
    hesaplanıyordu ama gözle "gereksiz yukarıda" duruyordu. Gerçek pencerede
    ölçüldü (1376×790): katman 110 px ve `overlay_timeline` katmanın EN
    ÜSTÜNDEN başlıyor (y=0..47). O 47 px'in çoğu TIKLAMA alanıdır
    (`OVERLAY_TIMELINE_HIT_HEIGHT`); kullanıcının gördüğü çubuk yalnız 3 px
    ve dikeyde ORTALANMIŞ. Yani çizilen çubuğun üstünde ~22 px GÖRÜNMEZ pay
    var ve ayrılan bant onu da temizliyordu: altyazının altı 672, görünen
    çubuk 708 → 36 px boşluk.

    Bant artık bu görünmez payı saymaz. Kullanıcının GÖRDÜĞÜ hiçbir kontrolle
    çakışma imkânı doğmaz; yalnız boşa harcanan pay geri verilir. Tıklama
    alanı KÜÇÜLTÜLMEZ — o bilerek geniştir (bkz. `OVERLAY_TIMELINE_HIT_HEIGHT`).
    """
    return max(0, (OVERLAY_TIMELINE_HIT_HEIGHT
                   - OVERLAY_TIMELINE_GROOVE_HEIGHT) // 2)
# Windows, `WS_EX_LAYERED` olan overlay penceresinde fare hedefini PİKSEL
# ALFASINA göre seçer: alfa=0 pikseller alttaki mpv `wid` yüzeyine düşer ve
# kontrol gerçek tıklamayla ÇALIŞMAZ (ölçüm: `WindowFromPoint` overlay yerine
# video yüzeyini döndürür, düğmeye hiç `MouseButtonPress` gelmez).
# Bu yüzden bütün interaktif kontroller en düşük KANITLANMIŞ nötr alfayla
# boyanır. Ölçülen minimum 2/255'tir; gözle fark edilmez ve gradient, turuncu
# vurgu, ikon, hover ve geometri değişmez. TEK kaynak budur.
OVERLAY_HIT_ALPHA = 2
OVERLAY_HIT_BACKGROUND = f"rgba(0, 0, 0, {OVERLAY_HIT_ALPHA})"
# Hover'da yalnızca çizim büyür (geometri değişmez).
OVERLAY_ACCENT_HOVER = "#FF7A48"
# CC durum etiketleri
# Modül sabiti: import anında çevirmen yoktur; `tr_mark()` yalnız
# işaretler, çeviri kullanım yerinde `translate_marked()` ile yapılır.
SUBTITLES_ACTIVE_LABEL = tr_mark("Altyazıları Kapat")
SUBTITLES_INACTIVE_LABEL = tr_mark("Altyazıları Aç")
# mpv `sid` bu değerlerde "seçili altyazı yok" demektir.
DISABLED_SID_VALUES = frozenset({"no", "none", "", "0", "false"})
# Görünmez hit alanları: ikonlar 18 px kalır, yalnızca tıklanabilir
# yüzey büyür.
OVERLAY_SIDE_BUTTON_SIZE = 40
OVERLAY_SKIP_BUTTON_SIZE = 40
# Satır aralıkları: geniş pencerede referans görünüm, dar pencerede
# kontroller sığsın diye daraltılır (buton hit alanları sabit kalır).
OVERLAY_CENTRE_SPACING = 8
OVERLAY_RIGHT_SPACING = 10
OVERLAY_NARROW_CENTRE_SPACING = 4
OVERLAY_NARROW_RIGHT_SPACING = 4
# Göster/gizle geçişlerinin fade süreleri.
OVERLAY_FADE_IN_MS = 140
OVERLAY_FADE_OUT_MS = 180

class SubtitleTrackWatcher(QObject):
    """MPV altyazı parçası değişimini ANA thread'e taşıyan tek nokta.

    Neden merkezi: efektif ASS `sub_pos` düzeltmesi yalnız `sub_add`
    çağrılarının yanına yamanırsa bir yol mutlaka unutulur. Ölçülen
    açık tam da buydu — `select_subtitle_language()` yalnız `sid`
    yazıyor, bant senkronlanmıyordu. Burada MPV'nin `sid` ve
    `track-list` özellikleri gözlenir; hangi ürün yolu parçayı
    değiştirirse değiştirsin bant uygulanır.

    THREAD KURALI: MPV callback'i kendi olay thread'inden gelir. Qt
    widget'larına oradan DOKUNULMAZ; iş bir sinyalle ana thread'e
    aktarılır (`AutoConnection` farklı thread'de kuyruğa alır).
    """

    changed = pyqtSignal()

    def __init__(self, on_changed, parent=None):
        super().__init__(parent)
        self._on_changed = on_changed
        self._state_lock = threading.Lock()
        self._mpv_player = None
        self._observed = []
        self._attached = False
        self._notification_queued = False
        # Son GÖZLENEN property değerleri. Bunlar olmadan bant hesabı aynı
        # değerleri libmpv'den SENKRON okumak zorunda kalıyordu; yeniden
        # boyutlandırma sırasında bu okuma mpv'nin core lock'unu bekleyip
        # GUI thread'ini 80 ms'ye kadar durduruyordu (ölçüldü).
        self._values = {}
        # `python-mpv` gözlemciyi kaldırırken kayıt sırasında verilen
        # callback'in AYNISINI ister. Bound-method özniteliğini her okumada
        # yeniden üretmek yerine tek nesne saklanır.
        self._mpv_callback = self._notify
        # Açıkça queued: test/ürün hangi thread'den bildirirse bildirsin
        # senkron aynı çağrı yığınının içinde çalışmaz; fırtına tek olaya
        # birleşir ve QWidget erişimi daima watcher'ın Qt thread'indedir.
        self.changed.connect(self._run, Qt.ConnectionType.QueuedConnection)

    #: Gözlenen MPV özellikleri.
    #:
    #: - `sid`: kullanıcı parçayı değiştirir.
    #: - `track-list`: codec bilgisi GECİKMELİ geldiğinde ikinci kez
    #:   tetikler (dış dosya ekleme de buradan gelir).
    #: - `osd-dimensions`: RENDER ALANI ölçek referansıdır. Tam ekran ve
    #:   playlist geçişinde mpv yeni alanı Qt'nin resize olayından SONRA
    #:   yerleştiriyor; yalnız geometriye bağlanan senkron eski alanla
    #:   hesaplıyor ve boşluk kayıyordu (ölçüldü: tam ekranda 182 px,
    #:   %150 playlistte -91 px).
    #: - `sub-scale`: mpv 0.41 `sub-margin-y`yi yazı ölçeğiyle ÇARPAR
    #:   (ölçüldü; bkz. `VideoFrame.subtitle_margin_scale()`). Marj bu
    #:   yüzden ölçek değişiminde yeniden hesaplanmalı ve değer SENKRON
    #:   okunmamalı — okuma boyutlandırmada core lock'u bekletiyor.
    OBSERVED = ("sid", "track-list", "osd-dimensions", "sub-scale")

    def attach(self, mpv_player):
        """Altyazı parçası ve render alanı değişimlerini gözler."""
        with self._state_lock:
            if self._attached and self._mpv_player is mpv_player:
                return self
        self.detach()
        observed = []
        for name in self.OBSERVED:
            try:
                mpv_player.observe_property(name, self._mpv_callback)
                observed.append(name)
            except Exception as exc:
                safe_console("Could not observe the subtitle track "
                             f"({name}): {type(exc).__name__}")
        with self._state_lock:
            self._mpv_player = mpv_player
            self._observed = observed
            self._attached = True
        return self

    def detach(self):
        """MPV gözlemcilerini tam bir kez ayırır; tekrar çağrı güvenlidir."""
        with self._state_lock:
            player = self._mpv_player
            observed = tuple(self._observed)
            self._mpv_player = None
            self._observed = []
            self._attached = False
            # Yeni oturum eski oturumun değerlerini DEVRALMAZ.
            self._values = {}
            # Kuyrukta bekleyen Qt sinyali `_run()` içinde no-op olur.
            self._notification_queued = False
        if player is None:
            return
        for name in observed:
            try:
                player.unobserve_property(name, self._mpv_callback)
            except Exception as exc:
                # Kapanış ENGELLENMEZ; ham libmpv metni/yolu yazdırılmaz.
                safe_console("Could not detach the subtitle watcher "
                             f"({name}): {type(exc).__name__}")

    def latest(self, name, default=None):
        """Son GÖZLENEN değer; henüz bildirim gelmediyse `default`.

        Bant hesabı bu değeri kullanır ve libmpv'yi SENKRON okumaz — bkz.
        `VideoFrame._observed_property()` içindeki ölçüm.
        """
        with self._state_lock:
            return self._values.get(name, default)

    def _notify(self, name, value):
        """MPV OLAY THREAD'İ. Değeri saklar ve yalnız sinyal yayınlar."""
        # Bir olay fırtınasındaki ilk callback tek bir queued Qt sinyali
        # üretir. Ana thread çalışana kadar sonraki bildirimler birleşir;
        # SON değer burada saklandığı için senkron okumaya gerek kalmaz.
        with self._state_lock:
            self._values[name] = value
            if not self._attached or self._notification_queued:
                return
            self._notification_queued = True
        try:
            self.changed.emit()
        except RuntimeError:
            with self._state_lock:
                self._notification_queued = False

    def _run(self):
        """ANA THREAD. Bant senkronu burada çalışır."""
        with self._state_lock:
            if not self._attached:
                self._notification_queued = False
                return
            self._notification_queued = False
        try:
            self._on_changed()
        except Exception as exc:
            safe_console("Could not refresh the subtitle band on a track "
                         "change: "
                         f"{type(exc).__name__}")


class _PlaceholderStateLabel(QLabel):
    """Legacy placeholder state that never enters the visible/accessibility tree.

    URL loading still uses ``text`` and logical visibility as its state
    contract. The approved ``EmptyStateOverlay`` is the only rendered and
    announced UI, so the old QLabel remains physically hidden at all times.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._placeholder_requested = True
        QLabel.setVisible(self, False)

    def setVisible(self, visible):
        self._placeholder_requested = bool(visible)
        QLabel.setVisible(self, False)

    def show(self):
        self.setVisible(True)

    def hide(self):
        self.setVisible(False)

    def isHidden(self):
        return not self._placeholder_requested

    def placeholderRequested(self):
        return self._placeholder_requested


class VideoFrame(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.is_video_fullscreen = False
        self.control_overlay = None
        self.empty_state_overlay = None
        self.playlist_panel = None
        self._overlay_updating_position = False
        self._overlay_updating_volume = False
        # Video sahnesi üzerindeki tekerlek kademesi için biriktirici.
        self._wheel_angle_remainder = 0
        # Otomatik gizlenme durumu. _overlay_auto_hidden yalnızca
        # etkileşimsizlik nedeniyle gizlenmeyi işaretler; owner deactivate
        # veya minimize nedeniyle gizlenme bundan ayrıdır.
        self.overlay_hide_timer = None
        # (mpv nesnesi, uygulanan marj). Yalnız BAŞARILI yazımdan sonra
        # dolar; aynı geometride tekrar yazım yapılmaz.
        self._subtitle_band_state = None
        self._overlay_auto_hidden = False
        # Ürünün kendi yardımcı pencereleri (ör. Altyazı Merkezi) açıkken
        # katman BASTIRILIR. `_player_owns_foreground()` yalnız SÜREÇ
        # sahipliğini ölçer; aynı süreçteki bir dialog öne geldiğinde ölçüm
        # hâlâ "player önde" der, owner olayları katmanı diriltir ve
        # `raise_()` onu top-level Tool penceresi olarak dialogun ÜSTÜNE
        # taşırdı (kullanıcının ekran görüntüsündeki hata).
        self._overlay_suppressed = False
        self._overlay_hover = False
        self._overlay_event_targets = ()
        self._last_cursor_pos = None
        self.overlay_fade = None
        self._overlay_fade_target = 1.0
        # CC göstergesi: None = henüz hiç hesaplanmadı
        self.overlay_subtitles_active = None
        self._picture_in_picture_mode = False
        self._pip_playlist_was_open = False

        # Mouse takibi için
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Mouse hareket zamanlayıcısı
        self.cursor_timer = QTimer(self)
        self.cursor_timer.setInterval(3000)  # 3 saniye
        self.cursor_timer.timeout.connect(self.hide_cursor)

        # Placeholder yaşam döngüsü (URL yükleme dahil) mevcut kod ve testler
        # için state taşıyıcısı olarak korunur. Görsel başlangıç ekranı artık
        # native child `EmptyStateOverlay`dir; bu eski metin hiçbir z-order
        # geçişinde kullanıcıya geri sızmamalıdır.
        self.placeholder_label = _PlaceholderStateLabel(self)
        self.placeholder_label.setText("MLC Player\nMedia Launch Codec Player")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label.setStyleSheet(
            "color: transparent; background-color: #11161B;"
        )
        self.placeholder_label.setGeometry(0, 0, self.width(), self.height())

        # Tam ekranda kontrol çubuğu görünmediği için geçici durum bildirimi.
        # mpv native render alanı normal child widget'ların üstünü kapatabilir.
        # Bu nedenle OSD ayrı bir üst pencere olarak gösterilir.
        osd_flags = Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
        self.osd_label = QLabel(self.main_window, osd_flags)
        self.osd_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.osd_label.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.osd_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.osd_label.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus)
        self.osd_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.osd_label.setStyleSheet(
            "color: #FFFFFF; background: transparent; border: none; "
            "padding: 0; font-size: 15px; font-weight: normal;"
        )
        self.osd_label.setMinimumWidth(0)
        self.osd_label.hide()
        self.osd_timer = QTimer(self)
        self.osd_timer.setSingleShot(True)
        self.osd_timer.timeout.connect(self.osd_label.hide)

        # Arayüz kararı ana penceredeki tek merkezi durumdan gelir; burada
        # doğrudan ortam değişkeni okunmaz.
        enabled = getattr(self.main_window, "cinematic_ui_enabled", None)
        if enabled is None:
            enabled = cinematic_ui_enabled()
        if enabled:
            self.empty_state_overlay = EmptyStateOverlay(self)
            self._create_control_overlay()
            self._create_playlist_panel()

    def _empty_state_requested(self):
        label = getattr(self, "placeholder_label", None)
        if label is None or label.isHidden():
            return False
        # Bazı ürün/test yolları medya durumunu doğrudan current_file ile
        # kurar. Medya varsa eski placeholder görünür kalsa bile başlangıç
        # yüzeyi kontrol katmanını örtemez. Tek istisna, kullanıcıya özellikle
        # gösterilen URL yükleme durumudur.
        return (not bool(getattr(self.main_window, "current_file", ""))
                or bool(self.main_window.__dict__.get("_url_loading_active")))

    def update_empty_state_geometry(self):
        surface = self.empty_state_overlay
        if surface is None:
            return
        surface.setGeometry(0, 0, max(1, self.width()),
                            max(1, self.height()))

    def sync_empty_state(self):
        """Başlangıç yüzeyini placeholder yaşam döngüsüyle aynı tut."""
        surface = self.empty_state_overlay
        if surface is None:
            return False
        requested = self._empty_state_requested()
        owner_ready = (self.main_window.isVisible()
                       and not self.main_window.isMinimized())
        if not requested or self._overlay_suppressed or not owner_ready:
            surface.hide()
            return False
        self.hide_overlay_immediately()
        # Geç import döngüyü önler: media_controls VideoFrame'i kullanır.
        from app.media_controls import PLACEHOLDER_DEFAULT_TEXT
        surface.set_placeholder_text(self.placeholder_label.text(),
                                     PLACEHOLDER_DEFAULT_TEXT)
        self.update_empty_state_geometry()
        if not surface.isVisible():
            surface.show()
        surface.raise_()
        return True

    def _create_control_overlay(self):
        if self.control_overlay is not None:
            return

        overlay_flags = Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
        self.control_overlay = QWidget(self.main_window, overlay_flags)
        self.control_overlay.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.control_overlay.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        # Düz QWidget'ta stylesheet arka planı ancak bu bayrakla boyanır;
        # aksi halde sinematik gradient hiç çizilmez.
        self.control_overlay.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.control_overlay.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus)
        self.control_overlay.setObjectName("controlOverlayPreview")
        self.control_overlay.setStyleSheet(
            # Üstte tamamen şeffaf başlayıp alta doğru koyulaşan sinematik
            # gradient; kapsül görünümü ve kenarlık yok.
            "QWidget#controlOverlayPreview { background: qlineargradient("
            "x1:0, y1:0, x2:0, y2:1, "
            "stop:0 rgba(12, 12, 14, 0), "
            "stop:0.45 rgba(12, 12, 14, 120), "
            "stop:1 rgba(12, 12, 14, 220)); } "
            # Interaktif kontrollerin TAMAMI en dusuk kanitlanmis notr
            # alfayla boyanir (bkz. OVERLAY_HIT_ALPHA): layered pencerede
            # alfa=0 pikseller Win32 hit-test'te mpv yuzeyine duserdi.
            f"QPushButton {{ background: {OVERLAY_HIT_BACKGROUND}; "
            "border: none; padding: 0; } "
            "QPushButton:hover { background: rgba(255, 255, 255, 28); "
            "border-radius: 4px; } "
            f"QPushButton#overlayPlayPause {{ border: 2px solid {OVERLAY_ACCENT}; "
            f"border-radius: 22px; background: {OVERLAY_HIT_BACKGROUND}; }} "
            f"QPushButton#overlayPlayPause[pipMode=\"true\"] "
            f"{{ border-radius: 16px; }} "
            f"QPushButton#overlayPlayPause:hover {{ background: rgba(242, 106, 61, 45); }} "
            "QSlider::groove:horizontal { height: 3px; background: "
            "rgba(255, 255, 255, 70); border-radius: 1px; } "
            f"QSlider::sub-page:horizontal {{ height: 3px; background: {OVERLAY_ACCENT}; "
            "border-radius: 1px; } "
            f"QSlider::handle:horizontal {{ width: 11px; height: 11px; "
            f"margin: -4px 0; background: {OVERLAY_ACCENT}; border-radius: 5px; }} "
            # Hover yalnızca timeline'a özgüdür; genel QSlider ve ses çubuğu
            # etkilenmez. Yalnızca subcontrol çizimi büyür, geometri değişmez.
            # Hover vurgusu: yalnızca timeline widget'ında, dikey olarak
            # kenarlarda tamamen şeffaf, merkeze doğru hafif belirginleşen
            # nötr ve düşük opaklıklı gradient. Turuncu yalnızca asıl çizgi
            # ve tutamaçta kalır; çevrede turuncu hale oluşmaz.
            # Genel kural: HER slider hit-test alfasi alir. Ses cubugu ADIYLA
            # anilmaz; boylece timeline'a ozgu hover/gradient kurallarinin
            # ses cubuguna sizmadigi mevcut degismezi korunur.
            f"QSlider {{ background: {OVERLAY_HIT_BACKGROUND}; }} "
            f"QSlider#overlayTimeline {{ background: {OVERLAY_HIT_BACKGROUND}; }} "
            "QSlider#overlayTimeline[timelineHover=\"true\"] { background: "
            "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            f"stop:0 rgba(255, 255, 255, {OVERLAY_HIT_ALPHA}), "
            "stop:0.28 rgba(255, 255, 255, 4), "
            "stop:0.44 rgba(255, 255, 255, 10), "
            "stop:0.5 rgba(255, 255, 255, 18), "
            "stop:0.56 rgba(255, 255, 255, 10), "
            "stop:0.72 rgba(255, 255, 255, 4), "
            f"stop:1 rgba(255, 255, 255, {OVERLAY_HIT_ALPHA})); "
            "border-radius: 4px; } "
            "QSlider#overlayTimeline[timelineHover=\"true\"]::groove:horizontal "
            "{ height: 5px; "
            "background: rgba(255, 255, 255, 95); border-radius: 2px; } "
            f"QSlider#overlayTimeline[timelineHover=\"true\"]::sub-page:horizontal "
            f"{{ height: 5px; "
            f"background: {OVERLAY_ACCENT_HOVER}; border-radius: 2px; }} "
            f"QSlider#overlayTimeline[timelineHover=\"true\"]::handle:horizontal "
            f"{{ width: 15px; "
            f"height: 15px; margin: -5px 0; background: {OVERLAY_ACCENT_HOVER}; "
            "border-radius: 7px; }"
        )

        layout = QVBoxLayout(self.control_overlay)
        # Geniş timeline hit alanı alt kontrol satırını aşağı itmesin diye üst
        # boşluk sıfırlanır ve aradaki boşluk daraltılır; alt satırın dikey
        # konumu (merkez y=66) değişmez.
        layout.setContentsMargins(OVERLAY_SIDE_PADDING, 0,
                                  OVERLAY_SIDE_PADDING, 18)
        layout.setSpacing(0)

        # Üst sıra: geniş timeline
        self.overlay_timeline = ClickableSlider(Qt.Orientation.Horizontal)
        self.overlay_timeline.setRange(0, 1000)
        self.overlay_timeline.setObjectName("overlayTimeline")
        # Görsel groove 3 px kalır; tıklanabilir dikey alan kullanıcı için
        # yeterli olsun diye widget yüksekliği büyütülür (ses çubuğu 14 px).
        self.overlay_timeline.setFixedHeight(OVERLAY_TIMELINE_HIT_HEIGHT)
        self.overlay_timeline.setCursor(Qt.CursorShape.PointingHandCursor)
        # NOT: QSS :hover sözde durumu WA_Hover olmadan bu slider'a ulaşmıyor;
        # bayrak olmadan hover büyümesi hiç çizilmiyordu.
        self.overlay_timeline.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.overlay_timeline.setProperty("timelineHover", "false")
        self.overlay_timeline.valueChanged.connect(self._overlay_seek)
        layout.addWidget(self.overlay_timeline)

        # Alt sıra: sol süre, orta medya kontrolleri, sağ tam ekran
        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(OVERLAY_CENTRE_SPACING)
        self._overlay_controls_row = controls

        time_row = QHBoxLayout()
        time_row.setContentsMargins(0, 0, 0, 0)
        time_row.setSpacing(4)
        self.overlay_current_time_label = QLabel("00:00")
        self.overlay_current_time_label.setStyleSheet(
            f"color: {OVERLAY_ACCENT}; background: transparent; font-size: 16px;")
        self.overlay_time_separator = QLabel("/")
        self.overlay_time_separator.setStyleSheet(
            "color: #B9BFC6; background: transparent; font-size: 16px;")
        separator = self.overlay_time_separator
        self.overlay_total_time_label = QLabel("00:00")
        self.overlay_total_time_label.setStyleSheet(
            "color: #D6DBE1; background: transparent; font-size: 16px;")
        for widget in (self.overlay_current_time_label, separator,
                       self.overlay_total_time_label):
            time_row.addWidget(widget)
        self.overlay_time_container = QWidget(self.control_overlay)
        time_container = self.overlay_time_container
        time_container.setLayout(time_row)
        time_container.setStyleSheet("background: transparent;")
        # Sol ve sağ bloklar eşit stretch payı alır; böylece ortadaki medya
        # kontrolleri katmanın gerçek yatay merkezine oturur ve dar pencerede
        # ikisi birlikte küçülür.
        time_container.setMinimumWidth(0)
        # Dar pencerede tek esnek öğe süre metnidir; ikonlar tam boyutta
        # kalabilsin diye bu blok sıkışabilir.
        time_container.setSizePolicy(QSizePolicy.Policy.Ignored,
                                     QSizePolicy.Policy.Preferred)
        controls.addWidget(time_container, 1, Qt.AlignmentFlag.AlignVCenter |
                           Qt.AlignmentFlag.AlignLeft)

        previous = self._make_overlay_button(
            "overlayPrevious", "previous", tr("Önceki"),
            OVERLAY_SKIP_BUTTON_SIZE, 25)
        previous.clicked.connect(
            lambda: self._run_overlay_action(self.main_window.play_previous))
        self.overlay_previous_button = previous
        controls.addWidget(previous, 0, Qt.AlignmentFlag.AlignVCenter)

        # Referans görselde merkez sembol de turuncudur.
        self.overlay_play_pause_button = self._make_overlay_button(
            "overlayPlayPause", "play", tr("Oynat"), 44, 27, OVERLAY_ACCENT)
        self.overlay_play_pause_button.clicked.connect(
            lambda: self._run_overlay_action(self.main_window.play_pause))
        controls.addWidget(self.overlay_play_pause_button, 0,
                           Qt.AlignmentFlag.AlignVCenter)

        next_button = self._make_overlay_button(
            "overlayNext", "next", tr("Sonraki"),
            OVERLAY_SKIP_BUTTON_SIZE, 25)
        next_button.clicked.connect(
            lambda: self._run_overlay_action(self.main_window.play_next))
        self.overlay_next_button = next_button
        controls.addWidget(next_button, 0, Qt.AlignmentFlag.AlignVCenter)

        right_row = QHBoxLayout()
        right_row.setContentsMargins(0, 0, 0, 0)
        right_row.setSpacing(OVERLAY_RIGHT_SPACING)
        self._overlay_right_row = right_row
        right_row.addStretch(1)

        # İşlevsel sıra: CC, ayarlar, ses, ses çubuğu, tam ekran.
        # Ses düğmesi ses çubuğunun hemen yanında kalır.
        self.overlay_subtitles_button = self._make_overlay_button(
            "overlaySubtitles", "subtitles",
            translate_marked(SUBTITLES_INACTIVE_LABEL),
            OVERLAY_SIDE_BUTTON_SIZE, 22)
        self.overlay_subtitles_button.clicked.connect(
            self._on_overlay_subtitles_clicked)
        right_row.addWidget(self.overlay_subtitles_button, 0,
                            Qt.AlignmentFlag.AlignVCenter)

        settings = self._make_overlay_button(
            "overlaySettings", "settings", tr("Video Ayarları"),
            OVERLAY_SIDE_BUTTON_SIZE, 22)
        settings.clicked.connect(lambda: self._run_overlay_action(
            self.main_window.setup_video_adjustments))
        self.overlay_settings_button = settings
        right_row.addWidget(settings, 0, Qt.AlignmentFlag.AlignVCenter)

        self.overlay_volume_button = self._make_overlay_button(
            "overlayVolume", "volume", tr("Sessiz"),
            OVERLAY_SIDE_BUTTON_SIZE, 22)
        self.overlay_volume_button.clicked.connect(
            lambda: self._run_overlay_action(self.main_window.toggle_mute))
        right_row.addWidget(self.overlay_volume_button, 0,
                            Qt.AlignmentFlag.AlignVCenter)

        self.overlay_volume_slider = ClickableSlider(Qt.Orientation.Horizontal)
        self.overlay_volume_slider.setObjectName("overlayVolumeSlider")
        self.overlay_volume_slider.setRange(0, MAX_VOLUME)
        self.overlay_volume_slider.setFixedHeight(14)
        # Dar pencerede bile kullanılabilir kalsın (aşırı daralmasın).
        self.overlay_volume_slider.setMinimumWidth(36)
        self.overlay_volume_slider.setMaximumWidth(96)
        self.overlay_volume_slider.setToolTip(tr("Ses Seviyesi"))
        self.overlay_volume_slider.valueChanged.connect(self._overlay_volume_changed)
        source = getattr(self.main_window, "volume_slider", None)
        if source is not None:
            self._overlay_updating_volume = True
            self.overlay_volume_slider.setValue(int(source.value()))
            self._overlay_updating_volume = False
        right_row.addWidget(self.overlay_volume_slider, 0,
                            Qt.AlignmentFlag.AlignVCenter)

        fullscreen = self._make_overlay_button(
            "overlayFullscreen", "fullscreen", tr("Tam Ekran"),
            OVERLAY_SIDE_BUTTON_SIZE, 22)
        fullscreen.clicked.connect(lambda: self._run_overlay_action(
            self.main_window.toggle_fullscreen))
        self.overlay_fullscreen_button = fullscreen
        right_row.addWidget(fullscreen, 0, Qt.AlignmentFlag.AlignVCenter)
        self.overlay_pip_exit_button = self._make_overlay_button(
            "overlayPipExit", "restore", tr("Normal Pencereye Dön"), 32, 19)
        self.overlay_pip_exit_button.clicked.connect(
            lambda: self._run_overlay_action(
                lambda: self.main_window.toggle_picture_in_picture(False)))
        self.overlay_pip_exit_button.hide()
        right_row.addWidget(self.overlay_pip_exit_button, 0,
                            Qt.AlignmentFlag.AlignVCenter)
        right_container = QWidget(self.control_overlay)
        right_container.setLayout(right_row)
        # NOT: kapsayicinin stylesheet'i cocuklarina da uygulanir. Duz
        # `transparent` verilirse icindeki CC/ayarlar/ses/tam ekran
        # dugmeleri alfa=0 kalir ve Win32 hit-test'te mpv yuzeyine duser
        # (bkz. OVERLAY_HIT_ALPHA). Bu yuzden ayni en dusuk notr alfa
        # kullanilir.
        right_container.setStyleSheet(
            f"background: {OVERLAY_HIT_BACKGROUND};")
        right_container.setMinimumWidth(0)
        self.overlay_right_container = right_container
        controls.addWidget(right_container, 1, Qt.AlignmentFlag.AlignVCenter |
                           Qt.AlignmentFlag.AlignRight)

        layout.addLayout(controls)

        # Tek, yeniden kullanılan fade animasyonu.
        self.overlay_fade = QPropertyAnimation(
            self.control_overlay, b"windowOpacity", self)
        self.overlay_fade.setDuration(OVERLAY_FADE_IN_MS)
        self.overlay_fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.overlay_fade.finished.connect(self._on_overlay_fade_finished)
        self.control_overlay.setWindowOpacity(0.0)

        # Tek, singleShot auto-hide timer'ı. cursor_timer'dan bağımsızdır.
        self.overlay_hide_timer = QTimer(self)
        self.overlay_hide_timer.setSingleShot(True)
        self.overlay_hide_timer.setInterval(OVERLAY_AUTO_HIDE_MS)
        self.overlay_hide_timer.timeout.connect(self.hide_overlay_for_inactivity)

        self.main_window.installEventFilter(self)
        self.installEventFilter(self)

        # Overlay ve child kontrollerinde etkileşim izleme. Her hedefe yalnızca
        # bir kez filtre kurulur.
        targets = [self.control_overlay] + self.control_overlay.findChildren(QWidget)
        for target in targets:
            target.installEventFilter(self)
        self._overlay_event_targets = tuple(targets)
        self._last_cursor_pos = QCursor.pos()

    def set_picture_in_picture_mode(self, enabled):
        """Normal panel ile PiP'nin ince, video-odakli seridini degistirir.

        PiP ayni libmpv HWND'sini kullanir. Burada yalniz yardimci kontrol
        yuzeyinin olculeri/gorunurlugu degisir; medya yeniden yuklenmez.
        """
        enabled = bool(enabled)
        if self.control_overlay is None:
            self._picture_in_picture_mode = enabled
            return
        if enabled == self._picture_in_picture_mode:
            return

        self._picture_in_picture_mode = enabled
        panel = self.playlist_panel
        if enabled and panel is not None:
            self._pip_playlist_was_open = (
                self._pip_playlist_was_open or bool(panel.is_open))
            if panel.is_open:
                panel.close_animated()
                panel.finish_animation()

        normal_only = (
            self.overlay_previous_button,
            self.overlay_next_button,
            self.overlay_subtitles_button,
            self.overlay_settings_button,
            self.overlay_volume_button,
            self.overlay_volume_slider,
            self.overlay_fullscreen_button,
            self.overlay_current_time_label,
            self.overlay_time_separator,
            self.overlay_total_time_label,
        )
        for widget in normal_only:
            widget.setVisible(not enabled)
        self.overlay_pip_exit_button.setVisible(enabled)

        if enabled:
            self.overlay_timeline.setFixedHeight(PIP_TIMELINE_HIT_HEIGHT)
            self.overlay_play_pause_button.setFixedSize(
                PIP_PLAY_BUTTON_SIZE, PIP_PLAY_BUTTON_SIZE)
            self.overlay_play_pause_button.setIconSize(QSize(20, 20))
            self.overlay_time_container.setMinimumWidth(
                PIP_PLAY_BUTTON_SIZE)
            self.control_overlay.setFixedHeight(PIP_OVERLAY_HEIGHT)
        else:
            self.control_overlay.setMinimumHeight(0)
            self.control_overlay.setMaximumHeight(16777215)
            self.overlay_timeline.setFixedHeight(
                OVERLAY_TIMELINE_HIT_HEIGHT)
            self.overlay_play_pause_button.setFixedSize(44, 44)
            self.overlay_play_pause_button.setIconSize(QSize(27, 27))
            self.overlay_time_container.setMinimumWidth(0)

        self.control_overlay.setProperty("pipMode", enabled)
        self.overlay_play_pause_button.setProperty("pipMode", enabled)
        self.control_overlay.style().unpolish(self.control_overlay)
        self.control_overlay.style().polish(self.control_overlay)
        self.overlay_play_pause_button.style().unpolish(
            self.overlay_play_pause_button)
        self.overlay_play_pause_button.style().polish(
            self.overlay_play_pause_button)
        self.update_overlay_geometry()
        self.show_overlay_for_interaction()

        if not enabled and self._pip_playlist_was_open:
            # Player ayni cagri icinde normal pencere geometrisini geri
            # yukler. Bir event turu ertelemek paneli eski PiP kenarina
            # yerlestirmeyi onler.
            QTimer.singleShot(0, self._restore_playlist_after_pip)

    def _restore_playlist_after_pip(self):
        panel = self.playlist_panel
        if self._picture_in_picture_mode:
            return
        should_restore = self._pip_playlist_was_open
        self._pip_playlist_was_open = False
        if (should_restore and not self._picture_in_picture_mode
                and panel is not None and not panel.is_open):
            panel.open_animated()

    def _create_playlist_panel(self):
        if self.playlist_panel is None:
            self.playlist_panel = PlaylistPanel(self.main_window, self)
            self._bind_playlist_state_store()

    def _bind_playlist_state_store(self):
        """Panelin genişlik/yapışma/konum kaydını gerçek ayarlara bağlar.

        Panel `QSettings` NESNESİ TUTMAZ; iki işlev enjekte edilir (Altyazı
        penceresiyle aynı politika). Ayarlar yoksa panel sessizce
        kalıcılıksız çalışır.
        """
        panel = self.playlist_panel
        settings = getattr(self.main_window, "settings", None)
        if panel is None or settings is None:
            return

        def read(key):
            try:
                value = settings.value(key)
            except Exception:
                return None
            if key == panel.STATE_SNAPPED and value is not None:
                # QSettings Ini biçiminde bool'u DİZE olarak geri verir;
                # "false" boş olmayan bir dizedir ve doğrudan `bool()`
                # ile True çıkardı.
                if isinstance(value, str):
                    return value.strip().lower() in ("true", "1", "yes")
                return bool(value)
            if key == panel.STATE_POS and value is not None:
                try:
                    return (int(value[0]), int(value[1]))
                except (TypeError, ValueError, IndexError):
                    return None
            return value

        def write(key, value):
            try:
                settings.setValue(key, list(value)
                                  if isinstance(value, tuple) else value)
            except Exception:
                pass

        panel.bind_state_store(read, write)

    def toggle_playlist_panel(self):
        """Sinematik playlist'i aynı ikonla açar/kapatır."""
        if self._picture_in_picture_mode:
            # PiP'nin urun sozlesmesi video disinda sahipli pencere acmaz.
            return False
        if self.playlist_panel is None:
            return False
        if self.playlist_panel.is_open:
            self.playlist_panel.close_animated()
        else:
            # NOT: Yer ayırmayı open_animated TEK SEFER yapar; burada ayrıca
            # reserve etmek gereksiz bir layout/video resize turu ekliyordu.
            self.playlist_panel.open_animated()
            # Panel açıkken kontrol overlay'i kendi kendine gizlenmemelidir.
            self.cancel_overlay_hide()
        return self.playlist_panel.is_open

    def refresh_playlist_panel(self):
        panel = self.playlist_panel
        if panel is not None and panel.is_open:
            # Kapalı panel açılırken `open_animated()` zaten taze modeli
            # kurar. Gizli panelin bütün satır widget'larını her medya
            # açılışında yeniden üretmek Windows'ta 170-840 ms GUI-thread
            # maliyeti ölçtü ve timeline'ın ilk boyamasını geciktiriyordu.
            panel.refresh()

    def update_playlist_panel_geometry(self):
        """Panele yerini YENIDEN hesaplattirir.

        Playlist artik ana pencerenin YANINDA duran bagimsiz bir penceredir
        (bkz. `app/playlist_panel.py::WindowPlacement`). Video alanindan yer
        AYRILMAZ; eski dock makinesi (`reserve_playlist_dock`,
        `apply_playlist_dock_width`, `release_playlist_dock`,
        `playlist_dock_target_width`, `set_playlist_panel_width`) bu adimda
        KALDIRILDI. Birakilsaydi her overlay guncellemesinde video alani
        daralmaya devam ederdi; olculdu: 982 -> 570 px.
        """
        panel = self.playlist_panel
        if panel is None or not panel.is_open:
            return
        apply_geometry = getattr(panel, "apply_panel_geometry", None)
        if callable(apply_geometry):
            apply_geometry()

    def _make_overlay_button(self, object_name, icon_kind, label, size, icon_size,
                             colour="#FFFFFF"):
        """Metinsiz, ikonlu ama erişilebilir kalan overlay düğmesi üretir."""
        button = QPushButton(self.control_overlay)
        button.setObjectName(object_name)
        button.setText("")
        button.setToolTip(label)
        button.setAccessibleName(label)
        button.setFixedSize(size, size)
        button.setIconSize(QSize(icon_size, icon_size))
        button.setIcon(make_media_icon(icon_kind, icon_size, colour))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return button

    def _overlay_seek(self, value):
        if not self._overlay_updating_position:
            self.main_window.seek_position(value)

    def _wheel_targets_video_scene(self, event):
        """Teker YALNIZ açık videonun çıplak sahnesinde ele alınır.

        Yer tutucu ekranda (medya yok) ve kaydırılabilir ÇOCUK yüzeylerin
        üzerinde olay ürüne bırakılır; kontrol katmanı, menüler ve playlist
        ayrı pencerelerdir, zaten buraya düşmez.
        """
        if not getattr(self.main_window, "current_file", None):
            return False
        return self.childAt(event.position().toPoint()) is None

    def wheelEvent(self, event):
        """Video sahnesinde dikey teker sesi bir kademe değiştirir.

        Ses TEK kaynaktan geçer: `change_volume()` -> `volume_slider` ->
        `set_volume()`. Sınırlar, etiket, mute durumu, overlay slider'ı ve
        OSD o ortak akıştan gelir; burada ikinci bir ses yolu yoktur.
        """
        angle = event.angleDelta()
        if (not self._wheel_targets_video_scene(event)
                or angle.y() == 0 or abs(angle.y()) <= abs(angle.x())):
            self._wheel_angle_remainder = 0
            super().wheelEvent(event)
            return
        # Yüksek çözünürlüklü fareler 120'den küçük artıklar gönderir; her
        # olay tek tek kademe saymaz, standart 120 birimde birikir.
        self._wheel_angle_remainder += angle.y()
        steps = int(self._wheel_angle_remainder / WHEEL_ANGLE_PER_STEP)
        if steps:
            self._wheel_angle_remainder -= steps * WHEEL_ANGLE_PER_STEP
            try:
                self.main_window.change_volume(steps * WHEEL_VOLUME_STEP)
            except Exception as e:
                # Kullanıcıya ham teknik metin çıkmaz.
                safe_console(f"Volume wheel error: {type(e).__name__}")
        event.accept()

    def _overlay_volume_changed(self, value):
        """Kullanıcı overlay ses çubuğunu değiştirdiğinde ürünün gerçek
        ses akışını (klasik volume_slider -> set_volume) çalıştırır."""
        if self._overlay_updating_volume:
            return
        source = getattr(self.main_window, "volume_slider", None)
        if source is not None and source.value() != int(value):
            source.setValue(int(value))

    def _subtitles_are_visible(self):
        """Gerçek MPV durumu: görünürlük + gerçekten seçili altyazı parçası.

        mpv `sid` özelliği "no"/"auto"/0/"0"/"" gibi değerler döndürebildiği
        için sadece sid'in dolu olması yeterli değildir; seçim track_list ile
        doğrulanır. Herhangi bir özellik okunamazsa güvenli tarafta kalınır.
        """
        player = getattr(self.main_window, "mpv_player", None)
        if player is None:
            return False
        try:
            if not bool(player.sub_visibility):
                return False
            sid = getattr(player, "sid", None)
        except Exception:
            return False

        if sid is None or sid is False:
            return False
        if isinstance(sid, str) and sid.strip().lower() in DISABLED_SID_VALUES:
            return False
        if isinstance(sid, bool):
            return False
        if isinstance(sid, int) and sid <= 0:
            return False

        try:
            tracks = list(getattr(player, "track_list", None) or [])
        except Exception:
            return False
        if not tracks:
            return False

        subtitle_tracks = [track for track in tracks
                           if isinstance(track, dict)
                           and track.get("type") == "sub"]
        if not subtitle_tracks:
            return False

        if isinstance(sid, str) and sid.strip().lower() == "auto":
            return any(bool(track.get("selected")) for track in subtitle_tracks)

        try:
            wanted = int(sid)
        except (TypeError, ValueError):
            return False
        return any(track.get("id") == wanted for track in subtitle_tracks)

    def _update_overlay_subtitle_state(self):
        """CC ikonunu gerçek altyazı durumuna göre renklendirir."""
        button = getattr(self, "overlay_subtitles_button", None)
        if button is None:
            return
        active = self._subtitles_are_visible()
        if active == self.overlay_subtitles_active:
            return
        self.overlay_subtitles_active = active
        label = translate_marked(
            SUBTITLES_ACTIVE_LABEL if active else SUBTITLES_INACTIVE_LABEL)
        button.setAccessibleName(label)
        button.setToolTip(label)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setIcon(make_media_icon(
            "subtitles", button.iconSize().width(),
            OVERLAY_ACCENT if active else "#FFFFFF"))

    def _overlay_action_allowed(self):
        """Tamamen gizli overlay'in kontrolleri işlem üretmemeli."""
        return (self.control_overlay is not None
                and self.control_overlay.isVisible())

    def _run_overlay_action(self, action):
        """Görünür overlay üzerinde çalışan kontrol eylemi."""
        if not self._overlay_action_allowed():
            return
        # Etkileşim overlay'i görünür tutar; fade-out sürüyorsa tersine döner.
        self.show_overlay_for_interaction()
        action()

    def _on_overlay_subtitles_clicked(self):
        if not self._overlay_action_allowed():
            return
        self.show_overlay_for_interaction()
        self.main_window.toggle_subtitles()
        self._update_overlay_subtitle_state()

    def _update_overlay_volume_state(self):
        """Klasik slider, klavye, mute veya ayar geri yükleme kaynaklı ses
        değişimlerini overlay'e yansıtır. Ek timer kullanmaz."""
        slider = getattr(self, "overlay_volume_slider", None)
        if slider is None:
            return
        source = getattr(self.main_window, "volume_slider", None)
        if source is not None and not slider.isSliderDown():
            value = int(source.value())
            if slider.value() != value:
                # Programatik güncelleme ikinci bir set_volume üretmemeli.
                self._overlay_updating_volume = True
                slider.setValue(value)
                self._overlay_updating_volume = False

        muted = (bool(getattr(self.main_window, "is_muted", False))
                 or slider.value() == 0)
        label = tr("Sesi Aç") if muted else tr("Sessiz")
        button = self.overlay_volume_button
        if button.accessibleName() != label:
            button.setAccessibleName(label)
            button.setToolTip(label)
            button.setIcon(make_media_icon(
                "volume_muted" if muted else "volume", button.iconSize().width()))

    @staticmethod
    def _format_overlay_time(seconds):
        try:
            seconds = float(seconds)
            if not math.isfinite(seconds) or seconds < 0:
                return "00:00"
            seconds = int(seconds)
        except (TypeError, ValueError):
            return "00:00"
        if seconds >= 3600:
            hours, remainder = divmod(seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return format_time(seconds)

    def update_overlay_state(self):
        if self.control_overlay is None:
            return

        self._poll_cursor_interaction()

        try:
            duration = float(getattr(self.main_window, "duration", 0) or 0)
            position = float(getattr(self.main_window, "position", 0) or 0)
        except (TypeError, ValueError):
            duration = 0
            position = 0

        valid_duration = math.isfinite(duration) and duration > 0
        valid_position = math.isfinite(position) and position >= 0
        if valid_duration:
            position = min(position if valid_position else 0, duration)
            timeline_value = int((position * 1000) / duration)
        else:
            position = 0
            timeline_value = 0

        if not self.overlay_timeline.isSliderDown():
            if self.overlay_timeline.value() != timeline_value:
                self._overlay_updating_position = True
                self.overlay_timeline.setValue(timeline_value)
                self._overlay_updating_position = False

        current_text = self._format_overlay_time(position)
        total_text = self._format_overlay_time(duration if valid_duration else 0)
        if self.overlay_current_time_label.text() != current_text:
            self.overlay_current_time_label.setText(current_text)
        if self.overlay_total_time_label.text() != total_text:
            self.overlay_total_time_label.setText(total_text)

        self._update_overlay_volume_state()
        self._update_overlay_subtitle_state()

    def update_overlay_play_state(self):
        if self.control_overlay is None:
            return
        paused = getattr(self.main_window, "is_paused", True)
        label = "Oynat" if paused else "Duraklat"
        button = self.overlay_play_pause_button
        if button.accessibleName() != label:
            # Metin görünmez; durum ikon, tooltip ve accessibleName ile taşınır.
            button.setAccessibleName(label)
            button.setToolTip(label)
            button.setIcon(make_media_icon(
                "play" if paused else "pause", button.iconSize().width(),
                OVERLAY_ACCENT))
        # Bu metot yalnızca gerçek oynatma geçişlerinden çağrılır
        # (play_pause, open_path, stop, playlist); periyodik update_ui'dan değil.
        self._sync_overlay_auto_hide()

    # --- Otomatik gizlenme ---

    def _overlay_playback_active(self):
        """Auto-hide yalnızca gerçekten oynatma sürerken anlamlıdır."""
        return (bool(getattr(self.main_window, "current_file", ""))
                and not getattr(self.main_window, "is_paused", True))

    def _overlay_interaction_blocked(self):
        panel = getattr(self, "playlist_panel", None)
        if panel is not None and panel.isVisible() and panel.is_open:
            return True
        if self._overlay_hover:
            return True
        for name in ("overlay_timeline", "overlay_volume_slider"):
            slider = getattr(self, name, None)
            if slider is not None and slider.isSliderDown():
                return True
        return False

    def _poll_cursor_interaction(self):
        """Native mpv yüzeyi VideoFrame'in mouse olaylarını yutabildiği için
        imleç hareketi mevcut update_ui döngüsünden okunur. Yeni timer
        oluşturulmaz; imleç kıpırdamadığında hiçbir şey tetiklenmez."""
        if self.control_overlay is None:
            return
        position = QCursor.pos()
        previous = self._last_cursor_pos
        self._last_cursor_pos = position

        # Hover durumu burada yetkili biçimde yeniden hesaplanır: native mpv
        # yüzeyine geçişte overlay'e Leave olayı ulaşmayabiliyor ve hover
        # takılı kalıyordu.
        hover = (self.control_overlay.isVisible()
                 and self.control_overlay.geometry().contains(position))
        if hover != self._overlay_hover:
            self._overlay_hover = hover
            self.schedule_overlay_hide()

        # Timeline'ın GENİŞ hit alanının tamamı hover görünümünü tetikler.
        # Qt'nin ::groove:hover durumu yalnızca 3 px'lik çizgide çalıştığı
        # için dinamik property kullanılır; geometri değişmez.
        self.set_timeline_hover(
            self.control_overlay.isVisible()
            and self._timeline_global_rect().contains(position))

        if previous is None or position == previous:
            return
        if not self._is_player_surface_active():
            return
        video_rect = QRect(self.mapToGlobal(QPoint(0, 0)), self.size())
        if not video_rect.contains(position):
            return
        self.show_overlay_for_interaction()

    def overlay_suppressed(self):
        """Yardımcı bir ürün penceresi katmanı bastırıyor mu?"""
        return bool(self._overlay_suppressed)

    def set_overlay_suppressed(self, suppressed):
        """Katmanı yardımcı pencere süresince gizler ve gizli TUTAR.

        Bastırma AÇIKKEN hiçbir owner olayı (show/resize/move/activation)
        katmanı geri getiremez ve `raise_()` çağrılmaz; böylece katman
        Altyazı Merkezi'nin üstüne çıkmaz. Kapatıldığında katman normal
        auto-hide akışına döner.
        """
        suppressed = bool(suppressed)
        if suppressed == self._overlay_suppressed:
            return
        self._overlay_suppressed = suppressed
        if suppressed:
            self.hide_overlay_immediately()
            empty_state = getattr(self, "empty_state_overlay", None)
            if empty_state is not None:
                empty_state.hide()
            return
        self._restore_overlay_after_activation()

    def fade_overlay_in(self):
        """Mevcut opaklıktan 1.0'a yumuşak geçiş; gerekiyorsa önce show().

        Altyazı, katman GÖSTERİLMEDEN ve fade-in BAŞLAMADAN önce yukarı
        alınır; aksi halde tek karelik bir kesişme oluşuyordu. Tüm
        gösterme yolları (etkileşim, aktivasyon, duraklatma) buradan
        geçtiği için karar tek noktadadır.
        """
        if self._overlay_suppressed:
            return
        if self.control_overlay is None or self.overlay_fade is None:
            return
        self._overlay_auto_hide_pending = False
        self._set_subtitle_band_collapsed(False)
        animation = self.overlay_fade
        animation.stop()
        if not self.control_overlay.isVisible():
            self.control_overlay.show()
        start = self.control_overlay.windowOpacity()
        self._overlay_fade_target = 1.0
        # CC göstergesi: None = henüz hiç hesaplanmadı
        self.overlay_subtitles_active = None
        animation.setDuration(OVERLAY_FADE_IN_MS)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.setStartValue(start)
        animation.setEndValue(1.0)
        if start >= 1.0:
            # Zaten tam görünür; gereksiz animasyon başlatılmaz.
            self.control_overlay.setWindowOpacity(1.0)
            return
        animation.start()

    def fade_overlay_out(self):
        """Mevcut opaklıktan 0.0'a geçiş; gizleme bitişte yapılır."""
        if self.control_overlay is None or self.overlay_fade is None:
            return
        animation = self.overlay_fade
        animation.stop()
        start = self.control_overlay.windowOpacity()
        self._overlay_fade_target = 0.0
        animation.setDuration(OVERLAY_FADE_OUT_MS)
        animation.setEasingCurve(QEasingCurve.Type.InCubic)
        animation.setStartValue(start)
        animation.setEndValue(0.0)
        animation.start()

    def _on_overlay_fade_finished(self):
        if self.control_overlay is None:
            return
        if self._overlay_fade_target == 0.0:
            self._finish_overlay_fade_out()
        else:
            self.control_overlay.setWindowOpacity(1.0)

    def _finish_overlay_fade_out(self):
        self.control_overlay.hide()
        self.control_overlay.setWindowOpacity(0.0)
        # Altyazı YALNIZ animasyon tamamen bittikten sonra aşağı iner ve
        # yalnız GERÇEK auto-hide için: minimize, odak kaybı, yardımcı
        # dialog ve kapanış gizlemeleri `hide_overlay_immediately()`
        # yolundan gelir ve `_overlay_auto_hidden` işaretlemez.
        if self._overlay_auto_hide_pending:
            self._overlay_auto_hide_pending = False
            self._set_subtitle_band_collapsed(True)

    def hide_overlay_immediately(self):
        """Owner/system olayları: fade kullanılmaz, anında gizlenir.

        Bekleyen auto-hide tamamlanması İPTAL edilir: bu yol minimize, odak
        kaybı, yardımcı dialog ve kapanış içindir, "timeline auto-hide oldu"
        anlamına GELMEZ. `_overlay_auto_hidden` bilerek korunur; aksi halde
        gerçekten tamamlanmış bir auto-hide'dan sonra aktivasyonda timeline
        kendiliğinden geri gelirdi.
        """
        self._overlay_auto_hide_pending = False
        if self.control_overlay is None:
            return
        if self.overlay_fade is not None:
            self.overlay_fade.stop()
        self.control_overlay.hide()
        self.control_overlay.setWindowOpacity(0.0)

    def _timeline_global_rect(self):
        origin = self.overlay_timeline.mapToGlobal(QPoint(0, 0))
        return QRect(origin, self.overlay_timeline.size())

    def set_timeline_hover(self, hovered):
        """Timeline'ın hover görünümünü açar/kapatır (yalnızca çizim)."""
        timeline = getattr(self, "overlay_timeline", None)
        if timeline is None:
            return
        value = "true" if hovered else "false"
        if timeline.property("timelineHover") == value:
            return
        timeline.setProperty("timelineHover", value)
        timeline.style().unpolish(timeline)
        timeline.style().polish(timeline)
        timeline.update()

    def show_overlay_for_interaction(self):
        """Kullanıcı etkileşiminde overlay'i gösterir ve sayacı tazeler."""
        if self.control_overlay is None or self._overlay_suppressed:
            return
        if self._empty_state_requested():
            self.sync_empty_state()
            return
        self._overlay_auto_hidden = False
        if self.main_window.isVisible() and not self.main_window.isMinimized():
            self.update_overlay_geometry()
            self.fade_overlay_in()
        self.schedule_overlay_hide()

    def schedule_overlay_hide(self):
        """Yalnızca oynatma sürüyorsa ve engel yoksa sayacı başlatır."""
        if self.overlay_hide_timer is None:
            return
        if self._overlay_playback_active() and not self._overlay_interaction_blocked():
            self.overlay_hide_timer.start(OVERLAY_AUTO_HIDE_MS)
        else:
            self.overlay_hide_timer.stop()

    def cancel_overlay_hide(self):
        if self.overlay_hide_timer is not None:
            self.overlay_hide_timer.stop()

    def hide_overlay_for_inactivity(self):
        """Timer slotu. Engel varsa veya oynatma yoksa gizleme yapılmaz."""
        if self.control_overlay is None:
            return
        if not self._overlay_playback_active():
            return
        if self._overlay_interaction_blocked():
            return
        self._overlay_auto_hidden = True
        self._overlay_auto_hide_pending = True
        self.fade_overlay_out()

    def _sync_overlay_auto_hide(self):
        """Oynatma state geçişlerinde görünürlüğü ve sayacı hizalar."""
        if self.control_overlay is None:
            return
        if self._overlay_playback_active():
            self.show_overlay_for_interaction()
            return
        # Duraklatılmış, durdurulmuş veya medya yok: overlay görünür kalır.
        self.cancel_overlay_hide()
        self._overlay_auto_hidden = False
        if self.main_window.isVisible() and not self.main_window.isMinimized():
            self.update_overlay_geometry()
            self.fade_overlay_in()

    def _player_owns_foreground(self):
        """Gerçek Windows foreground penceresi bu sürece mi ait?

        `QApplication.activeWindow()` tek başına yeterli kanıt değildir: bir
        Tool yüzeyi döndürebilir ve Qt aktivasyon isteği Windows tarafından
        reddedildiğinde gerçekle çelişebilir. Kullanıcının 1. ekran
        görüntüsünde kontrol katmanının başka uygulamanın üstünde kalması tam
        olarak bu ayrışmadan kaynaklanıyordu.

        Ölçüm anlıktır ve yalnızca mevcut aktivasyon olaylarından çağrılır;
        periyodik yoklama timer'ı YOKTUR. Offscreen platformda gerçek
        foreground kavramı bulunmadığı için ölçüm devre dışıdır.

        Windows'ta ölçüm BAŞARISIZ olursa (sıfır HWND/PID veya API hatası)
        sonuç False'tur. "Ölçemedim -> göster" yönü, yüzen bir katman için
        güvensizdir: başka uygulamanın üstünde asılı kalan kontrol katmanı
        hatasını geri getirir.
        """
        if not _foreground_measurement_supported():
            return True
        return _measure_foreground_pid() == os.getpid()

    def _is_player_surface_active(self):
        # Karar önce gerçek foreground sahipliğine, sonra Qt'nin hangi
        # yüzeyi aktif saydığına bakar. Playlist artık ana pencerenin
        # child'ı olduğu için ayrı bir yüzey olarak listelenmez.
        if not self._player_owns_foreground():
            return False
        return QApplication.activeWindow() in (
            self.main_window, self, self.control_overlay)

    def update_overlay_geometry(self):
        if self.control_overlay is None:
            return
        if self._overlay_suppressed:
            # Bastırılmışken geometri güncellemesi de `raise_()` etmemeli.
            self.hide_overlay_immediately()
            return
        if not self.main_window.isVisible() or self.main_window.isMinimized():
            self.hide_overlay_immediately()
            if self.empty_state_overlay is not None:
                self.empty_state_overlay.hide()
            return
        if self.sync_empty_state():
            self.update_playlist_panel_geometry()
            return
        # Dar pencerede sağ kontrol grubu sığsın diye yan iç boşluk daralır;
        # böylece hiçbir ikon kırpılmaz ve katman video genişliğini aşmaz.
        pip_mode = self._picture_in_picture_mode
        narrow = self.width() < OVERLAY_NARROW_WIDTH
        layout = self.control_overlay.layout()
        if layout is not None:
            if pip_mode:
                padding = PIP_OVERLAY_SIDE_PADDING
                bottom = PIP_OVERLAY_BOTTOM_PADDING
            else:
                padding = (OVERLAY_NARROW_SIDE_PADDING if narrow
                           else OVERLAY_SIDE_PADDING)
                bottom = 18
            current = layout.contentsMargins()
            if current.left() != padding or current.bottom() != bottom:
                layout.setContentsMargins(padding, current.top(),
                                          padding, bottom)

        centre_spacing = (0 if pip_mode else
                          OVERLAY_NARROW_CENTRE_SPACING if narrow
                          else OVERLAY_CENTRE_SPACING)
        right_spacing = (0 if pip_mode else
                         OVERLAY_NARROW_RIGHT_SPACING if narrow
                         else OVERLAY_RIGHT_SPACING)
        controls_row = getattr(self, "_overlay_controls_row", None)
        if controls_row is not None and controls_row.spacing() != centre_spacing:
            controls_row.setSpacing(centre_spacing)
        right_row = getattr(self, "_overlay_right_row", None)
        if right_row is not None and right_row.spacing() != right_spacing:
            right_row.setSpacing(right_spacing)

        # Dar pencerede süre metni yarım gösterilmektense tamamen gizlenir;
        # genişleyince kendiliğinden geri gelir.
        if not pip_mode:
            for widget in (self.overlay_current_time_label,
                           self.overlay_time_separator,
                           self.overlay_total_time_label):
                if widget.isVisibleTo(self.overlay_time_container) == narrow:
                    widget.setVisible(not narrow)

        video_origin = self.mapToGlobal(QPoint(0, 0))
        # Referans: katman video alanının tüm genişliğini kaplar ve alta
        # sıfır boşlukla oturur.
        width = max(1, self.width())
        target_height = PIP_OVERLAY_HEIGHT if pip_mode else OVERLAY_HEIGHT
        height = max(1, min(target_height, self.height()))
        x = video_origin.x()
        y = video_origin.y() + self.height() - height
        self.control_overlay.setGeometry(x, y, width, height)
        self.control_overlay.raise_()
        self.update_playlist_panel_geometry()
        # Bant değiştiyse altyazı marjı da güncellenir (pencere boyutu,
        # tam ekran, playlist ve DPI değişimi bu yoldan geçer). Yazım
        # DOĞRUDAN yapılmaz; boyut durulana kadar ertelenir (bkz.
        # `_schedule_subtitle_band_sync`).
        self._schedule_subtitle_band_sync()

    def _device_ratio(self):
        """Mantıksal → cihaz piksel oranı (%150 DPI'da 1.5)."""
        try:
            return float(self.devicePixelRatioF() or 1.0)
        except Exception:
            return 1.0

    # Gözlemciden GELEN son değerler. Ürün yolunda bunları
    # `SubtitleTrackWatcher` doldurur; test/erken çağrı yollarında boştur ve
    # davranış eskisi gibi senkron okumaya düşer.
    _observed_mpv_values = None

    def note_observed_property(self, name, value):
        """Gözlemcinin bildirdiği son değeri kaydeder (ANA THREAD)."""
        if self._observed_mpv_values is None:
            self._observed_mpv_values = {}
        self._observed_mpv_values[name] = value

    _OBSERVED_MISSING = object()

    def _observed_property(self, name):
        """Gözlenen değer; bilinmiyorsa `_OBSERVED_MISSING`.

        ÖLÇÜLEN KUSUR (16 Ağustos 2026): bant hesabı her çağrısında
        `osd-dimensions`, `sid` ve `track-list` özelliklerini libmpv'den
        SENKRON okuyordu. Okumaların kendisi ucuz (boştayken üçü 0,2 ms),
        ama yeniden boyutlandırma sırasında mpv swapchain'i kurarken core
        lock'u tutuyor ve GUI thread'i o kilidi bekliyor. Gerçek pencerede
        aynı prob: mpv 0.36'da p95 0,42 ms / max 1,24 ms; mpv 0.41'de
        p95 41,70 ms / max 84,55 ms — 60 Hz'de beş kare. Değerler zaten
        gözlendiği için senkron okumaya GEREK YOKTUR.
        """
        values = self._observed_mpv_values
        if values is not None and name in values:
            return values[name]
        watcher = getattr(self.main_window, "_subtitle_watcher", None)
        if watcher is not None:
            try:
                found = watcher.latest(name, self._OBSERVED_MISSING)
            except Exception:
                return self._OBSERVED_MISSING
            if found is not self._OBSERVED_MISSING:
                return found
        return self._OBSERVED_MISSING

    def selected_subtitle_codec(self):
        """SEÇİLİ altyazı parçasının codec'i (yoksa boş dize)."""
        player = getattr(self.main_window, "mpv_player", None)
        if player is None:
            return ""
        try:
            sid = self._observed_property("sid")
            if sid is self._OBSERVED_MISSING:
                sid = getattr(player, "sid", None)
            if not sid or sid in ("no", "auto"):
                return ""
            # MPV `sid`i bazı yollarda DİZE döndürür; karşılaştırma
            # güvenli biçimde tam sayıya çevrilerek yapılır.
            try:
                sid_number = int(sid)
            except (TypeError, ValueError):
                return ""
            tracks = self._observed_property("track-list")
            if tracks is self._OBSERVED_MISSING:
                tracks = getattr(player, "track_list", None)
            for track in list(tracks or []):
                if track.get("type") != "sub":
                    continue
                try:
                    track_id = int(track.get("id"))
                except (TypeError, ValueError):
                    continue
                if track_id == sid_number:
                    return str(track.get("codec") or "").lower()
        except Exception:
            return ""
        return ""

    def subtitle_uses_ass_positioning(self):
        """Seçili altyazı ASS betiği mi? (marj yerine `sub-pos` yolu)"""
        return self.selected_subtitle_codec() in ASS_SUB_CODECS

    def user_subtitle_position(self):
        """Kullanıcının KAYITLI `sub_pos` tercihi (MPV'deki efektif değil)."""
        from app.config import SUBTITLE_DEFAULTS
        from app.subtitle_style import normalise_subtitle_numeric

        default = float(SUBTITLE_DEFAULTS["sub_pos"])
        settings = getattr(self.main_window, "settings", None)
        if settings is None:
            return default
        try:
            stored = settings.value("subtitle/sub_pos", default)
        except Exception:
            return default
        return normalise_subtitle_numeric("sub_pos", stored)

    def subtitle_surface_reference(self):
        """ASS `sub-pos` yüzdesinin haritalandığı YÜKSEKLİK (cihaz px).

        ÖLÇÜLDÜ: `sub-pos` puanı VİDEO ALANINA değil MPV PENCERESİNE
        oranlanıyor. Playlist açıkken (alan 454, pencere 772) `sub_pos`
        100 → 84,2 arası hareket 202 px çıktı; bu 7,43 px/puan, yani
        pencere yüksekliği/100. Alan referansı kullanılırsa düzeltme
        yetersiz ya da aşırı olur (ölçüldü: -83 px ve +119 px).
        """
        player = getattr(self.main_window, "mpv_player", None)
        if player is not None:
            try:
                height = int(dict(player.osd_dimensions or {}).get("h") or 0)
                if height > 0:
                    return height
            except Exception:
                pass
        return max(1, int(self.height() * self._device_ratio()))

    def subtitle_position_offset(self, reference_height=None):
        """ASS için efektif `sub_pos` düşüşü (yüzde puan).

        Ayrılmış bant + boşluk, PENCERE yüksekliğine oranlanır.
        `sub-pos` %100 = altyazı en altta demektir; bu yüzde kadar
        düşmek altyazıyı tam bandın üstüne taşır.

        NOT: `reference_height` yalnız marj yolu için anlamlıdır ve
        burada KULLANILMAZ; konum yüzdesinin referansı farklıdır.
        """
        needed = (self.subtitle_reserved_bottom() + SUBTITLE_BAND_GAP)             * self._device_ratio()
        reference = self.subtitle_surface_reference()
        return max(0.0, min(100.0, needed * 100.0 / max(1, reference)))

    def effective_subtitle_position(self, reference_height=None):
        """MPV'ye YAZILACAK `sub_pos`. Kayıtlı tercih değişmez.

        - ASS betiği: kullanıcı değeri - bant ofseti (0'ın altına inmez).
        - Diğer metin altyazılar: kullanıcı değeri AYNEN (bant zaten
          `sub-margin-y` ile sağlanır; ikinci kez yukarı taşınmaz).
        """
        user_value = self.user_subtitle_position()
        if not self.subtitle_uses_ass_positioning():
            return user_value
        offset = self.subtitle_position_offset(reference_height)
        return max(0.0, round(user_value - offset, 2))

    def subtitle_scale_reference(self):
        """MPV'nin altyazı ölçeğinde kullandığı GERÇEK yükseklik.

        DÜZELTİLDİ (16 Ağustos 2026). Buraya uzun süre RENDER EDİLEN VİDEO
        ALANI (`h - mt - mb`) yazılıyordu. Ölçüm bunun yanlış olduğunu
        gösterdi: motor marjı YÜZEY yüksekliğine göre ölçekliyor ve
        `osd-dimensions` letterbox paylarından BAĞIMSIZ.

        Kanıt 1 — aynı pencerede letterbox değiştirildi, eğim sabit kaldı
        (iki motorda da): `osd h=1360 → 2,881 px/birim`,
        `osd h=639 → 2,881 px/birim`.

        Kanıt 2 — model gerçek kabul ölçümleriyle birebir tutuyor:
        `alt_kenar = yüzey - marj × (yüzey / 720) × sub_scale`.
        `single_line`: marj 116 × (772/720) = 124,4 → alt kenar 647,6;
        ÖLÇÜLEN bbox alt kenarı 647.

        Eski (alan) referansı yalnız letterbox payı KÜÇÜK olduğunda doğru
        sonuç veriyordu (`mt=mb=8` veya `28`). Playlist açıkken pay 159'a
        çıkıyor, alan 772 → 454 düşüyor ve marj ~1,7 kat şişiyordu:
        `o_case_playlist_open` boşluk 105 px (beklenen 10-28). Bu, bozulan
        TEK durumdu ve aynı zamanda letterbox'ı büyük olan TEK durumdu.

        Kaynak `osd-dimensions.h`tır; okunamazsa widget yüksekliğine
        düşülür (tek bir sihirli sabit varsayılmaz).
        """
        player = getattr(self.main_window, "mpv_player", None)
        if player is not None:
            try:
                raw = self._observed_property("osd-dimensions")
                if raw is self._OBSERVED_MISSING:
                    raw = player.osd_dimensions
                osd = dict(raw or {})
                surface = int(osd.get("h") or 0)
                if surface > 0:
                    return surface
            except Exception:
                pass
        return max(1, self.height())

    def subtitle_safe_margin(self, reference_height=None):
        """MPV `sub-margin-y` değeri; GERÇEK ayrılmış banttan türetilir.

        Ölçünün tek kaynağı `_osd_reserved_bottom()`tur: aynı ölçü OSD
        ile paylaşılır, ikinci bir kopya tutulmaz. Altyazının kullandığı
        bant ise `subtitle_reserved_bottom()` üzerinden türetilir:
        timeline auto-hide ile TAMAMEN gizlendiğinde (fade bittikten
        sonra) ayrılan yükseklik 0 olur ve altyazı aşağı iner; katman geri
        gelirken gösterilmeden ÖNCE yeniden yukarı alınır.
        `SUBTITLE_BAND_GAP` her iki durumda da korunur, bu yüzden altyazı
        ekranın dibine yapışmaz. Bastırma, minimize ve odak kaybı
        nedeniyle gizlenme auto-hide SAYILMAZ; bant korunur.

        `reference_height` MPV'nin ölçek referansıdır; bant ise PENCERE
        pikseliyle ölçülür (altyazı letterbox bandına da düşebilir).
        """
        reference = int(reference_height or max(1, self.height()))
        reserved = self.subtitle_reserved_bottom()
        # BİRİM UYUMU: ayrılmış bant MANTIKSAL, `osd-dimensions` ise
        # CİHAZ pikselindedir. %150 DPI'da ikisini karıştırmak marjı 1,5
        # kat küçük hesaplatıyor ve altyazı banda 19 px giriyordu
        # (ölçüldü). Bant, referansla aynı birime çevrilir.
        needed = (reserved + SUBTITLE_BAND_GAP) * self._device_ratio()
        margin = int(round(needed * MPV_MARGIN_REFERENCE_HEIGHT
                           / (max(1, reference) * self.subtitle_margin_scale())))
        # Çok kısa video alanında marj yüzeyi yutmasın.
        return max(0, min(margin, MPV_MARGIN_REFERENCE_HEIGHT // 2))

    def subtitle_margin_scale(self):
        """`sub-margin-y` biriminin YAZI ÖLÇEĞİYLE çarpanı.

        ÖLÇÜLDÜ (16 Ağustos 2026, gerçek pencere, ekran görüntüsünden
        piksel taraması, aynı prob iki motorda):

            margin 0 -> 160 arasında altyazının alt kenarı, alttan px:

            mpv 0.36   sub_scale=1.0:  29 -> 491   eğim 2,888 px/birim
                       sub_scale=2.0:  58 -> 519   eğim 2,881 px/birim   oran 0,998
            mpv 0.41   sub_scale=1.0:  21 -> 482   eğim 2,881 px/birim
                       sub_scale=2.0:  40 -> 963   eğim 5,769 px/birim   oran 2,003

        Yani mpv 0.41 `sub-margin-y`yi `sub-scale` ile ÇARPIYOR; 0.36
        çarpmıyordu. Ürünün marj hesabı 0.36'ya göre kalibre edildiği için
        2,00× yazıda altyazı iki kat yukarı çıkıyordu (`o_case_stress_2x_5px`
        boşluk 33 yerine 153 px). Bölme bu çarpanı geri alır.

        Taban eğim (2,88 = yüzey/720) İKİ MOTORDA DA AYNIDIR; değişen
        yalnız ölçek çarpanıdır, bu yüzden düzeltme de yalnız onu hedefler.
        """
        player = getattr(self.main_window, "mpv_player", None)
        if player is None:
            return 1.0
        try:
            raw = self._observed_property("sub-scale")
            if raw is self._OBSERVED_MISSING:
                raw = getattr(player, "sub_scale", 1.0)
            scale = float(raw or 1.0)
        except (TypeError, ValueError):
            return 1.0
        # Sıfır/negatif ölçek marjı patlatmasın.
        return scale if scale > 0.05 else 1.0

    # Ertelenmiş bant yazımının durumu (sınıf düzeyinde varsayılan).
    _band_sync_pending = False
    _band_sync_size = None

    def _schedule_subtitle_band_sync(self):
        """Bant yazımını pencere boyutu DURULANA kadar erteler.

        ÖLÇÜLEN KUSUR (17 Ağustos 2026; gerçek pencere, gerçek 4K HEVC,
        120 adımlık sürükleme): sürüklemenin toplam 1191,6 ms'sinin
        **345,6 ms'si (%29)** bu bant senkronunda geçiyordu. 476 çağrının
        yalnız 11'i libmpv'ye YAZIYOR, ama yazanların ortalaması 30,2 ms
        ve en kötüsü 54,8 ms — çünkü mpv boyutlandırma sırasında swapchain'i
        kurarken core lock'u tutuyor ve `mpv_set_property` o kilidi bekliyor.
        Önbelleğe düşen 465 çağrı zaten ucuzdu (0,029 ms).

        16 Ağustos'taki tur bu tehlikenin OKUMA yarısını kapatmıştı; onu
        doğrulayan test ise "boyutlandırma fırtınası" adını taşımasına
        rağmen boyutu HİÇ değiştirmiyor, bu yüzden yazma yolu hiç
        çalışmıyordu.

        Yeni kalıcı timer YOKTUR: tek atışlık `QTimer.singleShot(0, ...)`
        kullanılır (bu dosyada zaten kullanılan deyim). Sıradaki tur
        boyutun hâlâ değiştiğini görürse YAZMAZ, kendini yeniden sıraya
        koyar; yazım ancak boyut iki tur üst üste aynı kaldığında yapılır.
        """
        if self._band_sync_pending:
            # Zaten sırada; kaydedilen boyut GÜNCELLENMEZ, aksi hâlde
            # karşılaştırma daima eşit çıkar ve erteleme hiç işlemez.
            return
        self._band_sync_pending = True
        self._band_sync_size = (self.width(), self.height())
        # NOT: bu PyQt6 sürümünde `singleShot(ms, context, slot)` aşırı
        # yüklemesi YOKTUR (ölçüldü: TypeError). Bu yüzden silinmiş widget
        # koruması `_flush_subtitle_band()` içinde açıkça yapılır.
        QTimer.singleShot(0, self._flush_subtitle_band)

    def flush_subtitle_band(self):
        """Bekleyen bant yazımını HEMEN uygular (test ve kapanış yolu)."""
        self._band_sync_pending = False
        self._band_sync_size = None
        return self.sync_subtitle_safe_band()

    def _flush_subtitle_band(self):
        self._band_sync_pending = False
        recorded = self._band_sync_size
        self._band_sync_size = None
        try:
            current = (self.width(), self.height())
        except RuntimeError:
            # Widget kapanışta silinmiş (C++ nesnesi yok). Bekleyen yazım
            # DÜŞER; kapanış yolunda libmpv'ye dokunulmaz.
            return
        if recorded is not None and recorded != current:
            # Boyut hâlâ değişiyor: pahalı yazımı yapma, yeniden sıraya gir.
            self._schedule_subtitle_band_sync()
            return
        self.sync_subtitle_safe_band()

    def invalidate_subtitle_band(self):
        """Bant önbelleğini geçersiz kılar.

        ÖLÇÜLEN KUSUR: `atomic_apply()` (Uygula) kullanıcının HAM
        `sub_pos` değerini doğrudan MPV'ye yazıyor. Önbellek "durum
        değişmedi" dediği için efektif ASS düzeltmesi yeniden
        uygulanmıyor ve altyazı bandın içine düşüyordu (ölçüldü:
        gap +47 → -73). Dışarıdan yazan her yol bu metodu çağırır.
        """
        self._subtitle_band_state = None

    def sync_subtitle_safe_band(self):
        """Güvenli bandı GERÇEK MPV'ye yazar; DEĞİŞMEDİYSE yazmaz.

        ÖLÇÜLEN KUSUR: `update_overlay_geometry()` overlay üzerindeki
        FARE HAREKETLERİNDE de çağrılıyor ve geometri hiç değişmese bile
        her çağrıda üç libmpv özelliği yeniden yazılıyordu — 100 senkron
        = 300 property yazımı. Oynatma sırasında gereksiz ctypes/libmpv
        trafiği ve takılma riski.

        Önbellek YALNIZ başarılı yazımdan sonra güncellenir; hata
        durumunda kayıt tutulmaz ve sonraki çağrı yeniden dener. MPV
        nesnesi değişirse (yeni oturum) sözleşmenin tamamı yeni nesneye
        yazılır.
        """
        player = getattr(self.main_window, "mpv_player", None)
        if player is None:
            return None
        reference = self.subtitle_scale_reference()
        margin = self.subtitle_safe_margin(reference)
        is_ass = self.subtitle_uses_ass_positioning()
        position = self.effective_subtitle_position(reference)
        state = (margin, is_ass, position)
        cached = self._subtitle_band_state
        # Kimlik karşılaştırması: aynı nesne mi? (yeni mpv oturumu eski
        # önbelleği geçersiz kılar). Önbellek altyazı TÜRÜNÜ ve efektif
        # konumu da içerir; ASS/SRT geçişi kaçırılmaz.
        same_player = cached is not None and cached[0] is player
        try:
            if not same_player:
                # Düz metin altyazılarda marj varsayılan olarak etkindir;
                # ASS altyazıda da geçerli olması için açıkça zorlanır.
                player.sub_use_margins = True
                player.sub_ass_force_margins = True
                player.sub_margin_y = margin
                player.sub_pos = position
            else:
                if cached[1][0] != margin:
                    player.sub_margin_y = margin
                # ASS → SRT geçişinde kullanıcının GERÇEK değeri geri
                # yazılır; SRT → ASS geçişinde düzeltme uygulanır.
                if cached[1][1:] != state[1:]:
                    player.sub_pos = position
        except Exception as exc:
            # Başarısızlık ÖNBELLEKLENMEZ; durum bilinmiyor sayılır.
            self._subtitle_band_state = None
            safe_console(f"Could not apply the subtitle safe band: {exc}")
            return None
        self._subtitle_band_state = (player, state)
        return margin

    def showEvent(self, event):
        super().showEvent(event)
        if self.control_overlay is not None:
            QTimer.singleShot(0, self._restore_overlay_if_owner_visible)

    def _restore_overlay_if_owner_visible(self):
        if self._overlay_suppressed:
            self.hide_overlay_immediately()
            return
        # Etkileşimsizlik nedeniyle gizlenmiş overlay'i owner olayları
        # (show/resize/state change) kendiliğinden geri getirmemeli.
        # NOT: Playlist artık ana pencerenin child'ıdır; görünürlüğü Qt
        # tarafından otomatik yönetilir, geri yükleme makyajı gerekmez.
        if self.playlist_panel is not None:
            self.update_playlist_panel_geometry()
        # Foreground gerçekte başka bir süreçteyse owner olayları yüzen
        # yüzeyleri diriltmemelidir.
        if not self._player_owns_foreground():
            self.hide_overlay_immediately()
            if self.empty_state_overlay is not None:
                self.empty_state_overlay.hide()
            return
        if self.sync_empty_state():
            return
        if self._overlay_auto_hidden:
            return
        if (self.control_overlay is not None and self.main_window.isVisible()
                and not self.main_window.isMinimized()):
            self.update_overlay_geometry()
            self.fade_overlay_in()
            self.schedule_overlay_hide()

    def _restore_overlay_after_activation(self):
        # Ana pencere yeniden aktifleştiğinde overlay ilk anda görünür olur.
        # Qt aktivasyon olayı gerçek foreground devrini garanti etmediği için
        # ölçüm burada da tekrarlanır.
        if self._overlay_suppressed:
            self.hide_overlay_immediately()
            return
        if not self._player_owns_foreground():
            self.hide_overlay_immediately()
            return
        self._overlay_auto_hidden = False
        self._restore_overlay_if_owner_visible()

    def _handle_overlay_interaction_event(self, watched, event_type):
        # Timeline'ın 48 px'lik alanına giriş/çıkış anında yansır;
        # 100 ms imleç yoklaması yalnızca güvenli fallback'tir.
        if watched is getattr(self, "overlay_timeline", None):
            if event_type == QEvent.Type.Enter:
                self.set_timeline_hover(True)
            elif event_type == QEvent.Type.Leave:
                self.set_timeline_hover(False)

        if event_type == QEvent.Type.Enter:
            self._overlay_hover = True
            self.show_overlay_for_interaction()
        elif event_type == QEvent.Type.Leave:
            # Overlay'den bir child düğmeye geçişte de Leave gelir. underMouse()
            # child üzerindeyken False dönebildiği için gerçek imleç konumu
            # overlay dikdörtgeniyle karşılaştırılır.
            self._overlay_hover = False
            self.schedule_overlay_hide()
        elif event_type in (QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress,
                            QEvent.Type.MouseButtonRelease,
                            QEvent.Type.HoverMove):
            # NOT: Tamamen gizli overlay bir fare basışıyla geri getirilmez.
            # Aksi halde görünmeyen kontroller tıklamayı işleyebiliyordu.
            # Geri getirme yolu VideoFrame üzerindeki fare hareketidir.
            if self.control_overlay.isVisible():
                self.show_overlay_for_interaction()

    def eventFilter(self, watched, event):
        if (self.control_overlay is not None
                and watched in self._overlay_event_targets):
            if (event.type() == QEvent.Type.ContextMenu
                    and not isinstance(watched, (QPushButton, QSlider))
                    and self._overlay_action_allowed()):
                self.build_context_menu().exec(event.globalPos())
                event.accept()
                return True
            if (event.type() == QEvent.Type.MouseButtonDblClick
                    and not isinstance(watched, (QPushButton, QSlider))
                    and event.button() == Qt.MouseButton.LeftButton
                    and self._overlay_action_allowed()):
                # Katman ayrı bir top-level penceredir; etkileşimsiz gradient
                # veya süre etiketi üstündeki çift tık VideoFrame'e kendiliğinden
                # ulaşmaz. Düğme/slider kendi hareketini korur, boş yüzey ise
                # videonun standart tam-ekran komutuna yönlenir.
                self.main_window.toggle_fullscreen()
                event.accept()
                return True
            self._handle_overlay_interaction_event(watched, event.type())
            return super().eventFilter(watched, event)

        if watched in (self.main_window, self):
            if event.type() == QEvent.Type.Hide:
                self.hide_overlay_immediately()
            elif event.type() == QEvent.Type.WindowDeactivate:
                # Ana pencere -> owner'lı playlist/overlay geçişinde Qt kısa
                # süre activeWindow=None raporlayabilir. Bir event turu bekleyip
                # gerçek hedef belli olduktan sonra dış uygulama kararını ver.
                QTimer.singleShot(0, self._hide_owned_surfaces_if_inactive)
            elif event.type() == QEvent.Type.Show:
                QTimer.singleShot(0, self._restore_overlay_if_owner_visible)
            elif event.type() == QEvent.Type.WindowStateChange:
                if self.main_window.isMinimized():
                    self.hide_overlay_immediately()
                else:
                    QTimer.singleShot(0, self._restore_overlay_if_owner_visible)
            elif event.type() in (QEvent.Type.Move, QEvent.Type.Resize,
                                  QEvent.Type.ZOrderChange):
                self.update_overlay_geometry()
            elif event.type() == QEvent.Type.WindowActivate:
                # Aktivasyon senkron işlenir; gecikmeli çalışırsa aradaki
                # otomatik gizlenmeyi geri alabilir.
                self._restore_overlay_after_activation()
                QTimer.singleShot(0, self._restore_overlay_if_owner_visible)
            elif event.type() == QEvent.Type.Close:
                self.close_control_overlay()
        return super().eventFilter(watched, event)

    def release_overlay_surfaces(self):
        """Kapanışta YÜZEN overlay/OSD pencerelerini sahipli biçimde bırakır.

        `control_overlay` ve `osd_label` ayrı top-level (Tool) pencerelerdir:
        ana pencere kapanınca Qt onları kapatmaz ve sahipsiz kalırlar.
        Burada, MPV'ye dokunulmadan ÖNCE düzenli biçimde bırakılırlar:
        overlay/OSD timer'ları durur, fade animasyonu durur ve geç olayların
        tutunabileceği widget referansları temizlenir.

        KAPSAM NOTU: bu, düzenli UI teardown'udur. Native `0xC0000005`
        hatasının kök nedeninin bu yüzeyler olduğu KANITLANMADI; ölçülen
        tek kesin tetikleyici Qt + libmpv + `audio-device-list` okumasının
        ardından gelen DOĞAL Python finalizasyonudur ve ürün (bkz.
        `main.py`) o faza hiç girmez.

        Yalnız yüzen yüzeyler bırakılır; mpv `wid` yüzeyi (bu widget) ve
        gömülü playlist paneli DOKUNULMAZ. Çağrı idempotenttir ve bırakma
        sonrası gelen geç olaylar mevcut `is None` korumalarına düşer.
        """
        for timer_name in ("overlay_hide_timer", "osd_timer", "cursor_timer"):
            timer = self.__dict__.get(timer_name)
            if timer is None:
                continue
            try:
                timer.stop()
            except RuntimeError:
                pass
        fade = self.__dict__.get("overlay_fade")
        if fade is not None:
            try:
                fade.stop()
            except RuntimeError:
                pass
            self.overlay_fade = None
        # Overlay'in ÇOCUK widget referansları da bırakılır; aksi halde
        # üst yüzey silindikten sonra bunlara dokunan geç bir çağrı
        # "wrapped C/C++ object has been deleted" hatası verirdi.
        for name in ("overlay_timeline", "overlay_volume_slider",
                     "overlay_play_pause_button", "overlay_subtitles_button",
                     "overlay_volume_button", "overlay_previous_button",
                     "overlay_next_button", "overlay_settings_button",
                     "overlay_fullscreen_button", "overlay_pip_exit_button",
                     "overlay_right_container", "overlay_time_container",
                     "overlay_current_time_label", "overlay_time_separator",
                     "overlay_total_time_label"):
            if name in self.__dict__:
                setattr(self, name, None)
        for name in ("control_overlay", "osd_label"):
            widget = self.__dict__.get(name)
            if widget is None:
                continue
            # Referans ÖNCE bırakılır: silme sırasında tetiklenen geç bir
            # olay silinmiş C++ nesnesine ulaşamasın.
            setattr(self, name, None)
            try:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
            except RuntimeError:
                pass
        # `deleteLater()` kapanış sırasında işlenmeyebilir (event loop
        # birazdan biter) ve yüzeyler yorumlayıcı kapanışına kalırdı.
        # Bekleyen silme olayları BURADA, tek seferde boşaltılır: yeni
        # timer veya bekleme süresi eklenmez.
        app = QApplication.instance()
        if app is not None:
            app.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def _hide_owned_surfaces_if_inactive(self):
        # Playlist artık ana pencerenin child'ı olduğu için ayrıca gizlenmez;
        # yalnızca gerçekten yüzen yüzeyler (overlay, OSD) gizlenir.
        if self._is_player_surface_active():
            return
        self.hide_overlay_immediately()
        if self.empty_state_overlay is not None:
            self.empty_state_overlay.hide()
        if self.osd_label is None:
            return
        self.osd_timer.stop()
        self.osd_label.hide()

    def close_control_overlay(self):
        if self.playlist_panel is not None:
            self.playlist_panel.animation.stop()
            self.playlist_panel.hide()
            self.playlist_panel.close()
        if self.control_overlay is not None:
            if self.overlay_fade is not None:
                self.overlay_fade.stop()
            self.control_overlay.hide()
            self.control_overlay.close()
        if self.empty_state_overlay is not None:
            self.empty_state_overlay.hide()
            self.empty_state_overlay.close()

    def resizeEvent(self, event):
        self.placeholder_label.setGeometry(0, 0, self.width(), self.height())
        self.update_empty_state_geometry()
        # ÖNCE katman geometrisi: OSD konumu katmanın gerçek bandına göre
        # hesaplanır, bu yüzden eski geometriyle yerleştirilmemelidir.
        self.update_overlay_geometry()
        if self.osd_label is not None and self.osd_label.isVisible():
            self._center_osd()
        super().resizeEvent(event)

    # (mpv nesnesi, uygulanan marj) — sınıf düzeyinde varsayılan, böylece
    # `__init__` tamamlanmadan gelen bir çağrı da güvenlidir.
    _subtitle_band_state = None

    def _osd_reserved_bottom(self):
        """Kontrol katmanının ayrılmış bant yüksekliği (px).

        Gerçek `control_overlay.geometry()` esas alınır; katman henüz
        yerleşmemişse referans `OVERLAY_HEIGHT` kullanılır. Yükseklik
        kullanılır (konum değil), böylece pencere taşınmış ama katman
        geometrisi henüz güncellenmemişken de doğru bant bulunur.
        """
        if self.control_overlay is None:
            return 0
        height = self.control_overlay.geometry().height()
        if height <= 0:
            height = OVERLAY_HEIGHT
        return max(0, min(int(height), self.height()))

    # Timeline'ın auto-hide ile TAMAMEN gizlendiği durum. Fade sürerken ve
    # suppression/minimize/odak kaybı nedeniyle gizlemede FALSE kalır;
    # yalnız gerçek auto-hide fade'i bittiğinde TRUE olur.
    _overlay_band_hidden = False
    # Auto-hide fade'i BASLADI ama henuz bitmedi. Bastirma/minimize araya
    # girerse bu bekleme IPTAL edilir; kuyrukta kalmis eski fade-finished
    # geri cagrisi bandi cokertemez.
    _overlay_auto_hide_pending = False
    # MPV'ye BASARIYLA uygulanmis bant durumu. Hedef durumdan (
    # `_overlay_band_hidden`) AYRIDIR: yazim basarisizsa burasi dolmaz ve
    # ayni hedef durum bir sonraki cagride yeniden denenir.
    _overlay_band_applied = None

    def subtitle_reserved_bottom(self):
        """Altyazı için ayrılan alt bant yüksekliği (px).

        `_osd_reserved_bottom()` GERÇEK katman yüksekliğinin tek kaynağı
        olarak kalır ve bu karardan etkilenmez (OSD onu kullanmaya devam
        eder). Burada yalnız altyazının kullanacağı bant türetilir:
        timeline auto-hide ile tamamen gizlendiğinde ayrılan yükseklik
        0'dır. `SUBTITLE_BAND_GAP` çağıran taraflarda korunur, bu yüzden
        altyazı ekranın dibine YAPIŞMAZ.
        """
        if self._overlay_band_hidden:
            return 0
        # GÖRÜNMEZ tıklama payı sayılmaz: altyazı kullanıcının GÖRDÜĞÜ
        # çubuğu temizler, onun üstündeki boş alanı değil
        # (bkz. `overlay_timeline_top_padding()`).
        return max(0, self._osd_reserved_bottom()
                   - overlay_timeline_top_padding())

    def _set_subtitle_band_collapsed(self, collapsed):
        """Bant durumunu değiştirir ve YALNIZ gerçek geçişte MPV'ye yazar.

        Aynı durumdaki tekrar çağrılar hiçbir property yazımı üretmez.
        Yazım başarısız olursa `sync_subtitle_safe_band()` önbelleği
        güncellemez; sonraki gerçek olayda yeniden denenir.
        """
        collapsed = bool(collapsed)
        if (collapsed == self._overlay_band_hidden
                and self._overlay_band_applied is collapsed):
            # Durum aynı VE gerçekten uygulanmış: tek bir property bile
            # yeniden yazılmaz.
            return False
        self._overlay_band_hidden = collapsed
        self.invalidate_subtitle_band()
        try:
            applied = self.sync_subtitle_safe_band()
        except Exception as e:
            # Geç gelen kapanış olayları videoyu/kapanışı KESMEZ.
            safe_console(f"Could not update the subtitle band: {type(e).__name__}")
            applied = None
        # Başarısız yazım UYGULANMIŞ sayılmaz; sonraki gerçek olayda aynı
        # hedef durum yeniden denenir.
        self._overlay_band_applied = collapsed if applied is not None else None
        return True

    def _center_osd(self):
        self.osd_label.adjustSize()
        # Uzun metin video alanını aşmasın.
        max_width = max(1, self.width() - 2 * OSD_EDGE_MARGIN)
        if self.osd_label.width() > max_width:
            self.osd_label.resize(max_width, self.osd_label.height())
        video_origin = self.mapToGlobal(QPoint(0, 0))
        # OSD'nin ALT kenarı, katmanın üst kenarından OSD_OVERLAY_GAP kadar
        # yukarıda kalır. Çok kısa video alanında güvenli üst sınıra clamp
        # edilir; mesaj her hâlükârda video alanının içinde kalır.
        band_top = self.height() - self._osd_reserved_bottom()
        top = band_top - OSD_OVERLAY_GAP - self.osd_label.height()
        top = max(OSD_EDGE_MARGIN, top)
        top = min(top, max(0, self.height() - self.osd_label.height()))
        self.osd_label.move(
            video_origin.x() + max(0, (self.width() - self.osd_label.width()) // 2),
            video_origin.y() + top,
        )

    def show_osd(self, text, duration=1200):
        # OSD yüzen bir yüzeydir; yalnızca oynatıcı gerçekten öndeyken
        # görünür. Aksi halde başka uygulamanın üstünde asılı kalıyordu.
        # Kapanışta yüzey bırakıldıysa (bkz. `release_overlay_surfaces`)
        # geç gelen OSD isteği sessizce yok sayılır.
        if self.osd_label is None:
            return
        if not self._player_owns_foreground():
            return
        self.osd_label.setText(text)
        self._center_osd()
        self.osd_label.raise_()
        self.osd_label.show()
        self.osd_timer.start(duration)

    def _main_menu_bar(self):
        menu_bar = getattr(self.main_window, "menuBar", None)
        return menu_bar() if callable(menu_bar) else None

    def enter_fullscreen(self):
        # NOT: VideoFrame ayrı bir top-level pencereye taşınmaz. Aksi halde
        # eski ana pencere masaüstünde ikinci bir pencere olarak görünür kalır.
        # Bunun yerine ana pencerenin kendisi tam ekran yapılır; böylece mpv
        # wid değeri de değişmez.
        if (self.is_video_fullscreen
                or getattr(self.main_window,
                           "picture_in_picture_enabled", False)):
            return
        window = self.main_window
        self._pre_fullscreen_maximized = window.isMaximized()
        self._pre_fullscreen_geometry = window.geometry()

        menu_bar = self._main_menu_bar()
        self._menu_was_visible = bool(menu_bar and menu_bar.isVisible())
        if menu_bar:
            menu_bar.hide()

        panel = getattr(window, "control_container", None)
        self._panel_was_visible = bool(panel and panel.isVisible())
        if panel:
            panel.hide()

        title_bar = getattr(window, "title_bar", None)
        self._title_bar_was_visible = bool(title_bar and title_bar.isVisible())
        if title_bar:
            title_bar.hide()

        # ÖLÇÜLEN KUSUR (17 Ağustos 2026): playlist bu listede UNUTULMUŞTU.
        # Ayrı bir pencere olduğu için tam ekranda gizlenmiyor, 2560x1440
        # videonun ÜSTÜNDE (2140, 0, 420, 1392) kalıyordu. Yalnız GÖRÜNÜR
        # olan gizlenir; kapalı playlist çıkışta kendiliğinden AÇILMAZ.
        playlist = self.playlist_panel
        self._playlist_was_open = bool(playlist is not None
                                       and playlist.is_open)
        if playlist is not None and self._playlist_was_open:
            playlist.hide()

        # Frameless resize kenarı tam ekranda anlamsızdır; video ekranı
        # tam olarak doldurmalı.
        layout = getattr(window, "main_layout", None)
        self._pre_fullscreen_margins = (
            layout.contentsMargins() if layout is not None else None)
        if layout is not None:
            layout.setContentsMargins(0, 0, 0, 0)

        # NOT: Bayrak showFullScreen()'den ÖNCE set edilir; aksi halde
        # pencere durum olayı sırasında çalışan z-order yardımcısı hâlâ
        # normal pencere sanıp başlık çubuğunu geri gösteriyordu.
        self.is_video_fullscreen = True
        window.showFullScreen()
        self.setFocus()
        self.cursor_timer.start()
        self.update_overlay_geometry()
        self.show_overlay_for_interaction()

    def exit_fullscreen(self):
        if not self.is_video_fullscreen:
            return
        window = self.main_window
        self.cursor_timer.stop()
        self.setCursor(Qt.CursorShape.ArrowCursor)

        if getattr(self, "_pre_fullscreen_maximized", False):
            window.showMaximized()
        else:
            window.showNormal()
            geometry = getattr(self, "_pre_fullscreen_geometry", None)
            if geometry is not None:
                window.setGeometry(geometry)

        menu_bar = self._main_menu_bar()
        if menu_bar and getattr(self, "_menu_was_visible", True):
            menu_bar.show()

        # Klasik panel yalnızca fullscreen öncesinde görünürse geri gelir;
        # preview açıkken gizli kalmaya devam eder.
        panel = getattr(window, "control_container", None)
        if panel and getattr(self, "_panel_was_visible", False):
            panel.show()

        title_bar = getattr(window, "title_bar", None)
        if title_bar and getattr(self, "_title_bar_was_visible", False):
            title_bar.show()

        # Playlist yalnız tam ekrandan ÖNCE açıksa geri gelir. Geometrisi
        # yeniden hesaplanır: ana pencere tam ekrandayken boyutu değişti,
        # yapışık panelin eski konumu bayattır.
        playlist = self.playlist_panel
        if playlist is not None and getattr(self, "_playlist_was_open", False):
            playlist.show()
            playlist.apply_panel_geometry()

        layout = getattr(window, "main_layout", None)
        margins = getattr(self, "_pre_fullscreen_margins", None)
        if layout is not None and margins is not None:
            layout.setContentsMargins(margins)

        # NOT: Bayrak, z-order yardımcısından ÖNCE temizlenmelidir; aksi
        # halde ensure_title_bar_on_top() hâlâ fullscreen sanıp erken döner
        # ve başlık çubuğunun öne alınması tesadüfi Qt olaylarına kalır.
        self.is_video_fullscreen = False

        ensure = getattr(window, "ensure_title_bar_on_top", None)
        if callable(ensure):
            ensure()

        self.update_overlay_geometry()
        self.show_overlay_for_interaction()

    def closeEvent(self, event):
        self.osd_label.hide()
        self.close_control_overlay()
        if self.is_video_fullscreen:
            self.exit_fullscreen()
        event.accept()

    def hide_cursor(self):
        if self.is_video_fullscreen:
            self.setCursor(Qt.CursorShape.BlankCursor)

    def mouseMoveEvent(self, event):
        origin = getattr(self, "_pip_manual_move_origin", None)
        if (self._picture_in_picture_mode and origin is not None
                and event.buttons() & Qt.MouseButton.LeftButton):
            self.main_window.move(event.globalPosition().toPoint() - origin)
            event.accept()
            return
        if self.is_video_fullscreen:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.cursor_timer.start()
        # Video yüzeyindeki hareket overlay'i hemen geri getirir.
        self.show_overlay_for_interaction()
        super().mouseMoveEvent(event)

    def _start_pip_system_move(self):
        handle = self.main_window.windowHandle()
        if handle is not None and hasattr(handle, "startSystemMove"):
            return bool(handle.startSystemMove())
        return False

    def mousePressEvent(self, event):
        self.setFocus()
        if (self._picture_in_picture_mode
                and event.button() == Qt.MouseButton.LeftButton):
            if self._start_pip_system_move():
                event.accept()
                return
            # Eski Qt/platform yolu: yalnız native taşıma yoksa kullanılır.
            self._pip_manual_move_origin = (
                event.globalPosition().toPoint() - self.main_window.pos())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._pip_manual_move_origin = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if not self.is_video_fullscreen:
                self.enter_fullscreen()
            else:
                self.exit_fullscreen()
            event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.is_video_fullscreen:
            self.exit_fullscreen()
            event.accept()
        elif self.main_window:
            # Tam ekranda klavye odağı bu widget'tadır. Diğer kısayolların
            # ana pencerenin merkezi keyPressEvent işleyicisine ulaşmasını sağla.
            self.main_window.keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        # Menü KURULUMU ile GÖSTERİMİ ayrıldı: `build_context_menu()` saf
        # biçimde menüyü döndürür, böylece etiketler testte bloklayıcı
        # `exec()` çağrılmadan ölçülebilir.
        self.build_context_menu().exec(self.mapToGlobal(event.pos()))

    def build_context_menu(self):
        """Sağ-tık menüsünü KURAR ve döndürür (göstermez).

        Düz liste yerine gruplanmış hiyerarşi. Her satır MEVCUT bir player
        metodunu çağırır; metin ve işaret durumları gerçek oynatıcı
        durumundan okunur. Ses/altyazı satırları ana menüyle AYNI
        `track_labels` üreticisinden gelir.
        """
        # NOT: Parent olarak self (VideoFrame) kullanılamaz — mpv render'ı için
        # native pencere sahibi (winId'li) bir çocuk widget'tır. Qt, menü popup'ını
        # gösterirken QWindow::setTransientParent(parent) çağırır ve parent top-level
        # değilse "must be a top level window" uyarısı basar. Top-level pencereye parent et.
        menu = QMenu(self.window())
        # TEK noktadan tema; alt menüler bu stil sayfasını miras alır.
        menu.setStyleSheet(CONTEXT_MENU_STYLE)

        player = self.main_window
        has_media = bool(getattr(player, "current_file", ""))

        play_text = tr("Duraklat") if (has_media and not getattr(
            player, "is_paused", True)) else tr("Oynat")
        self._add_action(menu, play_text, player.play_pause)
        self._add_action(menu, tr("Durdur"), player.stop, enabled=has_media)
        self._add_action(menu, tr("Önceki"), player.play_previous,
                         enabled=self._can_step(-1))
        self._add_action(menu, tr("Sonraki"), player.play_next,
                         enabled=self._can_step(1))
        menu.addSeparator()

        media_menu = menu.addMenu(tr("Medya Aç"))
        self._add_action(media_menu, tr("Dosya Aç"), player.open_file)
        self._add_action(media_menu, tr("Klasör Aç"), player.open_folder)
        self._add_action(media_menu, tr("Bağlantıdan Oynat"), player.open_url)
        media_menu.addSeparator()
        # Ana menüyle AYNI üretici; satırlar menü her açıldığında taze okunur.
        populate_recent_menu(player, media_menu.addMenu(tr("Son Açılanlar")),
                             owner=media_menu)
        menu.addSeparator()

        self._add_action(menu, tr("Oynatma Listesi"), player.show_playlist)
        menu.addSeparator()

        self._build_audio_menu(menu.addMenu(tr("Ses")))
        self._build_subtitle_menu(menu.addMenu(tr("Altyazı")))
        self._build_video_menu(menu.addMenu(tr("Görüntü")), has_media)
        self._build_playback_menu(menu.addMenu(tr("Oynatma")), has_media)

        # Ana menüyle AYNI facade; ayrı dialog yolu veya alt menü yoktur.
        self._add_action(menu, tr("Medya Bilgisi"), player.show_media_info,
                         enabled=has_media)

        menu.addSeparator()
        self._add_action(menu, tr("Uygulamadan Çık"), player.close)
        return menu

    # --- Menü yardımcıları ---

    def _add_action(self, menu, text, slot, enabled=True, checkable=False,
                    checked=False, pass_checked=False):
        """Tek satır: gerçek ürün metodunu TAM BİR KEZ çağırır.

        `pass_checked=True` yalnızca ZORUNLU bir bool bekleyen metotlar
        içindir (`set_loop_file`, `set_loop_playlist`, `toggle_shuffle`).
        Diğer metotlar parametresizdir; `triggered(bool)` argümanı onlara
        GEÇİRİLMEZ.
        """
        action = QAction(text, menu)
        action.setEnabled(enabled)
        if checkable:
            action.setCheckable(True)
            action.setChecked(bool(checked))
        if pass_checked:
            action.triggered.connect(lambda value: slot(bool(value)))
        else:
            action.triggered.connect(lambda _checked=False: slot())
        menu.addAction(action)
        return action

    def _can_step(self, delta):
        """Playlist'te önceki/sonraki satır GERÇEKTEN var mı?"""
        player = self.main_window
        playlist = getattr(player, "playlist", None) or []
        if not playlist:
            return False
        index = getattr(player, "current_playlist_index", 0)
        if not isinstance(index, int):
            index = 0
        if index < 0:
            # Henüz hiçbir parça başlamadı: "önceki"nin anlamı yok. Liste
            # tekrarı açık olsa bile son parçaya SARILMAZ; "sonraki" ilk
            # parçayı başlatır.
            return delta > 0
        if getattr(player, "loop_playlist", False):
            return True
        return 0 <= index + delta < len(playlist)

    def _build_audio_menu(self, menu):
        player = self.main_window
        mute_text = (tr("Sesi Aç") if getattr(player, "is_muted", False)
                     else tr("Sessiz"))
        self._add_action(menu, mute_text, player.toggle_mute)
        self._populate_track_menu(
            menu.addMenu(tr("Ses Parçası")), "audio",
            track_labels.audio_track_labels,
            lambda: self.main_window.mpv_player.aid,
            player.select_audio_track,
            tr("Ses parçası bulunamadı"), tr("Ses parçaları yüklenemedi"))
        # Ses çıkışları ana menüyle ORTAK önbellekten gelir; menü açılışında
        # yeni aygıt taraması YAPILMAZ.
        populate_audio_device_menu(
            player, menu.addMenu(tr("Ses Çıkışı")),
            on_select=player.select_audio_device, owner=menu)

    def _build_subtitle_menu(self, menu):
        player = self.main_window
        try:
            visible = bool(player.mpv_player.sub_visibility)
        except Exception:
            visible = False
        toggle_text = (tr("Altyazıları Gizle") if visible
                       else tr("Altyazıları Göster"))
        self._add_action(menu, toggle_text, player.toggle_subtitles)
        self._populate_track_menu(
            menu.addMenu(tr("Altyazı Parçası")), "sub",
            track_labels.subtitle_track_labels,
            lambda: self.main_window.mpv_player.sid,
            player.select_subtitle_language,
            tr("Altyazı parçası bulunamadı"),
            tr("Altyazı parçaları yüklenemedi"),
            rescan=True)
        self._add_action(menu, tr("Altyazı Dosyası Ekle"),
                         player.open_subtitle)
        from app.config import SUBTITLE_SEARCH_UI_ENABLED
        if SUBTITLE_SEARCH_UI_ENABLED:
            self._add_action(menu, tr("Altyazı Bul"),
                             player.open_subtitle_center)
        self._add_action(menu, tr("Altyazı Ayarları"),
                         player.show_subtitle_settings)

    def _build_video_menu(self, menu, has_media):
        player = self.main_window
        self._add_action(menu, tr("Tam Ekran"), player.toggle_fullscreen,
                         checkable=True,
                         checked=bool(self.is_video_fullscreen))
        self._add_action(
            menu, tr("Resim İçinde Resim"),
            player.toggle_picture_in_picture, checkable=True,
            pass_checked=True,
            checked=bool(getattr(player, "picture_in_picture_enabled", False)))
        self._add_action(menu, tr("Ekran Görüntüsü Al"),
                         player.take_screenshot,
                         enabled=has_media)
        self._add_action(menu, tr("Video Ayarları"),
                         player.setup_video_adjustments)

    def _build_playback_menu(self, menu, has_media):
        player = self.main_window
        for text, delta in ((tr("5 Saniye Geri"), -5),
                            (tr("5 Saniye İleri"), 5),
                            (tr("30 Saniye Geri"), -30),
                            (tr("30 Saniye İleri"), 30)):
            action = QAction(text, menu)
            action.setEnabled(has_media)
            action.triggered.connect(
                lambda _checked=False, value=delta: player.seek_relative(value))
            menu.addAction(action)
        self._add_action(menu, tr("Zamana Git"), player.goto_time,
                         enabled=has_media)
        self._build_speed_menu(menu.addMenu(tr("Oynatma Hızı")))
        menu.addSeparator()
        # Bu üçü ZORUNLU bir bool alır; checked değeri metoda GEÇİRİLİR.
        self._add_action(menu, tr("Tek Dosyayı Tekrarla"),
                         player.set_loop_file,
                         checkable=True, pass_checked=True,
                         checked=bool(getattr(player, "loop_file", False)))
        self._add_action(menu, tr("Oynatma Listesini Tekrarla"),
                         player.set_loop_playlist, checkable=True,
                         pass_checked=True,
                         checked=bool(getattr(player, "loop_playlist", False)))
        self._add_action(menu, tr("Karıştır"), player.toggle_shuffle,
                         checkable=True, pass_checked=True,
                         checked=bool(getattr(player, "shuffle", False)))

    def _build_speed_menu(self, menu):
        """Ana menüyle AYNI hız seçenekleri; işaret gerçek state'ten okunur."""
        player = self.main_window
        try:
            current = float(player.mpv_player.speed)
        except Exception:
            current = 1.0
        group = QActionGroup(menu)
        group.setExclusive(True)
        for speed in PLAYBACK_SPEEDS:
            action = QAction(f"{speed}x", menu)
            action.setCheckable(True)
            action.setChecked(abs(current - speed) < 0.001)
            action.setData(speed)
            action.triggered.connect(
                lambda _checked=False, value=speed:
                player.set_playback_speed(value))
            group.addAction(action)
            menu.addAction(action)

    def _populate_track_menu(self, menu, kind, label_builder, current_getter,
                             on_select, empty_text, error_text, rescan=False):
        """Sağ-tık menüsündeki dinamik parça satırlarını kurar.

        Ana menüyle AYNI etiket üreticisini kullanır; seçim exclusive bir
        `QActionGroup` ile yönetilir ve teknik kimlik yalnız `data()` içinde
        taşınır.
        """
        if not self.main_window.current_file:
            return
        try:
            if rescan:
                self.main_window.mpv_player.command('rescan-external-files')
            track_list = self.main_window.mpv_player.track_list or []
            tracks = [track for track in track_list
                      if isinstance(track, dict) and track.get('type') == kind]
            current = current_getter()
        except Exception as e:
            safe_console(f"Track listing error: {e}")
            error_action = QAction(error_text, self)
            error_action.setEnabled(False)
            menu.addAction(error_action)
            return

        if not tracks:
            empty_action = QAction(empty_text, self)
            empty_action.setEnabled(False)
            menu.addAction(empty_action)
            return

        group = QActionGroup(menu)
        group.setExclusive(True)
        for track, label in zip(tracks, label_builder(tracks)):
            track_id = track.get('id')
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(track_id == current)
            action.setData(track_id)
            action.triggered.connect(
                lambda checked, value=track_id: on_select(value))
            group.addAction(action)
            menu.addAction(action)
