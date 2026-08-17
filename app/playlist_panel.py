# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
import os

from PyQt6.QtCore import (QEasingCurve, QEvent, QPoint, QRect, QSize, Qt,
                          QVariantAnimation)
from PyQt6.QtWidgets import (QAbstractItemView, QHBoxLayout,
                             QLabel, QLayout, QLineEdit, QListWidget, QListWidgetItem,
                             QApplication, QPushButton, QSizePolicy, QVBoxLayout,
                             QWidget)
from app.config import (MEDIA_EXTENSIONS, TOOLTIP_STYLE,
                        WINDOW_BACKGROUND)
from app.title_bar import (TITLE_BAR_ACCENT, TITLE_BAR_SIDE_MARGIN,
                           TITLE_BUTTON_ICON_SIZE, TITLE_BUTTON_SIZE)
from app.ui_icons import make_media_icon
from app.thumbnail_service import ThumbnailService
from app.i18n import tr


PLAYLIST_ACCENT = "#F26A3D"
PATH_ROLE = int(Qt.ItemDataRole.UserRole)
PLAYING_ROLE = PATH_ROLE + 1
ROW_HEIGHT = 74
PANEL_ANIMATION_MS = 190
PANEL_RESIZE_HANDLE_WIDTH = 14


class PlaylistResizeHandle(QWidget):
    """Video ile liste arasındaki sürüklenebilir dikey ayırıcı."""

    def __init__(self, panel):
        super().__init__(panel)
        self.panel = panel
        self._press_global_x = None
        self._press_width = 0
        self.setObjectName("playlistResizeHandle")
        self.setAccessibleName(tr("Oynatma listesi genişliğini ayarla"))
        self.setToolTip(tr("Sola veya sağa sürükleyerek liste genişliğini ayarla"))
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        self.setMouseTracking(True)
        self.setStyleSheet(
            "QWidget#playlistResizeHandle { background: rgba(255,255,255,7); "
            "border-left: 2px solid rgba(255,255,255,58); } "
            f"QWidget#playlistResizeHandle:hover {{ background: rgba(242,106,61,42); "
            f"border-left: 3px solid {PLAYLIST_ACCENT}; }}")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_global_x = int(event.globalPosition().x())
            self._press_width = self.panel.width()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (self._press_global_x is not None
                and event.buttons() & Qt.MouseButton.LeftButton):
            delta = self._press_global_x - int(event.globalPosition().x())
            # TEK genişlik yolu panelindir; tutamaç ile panelin kendi
            # sürüklemesi ayrışmamalıdır (ayrışmıştı: tutamaç dock yolunu
            # çağırıyordu ve pencere modelinde hiçbir şey yapmıyordu).
            self.panel.set_panel_width(self._press_width + delta)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_global_x = None
            event.accept()
            return
        super().mouseReleaseEvent(event)


class PlaylistListWidget(QListWidget):
    """Dahili sıralama ve harici medya bırakmayı aynı listede toplar."""

    def __init__(self, panel):
        super().__init__(panel)
        self.panel = panel
        self.setObjectName("playlistView")
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setAlternatingRowColors(False)
        self.setSpacing(2)
        self._drag_source = -1
        self._drag_target = -1
        self._drag_start = None
        self._drag_moved = False

    def _style_drag_target(self, row, active):
        item = self.item(row) if 0 <= row < self.count() else None
        widget = self.itemWidget(item) if item is not None else None
        if widget is None:
            return
        widget.setProperty("dragTarget", bool(active))
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    def _set_drag_target(self, row):
        if row == self._drag_target:
            return
        self._style_drag_target(self._drag_target, False)
        self._drag_target = row
        self._style_drag_target(self._drag_target, True)

    def _clear_drag_state(self):
        self._style_drag_target(self._drag_target, False)
        self._drag_source = -1
        self._drag_target = -1
        self._drag_start = None
        self._drag_moved = False

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.position().toPoint())
            self._drag_source = self.row(item) if item is not None else -1
            self._drag_target = self._drag_source
            self._drag_start = event.position().toPoint()
            self._drag_moved = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (self._drag_source >= 0
                and event.buttons() & Qt.MouseButton.LeftButton):
            point = event.position().toPoint()
            if (self._drag_start is not None
                    and (point - self._drag_start).manhattanLength()
                    >= QApplication.startDragDistance()):
                self._drag_moved = True
            if self._drag_moved:
                item = self.itemAt(point)
                target = self.row(item) if item is not None else -1
                if target >= 0:
                    self._set_drag_target(target)
                    self.scrollToItem(item)
                event.accept()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drag_source >= 0:
            source = self._drag_source
            target = self._drag_target
            moved = self._drag_moved
            if moved and target >= 0 and target != source:
                self.panel.move_playlist_item(source, target)
                self._clear_drag_state()
                event.accept()
                return
            self._clear_drag_state()
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            paths = [url.toLocalFile() for url in event.mimeData().urls()
                     if url.isLocalFile()]
            self.panel.add_external_files(paths)
            event.acceptProposedAction()
            return
        super().dropEvent(event)
        self.panel.sync_player_order_from_view()


class PlaylistRow(QWidget):
    def __init__(self, path, playing, parent=None):
        super().__init__(parent)
        self.setObjectName("playlistRow")
        self.setProperty("playing", bool(playing))
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAccessibleName(os.path.basename(path))
        self.setToolTip(path)
        # Satır, QListWidget viewport'unun gerçek fare hareketlerini almasına
        # engel olmamalı; sıralama hareketini liste tek yerden yönetir.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setStyleSheet(
            "QWidget#playlistRow { background: transparent; "
            "border-left: 3px solid transparent; border-radius: 4px; } "
            "QWidget#playlistRow[playing=\"true\"] { "
            "background: rgba(242, 106, 61, 28); "
            f"border-left: 3px solid {PLAYLIST_ACCENT}; }} "
            "QWidget#playlistRow[dragTarget=\"true\"] { "
            f"border-top: 2px solid {PLAYLIST_ACCENT}; }}"
        )
        self.setProperty("dragTarget", False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(12)

        self.thumbnail_label = QLabel(self)
        self.thumbnail_label.setObjectName("playlistThumbnail")
        self.thumbnail_label.setFixedSize(82, 50)
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setStyleSheet(
            "background: rgba(255,255,255,10); border: 1px solid "
            "rgba(255,255,255,18); border-radius: 4px;")
        self.thumbnail_label.setAccessibleName(tr("Video küçük resmi"))
        self.thumbnail_label.setProperty("thumbnailState", "empty")
        layout.addWidget(self.thumbnail_label)

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 2, 0, 2)
        text_column.setSpacing(4)
        self.filename_label = QLabel(os.path.basename(path), self)
        self.filename_label.setObjectName("playlistFilename")
        self.filename_label.setStyleSheet(
            "color: #F0F2F5; background: transparent; font-size: 14px;")
        self.filename_label.setSizePolicy(QSizePolicy.Policy.Ignored,
                                          QSizePolicy.Policy.Preferred)
        extension = os.path.splitext(path)[1].lstrip(".").upper() or "MEDYA"
        self.meta_label = QLabel(extension, self)
        self.meta_label.setObjectName("playlistMeta")
        self.meta_label.setStyleSheet(
            "color: #8E969F; background: transparent; font-size: 11px;")
        text_column.addWidget(self.filename_label)
        text_column.addWidget(self.meta_label)
        layout.addLayout(text_column, 1)

        # Liste modeli parça süresi tutmuyor. Yanlış bir süre uydurmak yerine
        # alanı gelecekteki gerçek metadata için boş bırakırız.
        self.duration_label = QLabel("", self)
        self.duration_label.setObjectName("playlistDuration")
        self.duration_label.setStyleSheet(
            "color: #B9BFC6; background: transparent; font-size: 12px;")
        layout.addWidget(self.duration_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self.drag_handle = QLabel("⠿", self)
        self.drag_handle.setObjectName("playlistDragHandle")
        self.drag_handle.setToolTip(tr("Sürükleyerek sırala"))
        self.drag_handle.setStyleSheet(
            "color: #AEB4BB; background: transparent; font-size: 16px;")
        layout.addWidget(self.drag_handle, 0, Qt.AlignmentFlag.AlignVCenter)

    def set_thumbnail(self, image_path):
        from PyQt6.QtGui import QPixmap

        source = QPixmap(image_path)
        if source.isNull():
            return False
        target = self.thumbnail_label.size()
        scaled = source.scaled(
            target, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation)
        x = max(0, (scaled.width() - target.width()) // 2)
        y = max(0, (scaled.height() - target.height()) // 2)
        self.thumbnail_label.setPixmap(scaled.copy(x, y, target.width(), target.height()))
        self.thumbnail_label.setProperty("thumbnailState", "ready")
        return True


#: Panelin bagimsiz pencere olarak varsayilan genisligi (px).
PANEL_WINDOW_DEFAULT_WIDTH = 420
#: Ana pencereyle arasinda birakilan bosluk. 0 = bitisik (yapisik).
PANEL_WINDOW_GAP = 0
#: Genislik sinirlari. ALT sinir okunabilirlik icindir. UST sinir gomulu
#: mimaride "container - 200" ile ORTULU olarak vardi; bagimsiz pencerede
#: o hesap ortadan kalkinca sinir da kalkmisti ve 10000 px'lik bir pencere
#: uretilebiliyordu. Sinir artik acikca burada.
#: Yapisma esigi (px). Panel birakildiginda sahibin SAG UST kosesine bu
#: kadar yakinsa yapisir. Yatay ve dikey AYRI AYRI denetlenir.
PANEL_SNAP_DISTANCE = 28
PANEL_MIN_WIDTH = 320
PANEL_MAX_WIDTH = 900


class WindowPlacement:
    """Panelin BAĞIMSIZ PENCERE yerleşimi (aşama 2).

    `DockPlacement`in yerini alır. Panel artık ana pencerenin İÇİNDE değil,
    YANINDA durur: sahipli bir top-level penceredir ve ana pencerenin sağ
    kenarına hizalanır. Video alanı playlist'ten ETKİLENMEZ.

    Neden `Qt.Window`, `Qt.Tool` DEĞİL: panel bir zamanlar `Tool`du ve
    kullanıcı "başka uygulama öne gelince playlist kayboluyor" diye
    raporlamıştı. Qt'de `Tool` pencereleri uygulama odağı kaybedince
    gizlenir; belirtinin sebebi ayrı pencere olmak değil, `Tool` olmaktı.
    Sahipli `Window` ana pencereyle birlikte simge durumuna iner, onun
    üstünde durur ama BAŞKA uygulamaların üstünde yüzmez.
    `WindowStaysOnTopHint` KULLANILMAZ.

    Aşama 3 (mıknatıs) bu sınıfın üstüne gelir: şu an panel her zaman
    yapışıktır, sürükleyip ayırma sonraki adımdır.
    """

    def __init__(self, panel, owner, video_frame):
        self.panel = panel
        self.owner = owner
        self.video_frame = video_frame
        self._width = PANEL_WINDOW_DEFAULT_WIDTH
        # Panel YAPISIK acilir; kullanici surukleyip ayirabilir.
        self.snapped = True

    @property
    def embedded(self):
        return False

    @property
    def target_width(self):
        return self._width

    def set_width(self, width):
        self._width = max(PANEL_MIN_WIDTH, min(PANEL_MAX_WIDTH, int(width)))

    def place_for(self, owner_rect, screen_rect, width):
        """Panelin dikdörtgenini hesaplar — SAF fonksiyon, yan etkisiz.

        Tercih SAĞDIR. Sağda yer yoksa SOLA geçer; iki yana da sığmıyorsa
        ekranın içine sıkıştırılır.

        ÖLÇÜLEN KUSUR (17 Ağustos 2026, kullanıcı bildirdi): koşulsuz
        `owner.right() + 1` kullanılıyordu. 2560x1392 ekranda ana pencere
        sağ kenardayken panelin **420 px'inin TAMAMI** ekran dışında
        kalıyordu; playlist hiç görünmüyordu.

        Genişliği daraltmak yerine tarafı değiştirmek seçildi: daraltma
        liste okunabilirliğini bozar, taraf değiştirmek bozmaz.

        Yükseklik ve dikey konum da ekrana sığdırılır; aksi hâlde uzun bir
        ana pencere paneli aşağıdan taşırır.
        """
        height = max(200, min(int(owner_rect.height()), screen_rect.height()))
        y = max(screen_rect.top(),
                min(int(owner_rect.top()), screen_rect.bottom() - height + 1))

        right_x = owner_rect.right() + 1 + PANEL_WINDOW_GAP
        left_x = owner_rect.left() - PANEL_WINDOW_GAP - width
        if right_x + width - 1 <= screen_rect.right():
            x = right_x
        elif left_x >= screen_rect.left():
            x = left_x
        else:
            # Iki yana da sigmiyor: ekranin ICINE sikistir.
            x = max(screen_rect.left(),
                    min(right_x, screen_rect.right() - width + 1))
        return QRect(int(x), int(y), int(width), int(height))

    def snap_candidate(self, owner_rect, screen_rect, width):
        """YAPIŞMA HEDEFİ: yalnız sahibin SAĞ ÜST köşesi.

        KULLANICI KARARI (17 Ağustos 2026): mıknatıs YALNIZ sağ tarafta
        çalışır. Sol, üst, alt ve orta yapışma YOKTUR. Otomatik yerleşimin
        (`place_for`) ekran dışına taşmamak için sola geçebilmesi AYRI bir
        konudur; kullanıcının sürükleyip yapıştırması buradan geçer.
        """
        height = max(200, min(int(owner_rect.height()), screen_rect.height()))
        y = max(screen_rect.top(),
                min(int(owner_rect.top()), screen_rect.bottom() - height + 1))
        return QRect(owner_rect.right() + 1 + PANEL_WINDOW_GAP, y,
                     width, height)

    def snap_for(self, owner_rect, screen_rect, width, dropped_rect):
        """Bırakılan panel yapışmalı mı? Yapışacaksa HEDEF, yoksa `None`.

        MIKNATIS SÜRÜKLEME SIRASINDA DEĞİL, BIRAKIŞTA çalışır. Sürüklerken
        yapıştırmak pencereyi farenin altından çekip alır ve eşik civarında
        yapış-kop-yapış titremesi üretir; bırakışta yapıştırmak hem
        öngörülebilir hem titremesiz.

        Yatay VE dikey yakınlık AYRI AYRI aranır. Tek bir toplam mesafe
        kullanmak, paneli sağ kenara ama dikeyde ortaya getirmeyi de
        "yakın" sayabilirdi; kullanıcı bunu açıkça istemedi: yapışma sağ
        ÜST köşeye yaklaşınca olur.
        """
        candidate = self.snap_candidate(owner_rect, screen_rect, width)
        if not screen_rect.contains(candidate):
            return None
        near_x = abs(candidate.left() - dropped_rect.left()) <= PANEL_SNAP_DISTANCE
        near_y = abs(candidate.top() - dropped_rect.top()) <= PANEL_SNAP_DISTANCE
        return candidate if (near_x and near_y) else None

    def release_snap(self):
        """Sürükleme başlarken mıknatısı bırakır.

        Bırakılmasaydı panel sürüklenirken ana pencereyi izlemeye devam
        eder ve kullanıcı onu koparamazdı.
        """
        self.snapped = False

    def settle_after_drag(self):
        """Bırakıştan sonra: yakınsa yapış, değilse AYRI kal."""
        owner = self.owner
        if owner is None or not owner.isVisible():
            return
        screen_rect = self._screen_rect()
        if screen_rect is None:
            return
        target = self.snap_for(owner.frameGeometry(), screen_rect,
                               self._width, self.panel.frameGeometry())
        if target is None:
            self.snapped = False
            return
        self.snapped = True
        self.panel.setGeometry(target)

    def _screen_rect(self):
        """Sahibin BULUNDUĞU ekranın kullanılabilir alanı (çok ekran)."""
        owner = self.owner
        screen = None
        try:
            handle = owner.screen() if owner is not None else None
            screen = handle or QApplication.primaryScreen()
        except Exception:
            screen = QApplication.primaryScreen()
        if screen is None:
            return None
        return screen.availableGeometry()

    def apply(self):
        """Paneli hesaplanan yere koyar (ekran dışına taşmadan).

        YALNIZ yapışıkken konumlandırır. Ayrı duran paneli ana pencerenin
        hareketi SÜRÜKLEMEZ; kullanıcı onu bilerek oraya koymuştur.
        """
        owner = self.owner
        if owner is None or not owner.isVisible() or not self.snapped:
            return
        screen_rect = self._screen_rect()
        if screen_rect is None:
            return
        target = self.place_for(owner.frameGeometry(), screen_rect,
                                self._width)
        self.panel.setGeometry(target)

    def reserve(self):
        """Pencere modelinde video alanindan yer AYRILMAZ."""
        return None

    def release(self):
        return None

    def reveal_surface(self):
        return None


class PlaylistPanel(QWidget):
    """Oynatma listesi — ana pencerenin YANINDA duran bağımsız pencere.

    AŞAMA 2 (17 Ağustos 2026, kullanıcı kararı). Panel artık ana pencerenin
    gömülü child'ı DEĞİL, onun SAHİPLİ top-level penceresidir. Video alanı
    playlist açılınca daralmaz.

    Sahiplik önemlidir ve `Qt.Tool` KULLANILMAZ: panel bir zamanlar `Tool`du
    ve "başka uygulama öne gelince playlist kayboluyor" hatası bundandı
    (Qt'de `Tool` pencereleri uygulama odağı kaybedince gizlenir). Sahipli
    `Qt.Window` ana pencereyle birlikte simge durumuna iner ve geri gelir,
    onun üstünde durur, ama başka uygulamaların üstünde YÜZMEZ.
    `WindowStaysOnTopHint` kullanılmaz.

    Videoyla kesişme artık "yapısal olarak imkânsız" değil, ÖLÇÜLEREK
    korunur: panel videonun yanındadır ve geometriler kesişmez
    (`tests/test_playlist_window_regressions.py`).
    """

    def __init__(self, player, video_frame):
        # Sahipli top-level pencere: parent ana penceredir, bayrak `Window`.
        # SAHİP GERÇEK BİR QWidget OLMAYABİLİR: içerik testleri (thumbnail,
        # satır durumu) paneli sahte bir `player` nesnesiyle kurar ve
        # konularının sahiplikle ilgisi yoktur. Eski kod da eksik host'u
        # savunmacı ele alıyordu; aynı politika korunur.
        owner = player if isinstance(player, QWidget) else None
        # FRAMELESS: ana pencere de framelesstir. Bayraksiz `Qt.Window`
        # Windows'ta 31 px'lik native baslik cubugu ciziyordu (olculdu) ve
        # panelin ZATEN kendi basligi + kapatma dugmesi oldugu icin
        # kullanici iki baslik goruyordu. Tasima kendi basligimizdan yapilir
        # (`begin_header_drag`).
        super().__init__(owner, Qt.WindowType.Window
                         | Qt.WindowType.FramelessWindowHint)
        self.player = player
        self.video_frame = video_frame
        self.host = None
        self.setWindowTitle(tr("Oynatma Listesi"))
        self._target_open = False
        self._split_press_global_x = None
        self._split_press_width = 0
        # Frameless pencerede basliktan tasima durumu.
        self._header_press_global = None
        self._header_press_origin = QPoint(0, 0)
        # Yerleşim TEK yerde (aşama 1 dikişi). Aşama 2'de gömülü yerleşimin
        # yerini bağımsız pencere yerleşimi aldı; panelin genel API'si aynı.
        self._placement = WindowPlacement(self, owner, video_frame)
        # Ana pencere taşınır/boyutlanırsa panel ONU İZLER. Bayat global
        # geometri eski mimaride paneli videonun ÜSTÜNE bindiriyordu; panel
        # artık videonun YANINDA olduğu için en kötü durum yanlış konumdur,
        # örtme değildir. Yine de izleme açık tutulur.
        self._owner = owner
        if owner is not None:
            owner.installEventFilter(self)

        self.setObjectName("playlistPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMouseTracking(True)
        self.setStyleSheet(
            # ANA PENCEREYLE AYNI yuzey rengi (tek kaynak: app.config).
            # Eski deger `rgba(19, 20, 22, 247)` idi: notr ve hafif saydam,
            # cunku panel VIDEO USTUNDE yuzen gomulu bir yuzeydi. Ayri
            # pencere olunca ana pencerenin yanina gelip farkli tonda
            # durmaya basladi. Saydamlik da kalkti; bu artik bir penceredir.
            f"QWidget#playlistPanel {{ background: {WINDOW_BACKGROUND}; "
            "border: 1px solid rgba(255,255,255,20); } "
            "QLabel { background: transparent; } "
            "QLineEdit#playlistSearch { color: #E9EDF1; "
            "background: rgba(255,255,255,12); border: 1px solid "
            "rgba(255,255,255,24); border-radius: 5px; padding: 7px 10px; "
            "font-size: 13px; } "
            "QLineEdit#playlistSearch:focus { border-color: rgba(242,106,61,150); } "
            "QListWidget#playlistView { color: #E9EDF1; background: transparent; "
            "border: none; outline: none; padding: 0; } "
            "QListWidget#playlistView::item { border-bottom: 1px solid "
            "rgba(255,255,255,14); background: transparent; } "
            "QListWidget#playlistView::item:selected { background: "
            "rgba(255,255,255,14); } "
            "QListWidget#playlistView::item:hover { background: "
            "rgba(255,255,255,9); } "
            "QPushButton { color: #DDE2E7; background: transparent; border: none; "
            "border-radius: 4px; padding: 7px 9px; font-size: 12px; } "
            "QPushButton:hover { background: rgba(255,255,255,20); color: white; } "
            f"QPushButton#playlistAdd {{ color: {PLAYLIST_ACCENT}; }} "
            # Ayri top-level pencere ANA PENCERENIN stilini almaz;
            # ipucu kurali urunun tek kaynagindan eklenir.
            + TOOLTIP_STYLE
        )
        self.resize_handle = PlaylistResizeHandle(self)
        self.resize_handle.raise_()

        root = QVBoxLayout(self)
        # Top-level tool window, child widget'ların doğal genişliğini pencereye
        # zorlamasın; 400x300 ana pencerede panel video yüzeyine sığabilsin.
        root.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        # Yan paylar baslik cubugununkiyle AYNI ritimde.
        root.setContentsMargins(TITLE_BAR_SIDE_MARGIN, 18,
                                TITLE_BAR_SIDE_MARGIN, 14)
        root.setSpacing(12)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)
        title_column = QVBoxLayout()
        title_column.setSpacing(2)
        heading = QLabel(tr("Oynatma Listesi"), self)
        heading.setObjectName("playlistHeading")
        heading.setStyleSheet("color: #F4F5F6; font-size: 19px;")
        # Sayaç TEK biçimden gelir; `0 öğe` ayrı bir çeviri girdisi olarak
        # tutulmaz, yoksa aynı metin iki kez çevrilir.
        self.count_label = QLabel(f"0 {tr('öğe')}", self)
        self.count_label.setObjectName("playlistCount")
        self.count_label.setStyleSheet("color: #929AA3; font-size: 12px;")
        title_column.addWidget(heading)
        title_column.addWidget(self.count_label)
        header.addLayout(title_column)
        header.addStretch(1)
        # Baslik cubugundakiyle AYNI dugme: ayni olcu, ayni ikon, ayni
        # hover rengi. Panel ayri bir pencere olsa da urunun kimligini
        # tasir; kendi olcusunu uydurmasi onu yabanci gosteriyordu.
        self.close_button = QPushButton(self)
        self.close_button.setObjectName("playlistClose")
        self.close_button.setText("")
        self.close_button.setAccessibleName(tr("Oynatma Listesini Kapat"))
        self.close_button.setToolTip(tr("Kapat (Esc)"))
        self.close_button.setFixedSize(TITLE_BUTTON_SIZE, TITLE_BUTTON_SIZE)
        self.close_button.setIconSize(QSize(TITLE_BUTTON_ICON_SIZE,
                                            TITLE_BUTTON_ICON_SIZE))
        self.close_button.setIcon(
            make_media_icon("close", TITLE_BUTTON_ICON_SIZE, "#FFFFFF"))
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.close_button.setStyleSheet(
            "QPushButton#playlistClose { background: transparent; border: none; "
            "padding: 0; border-radius: 4px; } "
            f"QPushButton#playlistClose:hover {{ background: {TITLE_BAR_ACCENT}; }}")
        self.close_button.clicked.connect(self.close_animated)
        header.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        self.search_field = QLineEdit(self)
        self.search_field.setObjectName("playlistSearch")
        self.search_field.setPlaceholderText(tr("Listede ara"))
        self.search_field.setClearButtonEnabled(True)
        self.search_field.textChanged.connect(self.apply_filter)
        root.addWidget(self.search_field)

        self.playlist_view = PlaylistListWidget(self)
        self.playlist_view.itemDoubleClicked.connect(self._play_item)
        root.addWidget(self.playlist_view, 1)

        self.empty_label = QLabel(tr("Oynatma listesi boş\nDosyaları buraya sürükleyin"), self)
        self.empty_label.setObjectName("playlistEmptyState")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet(
            "color: #9BA3AB; background: rgba(255,255,255,5); "
            "border: 1px dashed rgba(255,255,255,35); border-radius: 6px; "
            "font-size: 13px; padding: 24px;")
        root.addWidget(self.empty_label, 1)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 4, 0, 0)
        footer.setSpacing(4)
        self.add_button = QPushButton(tr("Dosya Ekle"), self)
        self.add_button.setObjectName("playlistAdd")
        self.remove_button = QPushButton(tr("Kaldır"), self)
        self.remove_button.setObjectName("playlistRemove")
        self.clear_button = QPushButton(tr("Listeyi Temizle"), self)
        self.clear_button.setObjectName("playlistClear")
        self.add_button.clicked.connect(self._add_files)
        self.remove_button.clicked.connect(self._remove_selected)
        self.clear_button.clicked.connect(self._clear)
        for button, minimum in (
                (self.add_button, 78),
                (self.remove_button, 58),
                (self.clear_button, 104)):
            button.setMinimumWidth(minimum)
            button.setSizePolicy(QSizePolicy.Policy.Preferred,
                                 QSizePolicy.Policy.Preferred)
        footer.addWidget(self.add_button)
        footer.addStretch(1)
        footer.addWidget(self.remove_button)
        footer.addWidget(self.clear_button)
        root.addLayout(footer)

        # Açılış/kapanış artık top-level geometri yerine host genişliğini
        # canlandırır; panel host'u doldurduğu için görsel etki aynıdır ama
        # layout gerçek yer ayırmaya devam eder.
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(PANEL_ANIMATION_MS)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self._apply_animated_opacity)
        self.animation.finished.connect(self._animation_finished)
        self.thumbnail_service = ThumbnailService(self)
        self.thumbnail_service.thumbnail_ready.connect(self._thumbnail_ready)
        # Basarisiz worker satiri SONSUZA KADAR `loading` birakmamali.
        self.thumbnail_service.thumbnail_failed.connect(
            lambda path: self._thumbnail_failed(path))
        self.hide()

    @property
    def is_open(self):
        return self._target_open

    @property
    def target_width(self):
        """Panelin açıkken alacağı genişlik."""
        return self._placement.target_width

    def apply_panel_geometry(self):
        """Paneli yerleşimin söylediği yere koyar (bkz. `WindowPlacement`)."""
        self._placement.apply()

    # --- Pencere durumunun kaliciligi ---------------------------------

    #: Kayit anahtarlari. Depo DISARIDAN enjekte edilir; panel `QSettings`
    #: nesnesi TUTMAZ (altyazi penceresiyle ayni politika).
    STATE_WIDTH = "playlist/width"
    STATE_SNAPPED = "playlist/snapped"
    STATE_POS = "playlist/pos"

    _state_read = None
    _state_write = None

    def bind_state_store(self, read, write):
        """Okuma/yazma islevlerini baglar (test ve urun ayni yoldan gecer)."""
        self._state_read = read
        self._state_write = write

    def save_window_state(self):
        if self._state_write is None:
            return
        self._state_write(self.STATE_WIDTH, int(self._placement.target_width))
        self._state_write(self.STATE_SNAPPED, bool(self._placement.snapped))
        self._state_write(self.STATE_POS, (int(self.x()), int(self.y())))

    def restore_window_state(self):
        """Kayitli genislik/yapisma/konumu uygular.

        YAPISIK kayitta konum KULLANILMAZ: ana pencere o zamandan beri
        tasinmis olabilir, kayitli konum bayattir. Ekran disina dusen
        konum da yok sayilir (kullanici monitor degistirmis olabilir);
        panel erisilemez bir yerde acilmamalidir.
        """
        if self._state_read is None:
            return
        width = self._state_read(self.STATE_WIDTH)
        if width:
            self._placement.set_width(int(width))
        snapped = self._state_read(self.STATE_SNAPPED)
        if snapped is not None:
            self._placement.snapped = bool(snapped)
        if self._placement.snapped:
            self.apply_panel_geometry()
            return
        position = self._state_read(self.STATE_POS)
        if not position:
            return
        x, y = int(position[0]), int(position[1])
        screen = self._placement._screen_rect()
        candidate = QRect(x, y, self._placement.target_width, self.height())
        if screen is not None and not screen.intersects(candidate):
            # Bayat/erisilemez konum: sahibin yanina don.
            self._placement.snapped = True
            self.apply_panel_geometry()
            return
        self.resize(self._placement.target_width, self.height())
        self.move(x, y)

    # --- Baslikatan tasima (frameless pencere) ------------------------

    def header_drag_zone(self):
        """Pencereyi taşıyan üst şerit (yerel koordinat).

        Arama kutusunun ÜSTÜNDE kalan alandır; ölçü sabit yazılmaz,
        gerçek arama kutusunun konumundan türer. Kapatma düğmesi bu
        şeridin içindedir ama kendi tıklamasını alır (aşağıya bakın).
        """
        bottom = self.search_field.geometry().top()
        return QRect(0, 0, self.width(), max(0, bottom))

    def _header_drag_target(self, local_point):
        """Nokta taşıma şeridinde mi? Kapatma düğmesi HARİÇ."""
        if not self.header_drag_zone().contains(local_point):
            return False
        return not self.close_button.geometry().contains(local_point)

    def begin_header_drag(self, global_point):
        """Taşımayı başlatır. Nokta GLOBAL'dir (gerçek fare olayı gibi)."""
        self._header_press_global = QPoint(global_point)
        self._header_press_origin = self.pos()
        # Mıknatıs bırakılmazsa panel sürüklenirken ana pencereyi izlemeye
        # devam eder ve kullanıcı onu koparamaz.
        self._placement.release_snap()

    def continue_header_drag(self, global_point):
        if self._header_press_global is None:
            return
        delta = QPoint(global_point) - self._header_press_global
        self.move(self._header_press_origin + delta)

    def end_header_drag(self):
        self._header_press_global = None
        # Bırakış anı: sahibin sağ üst köşesine yakınsa yapış, değilse AYRI kal.
        self._placement.settle_after_drag()
        self.save_window_state()

    def is_header_dragging(self):
        return self._header_press_global is not None

    def set_panel_width(self, width):
        """Panel genişliğinin TEK giriş noktası (tutamaç ve kenar sürüklemesi).

        Pencere modelinde genişlik ana pencereden yer ÇALMAZ; video alanı
        etkilenmez.
        """
        self._placement.set_width(width)
        self.apply_panel_geometry()
        self.save_window_state()

    def _apply_animated_opacity(self, value):
        """Görsel geçiş artık KAYDIRMA değil, pencere opaklığıdır.

        Top-level bir pencereyi her karede taşımak Windows'ta titriyor ve
        ana pencereyle senkron kalmıyor. Opaklık ucuzdur ve panelin konumu
        geçiş boyunca sabit kalır.
        """
        self.setWindowOpacity(max(0.0, min(1.0, float(value))))

    def open_animated(self):
        self.refresh()
        self._target_open = True
        self.animation.stop()
        # Kayitli genislik/yapisma/konum ONCE uygulanir; geometri ondan
        # sonra hesaplanir, aksi halde panel once varsayilan yere konup
        # gorunur bir sicrama yapardi.
        self.restore_window_state()
        # Video yüzeyi DOKUNULMADAN kalır: pencere modelinde yer ayrılmaz.
        self.apply_panel_geometry()
        self._apply_animated_opacity(0.0)
        self.show()
        self.raise_()
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.start()

    def close_animated(self):
        if not self._target_open:
            return
        self._target_open = False
        self.animation.stop()
        # Tersine çevirmede mevcut görsel durumdan devam edilir; sıçrama yok.
        self.animation.setStartValue(float(self.windowOpacity()))
        self.animation.setEndValue(0.0)
        self.animation.start()

    def finish_animation(self):
        """Test/smoke için animasyonu deterministik son durumuna taşır."""
        self.animation.stop()
        if self._target_open:
            self.apply_panel_geometry()
            self._apply_animated_opacity(1.0)
            self.show()
        else:
            self._finish_closed()

    def _finish_closed(self):
        """Kapanış sonu: pencere gizlenir, opaklık bir sonraki açılış için sıfırlanır."""
        self.hide()
        self._apply_animated_opacity(1.0)
        self._placement.release()
        # Kapanista son durum kaydedilir; bir sonraki acilis onu kullanir.
        self.save_window_state()
        self.video_frame.schedule_overlay_hide()

    def _animation_finished(self):
        if not self._target_open:
            self._finish_closed()

    def refresh(self):
        selected = self.playlist_view.currentRow()
        self.playlist_view.clear()
        playlist = list(getattr(self.player, "playlist", []))
        current = getattr(self.player, "current_playlist_index", -1)
        for index, path in enumerate(playlist):
            item = QListWidgetItem()
            item.setData(PATH_ROLE, path)
            item.setData(PLAYING_ROLE, index == current)
            item.setToolTip(tr("Sürükleyerek sırala • Oynatmak için çift tıkla"))
            item.setSizeHint(QSize(0, ROW_HEIGHT))
            self.playlist_view.addItem(item)
            row_widget = PlaylistRow(path, index == current, self.playlist_view)
            self.playlist_view.setItemWidget(item, row_widget)
            # Durum SERVISTEN sorulur: `request()` donusundeki `None`
            # "kuyrukta", "basarisiz" ve "uygun degil" arasinda ayrim
            # yapmadigi icin basarisiz satir yenilemede tekrar `loading`
            # gorunuyordu.
            cached = self.thumbnail_service.request(path)
            if cached:
                row_widget.set_thumbnail(cached)
            else:
                state = self.thumbnail_service.status(path)
                if state != "empty":
                    row_widget.thumbnail_label.setProperty("thumbnailState",
                                                           state)
        if playlist and selected >= 0:
            self.playlist_view.setCurrentRow(min(selected, len(playlist) - 1))
        self.count_label.setText(f"{len(playlist)} {tr('öğe')}")
        self.empty_label.setVisible(not playlist)
        self.playlist_view.setVisible(bool(playlist))
        self.remove_button.setEnabled(bool(playlist))
        self.clear_button.setEnabled(bool(playlist))
        self.apply_filter(self.search_field.text())

    def _thumbnail_ready(self, media_path, image_path):
        wanted = os.path.normcase(os.path.abspath(media_path))
        for row in range(self.playlist_view.count()):
            item = self.playlist_view.item(row)
            path = str(item.data(PATH_ROLE) or "")
            if os.path.normcase(os.path.abspath(path)) == wanted:
                widget = self.row_widget(row)
                if widget is not None:
                    widget.set_thumbnail(image_path)

    def _thumbnail_failed(self, media_path):
        """Kare uretilemedi: satir guvenli placeholder durumuna doner.

        Kullaniciya kirik resim veya sonsuz spinner gosterilmez; ham hata,
        traceback ve tam dosya yolu arayuze YAZILMAZ.
        """
        wanted = os.path.normcase(os.path.abspath(media_path))
        for row in range(self.playlist_view.count()):
            item = self.playlist_view.item(row)
            path = str(item.data(PATH_ROLE) or "")
            if os.path.normcase(os.path.abspath(path)) != wanted:
                continue
            widget = self.row_widget(row)
            if widget is None:
                continue
            label = widget.thumbnail_label
            label.clear()
            label.setProperty("thumbnailState", "failed")
            label.style().unpolish(label)
            label.style().polish(label)
            label.update()

    def row_widget(self, row):
        item = self.playlist_view.item(row)
        return self.playlist_view.itemWidget(item) if item is not None else None

    def apply_filter(self, text):
        needle = (text or "").strip().casefold()
        for row in range(self.playlist_view.count()):
            item = self.playlist_view.item(row)
            path = str(item.data(PATH_ROLE) or "")
            item.setHidden(bool(needle and needle not in os.path.basename(path).casefold()))

    def _play_item(self, item):
        row = self.playlist_view.row(item)
        if row >= 0:
            self.player.play_from_playlist(row)
            self.refresh()

    def _add_files(self):
        # Panel artık ana pencerenin child'ı; native dosya seçici kendiliğinden
        # önde açılır, bu yüzden gizle/geri yükle makyajına gerek yoktur.
        self.player.add_to_playlist()
        self.refresh()

    def _remove_selected(self):
        row = self.playlist_view.currentRow()
        if row >= 0:
            self.player.remove_from_playlist(row)
            self.refresh()

    def _clear(self):
        self.player.clear_playlist()
        self.refresh()

    def add_external_files(self, paths):
        allowed = {pattern.lstrip("*").lower()
                   for pattern in MEDIA_EXTENSIONS.split()}
        media = [os.path.normpath(path) for path in paths
                 if os.path.isfile(path)
                 and os.path.splitext(path)[1].lower() in allowed]
        if not media:
            return
        was_empty = not self.player.playlist
        self.player.playlist.extend(media)
        if was_empty and not getattr(self.player, "current_file", ""):
            self.player.play_from_playlist(0)
        self.refresh()

    def move_playlist_item(self, source, destination):
        count = self.playlist_view.count()
        if not (0 <= source < count and 0 <= destination < count):
            return
        if source == destination:
            return
        item = self.playlist_view.item(source)
        row_widget = self.playlist_view.itemWidget(item)
        item = self.playlist_view.takeItem(source)
        self.playlist_view.insertItem(destination, item)
        self.playlist_view.setItemWidget(item, row_widget)
        self.playlist_view.setCurrentRow(destination)
        self.sync_player_order_from_view()

    def sync_player_order_from_view(self):
        paths = []
        current = -1
        for row in range(self.playlist_view.count()):
            item = self.playlist_view.item(row)
            paths.append(item.data(PATH_ROLE))
            if bool(item.data(PLAYING_ROLE)):
                current = row
        self.player.playlist = paths
        self.player.current_playlist_index = current
        self.refresh()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close_animated()
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if (event.button() == Qt.MouseButton.LeftButton
                and event.position().x() <= PANEL_RESIZE_HANDLE_WIDTH):
            self._split_press_global_x = int(event.globalPosition().x())
            self._split_press_width = self.width()
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            event.accept()
            return
        if (event.button() == Qt.MouseButton.LeftButton
                and self._header_drag_target(event.position().toPoint())):
            self.begin_header_drag(event.globalPosition().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (self._split_press_global_x is not None
                and event.buttons() & Qt.MouseButton.LeftButton):
            delta = self._split_press_global_x - int(event.globalPosition().x())
            self.set_panel_width(self._split_press_width + delta)
            event.accept()
            return
        if (self.is_header_dragging()
                and event.buttons() & Qt.MouseButton.LeftButton):
            self.continue_header_drag(event.globalPosition().toPoint())
            event.accept()
            return
        if event.position().x() <= PANEL_RESIZE_HANDLE_WIDTH:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if (event.button() == Qt.MouseButton.LeftButton
                and self._split_press_global_x is not None):
            self._split_press_global_x = None
            event.accept()
            return
        if (event.button() == Qt.MouseButton.LeftButton
                and self.is_header_dragging()):
            self.end_header_drag()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        if self._split_press_global_x is None:
            self.unsetCursor()
        super().leaveEvent(event)

    #: Ana pencerenin panelin KONUMUNU etkileyen olayları.
    _OWNER_FOLLOW_EVENTS = (QEvent.Type.Resize, QEvent.Type.Move,
                            QEvent.Type.WindowStateChange)

    def eventFilter(self, watched, event):
        # Ana pencere taşınır/boyutlanırsa panel onu İZLER. Panel yalnız
        # AÇIKKEN taşınır; kapalıyken konum hesaplamak gereksiz iştir.
        if (watched is self._owner and self._owner is not None
                and self._target_open
                and event.type() in self._OWNER_FOLLOW_EVENTS):
            self.apply_panel_geometry()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        self.resize_handle.setGeometry(
            0, 0, PANEL_RESIZE_HANDLE_WIDTH, self.height())
        self.resize_handle.raise_()
        super().resizeEvent(event)

    def closeEvent(self, event):
        self.thumbnail_service.close()
        super().closeEvent(event)
