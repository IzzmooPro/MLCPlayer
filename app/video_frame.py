import os
import math

from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QMenu, QHBoxLayout,
                             QPushButton, QSizePolicy, QSlider, QVBoxLayout)
from PyQt6.QtGui import QAction, QCursor
from PyQt6.QtCore import (Qt, QTimer, QPoint, QRect, QSize, QEvent,
                          QEasingCurve, QPropertyAnimation)
from app.ui_components import ClickableSlider
from app.ui_icons import make_media_icon
from app.utils import format_time
from app.config import MAX_VOLUME

# Sinematik kontrol katmanı ölçüleri (onaylanmış referans görsele göre).
OVERLAY_HEIGHT = 110
OVERLAY_SIDE_PADDING = 28
OVERLAY_NARROW_SIDE_PADDING = 12
OVERLAY_NARROW_WIDTH = 560
OVERLAY_ACCENT = "#F26A3D"
# Oynatma sürerken etkileşimsizlik sonrası overlay'in gizlenme süresi.
OVERLAY_AUTO_HIDE_MS = 2500
# Göster/gizle geçişlerinin fade süreleri.
OVERLAY_FADE_IN_MS = 140
OVERLAY_FADE_OUT_MS = 180

class VideoFrame(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.is_video_fullscreen = False
        self.control_overlay = None
        self._overlay_updating_position = False
        self._overlay_updating_volume = False
        # Otomatik gizlenme durumu. _overlay_auto_hidden yalnızca
        # etkileşimsizlik nedeniyle gizlenmeyi işaretler; owner deactivate
        # veya minimize nedeniyle gizlenme bundan ayrıdır.
        self.overlay_hide_timer = None
        self._overlay_auto_hidden = False
        self._overlay_hover = False
        self._overlay_event_targets = ()
        self._last_cursor_pos = None
        self.overlay_fade = None
        self._overlay_fade_target = 1.0

        # Mouse takibi için
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Mouse hareket zamanlayıcısı
        self.cursor_timer = QTimer(self)
        self.cursor_timer.setInterval(3000)  # 3 saniye
        self.cursor_timer.timeout.connect(self.hide_cursor)

        # Video oynatılmadığında gösterilecek logo/yer tutucu
        self.placeholder_label = QLabel(self)
        self.placeholder_label.setText("MLC Player\nMedia Launch Codec Player")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label.setStyleSheet(
            "color: #9AA7B3; font-size: 22px; font-weight: 600;"
            "background-color: #151A1F;"
        )
        self.placeholder_label.setGeometry(0, 0, self.width(), self.height())

        # Tam ekranda kontrol çubuğu görünmediği için geçici durum bildirimi.
        # mpv native render alanı normal child widget'ların üstünü kapatabilir.
        # Bu nedenle OSD ayrı bir üst pencere olarak gösterilir.
        osd_flags = (
            Qt.WindowType.Tool |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.osd_label = QLabel(None, osd_flags)
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

        if os.environ.get("MLCPLAYER_OVERLAY_PREVIEW") == "1":
            self._create_control_overlay()

    def _create_control_overlay(self):
        if self.control_overlay is not None:
            return

        overlay_flags = (
            Qt.WindowType.Tool |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
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
            "QPushButton { background: transparent; border: none; padding: 0; } "
            "QPushButton:hover { background: rgba(255, 255, 255, 28); "
            "border-radius: 4px; } "
            f"QPushButton#overlayPlayPause {{ border: 2px solid {OVERLAY_ACCENT}; "
            "border-radius: 22px; background: transparent; } "
            f"QPushButton#overlayPlayPause:hover {{ background: rgba(242, 106, 61, 45); }} "
            "QSlider::groove:horizontal { height: 3px; background: "
            "rgba(255, 255, 255, 70); border-radius: 1px; } "
            f"QSlider::sub-page:horizontal {{ height: 3px; background: {OVERLAY_ACCENT}; "
            "border-radius: 1px; } "
            f"QSlider::handle:horizontal {{ width: 11px; height: 11px; "
            f"margin: -4px 0; background: {OVERLAY_ACCENT}; border-radius: 5px; }}"
        )

        layout = QVBoxLayout(self.control_overlay)
        layout.setContentsMargins(OVERLAY_SIDE_PADDING, 10,
                                  OVERLAY_SIDE_PADDING, 14)
        layout.setSpacing(10)

        # Üst sıra: geniş timeline
        self.overlay_timeline = ClickableSlider(Qt.Orientation.Horizontal)
        self.overlay_timeline.setRange(0, 1000)
        self.overlay_timeline.setObjectName("overlayTimeline")
        self.overlay_timeline.setFixedHeight(14)
        self.overlay_timeline.valueChanged.connect(self._overlay_seek)
        layout.addWidget(self.overlay_timeline)

        # Alt sıra: sol süre, orta medya kontrolleri, sağ tam ekran
        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(0)

        time_row = QHBoxLayout()
        time_row.setContentsMargins(0, 0, 0, 0)
        time_row.setSpacing(4)
        self.overlay_current_time_label = QLabel("00:00")
        self.overlay_current_time_label.setStyleSheet(
            f"color: {OVERLAY_ACCENT}; background: transparent; font-size: 13px;")
        self.overlay_time_separator = QLabel("/")
        self.overlay_time_separator.setStyleSheet(
            "color: #B9BFC6; background: transparent; font-size: 13px;")
        separator = self.overlay_time_separator
        self.overlay_total_time_label = QLabel("00:00")
        self.overlay_total_time_label.setStyleSheet(
            "color: #D6DBE1; background: transparent; font-size: 13px;")
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
            "overlayPrevious", "previous", "Önceki", 32, 18)
        previous.clicked.connect(lambda: self.main_window.play_previous())
        controls.addWidget(previous, 0, Qt.AlignmentFlag.AlignVCenter)
        controls.addSpacing(14)

        # Referans görselde merkez sembol de turuncudur.
        self.overlay_play_pause_button = self._make_overlay_button(
            "overlayPlayPause", "play", "Oynat", 44, 20, OVERLAY_ACCENT)
        self.overlay_play_pause_button.clicked.connect(
            lambda: self.main_window.play_pause())
        controls.addWidget(self.overlay_play_pause_button, 0,
                           Qt.AlignmentFlag.AlignVCenter)
        controls.addSpacing(14)

        next_button = self._make_overlay_button(
            "overlayNext", "next", "Sonraki", 32, 18)
        next_button.clicked.connect(lambda: self.main_window.play_next())
        controls.addWidget(next_button, 0, Qt.AlignmentFlag.AlignVCenter)

        right_row = QHBoxLayout()
        right_row.setContentsMargins(0, 0, 0, 0)
        right_row.setSpacing(0)
        right_row.addStretch(1)

        # Referans sırası: CC, ses, ayarlar, ses çubuğu, tam ekran
        subtitles = self._make_overlay_button(
            "overlaySubtitles", "subtitles", "Altyazıları Göster/Gizle", 30, 18)
        subtitles.clicked.connect(lambda: self.main_window.toggle_subtitles())
        right_row.addWidget(subtitles, 0, Qt.AlignmentFlag.AlignVCenter)
        right_row.addSpacing(10)

        self.overlay_volume_button = self._make_overlay_button(
            "overlayVolume", "volume", "Sessiz", 30, 18)
        self.overlay_volume_button.clicked.connect(
            lambda: self.main_window.toggle_mute())
        right_row.addWidget(self.overlay_volume_button, 0,
                            Qt.AlignmentFlag.AlignVCenter)
        right_row.addSpacing(10)

        settings = self._make_overlay_button(
            "overlaySettings", "settings", "Video Ayarları", 30, 18)
        settings.clicked.connect(lambda: self.main_window.setup_video_adjustments())
        right_row.addWidget(settings, 0, Qt.AlignmentFlag.AlignVCenter)
        right_row.addSpacing(10)

        self.overlay_volume_slider = ClickableSlider(Qt.Orientation.Horizontal)
        self.overlay_volume_slider.setObjectName("overlayVolumeSlider")
        self.overlay_volume_slider.setRange(0, MAX_VOLUME)
        self.overlay_volume_slider.setFixedHeight(14)
        self.overlay_volume_slider.setMinimumWidth(40)
        self.overlay_volume_slider.setMaximumWidth(96)
        self.overlay_volume_slider.setToolTip("Ses Seviyesi")
        self.overlay_volume_slider.valueChanged.connect(self._overlay_volume_changed)
        source = getattr(self.main_window, "volume_slider", None)
        if source is not None:
            self._overlay_updating_volume = True
            self.overlay_volume_slider.setValue(int(source.value()))
            self._overlay_updating_volume = False
        right_row.addWidget(self.overlay_volume_slider, 0,
                            Qt.AlignmentFlag.AlignVCenter)
        right_row.addSpacing(12)

        fullscreen = self._make_overlay_button(
            "overlayFullscreen", "fullscreen", "Tam Ekran", 30, 18)
        fullscreen.clicked.connect(lambda: self.main_window.toggle_fullscreen())
        right_row.addWidget(fullscreen, 0, Qt.AlignmentFlag.AlignVCenter)
        right_container = QWidget(self.control_overlay)
        right_container.setLayout(right_row)
        right_container.setStyleSheet("background: transparent;")
        right_container.setMinimumWidth(0)
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

    def _overlay_volume_changed(self, value):
        """Kullanıcı overlay ses çubuğunu değiştirdiğinde ürünün gerçek
        ses akışını (klasik volume_slider -> set_volume) çalıştırır."""
        if self._overlay_updating_volume:
            return
        source = getattr(self.main_window, "volume_slider", None)
        if source is not None and source.value() != int(value):
            source.setValue(int(value))

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
        label = "Sesi Aç" if muted else "Sessiz"
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

        if previous is None or position == previous:
            return
        if not self._is_player_surface_active():
            return
        video_rect = QRect(self.mapToGlobal(QPoint(0, 0)), self.size())
        if not video_rect.contains(position):
            return
        self.show_overlay_for_interaction()

    def fade_overlay_in(self):
        """Mevcut opaklıktan 1.0'a yumuşak geçiş; gerekiyorsa önce show()."""
        if self.control_overlay is None or self.overlay_fade is None:
            return
        animation = self.overlay_fade
        animation.stop()
        if not self.control_overlay.isVisible():
            self.control_overlay.show()
        start = self.control_overlay.windowOpacity()
        self._overlay_fade_target = 1.0
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

    def hide_overlay_immediately(self):
        """Owner/system olayları: fade kullanılmaz, anında gizlenir."""
        if self.control_overlay is None:
            return
        if self.overlay_fade is not None:
            self.overlay_fade.stop()
        self.control_overlay.hide()
        self.control_overlay.setWindowOpacity(0.0)

    def show_overlay_for_interaction(self):
        """Kullanıcı etkileşiminde overlay'i gösterir ve sayacı tazeler."""
        if self.control_overlay is None:
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

    def _is_player_surface_active(self):
        return QApplication.activeWindow() in (
            self.main_window, self, self.control_overlay)

    def update_overlay_geometry(self):
        if self.control_overlay is None:
            return
        if not self.main_window.isVisible() or self.main_window.isMinimized():
            self.hide_overlay_immediately()
            return
        # Dar pencerede sağ kontrol grubu sığsın diye yan iç boşluk daralır;
        # böylece hiçbir ikon kırpılmaz ve katman video genişliğini aşmaz.
        narrow = self.width() < OVERLAY_NARROW_WIDTH
        layout = self.control_overlay.layout()
        if layout is not None:
            padding = (OVERLAY_NARROW_SIDE_PADDING if narrow
                       else OVERLAY_SIDE_PADDING)
            current = layout.contentsMargins()
            if current.left() != padding:
                layout.setContentsMargins(padding, current.top(),
                                          padding, current.bottom())

        # Dar pencerede süre metni yarım gösterilmektense tamamen gizlenir;
        # genişleyince kendiliğinden geri gelir.
        for widget in (self.overlay_current_time_label,
                       self.overlay_time_separator,
                       self.overlay_total_time_label):
            if widget.isVisibleTo(self.overlay_time_container) == narrow:
                widget.setVisible(not narrow)

        video_origin = self.mapToGlobal(QPoint(0, 0))
        # Referans: katman video alanının tüm genişliğini kaplar ve alta
        # sıfır boşlukla oturur.
        width = max(1, self.width())
        height = max(1, min(OVERLAY_HEIGHT, self.height()))
        x = video_origin.x()
        y = video_origin.y() + self.height() - height
        self.control_overlay.setGeometry(x, y, width, height)
        self.control_overlay.raise_()

    def showEvent(self, event):
        super().showEvent(event)
        if self.control_overlay is not None:
            QTimer.singleShot(0, self._restore_overlay_if_owner_visible)

    def _restore_overlay_if_owner_visible(self):
        # Etkileşimsizlik nedeniyle gizlenmiş overlay'i owner olayları
        # (show/resize/state change) kendiliğinden geri getirmemeli.
        if self._overlay_auto_hidden:
            return
        if (self.control_overlay is not None and self.main_window.isVisible()
                and not self.main_window.isMinimized()):
            self.update_overlay_geometry()
            self.fade_overlay_in()
            self.schedule_overlay_hide()

    def _restore_overlay_after_activation(self):
        # Ana pencere yeniden aktifleştiğinde overlay ilk anda görünür olur.
        self._overlay_auto_hidden = False
        self._restore_overlay_if_owner_visible()

    def _handle_overlay_interaction_event(self, event_type):
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
            self.show_overlay_for_interaction()

    def eventFilter(self, watched, event):
        if (self.control_overlay is not None
                and watched in self._overlay_event_targets):
            self._handle_overlay_interaction_event(event.type())
            return super().eventFilter(watched, event)

        if watched in (self.main_window, self):
            if (event.type() == QEvent.Type.Hide or
                    (event.type() == QEvent.Type.WindowDeactivate and
                     not self._is_player_surface_active())):
                self.hide_overlay_immediately()
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

    def close_control_overlay(self):
        if self.control_overlay is not None:
            if self.overlay_fade is not None:
                self.overlay_fade.stop()
            self.control_overlay.hide()
            self.control_overlay.close()

    def resizeEvent(self, event):
        self.placeholder_label.setGeometry(0, 0, self.width(), self.height())
        if self.osd_label.isVisible():
            self._center_osd()
        self.update_overlay_geometry()
        super().resizeEvent(event)

    def _center_osd(self):
        self.osd_label.adjustSize()
        video_origin = self.mapToGlobal(QPoint(0, 0))
        self.osd_label.move(
            video_origin.x() + max(0, (self.width() - self.osd_label.width()) // 2),
            video_origin.y() + max(10, self.height() - self.osd_label.height() - 24),
        )

    def show_osd(self, text, duration=1200):
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
        if self.is_video_fullscreen:
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

        window.showFullScreen()
        self.is_video_fullscreen = True
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

        self.is_video_fullscreen = False
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
        if self.is_video_fullscreen:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.cursor_timer.start()
        # Video yüzeyindeki hareket overlay'i hemen geri getirir.
        self.show_overlay_for_interaction()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        self.setFocus()
        super().mousePressEvent(event)

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
        # NOT: Parent olarak self (VideoFrame) kullanılamaz — mpv render'ı için
        # native pencere sahibi (winId'li) bir çocuk widget'tır. Qt, menü popup'ını
        # gösterirken QWindow::setTransientParent(parent) çağırır ve parent top-level
        # değilse "must be a top level window" uyarısı basar. Top-level pencereye parent et.
        context_menu = QMenu(self.window())
        context_menu.setStyleSheet("QMenu { background-color: #1C2526; color: white; }")

        # Dosya Aç menüsü
        open_action = context_menu.addAction("Dosya Aç (Ctrl+O)")
        open_action.triggered.connect(self.main_window.open_file)

        # URL'den Oynat
        url_action = context_menu.addAction("URL'den Oynat (Ctrl+U)")
        url_action.triggered.connect(self.main_window.open_url)

        # Ekran Görüntüsü Al
        screenshot_action = context_menu.addAction("Ekran Görüntüsü Al (Ctrl+S)")
        screenshot_action.triggered.connect(self.main_window.take_screenshot)

        # Oynatma Listesi
        playlist_action = context_menu.addAction("Oynatma Listesi (Ctrl+P)")
        playlist_action.triggered.connect(self.main_window.show_playlist)

        # Video Ayarları
        video_adj_action = context_menu.addAction("Video Ayarları")
        video_adj_action.triggered.connect(self.main_window.setup_video_adjustments)

        # Ses Kanalı menüsü (canlı doldurulur)
        audio_menu = context_menu.addMenu("Ses Kanalı")
        audio_menu.setStyleSheet("QMenu { background-color: #1C2526; color: white; }")
        if self.main_window.current_file:
            try:
                track_list = self.main_window.mpv_player.track_list
                audio_tracks = [t for t in track_list if t['type'] == 'audio']
                current_aid = self.main_window.mpv_player.aid
                if not audio_tracks:
                    na_action = QAction("Ses kanalı bulunamadı", self)
                    na_action.setEnabled(False)
                    audio_menu.addAction(na_action)
                else:
                    for track in audio_tracks:
                        lang = track.get('lang') or track.get('title') or f"Ses Kanalı {track['id']}"
                        track_action = QAction(f"{lang} (ID: {track['id']})", self)
                        track_action.setCheckable(True)
                        if track['id'] == current_aid:
                            track_action.setChecked(True)
                        track_action.triggered.connect(lambda checked, aid=track['id']: self.main_window.select_audio_track(aid))
                        audio_menu.addAction(track_action)
            except Exception as e:
                print(f"Ses kanalı listeleme hatası: {e}")
                error_action = QAction("Ses kanalları yüklenemedi", self)
                error_action.setEnabled(False)
                audio_menu.addAction(error_action)

        # Altyazılar menüsü
        subtitle_menu = context_menu.addMenu("Altyazılar")

        # Dili Seç (S yalnızca altyazıları göster/gizle kısayoludur.)
        select_language_menu = subtitle_menu.addMenu("Dili Seç")
        select_language_menu.setStyleSheet("QMenu { background-color: #1C2526; color: white; }")

        # Mevcut altyazıları al ve alt menüye ekle
        if self.main_window.current_file:
            try:
                self.main_window.mpv_player.command('rescan-external-files')
                track_list = self.main_window.mpv_player.track_list
                subtitles = [track for track in track_list if track['type'] == 'sub']
                current_sub_id = self.main_window.mpv_player.sid

                if not subtitles:
                    no_sub_action = QAction("Altyazı Bulunamadı", self)
                    no_sub_action.setEnabled(False)
                    select_language_menu.addAction(no_sub_action)
                else:
                    for sub in subtitles:
                        sub_label = sub.get('title') or sub.get('lang') or f"Altyazı {sub['id']}"
                        sub_action = QAction(f"{sub_label} (ID: {sub['id']})", self)
                        sub_action.setCheckable(True)
                        if sub['id'] == current_sub_id:
                            sub_action.setChecked(True)
                        sub_action.triggered.connect(lambda checked, sid=sub['id']: self.main_window.select_subtitle_language(sid))
                        select_language_menu.addAction(sub_action)
            except Exception as e:
                print(f"Altyazı listeleme hatası: {e}")
                error_action = QAction("Altyazılar yüklenemedi", self)
                error_action.setEnabled(False)
                select_language_menu.addAction(error_action)

        # Altyazıları Göster (Alt+H)
        toggle_subtitles_action = subtitle_menu.addAction("Altyazıları Göster (Alt+H)")
        toggle_subtitles_action.setShortcut("Alt+H")
        toggle_subtitles_action.triggered.connect(self.main_window.toggle_subtitles)

        # Altyazı Ekle (Alt+E)
        subtitle_add_action = subtitle_menu.addAction("Altyazı Ekle (Alt+E)")
        subtitle_add_action.setShortcut("Alt+E")
        subtitle_add_action.triggered.connect(self.main_window.open_subtitle)

        # Menüyü göster
        context_menu.exec(self.mapToGlobal(event.pos()))
