# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Native smoke testleri için gerçek, ayrı Qt top-level süreç.

Bu süreç yalnızca native overlay smoke harness'i tarafından başlatılır. Amacı,
Windows foreground penceresini gerçekten devralmaktır; böylece MLC Player
penceresi sentetik QEvent gönderimiyle değil, normal Windows aktivasyon
değişimiyle deaktive olur.

Not Defteri gibi kullanıcıya ait hiçbir uygulama başlatılmaz. Süreç,
MLC_FOCUS_CHILD_MS süresi dolunca kendini kapatır; ayrıca harness tarafında
try/finally ile PID'i kesin olarak sonlandırılır.
"""
import os
import sys
import ctypes

if os.environ.get("MLC_NATIVE_SMOKE") != "1":
    print("SKIPPED: OPT_IN_REQUIRED", flush=True)
    raise SystemExit(0)

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout

LIFETIME_MS = int(os.environ.get("MLC_FOCUS_CHILD_MS", "2500"))

app = QApplication(sys.argv)

window = QWidget()
window.setWindowTitle("MLC Native Smoke Focus Child")
window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
# Varsayılan konum korunur; kompozisyon smoke'u pencereyi oynatıcının
# playlist/kontrol bölgesinin üzerine getirmek için bunu ezebilir.
GEOMETRY = os.environ.get("MLC_FOCUS_CHILD_GEOMETRY", "60,60,420,260")
try:
    _x, _y, _w, _h = (int(part) for part in GEOMETRY.split(","))
except ValueError:
    _x, _y, _w, _h = 60, 60, 420, 260
window.setGeometry(_x, _y, _w, _h)
layout = QVBoxLayout(window)
layout.addWidget(QLabel("MLC native smoke: gecici odak penceresi"))
window.show()


def force_foreground(hwnd):
    """Test penceresini mevcut foreground thread'ine bağlayarak öne alır."""
    if os.name != "nt":
        window.raise_()
        window.activateWindow()
        return True, hwnd
    user32 = ctypes.windll.user32
    foreground = int(user32.GetForegroundWindow())
    foreground_thread = user32.GetWindowThreadProcessId(foreground, None)
    current_thread = ctypes.windll.kernel32.GetCurrentThreadId()
    attached = False
    try:
        if foreground_thread and foreground_thread != current_thread:
            attached = bool(user32.AttachThreadInput(
                current_thread, foreground_thread, True))
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(current_thread, foreground_thread, False)
    actual = int(user32.GetForegroundWindow())
    return actual == hwnd, actual


def take_foreground(attempt=1):
    window.raise_()
    window.activateWindow()
    hwnd = int(window.winId())
    try:
        matched, foreground = force_foreground(hwnd)
    except Exception:
        matched, foreground = False, 0
    if matched:
        print(f"FOCUS_CHILD_FOREGROUND_CONFIRMED hwnd={hwnd} attempt={attempt}",
              flush=True)
    elif attempt < 10:
        QTimer.singleShot(100, lambda: take_foreground(attempt + 1))
    else:
        print(f"FOCUS_CHILD_FOREGROUND_FAILED hwnd={hwnd} "
              f"foreground={foreground}", flush=True)


QTimer.singleShot(150, take_foreground)
QTimer.singleShot(LIFETIME_MS, window.close)
QTimer.singleShot(LIFETIME_MS + 200, app.quit)

print("FOCUS_CHILD_READY", flush=True)
app.exec()
print("FOCUS_CHILD_EXIT", flush=True)
