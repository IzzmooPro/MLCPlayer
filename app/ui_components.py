# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
import os

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QSizePolicy, QSlider, QStyle
from PyQt6.QtCore import Qt, QSize, QRectF
from PyQt6.QtGui import QColor, QPainter
from app.utils import create_colored_icon, format_time
from app.config import (UI_ACCENT, cinematic_ui_enabled, DEFAULT_VOLUME,
                        MAX_VOLUME)
from app.i18n import tr

WHEEL_ANGLE_PER_STEP = 120
WHEEL_VOLUME_STEP = 5

# Özel QSlider sınıfı - tıklama ve sürükleme olaylarını yakalayabilmek için
class ClickableSlider(QSlider):
    def __init__(self, orientation):
        super().__init__(orientation)
        self.setMouseTracking(True)

    def _value_at(self, x):
        """Yatay konumu slider aralığına güvenli biçimde dönüştürür.

        x, kullanılabilir genişliğe sınırlanır; böylece kenarlara yapılan
        tıklamalar aralık dışına taşan değer üretmez.
        """
        width = max(1, self.width())
        ratio = min(1.0, max(0.0, x / width))
        span = self.maximum() - self.minimum()
        return int(round(self.minimum() + span * ratio))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setSliderDown(True)
            self.setValue(self._value_at(event.position().x()))
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setSliderDown(False)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.setValue(self._value_at(event.position().x()))
            event.accept()
        else:
            super().mouseMoveEvent(event)

# Ses çubuğu: 0-100 arası normal (mavi), 100-MAX_VOLUME arası
# amplifikasyon bölgesi (turuncu). Fare tekerleği ile de ses değiştirir.
class VolumeSlider(ClickableSlider):
    def __init__(self, orientation):
        super().__init__(orientation)
        self._wheel_angle_remainder = 0

    def wheelEvent(self, event):
        angle = event.angleDelta()
        if angle.y() == 0 or abs(angle.y()) <= abs(angle.x()):
            self._wheel_angle_remainder = 0
            event.ignore()
            return
        self._wheel_angle_remainder += angle.y()
        steps = int(self._wheel_angle_remainder / WHEEL_ANGLE_PER_STEP)
        if steps:
            self._wheel_angle_remainder -= steps * WHEEL_ANGLE_PER_STEP
            self.setValue(self.value() + steps * WHEEL_VOLUME_STEP)
        event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        groove_h = 4
        groove_y = (h - groove_h) // 2
        left, right = 6, w - 6
        groove_w = right - left

        painter.setPen(Qt.PenStyle.NoPen)
        # Zemin
        painter.setBrush(QColor("#3A4450"))
        painter.drawRoundedRect(QRectF(left, groove_y, groove_w, groove_h), 2, 2)

        # 100 sınırının çubuktaki konumu
        vmax = self.maximum() or 1
        val = max(0, min(vmax, self.value()))
        ratio100 = 100.0 / vmax
        ratio_val = val / vmax

        fill_w = groove_w * ratio_val
        # Normal bölge (0-100): mavi
        normal_w = min(fill_w, groove_w * ratio100)
        if normal_w > 0:
            painter.setBrush(QColor(UI_ACCENT))
            painter.drawRoundedRect(QRectF(left, groove_y, normal_w, groove_h), 2, 2)

        # Amplifikasyon bölgesi (100-MAX_VOLUME): turuncu
        if val > 100 and fill_w > normal_w:
            painter.setBrush(QColor("#F5A623"))
            painter.drawRoundedRect(QRectF(left + normal_w, groove_y, fill_w - normal_w, groove_h), 2, 2)

        # İşaretçi (handle)
        handle_x = left + fill_w - 4
        painter.setBrush(QColor("#E8EDF2"))
        painter.drawEllipse(QRectF(handle_x, groove_y - 2, 8, 8))

        painter.end()

def setup_controls(player):
    """Player için kontrol panelini oluştur"""
    # Ana kontrol container'ı
    control_container = QWidget()
    control_container.setObjectName("controlContainer")  # Bu çok önemli - bunu bulabilmek için
    control_container.setStyleSheet("""
        QWidget#controlContainer {
            background-color: #1A2027;
            border-top: 1px solid #2A323A;
        }
    """)

    # Container'ın yüksekliğini ayarla
    control_container.setFixedHeight(54)

    main_layout = QVBoxLayout(control_container)
    main_layout.setContentsMargins(12, 4, 12, 6)
    main_layout.setSpacing(2)

    # Timeline kısmı
    timeline_layout = QHBoxLayout()
    timeline_layout.setContentsMargins(0, 0, 0, 0)
    timeline_layout.setSpacing(6)

    # Geçerli zaman etiketi
    player.current_time_label = QLabel("00:00")
    player.current_time_label.setObjectName("timeLabel")
    player.current_time_label.setStyleSheet("font-size: 12px; color: #9AA7B3;")
    player.current_time_label.setMinimumWidth(30)
    timeline_layout.addWidget(player.current_time_label)

    # Timeline slider'ı
    player.position_slider = ClickableSlider(Qt.Orientation.Horizontal)
    player.position_slider.setObjectName("positionSlider")
    player.position_slider.setRange(0, 1000)
    player.position_slider.setValue(0)
    player.position_slider.valueChanged.connect(player.seek_position)
    timeline_layout.addWidget(player.position_slider)

    # Toplam süre etiketi
    player.total_time_label = QLabel("00:00")
    player.total_time_label.setObjectName("timeLabel")
    player.total_time_label.setStyleSheet("font-size: 12px; color: #9AA7B3;")
    player.total_time_label.setMinimumWidth(30)
    timeline_layout.addWidget(player.total_time_label)

    main_layout.addLayout(timeline_layout)

    # Kontrol butonları kısmı
    control_layout = QHBoxLayout()
    control_layout.setContentsMargins(0, 0, 0, 0)
    control_layout.setSpacing(4)

    # Oynat/Duraklat butonu
    player.play_button = QPushButton()
    player.play_button.setObjectName("playButton")
    play_icon = player.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
    pause_icon = player.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause)
    white_play_icon = create_colored_icon(play_icon, QColor(Qt.GlobalColor.white))
    white_pause_icon = create_colored_icon(pause_icon, QColor(Qt.GlobalColor.white))
    player.play_button.setIcon(white_play_icon)
    player.play_button.setIconSize(QSize(16, 16))
    player.play_button.setFixedSize(24, 24)
    player.play_button.clicked.connect(player.play_pause)
    player.play_button.setToolTip(tr("Oynat/Duraklat (Space)"))
    control_layout.addWidget(player.play_button)

    # Icon referanslarını sakla
    player.play_icon = white_play_icon
    player.pause_icon = white_pause_icon

    # Durdur butonu
    player.stop_button = QPushButton()
    player.stop_button.setObjectName("controlButton")
    stop_icon = player.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop)
    player.stop_button.setIcon(create_colored_icon(stop_icon, QColor(Qt.GlobalColor.white)))
    player.stop_button.setIconSize(QSize(16, 16))
    player.stop_button.setFixedSize(24, 24)
    player.stop_button.clicked.connect(player.stop)
    player.stop_button.setToolTip(tr("Durdur"))
    control_layout.addWidget(player.stop_button)

    # Orta kısım - Boşluk
    spacer = QWidget()
    spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    control_layout.addWidget(spacer)

    # Tam ekran butonu
    player.fullscreen_button = QPushButton()
    player.fullscreen_button.setObjectName("controlButton")
    fullscreen_icon = player.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarMaxButton)
    player.fullscreen_button.setIcon(create_colored_icon(fullscreen_icon, QColor(Qt.GlobalColor.white)))
    player.fullscreen_button.setIconSize(QSize(14, 14))
    player.fullscreen_button.setFixedSize(24, 24)
    player.fullscreen_button.clicked.connect(player.toggle_fullscreen)
    player.fullscreen_button.setToolTip(tr("Tam Ekran (F)"))
    control_layout.addWidget(player.fullscreen_button)

    # Altyazı butonu
    player.subtitle_button = QPushButton()
    player.subtitle_button.setObjectName("controlButton")
    subtitle_icon = player.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
    player.subtitle_button.setIcon(create_colored_icon(subtitle_icon, QColor(Qt.GlobalColor.white)))
    player.subtitle_button.setIconSize(QSize(14, 14))
    player.subtitle_button.setFixedSize(24, 24)
    player.subtitle_button.clicked.connect(player.toggle_subtitles)
    player.subtitle_button.setToolTip(tr("Altyazıları Göster/Gizle (S)"))
    control_layout.addWidget(player.subtitle_button)

    # Ekran görüntüsü butonu
    player.screenshot_button = QPushButton()
    player.screenshot_button.setObjectName("controlButton")
    screenshot_icon = player.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView)
    player.screenshot_button.setIcon(create_colored_icon(screenshot_icon, QColor(Qt.GlobalColor.white)))
    player.screenshot_button.setIconSize(QSize(14, 14))
    player.screenshot_button.setFixedSize(24, 24)
    player.screenshot_button.clicked.connect(player.take_screenshot)
    player.screenshot_button.setToolTip(tr("Ekran Görüntüsü (Ctrl+S)"))
    control_layout.addWidget(player.screenshot_button)

    # Ses butonu
    player.volume_icon = QPushButton()
    player.volume_icon.setObjectName("controlButton")
    player.volume_icon.setIcon(player.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume))
    player.volume_icon.setIconSize(QSize(14, 14))
    player.volume_icon.setFixedSize(24, 24)
    player.volume_icon.clicked.connect(player.toggle_mute)
    player.volume_icon.setToolTip(tr("Sessiz (M)"))
    control_layout.addWidget(player.volume_icon)

    # Ses seviyesi etiketi - volume_slider'dan ÖNCE oluşturulmalı ki
    # setValue yoluyla tetiklenen set_volume etikete erişebilsin
    player.volume_label = QLabel(f"%{int(DEFAULT_VOLUME)}")
    player.volume_label.setObjectName("volumeLabel")
    player.volume_label.setStyleSheet("font-size: 12px; color: #9AA7B3;")
    # Sabit genişlik/yükseklik: metin boyutu değişince etiket yukarı/aşağı kaymasın
    player.volume_label.setFixedWidth(38)
    player.volume_label.setFixedHeight(20)
    player.volume_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    # Ses seviyesi çubuğu (0-175: 100 üstü mpv amplifikasyonu, ikon ve etiket buna uyar)
    player.volume_slider = VolumeSlider(Qt.Orientation.Horizontal)
    player.volume_slider.setObjectName("volumeSlider")
    player.volume_slider.setRange(0, MAX_VOLUME)
    player.volume_slider.setFixedWidth(70)
    # valueChanged sinyalini önce bağla ki setValue varsayılan ses seviyesini MPV'ye uygulasın
    player.volume_slider.valueChanged.connect(player.set_volume)
    player.volume_slider.setValue(DEFAULT_VOLUME)
    player.volume_slider.setToolTip(tr("Ses Seviyesi"))
    control_layout.addWidget(player.volume_slider)
    control_layout.addWidget(player.volume_label)

    main_layout.addLayout(control_layout)

    # Ana düzene ekle
    player.main_layout.addWidget(control_container)

    # Sinematik arayüzde tek görünen oynatma kontrol yüzeyi overlay'dir.
    # Klasik panel nesneleri (position_slider, volume_slider, play_button vb.)
    # görünmez bir uyumluluk katmanı olarak yaşamaya devam eder; yalnızca
    # gizlenir ve layout'ta yer kaplamaz.
    player.control_container = control_container
    enabled = getattr(player, "cinematic_ui_enabled", None)
    if enabled is None:
        enabled = cinematic_ui_enabled()
    if enabled:
        control_container.setFixedHeight(0)
        control_container.hide()

    # Stil güncellemesi - daha küçük kontrollerle uyumlu
    additional_style = """
        QSlider#positionSlider::groove:horizontal {
            height: 4px;
            background: #3A4450;
            border-radius: 2px;
        }
        QSlider#positionSlider::handle:horizontal {
            background: #E8EDF2;
            width: 10px;
            height: 10px;
            margin: -3px 0;
            border-radius: 5px;
        }
        QSlider#positionSlider::handle:horizontal:hover {
            background: #FFFFFF;
        }
        QSlider#positionSlider::sub-page:horizontal {
            background: #F26A3D;
            border-radius: 2px;
        }
        QSlider#volumeSlider::groove:horizontal {
            height: 3px;
            background: #3A4450;
            border-radius: 1px;
        }
        QSlider#volumeSlider::handle:horizontal {
            background: #E8EDF2;
            width: 8px;
            height: 8px;
            margin: -2px 0;
            border-radius: 4px;
        }
        QSlider#volumeSlider::handle:horizontal:hover {
            background: #FFFFFF;
        }
        QSlider#volumeSlider::sub-page:horizontal {
            background: #F26A3D;
            border-radius: 1px;
        }
        QPushButton#controlButton, QPushButton#playButton {
            background-color: transparent;
            border: none;
            border-radius: 12px;
        }
        QPushButton#controlButton:hover, QPushButton#playButton:hover {
            background-color: rgba(80, 90, 102, 0.35);
        }
        QPushButton#controlButton:pressed, QPushButton#playButton:pressed {
            background-color: rgba(100, 112, 128, 0.45);
        }
        QPushButton#controlButton:disabled {
            background-color: transparent;
        }
    """
    player.setStyleSheet(player.styleSheet() + additional_style)

    # Update time label fonksiyonunu güncelle
    def update_time_label():
        if player.duration > 0:
            player.current_time_label.setText(format_time(player.position))
            player.total_time_label.setText(format_time(player.duration))

    player.update_time_label = update_time_label
