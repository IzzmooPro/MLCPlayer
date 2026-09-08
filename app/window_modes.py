# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Ana HWND'yi yeniden yaratmadan şeffaflık ve kompakt PiP yönetimi."""
import ctypes
import sys
from ctypes import wintypes

from PyQt6.QtCore import QRect, QSize
from PyQt6.QtWidgets import QApplication

MIN_OPACITY_PERCENT = 35
PIP_SIZE = QSize(480, 270)
PIP_MIN_SIZE = QSize(320, 180)
PIP_SCREEN_MARGIN = 24

if sys.platform == "win32":
    _user32 = ctypes.windll.user32
    _user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    _user32.MonitorFromWindow.restype = wintypes.HMONITOR
    _user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR,
                                        ctypes.c_void_p]
    _user32.GetMonitorInfoW.restype = wintypes.BOOL
    _user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.ShowWindow.restype = wintypes.BOOL
    _user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND,
                                     ctypes.c_int, ctypes.c_int,
                                     ctypes.c_int, ctypes.c_int,
                                     wintypes.UINT]
    _user32.SetWindowPos.restype = wintypes.BOOL
else:  # pragma: no cover - ürün yalnızca Windows'ta çalışır
    _user32 = None


class _NativeRect(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


class _MonitorInfo(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", _NativeRect),
                ("rcWork", _NativeRect), ("dwFlags", wintypes.DWORD)]


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
        result = _user32.SetWindowPos(
            wintypes.HWND(hwnd), wintypes.HWND(insert_after),
            0, 0, 0, 0, flags)
        return bool(result)
    except (AttributeError, OSError, TypeError, ValueError,
            ctypes.ArgumentError):
        return False


def _native_window_geometry_supported():
    app = QApplication.instance()
    return (sys.platform == "win32" and _user32 is not None
            and app is not None and app.platformName() == "windows")


def set_native_window_geometry(window, target):
    """Qt restore gecikirse ayni ana HWND'yi Win32 ile hedefe getirir."""
    if not _native_window_geometry_supported():
        return None
    try:
        hwnd = int(window.winId())
        monitor = _user32.MonitorFromWindow(
            wintypes.HWND(hwnd), 2)  # MONITOR_DEFAULTTONEAREST
        if not monitor:
            return False
        info = _MonitorInfo()
        info.cbSize = ctypes.sizeof(_MonitorInfo)
        if not _user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return False
        screen = window.screen()
        available = screen.availableGeometry() if screen is not None else QRect()
        target = QRect(target)
        if available.isEmpty() or target.isEmpty():
            return False
        native_width = info.rcWork.right - info.rcWork.left
        native_height = info.rcWork.bottom - info.rcWork.top
        scale_x = native_width / available.width()
        scale_y = native_height / available.height()
        x = info.rcWork.left + round((target.x() - available.x()) * scale_x)
        y = info.rcWork.top + round((target.y() - available.y()) * scale_y)
        width = round(target.width() * scale_x)
        height = round(target.height() * scale_y)
        # Qt normal-state bildirimini native show state izlemeyebilir.
        # SW_SHOWNOACTIVATE, SW_SHOWNORMAL gibi restore eder fakat odak almaz.
        _user32.ShowWindow(wintypes.HWND(hwnd), 4)
        flags = 0x0004 | 0x0010 | 0x0200
        # NOZORDER | NOACTIVATE | NOOWNERZORDER; ayni HWND korunur.
        return bool(_user32.SetWindowPos(
            wintypes.HWND(hwnd), wintypes.HWND(0),
            x, y, width, height, flags))
    except (AttributeError, OSError, TypeError, ValueError,
            ctypes.ArgumentError):
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
