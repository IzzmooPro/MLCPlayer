# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Kısa ürün bildirimleri için onaylanmış minimal bilgi penceresi."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget)

from app.i18n import tr


INFO_DIALOG_SIZE = (300, 150)


class ModernInfoDialog(QDialog):
    def __init__(self, parent, title, message):
        flags = Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint
        super().__init__(parent, flags)
        self._drag_offset = None
        self.setObjectName("modernInfoDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setFixedSize(*INFO_DIALOG_SIZE)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        card = QWidget(self)
        card.setObjectName("modernInfoCard")
        card.setStyleSheet(
            "QWidget#modernInfoCard { background: #171D23; "
            "border: 1px solid #35404A; border-radius: 10px; }")
        outer.addWidget(card)

        row = QHBoxLayout(card)
        row.setContentsMargins(7, 8, 8, 8)
        row.setSpacing(10)
        accent = QWidget(card)
        accent.setObjectName("modernInfoAccent")
        accent.setFixedWidth(4)
        accent.setStyleSheet("background: #FF5A1F; border-radius: 2px;")
        row.addWidget(accent)

        icon = QLabel("ⓘ", card)
        icon.setObjectName("modernInfoIcon")
        icon.setFixedWidth(42)
        icon.setAlignment(Qt.AlignmentFlag.AlignTop |
                          Qt.AlignmentFlag.AlignHCenter)
        icon.setStyleSheet(
            "color: #FF5A1F; background: transparent; border: none; "
            "font-size: 29px;")
        row.addWidget(icon)

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        header = QHBoxLayout()
        self.title_label = QLabel(title, card)
        self.title_label.setObjectName("modernInfoTitle")
        self.title_label.setStyleSheet(
            "color: #F4F4F4; background: transparent; border: none; "
            "font-size: 14px; font-weight: 600;")
        header.addWidget(self.title_label)
        header.addStretch()
        close_button = QPushButton("×", card)
        close_button.setObjectName("modernInfoClose")
        close_button.setAccessibleName(tr("Kapat"))
        close_button.setFixedSize(22, 22)
        close_button.setStyleSheet(
            "QPushButton { color: #AEB5BB; background: transparent; "
            "border: none; font-size: 20px; } "
            "QPushButton:hover { color: white; }")
        close_button.clicked.connect(self.reject)
        header.addWidget(close_button)
        body.addLayout(header)

        self.message_label = QLabel(message, card)
        self.message_label.setObjectName("modernInfoMessage")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignVCenter |
                                        Qt.AlignmentFlag.AlignLeft)
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet(
            "color: #D3D7DB; background: transparent; border: none; "
            "font-size: 14px;")
        body.addWidget(self.message_label, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        ok_button = QPushButton(tr("Tamam"), card)
        ok_button.setObjectName("modernInfoOk")
        ok_button.setFixedSize(76, 28)
        ok_button.setDefault(True)
        ok_button.setStyleSheet(
            "QPushButton { color: #F4F4F4; background: #1B2229; "
            "border: 1px solid #505B65; border-radius: 6px; "
            "font-size: 12px; font-weight: 600; } "
            "QPushButton:hover { border-color: #FF5A1F; }")
        ok_button.clicked.connect(self.accept)
        buttons.addWidget(ok_button)
        body.addLayout(buttons)
        row.addLayout(body, 1)

    def showEvent(self, event):
        parent = self.parentWidget()
        if parent is not None:
            self.move(parent.frameGeometry().center() - self.rect().center())
        super().showEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (event.globalPosition().toPoint()
                                 - self.frameGeometry().topLeft())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (self._drag_offset is not None
                and event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)


def show_information(parent, title, message):
    """Bilgi penceresini gösterirken native kontrol yüzeyini bastır."""
    frame = getattr(parent, "video_frame", None)
    suppress = getattr(frame, "set_overlay_suppressed", None)
    already_suppressed = bool(
        getattr(frame, "overlay_suppressed", lambda: False)())
    if callable(suppress) and not already_suppressed:
        suppress(True)
    try:
        return ModernInfoDialog(parent, title, message).exec()
    finally:
        if callable(suppress) and not already_suppressed:
            suppress(False)
