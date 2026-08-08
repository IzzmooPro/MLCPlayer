import os
import math

from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QMenu, QHBoxLayout, QPushButton, QSlider
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, QTimer, QPoint, QEvent
from app.ui_components import ClickableSlider
from app.utils import format_time

class VideoFrame(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.is_video_fullscreen = False
        self.control_overlay = None
        self._overlay_updating_position = False

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
        self.control_overlay.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus)
        self.control_overlay.setObjectName("controlOverlayPreview")
        self.control_overlay.setStyleSheet(
            "QWidget#controlOverlayPreview { background: rgba(18, 24, 30, 225); "
            "border: 1px solid rgba(255, 255, 255, 35); border-radius: 8px; } "
            "QPushButton { color: white; background: transparent; border: none; "
            "padding: 6px 10px; } QPushButton:hover { background: rgba(255,255,255,35); } "
            "QSlider::groove:horizontal { height: 3px; background: #59636D; } "
            "QSlider::sub-page:horizontal { background: #E06A3B; } "
            "QSlider::handle:horizontal { width: 10px; margin: -4px 0; "
            "background: #FFFFFF; border-radius: 5px; }"
        )

        layout = QHBoxLayout(self.control_overlay)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(0)

        previous = QPushButton("Önceki")
        previous.setFixedWidth(50)
        previous.clicked.connect(lambda: self.main_window.play_previous())
        layout.addWidget(previous)

        self.overlay_play_pause_button = QPushButton("Oynat")
        self.overlay_play_pause_button.setFixedWidth(50)
        self.overlay_play_pause_button.clicked.connect(lambda: self.main_window.play_pause())
        layout.addWidget(self.overlay_play_pause_button)

        next_button = QPushButton("Sonraki")
        next_button.setFixedWidth(50)
        next_button.clicked.connect(lambda: self.main_window.play_next())
        layout.addWidget(next_button)

        self.overlay_current_time_label = QLabel("00:00")
        self.overlay_current_time_label.setFixedWidth(38)
        layout.addWidget(self.overlay_current_time_label)

        self.overlay_timeline = ClickableSlider(Qt.Orientation.Horizontal)
        self.overlay_timeline.setRange(0, 1000)
        self.overlay_timeline.setMinimumWidth(20)
        self.overlay_timeline.setObjectName("overlayTimeline")
        self.overlay_timeline.valueChanged.connect(self._overlay_seek)
        layout.addWidget(self.overlay_timeline, 1)

        self.overlay_total_time_label = QLabel("00:00")
        self.overlay_total_time_label.setFixedWidth(38)
        layout.addWidget(self.overlay_total_time_label)

        fullscreen = QPushButton("Tam Ekran")
        fullscreen.setFixedWidth(65)
        fullscreen.clicked.connect(lambda: self.main_window.toggle_fullscreen())
        layout.addWidget(fullscreen)

        self.main_window.installEventFilter(self)
        self.installEventFilter(self)

    def _overlay_seek(self, value):
        if not self._overlay_updating_position:
            self.main_window.seek_position(value)

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

    def update_overlay_play_state(self):
        if self.control_overlay is None:
            return
        play_pause_text = (
            "Oynat" if getattr(self.main_window, "is_paused", True) else "Duraklat")
        if self.overlay_play_pause_button.text() != play_pause_text:
            self.overlay_play_pause_button.setText(play_pause_text)

    def _is_player_surface_active(self):
        return QApplication.activeWindow() in (
            self.main_window, self, self.control_overlay)

    def update_overlay_geometry(self):
        if self.control_overlay is None:
            return
        if not self.main_window.isVisible() or self.main_window.isMinimized():
            self.control_overlay.hide()
            return
        self.control_overlay.adjustSize()
        video_origin = self.mapToGlobal(QPoint(0, 0))
        width = min(760, max(1, self.width() - 24))
        height = self.control_overlay.sizeHint().height()
        x = video_origin.x() + max(12, (self.width() - width) // 2)
        y = video_origin.y() + max(12, self.height() - height - 12)
        self.control_overlay.setGeometry(x, y, width, height)
        self.control_overlay.raise_()

    def showEvent(self, event):
        super().showEvent(event)
        if self.control_overlay is not None:
            QTimer.singleShot(0, self._restore_overlay_if_owner_visible)

    def _restore_overlay_if_owner_visible(self):
        if (self.control_overlay is not None and self.main_window.isVisible()
                and not self.main_window.isMinimized()):
            self.update_overlay_geometry()
            self.control_overlay.show()

    def eventFilter(self, watched, event):
        if watched in (self.main_window, self):
            if (event.type() == QEvent.Type.Hide or
                    (event.type() == QEvent.Type.WindowDeactivate and
                     not self._is_player_surface_active())):
                self.control_overlay.hide()
            elif event.type() == QEvent.Type.Show:
                QTimer.singleShot(0, self._restore_overlay_if_owner_visible)
            elif event.type() == QEvent.Type.WindowStateChange:
                if self.main_window.isMinimized():
                    self.control_overlay.hide()
                else:
                    QTimer.singleShot(0, self._restore_overlay_if_owner_visible)
            elif event.type() in (QEvent.Type.Move, QEvent.Type.Resize,
                                  QEvent.Type.ZOrderChange):
                self.update_overlay_geometry()
            elif event.type() == QEvent.Type.WindowActivate:
                QTimer.singleShot(0, self._restore_overlay_if_owner_visible)
            elif event.type() == QEvent.Type.Close:
                self.close_control_overlay()
        return super().eventFilter(watched, event)

    def close_control_overlay(self):
        if self.control_overlay is not None:
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

    def enter_fullscreen(self):
        self.main_window.main_layout.removeWidget(self)
        self.setParent(None)
        self.showFullScreen()
        self.main_window.central_widget.hide()
        self.is_video_fullscreen = True
        self.setFocus()
        self.cursor_timer.start()
        self.update_overlay_geometry()

    def exit_fullscreen(self):
        if not self.is_video_fullscreen:
            return
        self.cursor_timer.stop()
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.showNormal()
        self.setParent(self.main_window.central_widget)
        self.main_window.main_layout.insertWidget(0, self)
        self.main_window.central_widget.show()
        self.is_video_fullscreen = False
        self.update_overlay_geometry()

    def closeEvent(self, event):
        # Tam ekran widget'ı ana pencereden ayrıldığı için kendi kapatılması
        # ana pencereyi de kapatmalı; aksi halde süreç arka planda kalabilir.
        self.osd_label.hide()
        self.close_control_overlay()
        if self.is_video_fullscreen:
            self.exit_fullscreen()
            if self.main_window:
                self.main_window.close()
        event.accept()

    def hide_cursor(self):
        if self.is_video_fullscreen:
            self.setCursor(Qt.CursorShape.BlankCursor)

    def mouseMoveEvent(self, event):
        if self.is_video_fullscreen:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.cursor_timer.start()
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
