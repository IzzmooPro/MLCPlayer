# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Medya yokken native video yüzeyinin üstünde görünen başlangıç ekranı."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from app.app_icon import application_icon
from app.config import (UI_ACCENT, UI_ACCENT_HOVER, UI_ACCENT_PRESSED,
                        UI_FONT_FAMILY)
from app.i18n import tr


EMPTY_STATE_TITLE = "İzlemeye hazır"
EMPTY_STATE_HINT = (
    "Bir videoyu buraya sürükleyin veya bilgisayarınızdan açın."
)


class EmptyStateOverlay(QWidget):
    """MPV'nin native child yüzeyinin üstünde kalan sahipli başlangıç yüzeyi."""

    def __init__(self, video_frame):
        super().__init__(video_frame)
        self.player = video_frame.main_window
        self.setObjectName("emptyStateOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # MPV doğrudan VideoFrame'in HWND'sine çizer. Başlangıç yüzeyi de
        # native child olmazsa normal QWidget olarak MPV'nin altında kalır.
        # Ayrı Tool penceresi yapılmaz: dosya seçicide gizlenip eski ekranı
        # açığa çıkarmamalı ve foreground tahminine bağımlı olmamalıdır.
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.winId()
        self.setAcceptDrops(True)
        self.setStyleSheet(
            f"QWidget#emptyStateOverlay {{ background: #11161B; "
            f"font-family: {UI_FONT_FAMILY}; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 24, 20, 24)
        root.setSpacing(0)
        root.addStretch(2)

        self.logo_label = QLabel(self)
        self.logo_label.setObjectName("emptyStateLogo")
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_label.setStyleSheet("background: transparent;")
        icon = application_icon()
        if not icon.isNull():
            self.logo_label.setPixmap(icon.pixmap(94, 94))
        root.addWidget(self.logo_label)
        root.addSpacing(18)

        self.title_label = QLabel(tr("İzlemeye hazır"), self)
        self.title_label.setObjectName("emptyStateTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet(
            "color: #F5F6F7; background: transparent; "
            "font-size: 30px; font-weight: 700;")
        root.addWidget(self.title_label)
        root.addSpacing(12)

        self.hint_label = QLabel(
            tr("Bir videoyu buraya sürükleyin veya bilgisayarınızdan açın."),
            self)
        self.hint_label.setObjectName("emptyStateHint")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setStyleSheet(
            "color: #B8BEC5; background: transparent; font-size: 16px;")
        root.addWidget(self.hint_label)
        root.addSpacing(26)

        self.open_file_button = QPushButton(tr("Dosya Aç"), self)
        self.open_file_button.setObjectName("emptyStateOpenFile")
        self.open_file_button.setFixedSize(124, 42)
        self.open_file_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_file_button.setStyleSheet(
            f"QPushButton {{ color: white; background: {UI_ACCENT}; border: none; "
            "border-radius: 7px; "
            f"font-family: {UI_FONT_FAMILY}; "
            "font-size: 14px; font-weight: 600; } "
            f"QPushButton:hover {{ background: {UI_ACCENT_HOVER}; }} "
            f"QPushButton:pressed {{ background: {UI_ACCENT_PRESSED}; }} "
            "QPushButton:focus { border: 1px solid #FFB092; }")
        self.open_file_button.clicked.connect(
            lambda: self._run_player_action("open_file"))
        root.addWidget(self.open_file_button, 0,
                       Qt.AlignmentFlag.AlignHCenter)
        root.addSpacing(12)

        self.open_folder_button = QPushButton(tr("Klasör Aç"), self)
        self.open_folder_button.setObjectName("emptyStateOpenFolder")
        self.open_folder_button.setFixedSize(124, 40)
        self.open_folder_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_folder_button.setStyleSheet(
            "QPushButton { color: #E7EAED; background: #252B31; "
            "border: 1px solid #414950; border-radius: 7px; "
            f"font-family: {UI_FONT_FAMILY}; "
            "font-size: 14px; font-weight: 600; } "
            "QPushButton:hover { color: white; background: #30373E; "
            "border-color: #59636C; } "
            "QPushButton:pressed { background: #1D2227; } "
            "QPushButton:focus { border-color: #707A84; }")
        self.open_folder_button.clicked.connect(
            lambda: self._run_player_action("open_folder"))
        root.addWidget(self.open_folder_button, 0,
                       Qt.AlignmentFlag.AlignHCenter)

        self.loading_label = QLabel(self)
        self.loading_label.setObjectName("emptyStateLoading")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet(
            "color: #D3D7DB; background: transparent; font-size: 16px;")
        self.loading_label.hide()
        root.addWidget(self.loading_label)
        root.addStretch(3)
        self.hide()

    def _run_player_action(self, name):
        # Yüzey native CHILD'dır; modal dosya seçici doğal olarak üstüne
        # gelir. Burada gizlemek alttaki eski placeholder'ı gösterirdi.
        action = getattr(self.player, name, None)
        if callable(action):
            action()

    def set_placeholder_text(self, text, default_text):
        """Normal başlangıç ve bağlantı-yükleniyor görünümleri arasında geç."""
        loading = bool(text and text != default_text)
        for widget in (self.logo_label, self.title_label, self.hint_label,
                       self.open_file_button, self.open_folder_button):
            widget.setVisible(not loading)
        self.loading_label.setText(text if loading else "")
        self.loading_label.setVisible(loading)

    # Yüzey ayrı bir native pencere olduğu için bırakma olaylarını gerçek
    # ana pencereye açıkça devreder; sürükle-bırak davranışı kopyalanmaz.
    def dragEnterEvent(self, event):
        self.player.dragEnterEvent(event)

    def dragMoveEvent(self, event):
        self.player.dragMoveEvent(event)

    def dropEvent(self, event):
        self.player.dropEvent(event)
