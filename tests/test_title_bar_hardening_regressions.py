# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Başlık çubuğu teknik sağlamlaştırma testleri.

1) Gerçek kenar resize olayının doğru widget'tan gelip startSystemResize
   çağırması, 2) overflow menüsünün birikmemesi.
"""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QEvent, QPoint, QRect, QSize, Qt
from PyQt6.QtGui import QKeyEvent, QMouseEvent
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QMenu, QPushButton, QVBoxLayout, QWidget)

from app.title_bar import (RESIZE_MARGIN, FramelessResizeFilter, TitleBar)
import app.player as player_module
from app.player import (ESCAPE_GEOMETRY_RETRY_LIMIT,
                        ESCAPE_GEOMETRY_STABLE_POLLS,
                        ESCAPE_STATE_RETRY_LIMIT, ESCAPE_STATE_RETRY_MS,
                        MPVPlayer)


@pytest.fixture
def frameless_window():
    created = []
    app_ref = []

    def qt_app():
        app = QApplication.instance() or QApplication([])
        if not app_ref:
            app_ref.append(app)
        return app

    def factory(size=(900, 600)):
        app = qt_app()
        window = QMainWindow()
        window.calls = []
        window.central_widget = QWidget(window)
        window.setCentralWidget(window.central_widget)
        window.main_layout = QVBoxLayout(window.central_widget)
        window.main_layout.setContentsMargins(
            RESIZE_MARGIN, RESIZE_MARGIN, RESIZE_MARGIN, RESIZE_MARGIN)
        for name in ("open_file", "show_playlist"):
            setattr(window, name, lambda name=name: window.calls.append(name))
        window.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        for label in ("Ortam", "Oynatma", "Ses", "Görüntü", "Alt Yazı",
                      "Araçlar", "Gezinim", "Görünüm", "Yardım"):
            window.menuBar().addMenu(label)
        window.menuBar().hide()
        bar = TitleBar(window)
        window.title_bar = bar
        window.main_layout.addWidget(bar)
        window.main_layout.addWidget(QWidget(window))
        window.resize(*size)
        window.show()
        app.processEvents()

        resize_filter = FramelessResizeFilter(window, bar)
        resize_filter.install()
        window.resize_filter = resize_filter
        created.append(window)
        return app, window, bar, resize_filter

    yield factory

    app = qt_app()
    for window in created:
        window.close()
        window.deleteLater()
    app.processEvents()


def spy_on_resize(resize_filter):
    started = []
    resize_filter._start_system_resize = (
        lambda edges: started.append(edges) or True)
    return started


def test_main_title_edge_uses_widget_cursor_without_global_override(
        frameless_window):
    """Başlık resize oku ikonların cursor'ını uygulama genelinde ezmemeli."""
    app, window, bar, resize_filter = frameless_window()

    resize_filter._apply_resize_cursor(bar, Qt.Edge.TopEdge)

    assert bar.cursor().shape() == Qt.CursorShape.SizeVerCursor
    assert QApplication.overrideCursor() is None
    assert (bar.playlist_button.cursor().shape()
            == Qt.CursorShape.PointingHandCursor)


def test_snapped_playlist_owns_middle_boundary_but_keeps_corner_resize(
        frameless_window):
    """Ortak orta sınır playlist'e ait, köşeler ana pencereye aittir."""
    app, window, bar, resize_filter = frameless_window()
    owner_rect = window.frameGeometry()
    panel = QWidget(window, Qt.WindowType.Window
                    | Qt.WindowType.FramelessWindowHint)
    panel._target_open = True
    panel._placement = SimpleNamespace(snapped=True)
    panel.setGeometry(owner_rect.right() + 1, owner_rect.top(),
                      420, owner_rect.height())
    panel.show()
    app.processEvents()
    window.video_frame = SimpleNamespace(playlist_panel=panel)

    middle_right = QPoint(window.width() - 1, window.height() // 2)
    top_right = QPoint(window.width() - 1, 0)

    assert resize_filter._effective_resize_edges(middle_right) == Qt.Edge(0)
    assert resize_filter._effective_resize_edges(top_right) == (
        Qt.Edge.RightEdge | Qt.Edge.TopEdge)

    panel.setGeometry(owner_rect.left() - panel.width(), owner_rect.top(),
                      panel.width(), owner_rect.height())
    app.processEvents()
    middle_left = QPoint(0, window.height() // 2)
    assert resize_filter._effective_resize_edges(middle_left) == Qt.Edge(0)

    panel._target_open = False
    assert (resize_filter._effective_resize_edges(middle_left)
            == Qt.Edge.LeftEdge)


def press_on(widget, local_point):
    point = QPoint(*local_point)
    return QMouseEvent(QEvent.Type.MouseButtonPress, point.toPointF(),
                       widget.mapToGlobal(point).toPointF(),
                       Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                       Qt.KeyboardModifier.NoModifier)


# --- 1. Gerçek kenar olayı ---

@pytest.mark.parametrize("corner,expected", [
    ("left", Qt.Edge.LeftEdge),
    ("right", Qt.Edge.RightEdge),
    ("top", Qt.Edge.TopEdge),
    ("bottom", Qt.Edge.BottomEdge),
    ("top_left", Qt.Edge.LeftEdge | Qt.Edge.TopEdge),
    ("top_right", Qt.Edge.RightEdge | Qt.Edge.TopEdge),
    ("bottom_left", Qt.Edge.LeftEdge | Qt.Edge.BottomEdge),
    ("bottom_right", Qt.Edge.RightEdge | Qt.Edge.BottomEdge),
])
def test_real_edge_press_on_central_widget_starts_system_resize(
        frameless_window, corner, expected):
    app, window, bar, resize_filter = frameless_window()
    started = spy_on_resize(resize_filter)
    central = window.central_widget

    # central_widget, ana pencere içinde RESIZE_MARGIN kadar içeridedir;
    # bu yüzden kenar noktaları negatif/aşan yerel koordinatlara denk gelir.
    offset = central.mapTo(window, QPoint(0, 0))
    points = {
        "left": (-offset.x(), central.height() // 2),
        "right": (window.width() - offset.x() - 1, central.height() // 2),
        "top": (central.width() // 2, -offset.y()),
        "bottom": (central.width() // 2, window.height() - offset.y() - 1),
        "top_left": (-offset.x(), -offset.y()),
        "top_right": (window.width() - offset.x() - 1, -offset.y()),
        "bottom_left": (-offset.x(), window.height() - offset.y() - 1),
        "bottom_right": (window.width() - offset.x() - 1,
                         window.height() - offset.y() - 1),
    }
    app.sendEvent(central, press_on(central, points[corner]))
    app.processEvents()

    assert started == [expected], f"{corner}: {started}"


def test_press_inside_content_area_does_not_start_resize(frameless_window):
    app, window, bar, resize_filter = frameless_window()
    started = spy_on_resize(resize_filter)
    central = window.central_widget

    app.sendEvent(central, press_on(central,
                                    (central.width() // 2, central.height() // 2)))
    app.processEvents()

    assert started == []


def test_edge_center_corner_resolves_to_diagonal_resize(frameless_window):
    app, window, bar, resize_filter = frameless_window()
    started = spy_on_resize(resize_filter)
    point = QPoint(window.width() - 2, window.height() - 2)

    app.sendEvent(window, press_on(window, (point.x(), point.y())))
    app.processEvents()

    assert started == [Qt.Edge.RightEdge | Qt.Edge.BottomEdge]


def test_escape_exits_fullscreen_then_restores_balanced_default_size(
        frameless_window):
    app, window, bar, resize_filter = frameless_window(size=(1250, 780))
    calls = []
    window.video_frame = type("Frame", (), {
        "is_video_fullscreen": True,
        "exit_fullscreen": lambda self: (
            calls.append("exit"), setattr(self, "is_video_fullscreen", False)),
    })()
    window.restore_default_window_size = lambda: (
        MPVPlayer.restore_default_window_size(window))
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape,
                      Qt.KeyboardModifier.NoModifier)

    MPVPlayer.keyPressEvent(window, event)
    assert calls == ["exit"]
    assert window.size() == QSize(1250, 780)

    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape,
                      Qt.KeyboardModifier.NoModifier)
    MPVPlayer.keyPressEvent(window, event)
    app.processEvents()

    available = window.screen().availableGeometry()
    assert window.size() == QSize(min(960, available.width() - 40),
                                  min(600, available.height() - 40))
    assert event.isAccepted()


def test_default_size_is_reapplied_after_maximized_state_transition(
        frameless_window, monkeypatch):
    app, window, bar, resize_filter = frameless_window(size=(1250, 780))
    callbacks = []
    window.showMaximized()
    app.processEvents()
    monkeypatch.setattr("app.player.QTimer.singleShot",
                        lambda delay, callback: callbacks.append(
                            (delay, callback)))

    MPVPlayer.restore_default_window_size(window)
    available = window.screen().availableGeometry()
    width = min(960, max(window.minimumWidth(), available.width() - 40))
    height = min(600, max(window.minimumHeight(), available.height() - 40))
    expected = (available.x() + (available.width() - width) // 2,
                available.y() + (available.height() - height) // 2,
                width, height)

    assert callbacks and callbacks[0][0] == 0
    # Windows'un gecikmiş showNormal restore mesajı ilk hedefi eski büyütülmüş
    # geometriye getirebilir; callback tam olarak bu durumu düzeltmelidir.
    window.setGeometry(0, 0, available.width(), available.height())
    calls = []
    window.setGeometry = lambda *values: calls.append(values)
    callbacks[0][1]()
    assert calls == [expected]


def test_stale_default_size_callback_cannot_override_newer_geometry(
        frameless_window, monkeypatch):
    app, window, bar, resize_filter = frameless_window(size=(1250, 780))
    callbacks = []
    window.showMaximized()
    app.processEvents()
    monkeypatch.setattr("app.player.QTimer.singleShot",
                        lambda delay, callback: callbacks.append(callback))

    MPVPlayer.restore_default_window_size(window)
    old_callback = callbacks[0]
    MPVPlayer.restore_default_window_size(window)
    calls = []
    window.setGeometry = lambda *values: calls.append(values)

    old_callback()
    assert calls == []


def test_default_size_callback_waits_for_windows_to_leave_maximized_state(
        frameless_window, monkeypatch):
    app, window, bar, resize_filter = frameless_window(size=(1250, 780))
    callbacks = []
    window.showMaximized()
    app.processEvents()
    monkeypatch.setattr("app.player.QTimer.singleShot",
                        lambda delay, callback: callbacks.append(
                            (delay, callback)))
    MPVPlayer.restore_default_window_size(window)
    calls = []
    window.setGeometry = lambda *values: calls.append(values)
    window.isMaximized = lambda: True

    callbacks[0][1]()
    assert calls == []
    assert len(callbacks) == 2
    assert callbacks[1][0] > 0

    window.isMaximized = lambda: False
    callbacks[1][1]()
    assert len(calls) == 1


def test_default_size_callback_rechecks_geometry_after_normal_transition(
        frameless_window, monkeypatch):
    app, window, bar, resize_filter = frameless_window(size=(1250, 780))
    callbacks = []
    window.showMaximized()
    app.processEvents()
    monkeypatch.setattr("app.player.QTimer.singleShot",
                        lambda delay, callback: callbacks.append(
                            (delay, callback)))
    MPVPlayer.restore_default_window_size(window)
    window.isMaximized = lambda: False
    window.isMinimized = lambda: False
    target = QRect(window.geometry())
    old_restore = QRect(0, 0, window.screen().availableGeometry().width(),
                        window.screen().availableGeometry().height())
    geometries = [target, old_restore]
    window.geometry = lambda: geometries.pop(0) if geometries else target
    calls = []
    window.setGeometry = lambda *values: calls.append(values)

    callbacks[0][1]()
    assert len(calls) == 1
    assert len(callbacks) == 2
    assert callbacks[1][0] == ESCAPE_STATE_RETRY_MS

    # Windows, normal-state bildiriminin ardından eski restore geometrisini
    # yeniden yazarsa sonraki doğrulama bunu tekrar hedefe getirmelidir.
    callbacks[1][1]()
    assert len(calls) == 2
    assert "_pending_escape_geometry" in window.__dict__

    index = 2
    while index < len(callbacks) and index < 200:
        callbacks[index][1]()
        index += 1
    assert len(callbacks) == ESCAPE_GEOMETRY_STABLE_POLLS + 2
    assert "_pending_escape_geometry" not in window.__dict__


def test_default_size_callback_applies_target_to_native_window(
        frameless_window, monkeypatch):
    app, window, bar, resize_filter = frameless_window(size=(1250, 780))
    callbacks = []
    overlay_calls = []
    window.video_frame = SimpleNamespace(
        is_video_fullscreen=False,
        update_overlay_geometry=lambda: overlay_calls.append(True))
    window.showMaximized()
    app.processEvents()
    monkeypatch.setattr("app.player.QTimer.singleShot",
                        lambda delay, callback: callbacks.append(callback))
    native_calls = []
    monkeypatch.setattr(player_module, "set_native_window_geometry",
                        lambda owner, target: native_calls.append(
                            (owner, target)) or True,
                        raising=False)

    MPVPlayer.restore_default_window_size(window)
    window.isMaximized = lambda: False
    window.isMinimized = lambda: False
    callbacks[0]()

    assert len(native_calls) == 1
    assert native_calls[0][0] is window
    assert native_calls[0][1] == window.geometry()
    assert overlay_calls == [True]


def test_native_geometry_failure_cannot_count_as_stable(
        frameless_window, monkeypatch):
    app, window, bar, resize_filter = frameless_window(size=(1250, 780))
    callbacks = []
    window.showMaximized()
    app.processEvents()
    monkeypatch.setattr("app.player.QTimer.singleShot",
                        lambda delay, callback: callbacks.append(callback))
    monkeypatch.setattr(player_module, "set_native_window_geometry",
                        lambda _owner, _target: False)
    MPVPlayer.restore_default_window_size(window)
    window.isMaximized = lambda: False
    window.isMinimized = lambda: False

    for index in range(ESCAPE_GEOMETRY_STABLE_POLLS):
        callbacks[index]()

    assert len(callbacks) == ESCAPE_GEOMETRY_STABLE_POLLS + 1
    assert "_pending_escape_geometry" in window.__dict__


def test_default_size_callback_stops_after_stable_geometry_checks(
        frameless_window, monkeypatch):
    app, window, bar, resize_filter = frameless_window(size=(1250, 780))
    callbacks = []
    window.showMaximized()
    app.processEvents()
    monkeypatch.setattr("app.player.QTimer.singleShot",
                        lambda delay, callback: callbacks.append(
                            (delay, callback)))
    MPVPlayer.restore_default_window_size(window)
    window.isMaximized = lambda: False
    window.isMinimized = lambda: False
    calls = []
    window.setGeometry = lambda *values: calls.append(values)

    index = 0
    while index < len(callbacks) and index < 200:
        callbacks[index][1]()
        index += 1

    assert len(callbacks) == ESCAPE_GEOMETRY_STABLE_POLLS
    assert len(calls) == ESCAPE_GEOMETRY_STABLE_POLLS
    assert all(delay == ESCAPE_STATE_RETRY_MS
               for delay, _callback in callbacks[1:])
    assert "_pending_escape_geometry" not in window.__dict__


def test_default_size_callback_survives_restore_after_first_200_ms(
        frameless_window, monkeypatch):
    app, window, bar, resize_filter = frameless_window(size=(1250, 780))
    callbacks = []
    window.showMaximized()
    app.processEvents()
    monkeypatch.setattr("app.player.QTimer.singleShot",
                        lambda delay, callback: callbacks.append(
                            (delay, callback)))
    MPVPlayer.restore_default_window_size(window)
    window.isMaximized = lambda: False
    window.isMinimized = lambda: False
    target = QRect(window.geometry())
    available = window.screen().availableGeometry()
    old_restore = QRect(0, 0, available.width(), available.height())
    geometries = ([target] * 8 + [old_restore]
                  + [target] * ESCAPE_GEOMETRY_STABLE_POLLS)
    window.geometry = lambda: geometries.pop(0)
    calls = []
    window.setGeometry = lambda *values: calls.append(values)

    for index in range(8):
        callbacks[index][1]()

    # Native ölçümde 200 ms'lik ilk stabil pencere yetersiz kaldı. Daha geç
    # restore yazısını görecek en az bir callback hâlâ bekliyor olmalıdır.
    assert len(callbacks) >= 9
    assert "_pending_escape_geometry" in window.__dict__
    callbacks[8][1]()
    assert calls[-1] == (target.x(), target.y(), target.width(),
                         target.height())
    assert "_pending_escape_geometry" in window.__dict__


def test_late_normal_state_retains_full_geometry_stability_budget(
        frameless_window, monkeypatch):
    app, window, bar, resize_filter = frameless_window(size=(1250, 780))
    callbacks = []
    window.showMaximized()
    app.processEvents()
    monkeypatch.setattr("app.player.QTimer.singleShot",
                        lambda delay, callback: callbacks.append(
                            (delay, callback)))
    MPVPlayer.restore_default_window_size(window)
    state = {"maximized": True}
    window.isMaximized = lambda: state["maximized"]
    window.isMinimized = lambda: False
    normal_calls = []
    window.showNormal = lambda: normal_calls.append(True)
    calls = []
    window.setGeometry = lambda *values: calls.append(values)

    for index in range(ESCAPE_STATE_RETRY_LIMIT - 1):
        callbacks[index][1]()
    state["maximized"] = False

    index = ESCAPE_STATE_RETRY_LIMIT - 1
    while index < len(callbacks) and index < 300:
        callbacks[index][1]()
        index += 1

    assert len(normal_calls) == ESCAPE_STATE_RETRY_LIMIT - 1
    assert len(calls) == ESCAPE_GEOMETRY_STABLE_POLLS
    assert "_pending_escape_geometry" not in window.__dict__


def test_state_oscillation_cannot_reset_geometry_retry_budget(
        frameless_window, monkeypatch):
    app, window, bar, resize_filter = frameless_window(size=(1250, 780))
    callbacks = []
    window.showMaximized()
    app.processEvents()
    monkeypatch.setattr("app.player.QTimer.singleShot",
                        lambda delay, callback: callbacks.append(
                            (delay, callback)))
    MPVPlayer.restore_default_window_size(window)
    state = {"maximized": False}
    window.isMaximized = lambda: state["maximized"]
    window.isMinimized = lambda: False
    available = window.screen().availableGeometry()
    old_restore = QRect(0, 0, available.width(), available.height())
    window.geometry = lambda: old_restore
    window.setGeometry = lambda *_values: None
    window.showNormal = lambda: None

    index = 0
    for _ in range(ESCAPE_GEOMETRY_RETRY_LIMIT - 1):
        callbacks[index][1]()
        index += 1
    state["maximized"] = True
    for _ in range(ESCAPE_STATE_RETRY_LIMIT - 1):
        callbacks[index][1]()
        index += 1
    state["maximized"] = False
    callbacks[index][1]()
    index += 1

    assert len(callbacks) == index
    assert index <= (ESCAPE_STATE_RETRY_LIMIT
                     + ESCAPE_GEOMETRY_RETRY_LIMIT)
    assert "_pending_escape_geometry" not in window.__dict__


def test_default_size_callback_has_a_bounded_maximized_wait(
        frameless_window, monkeypatch):
    app, window, bar, resize_filter = frameless_window(size=(1250, 780))
    callbacks = []
    window.showMaximized()
    app.processEvents()
    monkeypatch.setattr("app.player.QTimer.singleShot",
                        lambda delay, callback: callbacks.append(
                            (delay, callback)))
    MPVPlayer.restore_default_window_size(window)
    window.isMaximized = lambda: True
    normal_calls = []
    window.showNormal = lambda: normal_calls.append(True)
    calls = []
    window.setGeometry = lambda *values: calls.append(values)

    index = 0
    while index < len(callbacks) and index < 200:
        callbacks[index][1]()
        index += 1

    assert callbacks[0][0] == 0
    assert len(callbacks) == ESCAPE_STATE_RETRY_LIMIT + 1
    assert all(delay == ESCAPE_STATE_RETRY_MS
               for delay, _callback in callbacks[1:])
    assert len(normal_calls) == ESCAPE_STATE_RETRY_LIMIT
    assert calls == []
    assert "_pending_escape_geometry" not in window.__dict__


@pytest.mark.parametrize("unsafe_state", ["fullscreen", "pip", "closing"])
def test_default_size_callback_stops_before_a_new_window_mode(
        frameless_window, monkeypatch, unsafe_state):
    app, window, bar, resize_filter = frameless_window(size=(1250, 780))
    callbacks = []
    window.showMaximized()
    app.processEvents()
    monkeypatch.setattr("app.player.QTimer.singleShot",
                        lambda delay, callback: callbacks.append(callback))
    MPVPlayer.restore_default_window_size(window)
    if unsafe_state == "fullscreen":
        window.isFullScreen = lambda: True
    elif unsafe_state == "pip":
        window.picture_in_picture_enabled = True
    else:
        window._mlc_close_done = True
    calls = []
    window.setGeometry = lambda *values: calls.append(values)

    callbacks[0]()
    assert calls == []


def test_default_size_callback_tolerates_deleted_qt_window(
        frameless_window, monkeypatch):
    app, window, bar, resize_filter = frameless_window(size=(1250, 780))
    callbacks = []
    window.showMaximized()
    app.processEvents()
    monkeypatch.setattr("app.player.QTimer.singleShot",
                        lambda delay, callback: callbacks.append(callback))
    MPVPlayer.restore_default_window_size(window)
    window.isFullScreen = lambda: (_ for _ in ()).throw(
        RuntimeError("wrapped C/C++ object has been deleted"))

    callbacks[0]()


def test_resize_filter_includes_native_overlay_and_playlist_edge_surfaces(
        frameless_window):
    app, window, bar, resize_filter = frameless_window()
    resize_filter.remove()
    window.media_container = QWidget(window.central_widget)
    window.playlist_dock_host = QWidget(window.media_container)
    window.video_frame = QWidget(window.media_container)
    window.video_frame.control_overlay = QWidget(
        window, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
    window.video_frame.playlist_panel = QWidget(
        window, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)

    targets = resize_filter.install()

    assert window.media_container in targets
    # `playlist_dock_host` KALDIRILDI (playlist artik bagimsiz
    # pencere). Filtre adaylari arasinda aranmaz.
    assert window.video_frame.control_overlay in targets
    # PLAYLIST ARTIK HEDEF DEGIL. Panel ana pencerenin YANINDA duran
    # bagimsiz bir penceredir; ana pencerenin resize'ini surmemelidir.
    # Kullanici bildirdi (17 Agustos 2026): playlist uzerinde HER YERDE
    # yatay resize imleci cikiyordu, cunku panelin koordinatlari ana
    # pencereye eslenince anlamsiz kenarlar uretiyordu.
    assert window.video_frame.playlist_panel not in targets


def test_press_on_the_playlist_never_resizes_the_main_window(
        frameless_window):
    """TERSINE CEVRILDI (17 Agustos 2026, kullanici raporu).

    Bu test bir zamanlar panelin sag kenarina basmanin ANA PENCERE
    resize'ini baslatmasini SART KOSUYORDU. O beklenti panel ana
    pencerenin icindeki bir yuzeyken dogruydu.

    Panel artik ana pencerenin YANINDA duran bagimsiz bir penceredir.
    Kullanicinin gordugu belirti: playlist uzerinde HER YERDE yatay
    resize imleci cikiyor ve pencere buyutuluyordu. Panelin kendi
    genisligi kendi tutamaciyla degisir (`panel.set_panel_width`); ana
    pencereye DOKUNMAZ.
    """
    app, window, bar, resize_filter = frameless_window()
    resize_filter.remove()
    panel = QWidget(window, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
    window.video_frame = QWidget(window.central_widget)
    window.video_frame.playlist_panel = panel
    window.video_frame.control_overlay = None
    panel.setGeometry(window.mapToGlobal(QPoint(window.width() - 360, 80)).x(),
                      window.mapToGlobal(QPoint(0, 80)).y(), 360, 400)
    panel.show()
    resize_filter.install()

    # NOT: Basıştan SONRA `processEvents()` çağrılmaz. Panelin gösterilmesi
    # ana pencereye `WindowDeactivate` gönderiyor ve ürün bunu doğru biçimde
    # "bekleyen sürüklemeyi bırak" olarak yorumluyor; kuyruk boşaltılırsa
    # ölçülen şey basışın sonucu değil, o iptal olurdu.
    point = QPoint(panel.width() - 1, panel.height() // 2)
    app.sendEvent(panel, press_on(panel, (point.x(), point.y())))

    try:
        assert not resize_filter.manual_resize_active(), (
            "playlist uzerindeki basis ana pencere resize'ini baslatti")
    finally:
        resize_filter._end_manual_resize()
        app.processEvents()


def test_press_on_title_bar_button_does_not_start_resize(frameless_window):
    app, window, bar, resize_filter = frameless_window()
    started = spy_on_resize(resize_filter)
    close_button = next(b for b in bar.findChildren(QPushButton)
                        if b.objectName() == "titleClose")

    app.sendEvent(close_button,
                  press_on(close_button, (close_button.width() // 2,
                                          close_button.height() // 2)))
    app.processEvents()

    assert started == []


@pytest.mark.parametrize("state", ("maximized", "fullscreen", "minimized"))
def test_resize_is_blocked_in_non_normal_states(frameless_window, state):
    app, window, bar, resize_filter = frameless_window()
    started = spy_on_resize(resize_filter)
    getattr(window, {"maximized": "showMaximized",
                     "fullscreen": "showFullScreen",
                     "minimized": "showMinimized"}[state])()
    app.processEvents()

    central = window.central_widget
    offset = central.mapTo(window, QPoint(0, 0))
    app.sendEvent(central, press_on(central, (-offset.x(), -offset.y())))
    app.processEvents()

    assert started == []
    window.showNormal()
    app.processEvents()


def test_resize_works_again_after_returning_to_normal_state(frameless_window):
    app, window, bar, resize_filter = frameless_window()
    window.showMaximized()
    app.processEvents()
    window.showNormal()
    app.processEvents()

    started = spy_on_resize(resize_filter)
    central = window.central_widget
    offset = central.mapTo(window, QPoint(0, 0))
    app.sendEvent(central, press_on(central, (-offset.x(), central.height() // 2)))
    app.processEvents()

    assert started == [Qt.Edge.LeftEdge]


@pytest.mark.parametrize("state", ("maximized", "fullscreen", "minimized"))
def test_entering_a_non_resizable_state_clears_a_live_resize_cursor(
        frameless_window, state):
    app, window, bar, resize_filter = frameless_window()
    target = window.central_widget
    resize_filter._apply_resize_cursor(target, Qt.Edge.RightEdge)
    assert resize_filter._cursor_state is not None

    getattr(window, {"maximized": "showMaximized",
                     "fullscreen": "showFullScreen",
                     "minimized": "showMinimized"}[state])()
    app.processEvents()

    assert resize_filter._cursor_state is None
    assert QApplication.overrideCursor() is None
    window.showNormal()
    app.processEvents()


def test_filter_tracks_its_installed_targets(frameless_window):
    app, window, bar, resize_filter = frameless_window()
    assert window in resize_filter.targets
    assert window.central_widget in resize_filter.targets


def test_leave_between_bottom_corner_children_keeps_diagonal_cursor(
        frameless_window, monkeypatch):
    app, window, bar, resize_filter = frameless_window()
    target = window.central_widget
    point = window.mapToGlobal(QPoint(window.width() - 1,
                                      window.height() - 1))
    monkeypatch.setattr("app.title_bar.QCursor.pos", lambda: point)
    monkeypatch.setattr("app.title_bar.QApplication.widgetAt",
                        lambda _point: target)

    resize_filter._refresh_resize_cursor_from_global()

    assert resize_filter._cursor_state[0] is target
    assert resize_filter._cursor_state[3] == Qt.CursorShape.SizeFDiagCursor


def test_windows_outer_bottom_corner_uses_player_when_widget_at_is_none(
        frameless_window, monkeypatch):
    app, window, bar, resize_filter = frameless_window()
    point = window.mapToGlobal(QPoint(window.width() - 1,
                                      window.height() - 1))
    monkeypatch.setattr("app.title_bar.QCursor.pos", lambda: point)
    monkeypatch.setattr("app.title_bar.QApplication.widgetAt",
                        lambda _point: None)

    resize_filter._refresh_resize_cursor_from_global()

    assert resize_filter._cursor_state[0] is window
    assert resize_filter._cursor_state[3] == Qt.CursorShape.SizeFDiagCursor


def test_remove_uninstalls_from_every_tracked_target(frameless_window):
    app, window, bar, resize_filter = frameless_window()
    started = spy_on_resize(resize_filter)

    resize_filter.remove()
    assert resize_filter.targets == []

    central = window.central_widget
    offset = central.mapTo(window, QPoint(0, 0))
    app.sendEvent(central, press_on(central, (-offset.x(), central.height() // 2)))
    app.processEvents()
    assert started == []


def test_filter_does_not_consume_plain_content_clicks(frameless_window):
    app, window, bar, resize_filter = frameless_window()
    central = window.central_widget
    event = press_on(central, (central.width() // 2, central.height() // 2))
    handled = resize_filter.eventFilter(central, event)
    assert handled is False


# --- 2. Overflow menüsü birikmemeli ---

def test_overflow_menu_object_is_reused(frameless_window):
    app, window, bar, resize_filter = frameless_window()
    first = bar.build_overflow_menu()
    for _ in range(19):
        assert bar.build_overflow_menu() is first


def test_overflow_menus_do_not_accumulate_under_title_bar(frameless_window):
    app, window, bar, resize_filter = frameless_window()
    bar.build_overflow_menu()
    app.processEvents()
    before = len([m for m in bar.findChildren(QMenu)
                  if m.parent() is bar])

    for _ in range(20):
        bar.build_overflow_menu()
    app.processEvents()

    after = len([m for m in bar.findChildren(QMenu) if m.parent() is bar])
    assert after == before == 1, f"{before} -> {after}"


def test_overflow_menu_keeps_category_order_after_rebuilds(frameless_window):
    app, window, bar, resize_filter = frameless_window()
    expected = ["Ortam", "Oynatma", "Ses", "Görüntü", "Alt Yazı",
                "Araçlar", "Gezinim", "Görünüm", "Yardım"]
    for _ in range(5):
        menu = bar.build_overflow_menu()
        assert [a.text() for a in menu.actions() if a.menu()] == expected


def test_overflow_menu_reuses_existing_menu_objects_after_rebuilds(
        frameless_window):
    app, window, bar, resize_filter = frameless_window()
    existing = {a.menu() for a in window.menuBar().actions()}
    for _ in range(5):
        menu = bar.build_overflow_menu()
        reused = {a.menu() for a in menu.actions() if a.menu()}
        assert reused == existing


def test_overflow_menu_reflects_dynamic_action_state(frameless_window):
    app, window, bar, resize_filter = frameless_window()
    source = window.menuBar().actions()[0].menu()
    action = source.addAction("Dinamik")
    action.setCheckable(True)
    action.setEnabled(False)

    bar.build_overflow_menu()
    action.setChecked(True)
    action.setEnabled(True)

    menu = bar.build_overflow_menu()
    reused = next(a.menu() for a in menu.actions() if a.text() == "Ortam")
    live = reused.actions()[-1]
    assert live is action
    assert live.isChecked() is True
    assert live.isEnabled() is True
