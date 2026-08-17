# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Ürünün varsayılan modern başlık çubuğu.

Sinematik arayüzün parçasıdır ve normal açılışta kullanılır. Klasik QMenuBar
gizlenir ama aksiyonları yaşamaya devam eder; üç nokta menüsü mevcut QMenu
nesnelerini yeniden kullanır, kopya davranış üretmez.
"""
from PyQt6.QtCore import QEvent, QObject, QPoint, QRect, QSize, Qt
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QMenu,
                             QPushButton, QSizePolicy, QWidget)

from app.app_icon import application_icon
from app.ui_icons import make_media_icon
from app.i18n import tr

TITLE_BAR_HEIGHT = 48
# Baslik cubugu yuksekligini BUYUTMEYEN logo olcusu.
# Kullanici istegi (17 Agustos 2026): 20 px kucuk kaliyordu, buyutuldu.
# Tavan iki olcuden turer ve ikisi de testle korunur: logo dugme
# yuksekligini (34) ASMAZ ve cubukta (48) ustte/altta en az 6'sar px
# nefes payi kalir -> en fazla 36. 28 ikisini de saglar.
TITLE_LOGO_SIZE = 28
#: Baslik cubugu dugme olculeri ve yan pay -- URUNUN TEK kaynagi.
#: Playlist penceresi de bunlari kullanir; ayri pencere olmasi kendi
#: olcusunu uydurmasi anlamina GELMEZ (kullanici bildirdi, 17 Agustos
#: 2026: kapatma dugmesi yanlis konumlanmisti).
TITLE_BUTTON_SIZE = 34
TITLE_BUTTON_ICON_SIZE = 20
TITLE_BAR_SIDE_MARGIN = 16
RESIZE_MARGIN = 12
TITLE_BAR_BACKGROUND = "#11151A"
# Urunun vurgu rengi. Overlay (`video_frame.OVERLAY_ACCENT`) ve altyazi
# pencereleriyle AYNI deger; baslik cubugu ayri bir kimlik kurmaz.
# KULLANICI KARARI (17 Agustos 2026): kapatma dugmesi Windows
# kirmizisina (#E81123) DONMEZ, bu renge doner.
TITLE_BAR_ACCENT = "#F26A3D"

# Kenar/köşe bölgelerinde imleç şekilleri
_EDGE_CURSORS = {
    Qt.Edge.LeftEdge: Qt.CursorShape.SizeHorCursor,
    Qt.Edge.RightEdge: Qt.CursorShape.SizeHorCursor,
    Qt.Edge.TopEdge: Qt.CursorShape.SizeVerCursor,
    Qt.Edge.BottomEdge: Qt.CursorShape.SizeVerCursor,
    Qt.Edge.LeftEdge | Qt.Edge.TopEdge: Qt.CursorShape.SizeFDiagCursor,
    Qt.Edge.RightEdge | Qt.Edge.BottomEdge: Qt.CursorShape.SizeFDiagCursor,
    Qt.Edge.RightEdge | Qt.Edge.TopEdge: Qt.CursorShape.SizeBDiagCursor,
    Qt.Edge.LeftEdge | Qt.Edge.BottomEdge: Qt.CursorShape.SizeBDiagCursor,
}


def resize_edges_at(rect, position, margin=RESIZE_MARGIN):
    """Verilen noktanın hangi resize kenar(lar)ına düştüğünü döndürür."""
    edges = Qt.Edge(0)
    if position.x() <= rect.left() + margin:
        edges |= Qt.Edge.LeftEdge
    elif position.x() >= rect.right() - margin:
        edges |= Qt.Edge.RightEdge
    if position.y() <= rect.top() + margin:
        edges |= Qt.Edge.TopEdge
    elif position.y() >= rect.bottom() - margin:
        edges |= Qt.Edge.BottomEdge
    return edges


def cursor_for_edges(edges):
    return _EDGE_CURSORS.get(edges, Qt.CursorShape.ArrowCursor)


class TitleBar(QWidget):
    """48 px modern başlık çubuğu: sol komutlar, sağ pencere düğmeleri."""

    def __init__(self, player):
        super().__init__(player)
        self.player = player
        self._overflow_menu = None
        self.setObjectName("modernTitleBar")
        self.setFixedHeight(TITLE_BAR_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            f"QWidget#modernTitleBar {{ background-color: {TITLE_BAR_BACKGROUND}; "
            "border-bottom: 1px solid rgba(255, 255, 255, 18); } "
            "QPushButton { background: transparent; border: none; padding: 0; "
            "border-radius: 4px; } "
            # OLCULEN SORUN: 26/255 (~%10) koyu cubukta fark
            # edilmiyordu; kullanici dugmeye geldigini anlamiyordu.
            "QPushButton:hover { background: rgba(255, 255, 255, 48); } "
            f"QPushButton#titleClose:hover {{ background: {TITLE_BAR_ACCENT}; }} "
            # Menü AÇIKKEN aktif görünüm meşrudur.
            "QPushButton#titleMore[menuOpen=\"true\"] { "
            "background: rgba(255, 255, 255, 48); } "
            # Menü kapandıktan sonra imleç hâlâ düğmedeyse hover GEÇİCİ
            # olarak bastırılır; aksi halde düğme seçiliymiş gibi gri
            # kalıyordu. Bastırma yalnız gerçek `Leave` olayına kadar sürer.
            "QPushButton#titleMore[menuDismissed=\"true\"], "
            "QPushButton#titleMore[menuDismissed=\"true\"]:hover { "
            "background: transparent; }"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(TITLE_BAR_SIDE_MARGIN, 0,
                                  TITLE_BAR_SIDE_MARGIN, 0)
        layout.setSpacing(6)

        # Frameless pencerede Windows'un dogal ikon alani yok; ortak logo
        # baslik yazisinin SOLUNDA gosterilir. Fare olaylarini gecirir,
        # boylece baslik surukleme ve dugmeler etkilenmez.
        self.logo_label = QLabel(self)
        self.logo_label.setObjectName("titleLogo")
        self.logo_label.setAccessibleName(tr("MLC Player simgesi"))
        self.logo_label.setFixedSize(TITLE_LOGO_SIZE, TITLE_LOGO_SIZE)
        self.logo_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.logo_label.setScaledContents(True)
        logo_icon = application_icon()
        if not logo_icon.isNull():
            self.logo_label.setPixmap(
                logo_icon.pixmap(TITLE_LOGO_SIZE, TITLE_LOGO_SIZE))
        layout.addWidget(self.logo_label, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addSpacing(8)

        self.title_label = QLabel("MLC Player", self)
        self.title_label.setObjectName("titleText")
        self.title_label.setStyleSheet(
            "color: #E6EAF0; background: transparent; font-size: 16px;")
        # Dar pencerede başlık metni daralabilir; düğmeler kırpılmaz.
        # Ignored yerine Preferred: geniş pencerede metin görünür kalır.
        self.title_label.setMinimumWidth(0)
        self.title_label.setSizePolicy(QSizePolicy.Policy.Preferred,
                                       QSizePolicy.Policy.Preferred)
        layout.addWidget(self.title_label, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addSpacing(8)

        self.open_button = self._make_button(
            "titleOpenFile", "open_folder", tr("Dosya Aç"))
        self.open_button.clicked.connect(lambda: self.player.open_file())
        layout.addWidget(self.open_button, 0, Qt.AlignmentFlag.AlignVCenter)

        self.playlist_button = self._make_button(
            "titlePlaylist", "playlist", "Playlist")
        self.playlist_button.clicked.connect(lambda: self.player.show_playlist())
        layout.addWidget(self.playlist_button, 0, Qt.AlignmentFlag.AlignVCenter)

        self.more_button = self._make_button("titleMore", "more",
                                             tr("Menü"))
        self.more_button.clicked.connect(self.show_overflow_menu)
        # Durumlar BAŞTAN tanımlı olmalı; aksi halde ilk repolish'e kadar
        # seçici hiç eşleşmez.
        self._set_more_state(menu_open=False, dismissed=False)
        # Yalnız bu düğmenin Enter/Leave olayları ele alınır; başka hiçbir
        # olay yutulmaz (bkz. `eventFilter`).
        self.more_button.installEventFilter(self)
        layout.addWidget(self.more_button, 0, Qt.AlignmentFlag.AlignVCenter)

        layout.addStretch(1)

        self.minimize_button = self._make_button(
            "titleMinimize", "minimize", tr("Küçült"))
        self.minimize_button.clicked.connect(lambda: self.player.showMinimized())
        layout.addWidget(self.minimize_button, 0, Qt.AlignmentFlag.AlignVCenter)

        self.maximize_button = self._make_button(
            "titleMaximize", "maximize", tr("Büyüt"))
        self.maximize_button.clicked.connect(self.toggle_maximized)
        layout.addWidget(self.maximize_button, 0, Qt.AlignmentFlag.AlignVCenter)

        self.close_button = self._make_button("titleClose", "close",
                                              tr("Kapat"))
        self.close_button.clicked.connect(lambda: self.player.close())
        layout.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignVCenter)

    # --- Kurulum yardımcıları ---

    def _make_button(self, object_name, icon_kind, label,
                     size=TITLE_BUTTON_SIZE,
                     icon_size=TITLE_BUTTON_ICON_SIZE):
        button = QPushButton(self)
        button.setObjectName(object_name)
        button.setText("")
        button.setToolTip(label)
        button.setAccessibleName(label)
        button.setFixedSize(size, size)
        button.setIconSize(QSize(icon_size, icon_size))
        button.setIcon(make_media_icon(icon_kind, icon_size))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return button

    # --- Menü ---

    def build_overflow_menu(self):
        """Kalıcı tek kök menüyü tazeler.

        Her açılışta yeni QMenu üretilmez; mevcut kök menü temizlenip klasik
        QMenuBar'daki QMenu/QAction nesneleri yeniden eklenir. Böylece dinamik
        checked/enabled durumları canlı kalır ve TitleBar altında menü
        birikmesi olmaz.
        """
        if self._overflow_menu is None:
            self._overflow_menu = QMenu(self)
            self._overflow_menu.setStyleSheet(
                "QMenu { background-color: #1C2526; color: white; }")
        menu = self._overflow_menu
        menu.clear()
        for action in self.player.menuBar().actions():
            submenu = action.menu()
            if submenu is not None:
                menu.addMenu(submenu)
            else:
                menu.addAction(action)
        return menu

    def _set_more_state(self, menu_open=None, dismissed=None):
        """Üç nokta düğmesinin AÇIK görünüm durumlarını yazar.

        `menuOpen` menünün açık olduğunu, `menuDismissed` ise menü
        kapandıktan sonra imlecin hâlâ düğmede olduğunu anlatır. İkisi
        ayrı tutulur: sorun basılı durum değil, menü-aktif ile düz hover'ın
        ayrışmamasıydı; bu yüzden `setDown(False)` tek başına yetmez.
        """
        button = self.more_button
        changed = False
        for name, value in (("menuOpen", menu_open),
                            ("menuDismissed", dismissed)):
            if value is None:
                continue
            text = "true" if value else "false"
            if button.property(name) != text:
                button.setProperty(name, text)
                changed = True
        if changed:
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

    def _cursor_over_more_button(self):
        """GERÇEK imleç düğmenin üzerinde mi?

        `underMouse()` tek başına güvenilir değildir: menü kapanışında Qt
        henüz taze bir hover olayı işlememiş olabilir. Ölçüm gerçek imleç
        konumundan yapılır.
        """
        button = self.more_button
        try:
            local = button.mapFromGlobal(QCursor.pos())
        except RuntimeError:
            return False
        return button.rect().contains(local)

    def show_overflow_menu(self):
        menu = self.build_overflow_menu()
        origin = self.more_button.mapToGlobal(
            QPoint(0, self.more_button.height()))
        # Yeni açılış ESKİ bastırmayı temizler.
        self._set_more_state(menu_open=True, dismissed=False)
        try:
            menu.exec(origin)
        finally:
            # Menü hangi yolla kapanırsa kapansın (seçim, dışarı tıklama,
            # Escape, istisna) aktif görünüm KESİNLİKLE temizlenir.
            self.more_button.setDown(False)
            self._set_more_state(menu_open=False,
                                 dismissed=self._cursor_over_more_button())

    def eventFilter(self, watched, event):
        """Yalnız üç nokta düğmesinin Enter/Leave olayları.

        Hiçbir olay yutulmaz; her durumda `False` döner.
        """
        if watched is self.more_button:
            if event.type() == QEvent.Type.Leave:
                # GERÇEK ayrılma: bastırma biter, sonraki Enter'da normal
                # hover yeniden çalışır.
                self._set_more_state(dismissed=False)
        return False

    # --- Pencere durumu ---

    def toggle_maximized(self):
        if self.player.isMaximized():
            self.player.showNormal()
        else:
            self.player.showMaximized()
        self.update_maximize_state()

    def update_maximize_state(self):
        maximized = self.player.isMaximized()
        label = tr("Geri Yükle") if maximized else tr("Büyüt")
        if self.maximize_button.accessibleName() == label:
            return
        self.maximize_button.setAccessibleName(label)
        self.maximize_button.setToolTip(label)
        self.maximize_button.setIcon(make_media_icon(
            "restore" if maximized else "maximize",
            self.maximize_button.iconSize().width()))

    def can_resize_window(self):
        return not (self.player.isMaximized() or self.player.isFullScreen()
                    or self.player.isMinimized())

    # --- Taşıma ---

    def _child_at(self, position):
        child = self.childAt(position)
        return child if isinstance(child, QPushButton) else None

    def _start_system_move(self):
        handle = self.player.windowHandle()
        if handle is not None and hasattr(handle, "startSystemMove"):
            return bool(handle.startSystemMove())
        return False

    def mousePressEvent(self, event):
        if (event.button() == Qt.MouseButton.LeftButton
                and self._child_at(event.position().toPoint()) is None):
            if self._start_system_move():
                event.accept()
                return
            # Güvenli fallback: yalnızca startSystemMove yoksa kullanılır.
            self._manual_move_origin = (
                event.globalPosition().toPoint() - self.player.pos())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        origin = getattr(self, "_manual_move_origin", None)
        if origin is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.player.move(event.globalPosition().toPoint() - origin)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._manual_move_origin = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if (event.button() == Qt.MouseButton.LeftButton
                and self._child_at(event.position().toPoint()) is None):
            self.toggle_maximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class FramelessResizeFilter(QObject):
    """Frameless pencerede sekiz yönlü resize: native yol + sınırlı yedek.

    Kenar bandı olayları ana pencereye değil child widget'lara ulaşabilir.
    Bu nedenle filtre hem ana pencereye hem de kenar olaylarını alan
    widget'lara kurulur ve koordinatlar global tur üzerinden ana pencere
    koordinatına çevrilir.

    İKİ YOL VARDIR:

    1. Olay ana pencerenin KENDİ top-level penceresinden geliyorsa
       `QWindow.startSystemResize()` kullanılır; Windows'un kendi
       resize/snap davranışı ve imleç yakalaması korunur.
    2. `control_overlay` AYRI bir top-level `Qt.Tool` penceresidir ve
       videonun alt bandını kaplar. Native resize döngüsü başka bir
       pencerenin girdi akışından devralamadığı için alt köşeler ve yan
       kenarların alt bölümü hiç çalışmıyordu. Bu durumda SINIRLI bir
       manuel sürükleme devreye girer: başlangıç imleci + `geometry()`
       kaydedilir, yalnız kenarın gerektirdiği taraf değişir ve pencerenin
       minimum boyutu korunur.

    Manuel yol FAIL-CLOSED'dur: fare yakalanamazsa sürükleme hiç
    başlamaz; sol tuş bırakılmış bir hareket, okuma hatası, odak kaybı,
    gizlenme veya pencerenin resize edilemez hâle gelmesi sürüklemeyi
    KESİN olarak bitirir ve yakalamayı bırakır. Sürekli geometri döngüsü,
    timer, polling veya global event filter kurulmaz.
    """

    def __init__(self, player, title_bar):
        super().__init__(player)
        self.player = player
        self.title_bar = title_bar
        self.targets = []
        # Sınırlı manuel yedek sürükleme durumu.
        self._manual = None
        # Geçici resize imlecinin uygulandığı GERÇEK hedef ve o hedefin
        # ÖZGÜN imleci: (widget, had_explicit_cursor, cursor, shape).
        self._cursor_state = None
        # GÖRÜNÜR imleç: yalnız bu filtreye ait `QApplication` override.
        self._owns_override = False
        self._override_shape = None

    def install(self):
        """Ana pencere ve gerçek kenar olaylarını alan widget'lara kurulur."""
        video_frame = getattr(self.player, "video_frame", None)
        overlay = getattr(video_frame, "control_overlay", None)
        candidates = [
            self.player,
            getattr(self.player, "central_widget", None),
            getattr(self.player, "title_bar", None),
            getattr(self.player, "media_container", None),
            video_frame,
            overlay,
            # PLAYLIST YOK: ayri bir penceredir ve ANA pencerenin
            # resize'ini surmemelidir. Gomuluyken mesruydu (kenar
            # olaylari ona dusebiliyordu); ayri pencerede
            # koordinatlar ana pencereye eslenince anlamsiz kenar
            # uretiyor ve imlec her yerde resize'a donuyordu.
        ]
        # Overlay AYRI top-level penceredir; yerleşimi değişirse kenar
        # bandına bir child düşebilir. YALNIZ bu ağaç gezilir; global
        # QApplication filtresi kurulmaz. Kurulum idempotenttir.
        if overlay is not None:
            candidates.extend(overlay.findChildren(QWidget))
        for target in candidates:
            if target is not None and target not in self.targets:
                target.installEventFilter(self)
                target.setMouseTracking(True)
                self.targets.append(target)
        return self.targets

    def remove(self):
        """Yalnızca kurulan hedeflerden filtreyi kaldırır."""
        self._end_manual_resize()
        self._restore_resize_cursor()
        for target in self.targets:
            try:
                target.removeEventFilter(self)
            except RuntimeError:
                pass
        self.targets = []

    def _window_position(self, watched, event):
        point = event.position().toPoint()
        if watched is self.player:
            return point
        # NOT: `mapTo()` yalnız aynı pencere hiyerarşisindeki child'lar için
        # doğrudur. control_overlay ayrı bir üst seviye Tool penceresidir ve
        # orada mapTo ana pencere değil global ekran koordinatı üretir.
        # Global tur her iki durumda da doğru sonucu verir.
        global_point = event.globalPosition().toPoint()
        return self.player.mapFromGlobal(global_point)

    def eventFilter(self, watched, event):
        # NOT: Yalnızca gereken olay tipleri ele alınır ve super() çağrılmaz.
        # Aksi halde MPV kurulumu sırasındaki yoğun pencere olaylarında
        # yeniden girişli çağrı zinciri yığını taşırıyordu.
        if watched not in self.targets:
            return False
        event_type = event.type()
        if event_type in (QEvent.Type.WindowDeactivate, QEvent.Type.Hide,
                          QEvent.Type.Leave):
            # Odak kaybı / gizlenme / yüzeyden çıkış: bekleyen sürükleme ve
            # geçici imleç güvenle bırakılır.
            self._end_manual_resize()
            self._restore_resize_cursor()
            return False
        if event_type in (QEvent.Type.WindowStateChange,
                          QEvent.Type.WindowActivate, QEvent.Type.Show):
            self.title_bar.update_maximize_state()
            ensure = getattr(self.player, "ensure_title_bar_on_top", None)
            if callable(ensure):
                ensure()
            return False
        if event_type == QEvent.Type.MouseButtonRelease:
            # Sürükleme HER hâlükârda burada biter; yakalama takılı kalmaz.
            return self._end_manual_resize()
        if event_type in (QEvent.Type.Enter, QEvent.Type.HoverMove):
            # ÖLÇÜLEN KUSUR: resize oku yalnız basıştan SONRA görünüyordu.
            # Kullanıcı köşeye gelir gelmez resize alanında olduğunu
            # anlamalı. Sürükleme sürerken karar sabit kalır.
            if self._manual is None:
                self._update_resize_cursor(watched, event)
            return False
        if event_type not in (QEvent.Type.MouseMove,
                              QEvent.Type.MouseButtonPress):
            return False
        if self._manual is not None and event_type == QEvent.Type.MouseMove:
            # Release olayı kaybolmuş olabilir: sol tuş basılı DEĞİLSE
            # sürükleme burada biter ve olay yutulmaz. Aksi halde sonraki
            # normal fare hareketleri pencereyi boyutlandırıyordu.
            if not self._left_button_held(event):
                self._end_manual_resize()
                return False
            if not self.title_bar.can_resize_window():
                self._end_manual_resize()
                self._restore_resize_cursor()
                return False
            # Sürükleme boyunca imleç sabit kalır; child hover'ı ezemez.
            self._apply_resize_cursor(self._manual["grabber"],
                                      self._manual["edges"])
            self._apply_manual_resize(event)
            return True
        if not self.title_bar.can_resize_window():
            self._restore_resize_cursor()
            return False
        if event_type == QEvent.Type.MouseMove:
            self._update_resize_cursor(watched, event)
            return False
        edges = resize_edges_at(self.player.rect(),
                               self._window_position(watched, event))
        if event.button() != Qt.MouseButton.LeftButton or not edges:
            return False
        # Basış anında da görünür imleç uygulanır; yalnız önceki MouseMove
        # olayına güvenilmez (ilk temas doğrudan basış olabilir).
        self._apply_resize_cursor(watched, edges)
        # ÖNCE Windows'un kendi resize/snap döngüsü denenir. Bu döngü
        # yalnız ana pencerenin KENDİ girdi akışından başlatılabilir.
        if (self._can_use_system_resize(watched)
                and self._start_system_resize(edges)):
            return True
        # ÖLÇÜLEN KUSUR: `control_overlay` ayrı bir top-level `Qt.Tool`
        # penceresidir (`overlay.window() is not player`) ve videonun alt
        # bandını kaplar. Basış oraya teslim edilince ana pencerenin native
        # resize döngüsü devralamıyor; alt köşeler ve yan kenarların alt
        # bölümü HİÇ çalışmıyordu. Sınırlı manuel yedek devreye girer.
        return self._begin_manual_resize(watched, edges, event)

    # --- Geçici resize imleci (gerçek hedef üzerinde) ---

    def _event_global_point(self, event):
        """Olayın global konumu; yoksa GERÇEK imleç konumu.

        `QEnterEvent`in local/global alanları platforma göre eksik
        olabildiği için güvenli yedek `QCursor.pos()`tur.
        """
        try:
            return event.globalPosition().toPoint()
        except (AttributeError, RuntimeError):
            pass
        try:
            return QCursor.pos()
        except (AttributeError, RuntimeError):
            return None

    def _update_resize_cursor(self, watched, event=None):
        """MouseMove, HoverMove ve Enter için TEK karar noktası.

        Üç olay da aynı kenar hesabından geçer; ayrı kopya mantık yoktur.
        """
        if not self.title_bar.can_resize_window():
            self._restore_resize_cursor()
            return
        point = self._event_global_point(event)
        if point is None:
            return
        try:
            local = self.player.mapFromGlobal(point)
        except (AttributeError, RuntimeError):
            return
        self._apply_resize_cursor(watched,
                                  resize_edges_at(self.player.rect(), local))

    def _apply_resize_cursor(self, watched, edges):
        """Resize imlecini olayın geldiği GERÇEK widget'a uygular.

        Hedef değişirse önceki hedefin ÖZGÜN imleci hemen geri yüklenir;
        aynı hedefe aynı şekil ikinci kez YAZILMAZ.
        """
        if not edges:
            self._restore_resize_cursor()
            return
        if watched is None:
            return
        shape = cursor_for_edges(edges)
        state = self._cursor_state
        if state is not None and state[0] is watched and state[3] == shape:
            # Widget'a tekrar yazılmaz; görünür override zaten bu şekilde
            # olduğu için `_apply_override_cursor` da hiçbir şey yapmaz.
            self._apply_override_cursor(shape)
            return
        if state is not None and state[0] is not watched:
            self._restore_resize_cursor()
        elif state is not None:
            # Aynı hedef, farklı şekil: özgün imleç kaydı KORUNUR.
            try:
                watched.setCursor(shape)
            except (AttributeError, RuntimeError):
                self._cursor_state = None
                return
            self._cursor_state = (state[0], state[1], state[2], shape)
            self._apply_override_cursor(shape)
            return
        try:
            # Widget'ın AÇIKÇA kendi imleci var mı? Yoksa temizlerken
            # körlemesine ArrowCursor vermek yerine miras geri getirilir.
            had_cursor = bool(watched.testAttribute(
                Qt.WidgetAttribute.WA_SetCursor))
            original = watched.cursor() if had_cursor else None
            watched.setCursor(shape)
        except (AttributeError, RuntimeError):
            self._cursor_state = None
            self._apply_override_cursor(shape)
            return
        self._cursor_state = (watched, had_cursor, original, shape)
        self._apply_override_cursor(shape)

    def _apply_override_cursor(self, shape):
        """GÖRÜNÜR imleç: ayrı top-level yüzeyde tek güvenilir yol.

        ÖLÇÜLEN KUSUR: pencere alt kenardan gerçekten boyutlanıyordu ama
        imleç normal ok / el işareti kalıyordu; ayrı top-level
        `control_overlay` üzerinde widget imleci ekranda görünmüyor.

        Override YALNIZ bu filtre açtıysa yönetilir. Başka bir bileşenin
        override'ı varsa stack'ine DOKUNULMAZ: ne sahiplenilir, ne
        değiştirilir, ne de restore edilir.
        """
        if self._owns_override:
            if shape != self._override_shape:
                try:
                    QApplication.changeOverrideCursor(QCursor(shape))
                except Exception:
                    return
                self._override_shape = shape
            return
        if QApplication.overrideCursor() is not None:
            return
        try:
            QApplication.setOverrideCursor(QCursor(shape))
        except Exception:
            return
        self._owns_override = True
        self._override_shape = shape

    def _restore_override_cursor(self):
        """Yalnız BİZE ait override, TAM BİR KEZ bırakılır."""
        if not self._owns_override:
            return False
        self._owns_override = False
        self._override_shape = None
        try:
            QApplication.restoreOverrideCursor()
        except Exception:
            pass
        return True

    def _restore_resize_cursor(self):
        """İdempotent: hedefin özgün imleci ve görünür override bırakılır."""
        state = self._cursor_state
        self._cursor_state = None
        self._restore_override_cursor()
        if state is None:
            return False
        widget, had_cursor, original, _shape = state
        try:
            if had_cursor:
                widget.setCursor(original)
            else:
                widget.unsetCursor()
        except (AttributeError, RuntimeError):
            pass
        return True

    @staticmethod
    def _left_button_held(event):
        """Sürükleme hâlâ sol tuşla mı sürüyor?"""
        try:
            return bool(event.buttons() & Qt.MouseButton.LeftButton)
        except (AttributeError, RuntimeError):
            return False

    def _can_use_system_resize(self, watched):
        """Olay ana pencerenin KENDİ top-level penceresinden mi geliyor?"""
        try:
            return watched.window() is self.player
        except (AttributeError, RuntimeError):
            return False

    def _start_system_resize(self, edges):
        handle = self.player.windowHandle()
        if handle is not None and hasattr(handle, "startSystemResize"):
            return bool(handle.startSystemResize(edges))
        return False

    # --- Sınırlı manuel yedek yol ---

    def manual_resize_active(self):
        return self._manual is not None

    def _begin_manual_resize(self, watched, edges, event):
        """Başlangıç imleci ve frameGeometry kaydedilir; fare yakalanır."""
        try:
            start = event.globalPosition().toPoint()
            # NOT: `setGeometry()` İSTEMCİ dikdörtgenini yazar. Başlangıcı
            # `frameGeometry()`den okumak, çerçeve payı olan bir pencerede
            # her sürüklemede o pay kadar kayma üretiyordu (ölçüldü: 2 px).
            # Okuma ve yazma AYNI koordinat uzayında tutulur.
            rect = QRect(self.player.geometry())
        except (AttributeError, RuntimeError):
            return False
        # FAIL-CLOSED: yakalama gerçekten alınmadan sürükleme başlamaz.
        # Aksi halde bırakma olayı hiç gelmeyebilir ve pencere sonraki
        # sıradan hareketlerde boyutlanırdı.
        try:
            watched.grabMouse()
        except (AttributeError, RuntimeError):
            return False
        if QWidget.mouseGrabber() is not watched:
            return False
        self._manual = {"edges": edges, "start": start, "rect": rect,
                        "grabber": watched}
        return True

    def _apply_manual_resize(self, event):
        """Yalnız kenarın gerektirdiği taraf değişir; minimum korunur."""
        state = self._manual
        if state is None:
            return
        try:
            current = event.globalPosition().toPoint()
        except (AttributeError, RuntimeError):
            # Konum okunamıyorsa sürükleme sürdürülemez: durum ve yakalama
            # KESİN olarak bırakılır.
            self._end_manual_resize()
            return
        delta_x = current.x() - state["start"].x()
        delta_y = current.y() - state["start"].y()
        rect = QRect(state["rect"])
        edges = state["edges"]
        minimum_width = max(1, self.player.minimumWidth())
        minimum_height = max(1, self.player.minimumHeight())
        if edges & Qt.Edge.LeftEdge:
            rect.setLeft(min(rect.left() + delta_x,
                             rect.right() - minimum_width + 1))
        elif edges & Qt.Edge.RightEdge:
            rect.setRight(max(rect.right() + delta_x,
                              rect.left() + minimum_width - 1))
        if edges & Qt.Edge.TopEdge:
            rect.setTop(min(rect.top() + delta_y,
                            rect.bottom() - minimum_height + 1))
        elif edges & Qt.Edge.BottomEdge:
            rect.setBottom(max(rect.bottom() + delta_y,
                               rect.top() + minimum_height - 1))
        try:
            self.player.setGeometry(rect)
        except RuntimeError:
            self._end_manual_resize()

    def _end_manual_resize(self):
        """İdempotent: yakalama bırakılır, durum silinir."""
        state = self._manual
        self._manual = None
        if state is None:
            return False
        grabber = state.get("grabber")
        if grabber is not None:
            try:
                grabber.releaseMouse()
            except (AttributeError, RuntimeError):
                pass
        self._restore_resize_cursor()
        return True
