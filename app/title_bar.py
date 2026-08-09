"""Preview moduna özel modern başlık çubuğu prototipi.

Yalnızca MLCPLAYER_OVERLAY_PREVIEW=1 iken kullanılır. Klasik QMenuBar
gizlenir ama aksiyonları yaşamaya devam eder; üç nokta menüsü mevcut QMenu
nesnelerini yeniden kullanır, kopya davranış üretmez.
"""
from PyQt6.QtCore import QEvent, QObject, QPoint, QSize, Qt
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QMenu, QPushButton,
                             QSizePolicy, QWidget)

from app.ui_icons import make_media_icon

TITLE_BAR_HEIGHT = 42
RESIZE_MARGIN = 6
TITLE_BAR_BACKGROUND = "#11151A"

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
    """42 px modern başlık çubuğu: sol komutlar, sağ pencere düğmeleri."""

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
            "QPushButton:hover { background: rgba(255, 255, 255, 26); } "
            "QPushButton#titleClose:hover { background: #E81123; }"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(6)

        self.title_label = QLabel("MLC Player", self)
        self.title_label.setObjectName("titleText")
        self.title_label.setStyleSheet(
            "color: #E6EAF0; background: transparent; font-size: 13px;")
        # Dar pencerede başlık metni daralabilir; düğmeler kırpılmaz.
        # Ignored yerine Preferred: geniş pencerede metin görünür kalır.
        self.title_label.setMinimumWidth(0)
        self.title_label.setSizePolicy(QSizePolicy.Policy.Preferred,
                                       QSizePolicy.Policy.Preferred)
        layout.addWidget(self.title_label, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addSpacing(8)

        self.open_button = self._make_button(
            "titleOpenFile", "open_folder", "Dosya Aç")
        self.open_button.clicked.connect(lambda: self.player.open_file())
        layout.addWidget(self.open_button, 0, Qt.AlignmentFlag.AlignVCenter)

        self.playlist_button = self._make_button(
            "titlePlaylist", "playlist", "Playlist")
        self.playlist_button.clicked.connect(lambda: self.player.show_playlist())
        layout.addWidget(self.playlist_button, 0, Qt.AlignmentFlag.AlignVCenter)

        self.more_button = self._make_button("titleMore", "more", "Menü")
        self.more_button.clicked.connect(self.show_overflow_menu)
        layout.addWidget(self.more_button, 0, Qt.AlignmentFlag.AlignVCenter)

        layout.addStretch(1)

        self.minimize_button = self._make_button(
            "titleMinimize", "minimize", "Küçült")
        self.minimize_button.clicked.connect(lambda: self.player.showMinimized())
        layout.addWidget(self.minimize_button, 0, Qt.AlignmentFlag.AlignVCenter)

        self.maximize_button = self._make_button(
            "titleMaximize", "maximize", "Büyüt")
        self.maximize_button.clicked.connect(self.toggle_maximized)
        layout.addWidget(self.maximize_button, 0, Qt.AlignmentFlag.AlignVCenter)

        self.close_button = self._make_button("titleClose", "close", "Kapat")
        self.close_button.clicked.connect(lambda: self.player.close())
        layout.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignVCenter)

    # --- Kurulum yardımcıları ---

    def _make_button(self, object_name, icon_kind, label, size=30, icon_size=16):
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

    def show_overflow_menu(self):
        menu = self.build_overflow_menu()
        origin = self.more_button.mapToGlobal(
            QPoint(0, self.more_button.height()))
        menu.exec(origin)

    # --- Pencere durumu ---

    def toggle_maximized(self):
        if self.player.isMaximized():
            self.player.showNormal()
        else:
            self.player.showMaximized()
        self.update_maximize_state()

    def update_maximize_state(self):
        maximized = self.player.isMaximized()
        label = "Geri Yükle" if maximized else "Büyüt"
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
    """Frameless pencerede sekiz yönlü resize.

    6 px kenar alanı main_layout iç boşluğunda kaldığı için gerçek fare
    olayı ana pencereye değil central_widget'a ulaşabilir. Bu nedenle filtre
    hem ana pencereye hem de kenar olaylarını alan widget'lara kurulur ve
    child koordinatları ana pencere koordinatına map edilir.

    Windows'un kendi resize/snap davranışını korumak için
    QWindow.startSystemResize kullanılır; sürekli geometri döngüsü kurulmaz.
    """

    def __init__(self, player, title_bar):
        super().__init__(player)
        self.player = player
        self.title_bar = title_bar
        self.targets = []

    def install(self):
        """Ana pencere ve gerçek kenar olaylarını alan widget'lara kurulur."""
        candidates = [self.player, getattr(self.player, "central_widget", None)]
        for target in candidates:
            if target is not None and target not in self.targets:
                target.installEventFilter(self)
                target.setMouseTracking(True)
                self.targets.append(target)
        return self.targets

    def remove(self):
        """Yalnızca kurulan hedeflerden filtreyi kaldırır."""
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
        return watched.mapTo(self.player, point)

    def eventFilter(self, watched, event):
        # NOT: Yalnızca gereken olay tipleri ele alınır ve super() çağrılmaz.
        # Aksi halde MPV kurulumu sırasındaki yoğun pencere olaylarında
        # yeniden girişli çağrı zinciri yığını taşırıyordu.
        if watched not in self.targets:
            return False
        event_type = event.type()
        if event_type in (QEvent.Type.WindowStateChange,
                          QEvent.Type.WindowActivate, QEvent.Type.Show):
            self.title_bar.update_maximize_state()
            ensure = getattr(self.player, "ensure_title_bar_on_top", None)
            if callable(ensure):
                ensure()
            return False
        if event_type not in (QEvent.Type.MouseMove,
                              QEvent.Type.MouseButtonPress):
            return False
        if not self.title_bar.can_resize_window():
            self.player.setCursor(Qt.CursorShape.ArrowCursor)
            return False
        edges = resize_edges_at(self.player.rect(),
                               self._window_position(watched, event))
        if event_type == QEvent.Type.MouseMove:
            self.player.setCursor(cursor_for_edges(edges))
            return False
        if (event.button() == Qt.MouseButton.LeftButton and edges
                and self._start_system_resize(edges)):
            return True
        return False

    def _start_system_resize(self, edges):
        handle = self.player.windowHandle()
        if handle is not None and hasattr(handle, "startSystemResize"):
            return bool(handle.startSystemResize(edges))
        return False
