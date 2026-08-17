# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Kenar/köşe resize olayı ayrı ÜST SEVİYE overlay penceresinden gelirse.

`FramelessResizeFilter._window_position()` child koordinatını
`watched.mapTo(player, point)` ile çeviriyordu. Bu yalnız aynı pencere
hiyerarşisindeki child'lar için doğrudur. `control_overlay` ise
`Qt.WindowType.Tool | FramelessWindowHint` ile AYRI bir üst seviye penceredir
ve videonun alt kenarına sıfır boşlukla, tüm genişlikte oturur. Böyle bir
widget için `mapTo()` ana pencere koordinatı değil GLOBAL ekran koordinatı
üretir; pencere (0, 0)'da değilse hit-test ana pencerenin global konumu kadar
kayar.

Sonuç iki yönlüdür:
  * Sol kenar ve sol-alt köşe overlay üzerindeyken hiç algılanmaz.
  * Overlay'in iç bölgesi (pencere altından 100 px yukarısı) yanlışlıkla
    alt kenar sanılır ve sürükleme resize başlatır.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget

from app.title_bar import FramelessResizeFilter

WINDOW_SIZE = (800, 600)
WINDOW_ORIGIN = (300, 200)
OVERLAY_HEIGHT = 110


class _TitleBarStub:
    """Yalnız filtrenin kullandığı iki davranışı taşır."""

    def __init__(self):
        self.state_updates = 0

    def can_resize_window(self):
        return True

    def update_maximize_state(self):
        self.state_updates += 1


@pytest.fixture
def overlay_window():
    app = QApplication.instance() or QApplication([])
    window = QMainWindow()
    window.resize(*WINDOW_SIZE)
    window.move(*WINDOW_ORIGIN)
    central = QWidget(window)
    window.setCentralWidget(central)
    window.central_widget = central
    window.show()
    app.processEvents()

    # Ürünle aynı kurulum: overlay ana pencerenin child'ı ama AYRI bir
    # üst seviye Tool penceresi ve videonun alt kenarına oturuyor.
    overlay = QWidget(window,
                      Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
    origin = window.mapToGlobal(QPoint(0, 0))
    overlay.setGeometry(origin.x(),
                        origin.y() + window.height() - OVERLAY_HEIGHT,
                        window.width(), OVERLAY_HEIGHT)
    overlay.show()
    app.processEvents()

    video_frame = QWidget(central)
    video_frame.control_overlay = overlay
    video_frame.playlist_panel = None
    window.video_frame = video_frame

    title_bar = _TitleBarStub()
    filt = FramelessResizeFilter(window, title_bar)
    filt.install()

    # NOT: Eskiden burada `_start_system_resize` `True` dönecek şekilde
    # değiştiriliyordu; bu, "metot çağrıldı" ölçüyor ve GERÇEK ürün yolunu
    # atlıyordu (kullanıcı gerçek uygulamada boyutlandıramadı). Ayrı
    # top-level overlay'de ürün native yolu bilerek atlar ve sınırlı manuel
    # yedeği başlatır; ölçüm artık BAŞLATILAN KENARLAR üzerinden yapılır.
    started = []
    real_begin = filt._begin_manual_resize

    def spy(watched, edges, event):
        started.append(edges)
        return real_begin(watched, edges, event)

    filt._begin_manual_resize = spy

    yield app, window, overlay, filt, started

    filt.remove()
    overlay.close()
    window.close()
    app.processEvents()


def _press(overlay, local_point):
    global_point = overlay.mapToGlobal(local_point)
    return QMouseEvent(QEvent.Type.MouseButtonPress,
                       QPointF(local_point),
                       QPointF(global_point),
                       Qt.MouseButton.LeftButton,
                       Qt.MouseButton.LeftButton,
                       Qt.KeyboardModifier.NoModifier)


# --- Koordinat çevirisi ---

def test_overlay_point_maps_into_main_window_coordinates(overlay_window):
    app, window, overlay, filt, _started = overlay_window
    local = QPoint(400, OVERLAY_HEIGHT - 5)

    mapped = filt._window_position(overlay, _press(overlay, local))

    assert mapped == QPoint(400, window.height() - 5), (
        f"overlay noktası ana pencere koordinatına çevrilmedi: {mapped}")


# --- Gerçek kenar ve köşeler overlay üzerinden çalışmalı ---

@pytest.mark.parametrize("local_x, expected", (
    (2, Qt.Edge.LeftEdge | Qt.Edge.BottomEdge),
    (400, Qt.Edge.BottomEdge),
    (WINDOW_SIZE[0] - 3, Qt.Edge.RightEdge | Qt.Edge.BottomEdge),
))
def test_bottom_edge_and_corners_start_resize_over_overlay(
        overlay_window, local_x, expected):
    app, window, overlay, filt, started = overlay_window
    event = _press(overlay, QPoint(local_x, OVERLAY_HEIGHT - 2))

    handled = filt.eventFilter(overlay, event)

    assert handled is True, "overlay üzerindeki kenar basışı resize başlatmadı"
    assert started == [expected], f"başlatılan kenarlar: {started}"


def test_left_edge_over_overlay_starts_horizontal_resize(overlay_window):
    app, window, overlay, filt, started = overlay_window
    # Overlay'in üst yarısı: pencere altından uzak, ama sol kenarda.
    event = _press(overlay, QPoint(3, 10))

    handled = filt.eventFilter(overlay, event)

    assert handled is True
    assert started == [Qt.Edge.LeftEdge], f"başlatılan kenarlar: {started}"


# --- Overlay'in iç bölgesi resize başlatmamalı ---

def test_overlay_interior_press_does_not_start_resize(overlay_window):
    app, window, overlay, filt, started = overlay_window
    # Pencerenin altından ~105 px yukarıda, yanlardan uzak: kenar DEĞİL.
    event = _press(overlay, QPoint(400, 5))

    handled = filt.eventFilter(overlay, event)

    assert handled is False, "overlay ortası yanlışlıkla resize başlattı"
    assert started == [], f"beklenmeyen resize: {started}"
