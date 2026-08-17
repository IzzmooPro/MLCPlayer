# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Testin KENDI 'baska uygulama' penceresi (ayri surec).

Notepad veya kullanicinin baska uygulamalari ACILMAZ. Bu pencere yalnizca
z-order/aktivasyon olcumu icin vardir; olcum bitince ana surec bu child'i
kaydedilen KESIN PID uzerinden sonlandirir.

stdout'a tek satir HWND yazar ve beklemeye gecer.
"""
import os
import sys

os.environ.pop("QT_QPA_PLATFORM", None)

from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication, QLabel, QWidget  # noqa: E402

TITLE = "MLC Test Yabanci Pencere"


def main():
    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle(TITLE)
    window.resize(420, 260)
    label = QLabel("MLC test penceresi", window)
    label.move(20, 20)
    window.show()
    window.raise_()
    window.activateWindow()

    def announce():
        print(f"FOREIGN_HWND={int(window.winId())}", flush=True)

    QTimer.singleShot(200, announce)
    # Guvenlik agi: ana surec olduruemezse kendi kendine kapanir.
    QTimer.singleShot(120000, app.quit)
    return app.exec()


raise SystemExit(main())
