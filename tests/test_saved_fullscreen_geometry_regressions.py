# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Tam ekranda kapatılan pencere sonraki açılışta tam ekran başlamamalı.

Qt `saveGeometry()` tam ekran bayrağını da kaydeder ve `restoreGeometry()`
onu geri getirir. Ürünün tam ekran durumu (`is_video_fullscreen`) ise
kalıcı değildir; pencere yerel olarak tam ekran açılır ama ürün bunu
bilmez: başlık/kontroller pencere modunda kalır ve Esc çıkaramaz.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMainWindow

from app.player import restore_saved_window_geometry


def _saved_blob(app, fullscreen, maximized=False):
    window = QMainWindow()
    window.resize(800, 450)
    window.show()
    app.processEvents()
    if maximized:
        window.showMaximized()
    if fullscreen:
        window.showFullScreen()
    app.processEvents()
    blob = window.saveGeometry()
    window.close()
    return blob


def test_fullscreen_state_is_not_restored_but_size_is():
    app = QApplication.instance() or QApplication([])
    window = QMainWindow()
    try:
        assert restore_saved_window_geometry(window, _saved_blob(app, True))
        assert not window.windowState() & Qt.WindowState.WindowFullScreen
        window.show()
        app.processEvents()
        assert not window.isFullScreen()
        assert abs(window.width() - 800) <= 4 and abs(window.height() - 450) <= 4
    finally:
        window.close()


def test_maximized_state_is_still_restored():
    app = QApplication.instance() or QApplication([])
    window = QMainWindow()
    try:
        restore_saved_window_geometry(window, _saved_blob(app, False, True))
        assert window.windowState() & Qt.WindowState.WindowMaximized
    finally:
        window.close()


def test_missing_geometry_is_a_no_op():
    app = QApplication.instance() or QApplication([])
    window = QMainWindow()
    try:
        assert restore_saved_window_geometry(window, None) is False
        assert window.windowState() == Qt.WindowState.WindowNoState
    finally:
        window.close()
        app.processEvents()
