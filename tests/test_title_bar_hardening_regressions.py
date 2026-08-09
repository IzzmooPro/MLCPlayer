"""Başlık çubuğu teknik sağlamlaştırma testleri.

1) Gerçek kenar resize olayının doğru widget'tan gelip startSystemResize
   çağırması, 2) overflow menüsünün birikmemesi.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QEvent, QPoint, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QMenu, QPushButton, QVBoxLayout, QWidget)

from app.title_bar import (RESIZE_MARGIN, FramelessResizeFilter, TitleBar)


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


def test_filter_tracks_its_installed_targets(frameless_window):
    app, window, bar, resize_filter = frameless_window()
    assert window in resize_filter.targets
    assert window.central_widget in resize_filter.targets


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
