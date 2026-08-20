# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Ana HWND'yi yeniden yaratmadan şeffaflık ve kompakt PiP yönetimi."""
import ctypes
import sys
from ctypes import wintypes

from PyQt6.QtCore import QRect, QSize

MIN_OPACITY_PERCENT = 35
PIP_SIZE = QSize(480, 270)
PIP_MIN_SIZE = QSize(320, 180)
PIP_SCREEN_MARGIN = 24


def keep_rect_inside(rect, available):
    """PiP dikdortgenini erisilebilir ekran alaninin icinde tutar."""
    rect = QRect(rect)
    available = QRect(available)
    if available.isEmpty():
        return rect
    width = min(rect.width(), available.width())
    height = min(rect.height(), available.height())
    x = max(available.left(), min(rect.x(), available.right() - width + 1))
    y = max(available.top(), min(rect.y(), available.bottom() - height + 1))
    return QRect(x, y, width, height)


def set_native_topmost(window, enabled):
    """Windows z-order'ını pencere bayraklarını değiştirmeden günceller.

    Runtime'da Qt.WindowStaysOnTopHint değiştirmek HWND'yi yeniden yaratabilir;
    libmpv mevcut ``wid`` içine çizdiği için bu ürün açısından güvenli değildir.
    """
    if sys.platform != "win32":
        return False
    try:
        hwnd = int(window.winId())
        insert_after = -1 if enabled else -2  # HWND_TOPMOST / HWND_NOTOPMOST
        flags = 0x0001 | 0x0002 | 0x0010  # NOSIZE | NOMOVE | NOACTIVATE
        result = ctypes.windll.user32.SetWindowPos(
            wintypes.HWND(hwnd), wintypes.HWND(insert_after),
            0, 0, 0, 0, flags)
        return bool(result)
    except (AttributeError, OSError, TypeError, ValueError):
        return False


def pip_geometry_for(window):
    screen = window.screen()
    available = screen.availableGeometry() if screen is not None else QRect()
    width = min(PIP_SIZE.width(), max(window.minimumWidth(), available.width()))
    height = min(PIP_SIZE.height(), max(window.minimumHeight(), available.height()))
    x = available.right() - width - PIP_SCREEN_MARGIN + 1
    y = available.bottom() - height - PIP_SCREEN_MARGIN + 1
    return QRect(max(available.left(), x), max(available.top(), y), width, height)


def keep_pip_window_on_screen(window):
    """Yeniden boyutlandirilan PiP'nin cikis kontrolunu ekranda tutar."""
    screen = window.screen()
    if screen is None:
        return False
    current = window.geometry()
    bounded = keep_rect_inside(current, screen.availableGeometry())
    if bounded == current:
        return False
    window.setGeometry(bounded)
    return True
