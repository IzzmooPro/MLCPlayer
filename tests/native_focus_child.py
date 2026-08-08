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
window.setGeometry(60, 60, 420, 260)
layout = QVBoxLayout(window)
layout.addWidget(QLabel("MLC native smoke: gecici odak penceresi"))
window.show()


def take_foreground():
    window.raise_()
    window.activateWindow()
    print("FOCUS_CHILD_FOREGROUND", flush=True)


QTimer.singleShot(150, take_foreground)
QTimer.singleShot(LIFETIME_MS, window.close)
QTimer.singleShot(LIFETIME_MS + 200, app.quit)

print("FOCUS_CHILD_READY", flush=True)
app.exec()
print("FOCUS_CHILD_EXIT", flush=True)
