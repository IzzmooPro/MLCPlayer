# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Alt köşelerden GERÇEK yeniden boyutlandırma (ürün davranışı).

ÖNCEKİ TURUN AÇIĞI: koordinat dönüşümü düzeltildi ama ürün davranışı
kanıtlanmadı. O turun testi `_start_system_resize`i `lambda: True` ile
değiştirdiği için "metot çağrıldı" ölçüyordu; gerçek başarısızlık yolu hiç
çalışmadı ve kullanıcı gerçek uygulamada alt köşelerden boyutlandıramadı.

ÖLÇÜLEN KÖK NEDEN: `control_overlay` AYRI bir top-level `Qt.Tool`
penceresidir (`overlay.window() is not player`) ve video alanının alt
110 px'ini kaplar. Basış o pencereye teslim edilir; ürün ise ANA pencerenin
`QWindow.startSystemResize()` metodunu çağırır. Windows'un native resize
döngüsü başka bir pencerenin girdi akışından devralamaz: çağrı `False`
döner (veya döngü hiç yürümez) ve üründe HİÇBİR yedek yol yoktur —
`eventFilter` `False` dönüp olayı bırakır, pencere hiç boyutlanmaz.

Bu dosya "metot çağrıldı" ölçmez: ana pencerenin GERÇEK geometrisinin
değiştiğini doğrular.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt6.QtGui import QCursor, QEnterEvent, QMouseEvent
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, QSlider,
                             QVBoxLayout, QWidget)

from app import title_bar as title_bar_module
from app.title_bar import FramelessResizeFilter

ORIGIN = (300, 200)
SIZE = (1200, 720)
OVERLAY_HEIGHT = 110
MIN_SIZE = (640, 360)


class _TitleBarStub:
    def __init__(self, can_resize=True):
        self.can_resize = can_resize
        self.state_updates = 0

    def can_resize_window(self):
        return self.can_resize

    def update_maximize_state(self):
        self.state_updates += 1


@pytest.fixture
def scene():
    app = QApplication.instance() or QApplication([])
    made = []

    def factory(can_resize=True, native_ok=False):
        window = QMainWindow()
        window.resize(*SIZE)
        window.move(*ORIGIN)
        window.setMinimumSize(*MIN_SIZE)
        central = QWidget(window)
        window.setCentralWidget(central)
        window.central_widget = central
        window.show()
        app.processEvents()

        # Ürünle AYNI kurulum: ayrı top-level Tool penceresi, videonun alt
        # kenarına oturuyor ve içinde GERÇEK child'lar var.
        overlay = QWidget(window, Qt.WindowType.Tool
                          | Qt.WindowType.FramelessWindowHint)
        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(0, 0, 0, 0)
        corner_child = QWidget(overlay)
        corner_child.setObjectName("overlayCornerChild")
        layout.addWidget(corner_child)
        # Üründeki oynat/ses düğmeleri gibi KENDİ imleci olan bir child.
        hand_child = QWidget(overlay)
        hand_child.setObjectName("overlayHandChild")
        hand_child.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(hand_child)
        overlay.hand_child = hand_child
        start = window.mapToGlobal(QPoint(0, 0))
        overlay.setGeometry(start.x(),
                            start.y() + window.height() - OVERLAY_HEIGHT,
                            window.width(), OVERLAY_HEIGHT)
        overlay.show()
        app.processEvents()

        video_frame = QWidget(central)
        video_frame.control_overlay = overlay
        video_frame.playlist_panel = None
        window.video_frame = video_frame

        title_bar = _TitleBarStub(can_resize)
        filt = FramelessResizeFilter(window, title_bar)
        filt.install()
        native_calls = []

        def native(edges):
            native_calls.append(edges)
            return bool(native_ok)

        filt._start_system_resize = native
        made.append((window, overlay, filt))
        return window, overlay, corner_child, filt, native_calls

    yield factory

    for window, overlay, filt in made:
        filt.remove()
        overlay.close()
        window.close()
    # Hiçbir test artan override cursor bırakmamalı.
    while QApplication.overrideCursor() is not None:
        QApplication.restoreOverrideCursor()
    app.processEvents()


def mouse(kind, widget, local, buttons=Qt.MouseButton.LeftButton):
    point = QPointF(local)
    glob = QPointF(widget.mapToGlobal(local))
    button = (Qt.MouseButton.LeftButton
              if kind != QEvent.Type.MouseMove else Qt.MouseButton.NoButton)
    return QMouseEvent(kind, point, glob, button, buttons,
                       Qt.KeyboardModifier.NoModifier)


def move_to(widget, local_start, delta):
    """Sürükleme: aynı widget üzerinde global konumu delta kadar kaydır."""
    return QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(local_start.x() + delta[0], local_start.y() + delta[1]),
        QPointF(widget.mapToGlobal(local_start).x() + delta[0],
                widget.mapToGlobal(local_start).y() + delta[1]),
        Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier)


def drag(filt, target, local, delta, release=True):
    filt.eventFilter(target, mouse(QEvent.Type.MouseButtonPress, target, local))
    filt.eventFilter(target, move_to(target, local, delta))
    if release:
        filt.eventFilter(target, mouse(QEvent.Type.MouseButtonRelease,
                                       target, local))


def rect_of(window):
    geometry = window.geometry()
    return (geometry.left(), geometry.top(), geometry.right(),
            geometry.bottom())


# --- Filtre gerçekten overlay ağacını görüyor mu ------------------------

def test_the_overlay_children_are_watched_exactly_once(scene):
    _window, overlay, corner_child, filt, _native = scene()

    assert overlay in filt.targets
    assert corner_child in filt.targets, "overlay child'ı filtre görmüyor"
    assert filt.targets.count(corner_child) == 1
    filt.install()                       # idempotent olmalı
    assert filt.targets.count(corner_child) == 1
    assert filt.targets.count(overlay) == 1


# --- GERÇEK geometri: alt köşeler ---------------------------------------

def test_the_bottom_left_corner_really_resizes_the_window(scene):
    window, _overlay, corner_child, filt, native = scene(native_ok=False)
    before = rect_of(window)

    drag(filt, corner_child, QPoint(3, OVERLAY_HEIGHT - 3), (-70, 70))

    left, top, right, bottom = rect_of(window)
    assert left == before[0] - 70, f"sol kenar taşınmadı: {before} -> {left}"
    assert bottom == before[3] + 70, "alt kenar taşınmadı"
    assert top == before[1] and right == before[2], "sabit kenarlar oynadı"
    # Ayrı top-level overlay'den gelen basışta native yol BİLEREK denenmez:
    # Windows'un resize döngüsü başka pencerenin girdi akışını devralamaz.
    assert native == [], "ayrı top-level'da native yol denendi"


def test_the_bottom_right_corner_really_resizes_the_window(scene):
    window, _overlay, corner_child, filt, _native = scene(native_ok=False)
    before = rect_of(window)
    local = QPoint(window.width() - 3, OVERLAY_HEIGHT - 3)

    drag(filt, corner_child, local, (70, 70))

    left, top, right, bottom = rect_of(window)
    assert right == before[2] + 70
    assert bottom == before[3] + 70
    assert left == before[0] and top == before[1]


@pytest.mark.parametrize("local_x, delta, moved", (
    (3, (-60, 0), "left"),
    (SIZE[0] - 3, (60, 0), "right"),
))
def test_the_side_edges_work_inside_the_overlay_area(scene, local_x, delta,
                                                     moved):
    window, _overlay, corner_child, filt, _native = scene(native_ok=False)
    before = rect_of(window)

    drag(filt, corner_child, QPoint(local_x, OVERLAY_HEIGHT // 2), delta)

    left, top, right, bottom = rect_of(window)
    assert top == before[1] and bottom == before[3], "dikey kenarlar oynadı"
    if moved == "left":
        assert left == before[0] - 60 and right == before[2]
    else:
        assert right == before[2] + 60 and left == before[0]


def test_overlay_button_keeps_click_ownership_inside_the_resize_band(scene):
    """Dar/PiP katmanında düğmenin kenar pikseli resize'a dönüşmemeli."""
    window, overlay, _corner_child, filt, native = scene(native_ok=False)
    button = QPushButton("action", overlay)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setGeometry(overlay.width() - 40, overlay.height() - 40, 40, 40)
    button.show()
    filt.install()
    clicked = []
    button.clicked.connect(lambda: clicked.append(True))
    before = rect_of(window)

    local = QPoint(button.width() - 2, button.height() - 2)
    QApplication.sendEvent(
        button, mouse(QEvent.Type.MouseButtonPress, button, local))
    QApplication.sendEvent(
        button, mouse(QEvent.Type.MouseButtonRelease, button, local,
                      buttons=Qt.MouseButton.NoButton))

    assert clicked == [True]
    assert rect_of(window) == before
    assert native == []
    assert not filt.manual_resize_active()
    assert button.cursor().shape() == Qt.CursorShape.PointingHandCursor


def test_overlay_slider_keeps_drag_ownership_inside_the_resize_band(scene):
    window, overlay, _corner_child, filt, native = scene(native_ok=False)
    slider = QSlider(Qt.Orientation.Horizontal, overlay)
    slider.setCursor(Qt.CursorShape.PointingHandCursor)
    slider.setGeometry(0, overlay.height() - 20, 160, 20)
    slider.show()
    filt.install()
    before = rect_of(window)
    local = QPoint(2, slider.height() - 2)

    handled = filt.eventFilter(
        slider, mouse(QEvent.Type.MouseButtonPress, slider, local))

    assert handled is False
    assert rect_of(window) == before
    assert native == []
    assert not filt.manual_resize_active()
    assert slider.cursor().shape() == Qt.CursorShape.PointingHandCursor


# --- Durum temizliği -----------------------------------------------------

def test_after_the_release_a_plain_move_changes_nothing(scene):
    window, _overlay, corner_child, filt, _native = scene(native_ok=False)
    drag(filt, corner_child, QPoint(3, OVERLAY_HEIGHT - 3), (-70, 70))
    after_drag = rect_of(window)

    filt.eventFilter(corner_child,
                     move_to(corner_child, QPoint(3, OVERLAY_HEIGHT - 3),
                             (-200, 200)))

    assert rect_of(window) == after_drag, "release sonrası sürükleme sürüyor"


def test_removing_the_filter_clears_a_pending_drag(scene):
    window, _overlay, corner_child, filt, _native = scene(native_ok=False)
    filt.eventFilter(corner_child,
                     mouse(QEvent.Type.MouseButtonPress, corner_child,
                           QPoint(3, OVERLAY_HEIGHT - 3)))

    filt.remove()

    assert not filt.manual_resize_active()


# --- Sınırlar -------------------------------------------------------------

def test_the_minimum_size_is_never_crossed(scene):
    window, _overlay, corner_child, filt, _native = scene(native_ok=False)

    drag(filt, corner_child, QPoint(window.width() - 3, OVERLAY_HEIGHT - 3),
         (-5000, -5000))

    assert window.width() >= MIN_SIZE[0]
    assert window.height() >= MIN_SIZE[1]


def test_a_blocked_window_state_never_starts_a_resize(scene):
    window, _overlay, corner_child, filt, native = scene(can_resize=False,
                                                         native_ok=False)
    before = rect_of(window)

    drag(filt, corner_child, QPoint(3, OVERLAY_HEIGHT - 3), (-70, 70))

    assert rect_of(window) == before
    assert native == [], "maksimize/tam ekranda native yol denendi"


# --- Native yol ile yedek yolun AYRIMI ------------------------------------

def test_a_successful_native_resize_never_runs_the_manual_path(scene):
    """ANA pencerenin kendi yüzeyinde native yol korunur ve tek çalışır."""
    window, _overlay, _corner_child, filt, native = scene(native_ok=True)
    target = window.central_widget
    before = rect_of(window)

    drag(filt, target, QPoint(3, window.height() - 3), (-70, 70))

    assert len(native) == 1, f"native yol {len(native)} kez çağrıldı"
    assert rect_of(window) == before, (
        "native başarılıyken manuel yol da çalıştı (çift boyutlandırma)")
    assert not filt.manual_resize_active()


# --- İMLEÇ: ayrı top-level yüzeyde GERÇEK hedefe uygulanmalı -------------
#
# ÖLÇÜLEN KUSUR: `MouseMove` yolunda imleç yalnız `player.setCursor()` ile
# yazılıyordu. Alt 110 px'te imlecin üzerindeki gerçek hedef AYRI top-level
# `control_overlay` veya onun child'ıdır; ana pencereye yazmak o yüzeydeki
# imleci değiştirmez. Bazı child'ların kendi `PointingHandCursor` değeri
# ayrıca bunu eziyordu: alt kenar ve köşelerde yanlış/kararsız ok.

def at_window(widget, window, wx, wy):
    """PENCERE koordinatındaki noktanın hedef widget'taki karşılığı.

    Child yerleşimi VARSAYILMAZ; nokta her zaman gerçek pencere kenarına
    göre hesaplanır.
    """
    return widget.mapFromGlobal(window.mapToGlobal(QPoint(wx, wy)))


def hover(filt, widget, local):
    return filt.eventFilter(
        widget,
        QMouseEvent(QEvent.Type.MouseMove, QPointF(local),
                    QPointF(widget.mapToGlobal(local)),
                    Qt.MouseButton.NoButton, Qt.MouseButton.NoButton,
                    Qt.KeyboardModifier.NoModifier))


def shape_of(widget):
    return widget.cursor().shape()


@pytest.mark.parametrize("window_point, expected, label", (
    ((3, SIZE[1] - 3), Qt.CursorShape.SizeBDiagCursor, "sol-alt köşe"),
    ((600, SIZE[1] - 3), Qt.CursorShape.SizeVerCursor, "alt orta"),
    ((SIZE[0] - 3, SIZE[1] - 3), Qt.CursorShape.SizeFDiagCursor, "sağ-alt köşe"),
    ((3, SIZE[1] - 60), Qt.CursorShape.SizeHorCursor, "sol kenar alt bölüm"),
    ((SIZE[0] - 3, SIZE[1] - 60), Qt.CursorShape.SizeHorCursor,
     "sağ kenar alt bölüm"),
))
def test_the_resize_cursor_lands_on_the_real_target(scene, window_point,
                                                    expected, label):
    window, _overlay, corner_child, filt, _native = scene()

    hover(filt, corner_child, at_window(corner_child, window, *window_point))

    assert shape_of(corner_child) == expected, (
        f"{label}: imleç gerçek hedefe uygulanmadı")


def test_leaving_the_edge_band_restores_the_original_cursor(scene):
    window, _overlay, corner_child, filt, _native = scene()
    before = shape_of(corner_child)
    hover(filt, corner_child, at_window(corner_child, window, 3, SIZE[1] - 3))
    assert shape_of(corner_child) == Qt.CursorShape.SizeBDiagCursor

    hover(filt, corner_child,
          at_window(corner_child, window, 600, SIZE[1] - 60))

    assert shape_of(corner_child) == before


def test_moving_between_overlay_children_never_leaves_one_stuck(scene):
    window, overlay, corner_child, filt, _native = scene()
    hand_child = overlay.hand_child
    hover(filt, corner_child, at_window(corner_child, window, 3, SIZE[1] - 3))
    assert shape_of(corner_child) == Qt.CursorShape.SizeBDiagCursor

    hover(filt, hand_child,
          at_window(hand_child, window, SIZE[0] - 3, SIZE[1] - 3))

    assert shape_of(corner_child) == Qt.CursorShape.ArrowCursor, (
        "eski child resize imleciyle takılı kaldı")
    assert shape_of(hand_child) == Qt.CursorShape.SizeFDiagCursor


def test_a_hand_cursor_child_gets_its_own_cursor_back(scene):
    """(8) Oynat/ses düğmesi: el → kenar bandında resize → yeniden el."""
    window, overlay, _corner_child, filt, _native = scene()
    hand_child = overlay.hand_child
    assert shape_of(hand_child) == Qt.CursorShape.PointingHandCursor

    hover(filt, hand_child, at_window(hand_child, window, 3, SIZE[1] - 60))
    in_band = shape_of(hand_child)

    hover(filt, hand_child, at_window(hand_child, window, 600, SIZE[1] - 60))

    assert in_band == Qt.CursorShape.SizeHorCursor, "kenar bandında el imleci kaldı"
    assert shape_of(hand_child) == Qt.CursorShape.PointingHandCursor, (
        "düğmenin özgün imleci geri gelmedi")


@pytest.mark.parametrize("event_type", (QEvent.Type.Leave,
                                        QEvent.Type.WindowDeactivate,
                                        QEvent.Type.Hide))
def test_leave_deactivate_and_hide_clear_the_temporary_cursor(scene,
                                                              event_type):
    window, overlay, _corner_child, filt, _native = scene()
    hand_child = overlay.hand_child
    hover(filt, hand_child, at_window(hand_child, window, 3, SIZE[1] - 60))
    assert shape_of(hand_child) == Qt.CursorShape.SizeHorCursor

    filt.eventFilter(hand_child, QEvent(event_type))

    assert shape_of(hand_child) == Qt.CursorShape.PointingHandCursor


def test_removing_the_filter_restores_the_cursor(scene):
    window, overlay, _corner_child, filt, _native = scene()
    hand_child = overlay.hand_child
    hover(filt, hand_child, at_window(hand_child, window, 3, SIZE[1] - 60))

    filt.remove()

    assert shape_of(hand_child) == Qt.CursorShape.PointingHandCursor


def test_the_cursor_stays_stable_during_a_manual_drag(scene):
    """(10) Sürükleme boyunca çapraz imleç child hover'ıyla ezilmemeli."""
    window, _overlay, corner_child, filt, _native = scene(native_ok=False)
    local = at_window(corner_child, window, 3, SIZE[1] - 3)

    filt.eventFilter(corner_child,
                     mouse(QEvent.Type.MouseButtonPress, corner_child, local))
    filt.eventFilter(corner_child, move_to(corner_child, local, (-40, 40)))

    assert shape_of(corner_child) == Qt.CursorShape.SizeBDiagCursor
    filt.eventFilter(corner_child,
                     mouse(QEvent.Type.MouseButtonRelease, corner_child, local))
    assert shape_of(corner_child) == Qt.CursorShape.ArrowCursor


def test_the_same_cursor_is_never_written_twice(scene, monkeypatch):
    window, _overlay, corner_child, filt, _native = scene()
    writes = []
    original = corner_child.setCursor
    monkeypatch.setattr(corner_child, "setCursor",
                        lambda shape: (writes.append(shape), original(shape)))

    point = at_window(corner_child, window, 3, SIZE[1] - 3)
    for _ in range(10):
        hover(filt, corner_child, point)

    assert len(writes) == 1, f"aynı imleç {len(writes)} kez yazıldı"


# --- BASIŞSIZ hover: köşeye gelir gelmez ok görünmeli --------------------
#
# MANUEL KABUL: sürükleme çalışıyor ama resize oku YALNIZ `MouseButtonPress`
# sonrasında görünüyordu. Kullanıcı tıklamadan önce resize alanında olduğunu
# anlayamıyordu: basış öncesi `Enter`/`HoverMove` teslimi hiç işlenmiyordu.


def enter_event(widget, local):
    """Gerçek `QEnterEvent`: fare dışarıdan doğrudan bu noktaya girdi."""
    point = QPointF(local)
    glob = QPointF(widget.mapToGlobal(local))
    return QEnterEvent(point, point, glob)


class HoverStub:
    """Yalnız ürünün okuduğu sözleşme: `type()` + `globalPosition()`."""

    def __init__(self, widget, local):
        self._global = QPointF(widget.mapToGlobal(local))

    @staticmethod
    def type():
        return QEvent.Type.HoverMove

    def globalPosition(self):
        return self._global


@pytest.mark.parametrize("window_point, expected, label", (
    ((3, SIZE[1] - 3), Qt.CursorShape.SizeBDiagCursor, "sol-alt köşe"),
    ((SIZE[0] - 3, SIZE[1] - 3), Qt.CursorShape.SizeFDiagCursor, "sağ-alt köşe"),
    ((600, SIZE[1] - 3), Qt.CursorShape.SizeVerCursor, "alt orta"),
))
def test_a_plain_enter_shows_the_resize_cursor_without_any_click(
        scene, window_point, expected, label):
    window, _overlay, corner_child, filt, _native = scene()
    local = at_window(corner_child, window, *window_point)

    handled = filt.eventFilter(corner_child, enter_event(corner_child, local))

    assert override_shape() == expected, f"{label}: tıklamadan önce ok yok"
    assert handled is False, "Enter olayı yutuldu"


def test_a_hover_move_uses_the_same_decision(scene):
    window, _overlay, corner_child, filt, _native = scene()
    local = at_window(corner_child, window, SIZE[0] - 3, SIZE[1] - 3)

    handled = filt.eventFilter(corner_child, HoverStub(corner_child, local))

    assert override_shape() == Qt.CursorShape.SizeFDiagCursor
    assert handled is False


def test_an_enter_falls_back_to_the_real_cursor_position(scene, monkeypatch):
    """QEnterEvent alanları eksik olursa gerçek imleç konumu kullanılır."""
    window, _overlay, corner_child, filt, _native = scene()
    target = window.mapToGlobal(QPoint(3, SIZE[1] - 3))

    # NOT: `QCursor`dan TÜRETİLİR; ürün aynı adı `QCursor(shape)` yapımı
    # için de kullanıyor ve düz bir sahte sınıf onu bozardı.
    class FakeCursor(QCursor):
        @staticmethod
        def pos():
            return target

    monkeypatch.setattr(title_bar_module, "QCursor", FakeCursor)

    class BareEnter:
        @staticmethod
        def type():
            return QEvent.Type.Enter

    filt.eventFilter(corner_child, BareEnter())

    assert override_shape() == Qt.CursorShape.SizeBDiagCursor


def test_an_enter_outside_the_band_opens_no_override(scene):
    window, _overlay, corner_child, filt, _native = scene()
    local = at_window(corner_child, window, 600, SIZE[1] - 60)

    filt.eventFilter(corner_child, enter_event(corner_child, local))

    assert override_shape() is None


def test_a_leave_after_a_plain_enter_clears_everything(scene):
    window, _overlay, corner_child, filt, _native = scene()
    local = at_window(corner_child, window, 3, SIZE[1] - 3)
    filt.eventFilter(corner_child, enter_event(corner_child, local))
    assert override_shape() is not None

    filt.eventFilter(corner_child, QEvent(QEvent.Type.Leave))

    assert override_shape() is None
    assert not filt.manual_resize_active()


def test_an_enter_and_move_sequence_never_grows_the_stack(scene):
    window, _overlay, corner_child, filt, _native = scene()
    local = at_window(corner_child, window, 3, SIZE[1] - 3)

    for _ in range(25):
        filt.eventFilter(corner_child, enter_event(corner_child, local))
        hover(filt, corner_child, local)

    assert override_shape() == Qt.CursorShape.SizeBDiagCursor
    QApplication.restoreOverrideCursor()
    assert QApplication.overrideCursor() is None, "yığın büyümüş"


def test_an_enter_never_touches_a_foreign_override(scene):
    window, _overlay, corner_child, filt, _native = scene()
    QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
    try:
        filt.eventFilter(
            corner_child,
            enter_event(corner_child,
                        at_window(corner_child, window, 3, SIZE[1] - 3)))

        assert override_shape() == Qt.CursorShape.WaitCursor
    finally:
        QApplication.restoreOverrideCursor()


def test_an_enter_during_a_drag_keeps_the_drag_cursor(scene):
    """(7) Basış yolu ve manuel resize davranışı değişmez."""
    window, _overlay, corner_child, filt, _native = scene(native_ok=False)
    local = at_window(corner_child, window, 3, SIZE[1] - 3)
    filt.eventFilter(corner_child,
                     mouse(QEvent.Type.MouseButtonPress, corner_child, local))
    filt.eventFilter(corner_child, move_to(corner_child, local, (-40, 40)))

    filt.eventFilter(
        corner_child,
        enter_event(corner_child,
                    at_window(corner_child, window, 600, SIZE[1] - 60)))

    assert override_shape() == Qt.CursorShape.SizeBDiagCursor
    assert filt.manual_resize_active()


# --- GÖRÜNÜR imleç: QApplication override -------------------------------
#
# MANUEL KABUL: pencere alt kenar/köşelerden gerçekten boyutlanıyor ama
# imleç normal ok / el işareti olarak kalıyordu. Ayrı top-level
# `control_overlay` üzerinde widget cursor'u ekranda görünmüyor; kullanıcı
# resize alanında olduğunu anlayamıyor. Görünür karar `QApplication`
# override cursor ile verilir ve YALNIZ bu filtreye ait olduğunda yönetilir.

def override_shape():
    cursor = QApplication.overrideCursor()
    return None if cursor is None else cursor.shape()


@pytest.mark.parametrize("window_point, expected, label", (
    ((600, SIZE[1] - 3), Qt.CursorShape.SizeVerCursor, "alt kenar"),
    ((3, SIZE[1] - 3), Qt.CursorShape.SizeBDiagCursor, "sol-alt köşe"),
    ((SIZE[0] - 3, SIZE[1] - 3), Qt.CursorShape.SizeFDiagCursor, "sağ-alt köşe"),
    ((3, SIZE[1] - 60), Qt.CursorShape.SizeHorCursor, "sol kenar alt bölüm"),
))
def test_the_override_cursor_shows_the_resize_shape(scene, window_point,
                                                    expected, label):
    window, _overlay, corner_child, filt, _native = scene()

    hover(filt, corner_child, at_window(corner_child, window, *window_point))

    assert override_shape() == expected, f"{label}: görünür imleç yok"


def test_a_press_applies_the_visible_cursor_without_a_previous_move(scene):
    """(Basış) Yalnız önceki MouseMove olayına güvenilmez."""
    window, _overlay, corner_child, filt, _native = scene(native_ok=False)
    local = at_window(corner_child, window, 3, SIZE[1] - 3)

    filt.eventFilter(corner_child,
                     mouse(QEvent.Type.MouseButtonPress, corner_child, local))

    assert override_shape() == Qt.CursorShape.SizeBDiagCursor


def test_the_override_survives_the_whole_manual_drag(scene):
    window, _overlay, corner_child, filt, _native = scene(native_ok=False)
    local = at_window(corner_child, window, 3, SIZE[1] - 3)

    filt.eventFilter(corner_child,
                     mouse(QEvent.Type.MouseButtonPress, corner_child, local))
    filt.eventFilter(corner_child, move_to(corner_child, local, (-40, 40)))

    assert override_shape() == Qt.CursorShape.SizeBDiagCursor


@pytest.mark.parametrize("closer", ("leave_band", "release", "deactivate",
                                    "hide", "remove"))
def test_every_cleanup_path_drops_the_override(scene, closer):
    window, _overlay, corner_child, filt, _native = scene(native_ok=False)
    local = at_window(corner_child, window, 3, SIZE[1] - 3)
    filt.eventFilter(corner_child,
                     mouse(QEvent.Type.MouseButtonPress, corner_child, local))
    assert override_shape() is not None

    if closer == "leave_band":
        filt.eventFilter(corner_child,
                         mouse(QEvent.Type.MouseButtonRelease, corner_child,
                               local))
        hover(filt, corner_child,
              at_window(corner_child, window, 600, SIZE[1] - 60))
    elif closer == "release":
        filt.eventFilter(corner_child,
                         mouse(QEvent.Type.MouseButtonRelease, corner_child,
                               local))
    elif closer == "deactivate":
        filt.eventFilter(corner_child, QEvent(QEvent.Type.WindowDeactivate))
    elif closer == "hide":
        filt.eventFilter(corner_child, QEvent(QEvent.Type.Hide))
    else:
        filt.remove()

    assert override_shape() is None, f"{closer}: override bırakılmadı"


def test_repeated_hovers_never_grow_the_override_stack(scene):
    """(5) Tek `restoreOverrideCursor()` yığını boşaltmalı."""
    window, _overlay, corner_child, filt, _native = scene()
    point = at_window(corner_child, window, 3, SIZE[1] - 3)

    for _ in range(50):
        hover(filt, corner_child, point)

    assert override_shape() == Qt.CursorShape.SizeBDiagCursor
    QApplication.restoreOverrideCursor()
    assert QApplication.overrideCursor() is None, "yığın büyümüş"


def test_switching_shapes_changes_instead_of_stacking(scene):
    """(6) Şekil değişince yeni katman AÇILMAZ."""
    window, _overlay, corner_child, filt, _native = scene()

    hover(filt, corner_child, at_window(corner_child, window, 3, SIZE[1] - 3))
    hover(filt, corner_child, at_window(corner_child, window, 600, SIZE[1] - 3))
    hover(filt, corner_child,
          at_window(corner_child, window, SIZE[0] - 3, SIZE[1] - 3))

    assert override_shape() == Qt.CursorShape.SizeFDiagCursor
    QApplication.restoreOverrideCursor()
    assert QApplication.overrideCursor() is None, "her şekil yeni katman açtı"


def test_a_foreign_override_cursor_is_never_touched(scene):
    """(7) Başka bileşenin override'ı sahiplenilmez ve bozulmaz."""
    window, _overlay, corner_child, filt, _native = scene()
    QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
    try:
        hover(filt, corner_child,
              at_window(corner_child, window, 3, SIZE[1] - 3))
        assert override_shape() == Qt.CursorShape.WaitCursor, (
            "yabancı override ezildi")

        filt.remove()

        assert override_shape() == Qt.CursorShape.WaitCursor, (
            "yabancı override restore edilerek bozuldu")
    finally:
        QApplication.restoreOverrideCursor()


def test_after_the_release_the_button_keeps_its_hand_cursor(scene):
    """(8) Düğmenin özgün imleci ve temiz override birlikte."""
    window, overlay, _corner_child, filt, _native = scene(native_ok=False)
    hand_child = overlay.hand_child
    local = at_window(hand_child, window, 3, SIZE[1] - 60)

    filt.eventFilter(hand_child,
                     mouse(QEvent.Type.MouseButtonPress, hand_child, local))
    filt.eventFilter(hand_child,
                     mouse(QEvent.Type.MouseButtonRelease, hand_child, local))

    assert override_shape() is None
    assert shape_of(hand_child) == Qt.CursorShape.PointingHandCursor


# --- FAIL-CLOSED: yakalama, tuş durumu ve iptal yolları -----------------

def test_a_failed_mouse_grab_never_starts_a_drag(scene, monkeypatch):
    """Yakalama alınamadıysa sürükleme BAŞLAMAZ (fail-closed)."""
    window, _overlay, corner_child, filt, _native = scene(native_ok=False)
    before = rect_of(window)

    def angry_grab():
        raise RuntimeError("fare yakalanamadı")

    monkeypatch.setattr(corner_child, "grabMouse", angry_grab)

    handled = filt.eventFilter(
        corner_child, mouse(QEvent.Type.MouseButtonPress, corner_child,
                            QPoint(3, OVERLAY_HEIGHT - 3)))

    assert handled is False, "yakalama yokken olay yutuldu"
    assert not filt.manual_resize_active()
    filt.eventFilter(corner_child,
                     move_to(corner_child, QPoint(3, OVERLAY_HEIGHT - 3),
                             (-70, 70)))
    assert rect_of(window) == before


def test_a_silent_grab_failure_is_detected(scene, monkeypatch):
    """`grabMouse()` sessizce başarısızsa da durum başlatılmaz."""
    window, _overlay, corner_child, filt, _native = scene(native_ok=False)
    monkeypatch.setattr(corner_child, "grabMouse", lambda: None)

    handled = filt.eventFilter(
        corner_child, mouse(QEvent.Type.MouseButtonPress, corner_child,
                            QPoint(3, OVERLAY_HEIGHT - 3)))

    assert handled is False
    assert not filt.manual_resize_active()


def test_a_move_without_the_left_button_ends_the_drag(scene):
    """(2) Release olayı kaybolsa bile boş sürükleme sürmez."""
    window, _overlay, corner_child, filt, _native = scene(native_ok=False)
    filt.eventFilter(corner_child,
                     mouse(QEvent.Type.MouseButtonPress, corner_child,
                           QPoint(3, OVERLAY_HEIGHT - 3)))
    assert filt.manual_resize_active()
    before = rect_of(window)

    handled = filt.eventFilter(
        corner_child,
        QMouseEvent(QEvent.Type.MouseMove, QPointF(3.0, 40.0),
                    QPointF(1.0, 1.0), Qt.MouseButton.NoButton,
                    Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier))

    assert not filt.manual_resize_active(), "tuş bırakılmış ama sürükleme sürüyor"
    assert rect_of(window) == before
    assert handled is False, "normal hareket gereksiz yere yutuldu"


def test_an_unreadable_global_position_clears_everything(scene, monkeypatch):
    """(3) Okuma hatasında durum ve yakalama KESİN bırakılır."""
    window, _overlay, corner_child, filt, _native = scene(native_ok=False)
    filt.eventFilter(corner_child,
                     mouse(QEvent.Type.MouseButtonPress, corner_child,
                           QPoint(3, OVERLAY_HEIGHT - 3)))
    assert QWidget.mouseGrabber() is corner_child

    class Broken:
        @staticmethod
        def type():
            return QEvent.Type.MouseMove

        @staticmethod
        def buttons():
            return Qt.MouseButton.LeftButton

        @staticmethod
        def globalPosition():
            raise RuntimeError("konum okunamadı")

    filt.eventFilter(corner_child, Broken)

    assert not filt.manual_resize_active()
    assert QWidget.mouseGrabber() is None, "fare yakalaması takılı kaldı"


@pytest.mark.parametrize("event_type", (QEvent.Type.WindowDeactivate,
                                        QEvent.Type.Hide))
def test_deactivation_and_hide_cancel_a_pending_drag(scene, event_type):
    """(4) Odak kaybı / gizlenme aktif sürüklemeyi güvenle iptal eder."""
    window, _overlay, corner_child, filt, _native = scene(native_ok=False)
    filt.eventFilter(corner_child,
                     mouse(QEvent.Type.MouseButtonPress, corner_child,
                           QPoint(3, OVERLAY_HEIGHT - 3)))
    before = rect_of(window)

    filt.eventFilter(corner_child, QEvent(event_type))

    assert not filt.manual_resize_active()
    assert QWidget.mouseGrabber() is None
    filt.eventFilter(corner_child,
                     move_to(corner_child, QPoint(3, OVERLAY_HEIGHT - 3),
                             (-70, 70)))
    assert rect_of(window) == before


def test_a_blocked_window_state_cancels_a_pending_drag(scene):
    """Sürükleme sırasında pencere maksimize edilirse durum bırakılır."""
    window, _overlay, corner_child, filt, _native = scene(native_ok=False)
    filt.eventFilter(corner_child,
                     mouse(QEvent.Type.MouseButtonPress, corner_child,
                           QPoint(3, OVERLAY_HEIGHT - 3)))
    before = rect_of(window)
    filt.title_bar.can_resize = False

    filt.eventFilter(corner_child,
                     move_to(corner_child, QPoint(3, OVERLAY_HEIGHT - 3),
                             (-70, 70)))

    assert not filt.manual_resize_active()
    assert rect_of(window) == before


def test_a_release_without_a_drag_is_not_swallowed(scene):
    """(5) Normal release olayı gereksiz yere yutulmamalı."""
    _window, _overlay, corner_child, filt, _native = scene(native_ok=False)

    handled = filt.eventFilter(
        corner_child, mouse(QEvent.Type.MouseButtonRelease, corner_child,
                            QPoint(400, 40)))

    assert handled is False


def test_the_cleanup_is_idempotent(scene):
    """(7) release / remove / deactivate arka arkaya çağrılabilir."""
    _window, _overlay, corner_child, filt, _native = scene(native_ok=False)
    filt.eventFilter(corner_child,
                     mouse(QEvent.Type.MouseButtonPress, corner_child,
                           QPoint(3, OVERLAY_HEIGHT - 3)))

    assert filt.eventFilter(corner_child,
                            mouse(QEvent.Type.MouseButtonRelease,
                                  corner_child,
                                  QPoint(3, OVERLAY_HEIGHT - 3))) is True
    filt.eventFilter(corner_child, QEvent(QEvent.Type.WindowDeactivate))
    filt.remove()

    assert not filt.manual_resize_active()
    assert QWidget.mouseGrabber() is None


def test_the_filter_documents_the_native_and_fallback_paths():
    text = FramelessResizeFilter.__doc__ or ""

    assert "startSystemResize" in text
    assert "manuel" in text.lower()


def test_a_press_outside_the_edge_band_is_left_alone(scene):
    window, _overlay, corner_child, filt, native = scene(native_ok=False)
    before = rect_of(window)

    handled = filt.eventFilter(
        corner_child, mouse(QEvent.Type.MouseButtonPress, corner_child,
                            QPoint(400, 40)))

    assert handled is False
    assert native == []
    assert rect_of(window) == before
