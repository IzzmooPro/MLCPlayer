import os

from PyQt6.QtCore import QEasingCurve, QEvent, QSize, Qt, QVariantAnimation
from PyQt6.QtWidgets import (QAbstractItemView, QHBoxLayout,
                             QLabel, QLayout, QLineEdit, QListWidget, QListWidgetItem,
                             QApplication, QPushButton, QSizePolicy, QVBoxLayout,
                             QWidget)
from app.config import MEDIA_EXTENSIONS
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
            self.panel.video_frame.set_playlist_panel_width(
                self._press_width + delta)
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


class PlaylistPanel(QWidget):
    """Sinematik arayüzün sağdan açılan oynatma listesi paneli.

    Panel `playlist_dock_host`'un GERÇEK child widget'ıdır; ayrı bir top-level
    `Tool` penceresi değildir. Böylece video ile kesişmesi yapısal olarak
    imkânsızdır, Windows onu bağımsız sıralayamaz veya bayat global geometride
    bırakamaz ve ana pencereyle aynı görünürlük yaşam döngüsünü paylaşır.
    """

    def __init__(self, player, video_frame):
        host = getattr(player, "playlist_dock_host", None)
        # Klasik/test yardımcı pencerelerinde dock host bulunmayabilir; o
        # durumda bile top-level pencere ÜRETİLMEZ, panel video çerçevesinin
        # child'ı olarak kalır.
        super().__init__(host if host is not None else video_frame)
        self.player = player
        self.video_frame = video_frame
        self.host = host
        self._target_open = False
        self._split_press_global_x = None
        self._split_press_width = 0
        # Panelin host içindeki yerel x ofseti. 0 = tamamen açık,
        # host.width() = tamamen kapalı (host tarafından clip edilir).
        self._offset_x = 0
        if host is not None:
            # NOT: Panel host layout'una EKLENMEZ. Açılış/kapanış animasyonu
            # host genişliğini her karede değiştirmek yerine paneli host
            # içinde kaydırır; layout'a bağlı olsaydı her karede yeniden
            # konumlandırılır ve kaydırma mümkün olmazdı.
            host.installEventFilter(self)

        self.setObjectName("playlistPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMouseTracking(True)
        self.setStyleSheet(
            "QWidget#playlistPanel { background: rgba(19, 20, 22, 247); "
            "border-left: 1px solid rgba(255,255,255,24); } "
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
            f"QPushButton#playlistAdd {{ color: {PLAYLIST_ACCENT}; }}"
        )
        self.resize_handle = PlaylistResizeHandle(self)
        self.resize_handle.raise_()

        root = QVBoxLayout(self)
        # Top-level tool window, child widget'ların doğal genişliğini pencereye
        # zorlamasın; 400x300 ana pencerede panel video yüzeyine sığabilsin.
        root.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        root.setContentsMargins(18, 18, 18, 14)
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
        self.close_button = QPushButton("×", self)
        self.close_button.setObjectName("playlistClose")
        self.close_button.setAccessibleName(tr("Oynatma Listesini Kapat"))
        self.close_button.setToolTip(tr("Kapat (Esc)"))
        self.close_button.setFixedSize(36, 36)
        self.close_button.setStyleSheet(
            "font-size: 25px; font-weight: 300; background: transparent; "
            "color: #E7EAED; padding: 0;")
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
        self.animation.valueChanged.connect(self._apply_animated_offset)
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
        """Dock'un açıkken ayırması gereken genişlik."""
        return max(1, self.host.width()) if self.host is not None else self.width()

    @property
    def slide_offset(self):
        """Panelin host içindeki yerel x konumu (görsel animasyon durumu)."""
        return self._offset_x

    def apply_panel_geometry(self):
        """Paneli host'u dolduracak boyuta getirir ve ofsetine yerleştirir.

        Genişlik/yükseklik host'tan gelir, konum ise animasyon ofsetinden.
        Host child'ını clip ettiği için ofset > 0 iken panelin dışarı taşan
        kısmı çizilmez; video üzerine taşma oluşmaz.
        """
        if self.host is None:
            return
        width = max(1, self.host.width())
        height = max(1, self.host.height())
        self.setGeometry(int(self._offset_x), 0, width, height)

    def _apply_animated_offset(self, value):
        # Yalnızca panelin kendi konumu değişir: host genişliği, media_container
        # layout'u, VideoFrame ve MPV native wid yüzeyi DOKUNULMADAN kalır.
        self._offset_x = int(value)
        self.apply_panel_geometry()

    def open_animated(self):
        self.refresh()
        already_open = self._target_open
        self._target_open = True
        self.animation.stop()
        if self.host is None:
            self.show()
            return
        # Hedef genişlik BİR KEZ ayrılır; video/MPV yüzeyi tek sefer yeniden
        # boyutlanır. Animasyon bundan sonra yalnızca paneli kaydırır.
        if not already_open:
            self.video_frame.reserve_playlist_dock()
        self.host.show()
        start = self._offset_x if already_open else self.host.width()
        self._apply_animated_offset(start)
        self.show()
        self.animation.setStartValue(int(start))
        self.animation.setEndValue(0)
        self.animation.start()

    def close_animated(self):
        if not self._target_open:
            return
        self._target_open = False
        self.animation.stop()
        if self.host is None:
            self.hide()
            return
        # Tersine çevirmede mevcut görsel konumdan devam edilir; sıçrama yok.
        self.animation.setStartValue(int(self._offset_x))
        self.animation.setEndValue(int(max(1, self.host.width())))
        self.animation.start()

    def finish_animation(self):
        """Test/smoke için animasyonu deterministik son durumuna taşır."""
        self.animation.stop()
        if self._target_open:
            if self.host is not None:
                self.video_frame.reserve_playlist_dock()
                self.host.show()
            self._apply_animated_offset(0)
            self.show()
        else:
            self._finish_closed()

    def _finish_closed(self):
        """Kapanış sonu: host genişliği TEK SEFERDE 0, video tek seferde büyür."""
        self._apply_animated_offset(0)
        self.hide()
        self.video_frame.release_playlist_dock()
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
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (self._split_press_global_x is not None
                and event.buttons() & Qt.MouseButton.LeftButton):
            delta = self._split_press_global_x - int(event.globalPosition().x())
            self.video_frame.set_playlist_panel_width(
                self._split_press_width + delta)
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
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        if self._split_press_global_x is None:
            self.unsetCursor()
        super().leaveEvent(event)

    def eventFilter(self, watched, event):
        # Host yeniden boyutlandığında panel onu doldurmaya devam etmeli;
        # bu tek yol layout'un yerini alır (bkz. __init__ notu).
        if watched is self.host and event.type() == QEvent.Type.Resize:
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
