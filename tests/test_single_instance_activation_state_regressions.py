# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""İkinci başlatma simge durumundaki pencereyi ÖNCEKİ durumuyla getirmeli.

`showNormal()` büyütülmüş/tam ekran bayrağını da siler: büyütülüp simge
durumuna küçültülen oynatıcı, Explorer'dan yeni dosya açılınca normal
boyutta dönüyordu; tam ekranda ise ürün hâlâ tam ekran sanıyordu.
"""

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMainWindow

from app.single_instance import activate_window


@pytest.mark.parametrize("show, flag", [
    ("showMaximized", Qt.WindowState.WindowMaximized),
    ("showFullScreen", Qt.WindowState.WindowFullScreen),
])
def test_minimized_window_returns_to_its_previous_state(show, flag):
    app = QApplication.instance() or QApplication([])
    window = QMainWindow()
    opened = []
    window.open_external_target = opened.append
    try:
        window.resize(800, 450)
        window.show()
        getattr(window, show)()
        app.processEvents()
        window.setWindowState(
            window.windowState() | Qt.WindowState.WindowMinimized)
        app.processEvents()

        activate_window(window, "C:/video.mkv")
        app.processEvents()

        assert not window.isMinimized()
        assert window.windowState() & flag
        assert opened == ["C:/video.mkv"]
    finally:
        window.close()
        app.processEvents()
