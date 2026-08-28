# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Preview moduna özel modern başlık çubuğu regresyon testleri.

Gerçek widget geometrisi, gerçek QIcon pixmap'i ve gerçek player bağlantıları
ölçülür. Native MPV örneği gerekmez; ürün kabuğu ölçümleri ayrı shell
testindedir.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QEvent, QPoint, QRect, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QMenu, QPushButton, QVBoxLayout, QWidget)

from app.title_bar import (RESIZE_MARGIN, TITLE_BAR_HEIGHT, TitleBar,
                           resize_edges_at)
from app.ui_icons import make_media_pixmap

LEFT_ORDER = ("titleOpenFile", "titlePlaylist", "titleMore")
RIGHT_ORDER = ("titleTransparency", "titlePictureInPicture", "titleMinimize",
               "titleMaximize", "titleClose")


def test_transparency_icon_is_a_half_filled_opacity_symbol():
    app = QApplication.instance() or QApplication([])
    image = make_media_pixmap("transparency", 20).toImage()

    opaque_half = image.pixelColor(7, 10)
    transparent_half = image.pixelColor(13, 10)

    assert opaque_half.alpha() > 200
    assert transparent_half.alpha() < opaque_half.alpha() / 2


@pytest.fixture
def title_bar():
    created = []
    app_ref = []

    def qt_app():
        app = QApplication.instance() or QApplication([])
        if not app_ref:
            app_ref.append(app)
        return app

    def factory(size=(1280, 720)):
        app = qt_app()
        window = QMainWindow()
        window.calls = []
        window.central_widget = QWidget(window)
        window.setCentralWidget(window.central_widget)
        window.main_layout = QVBoxLayout(window.central_widget)
        window.main_layout.setContentsMargins(0, 0, 0, 0)
        for name in ("open_file", "show_playlist", "toggle_picture_in_picture"):
            setattr(window, name,
                    lambda name=name: window.calls.append(name))
        window.set_window_opacity_percent = lambda value: window.calls.extend(
            ("set_window_opacity_percent", value))
        window.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        # Gerçek üründeki gibi mevcut QMenuBar menüleri
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
        created.append(window)
        return app, window, bar

    yield factory

    app = qt_app()
    for window in created:
        window.close()
        window.deleteLater()
    app.processEvents()


def button(bar, name):
    return next(b for b in bar.findChildren(QPushButton)
                if b.objectName() == name)


def centre_x(bar, widget):
    return widget.mapTo(bar, widget.rect().center()).x()


def press_event(widget, point, button_type=Qt.MouseButton.LeftButton):
    return QMouseEvent(QEvent.Type.MouseButtonPress, QPoint(*point).toPointF(),
                       widget.mapToGlobal(QPoint(*point)).toPointF(),
                       button_type, button_type, Qt.KeyboardModifier.NoModifier)


# --- Görsel yapı ---

def test_title_bar_has_fixed_reference_height(title_bar):
    app, window, bar = title_bar()
    assert TITLE_BAR_HEIGHT == 40
    assert bar.height() == 40
    assert bar.minimumHeight() == 40
    assert bar.maximumHeight() == 40


def test_title_bar_uses_the_approved_reference_scale(title_bar):
    app, window, bar = title_bar()
    assert TITLE_BAR_HEIGHT == 40
    assert "font-size: 14px" in bar.title_label.styleSheet()
    for name in LEFT_ORDER + RIGHT_ORDER:
        widget = button(bar, name)
        assert widget.width() == 26
        assert widget.height() == 26
        assert widget.iconSize().width() == 18
        assert widget.iconSize().height() == 18


def test_title_bar_shows_product_name(title_bar):
    app, window, bar = title_bar()
    assert bar.title_label.text() == "MLC Player"


def test_left_controls_are_in_reference_order(title_bar):
    app, window, bar = title_bar()
    positions = [centre_x(bar, button(bar, name)) for name in LEFT_ORDER]
    assert positions == sorted(positions), dict(zip(LEFT_ORDER, positions))
    assert positions[0] > centre_x(bar, bar.title_label)


def test_window_buttons_are_in_reference_order_on_the_right(title_bar):
    app, window, bar = title_bar()
    positions = [centre_x(bar, button(bar, name)) for name in RIGHT_ORDER]
    assert positions == sorted(positions), dict(zip(RIGHT_ORDER, positions))
    assert positions[0] > max(centre_x(bar, button(bar, n)) for n in LEFT_ORDER)


def test_all_title_bar_buttons_have_no_visible_text(title_bar):
    app, window, bar = title_bar()
    for name in LEFT_ORDER + RIGHT_ORDER:
        assert button(bar, name).text() == ""


def test_all_title_bar_buttons_carry_non_null_icons(title_bar):
    app, window, bar = title_bar()
    for name in LEFT_ORDER + RIGHT_ORDER:
        widget = button(bar, name)
        assert not widget.icon().isNull()
        assert not widget.icon().pixmap(widget.iconSize()).isNull()


def test_all_title_bar_buttons_are_keyboard_reachable(title_bar):
    app, window, bar = title_bar()
    for name in LEFT_ORDER + RIGHT_ORDER:
        assert button(bar, name).focusPolicy() == Qt.FocusPolicy.TabFocus


def test_title_bar_buttons_expose_tooltip_and_accessible_name(title_bar):
    app, window, bar = title_bar()
    expected = {
        "titleOpenFile": "Dosya Aç",
        "titlePlaylist": "Playlist",
        "titleMore": "Menü",
        "titleMinimize": "Küçült",
        "titleTransparency": "Şeffaflık",
        "titlePictureInPicture": "Resim İçinde Resim",
        "titleMaximize": "Büyüt",
        "titleClose": "Kapat",
    }
    for name, label in expected.items():
        widget = button(bar, name)
        assert widget.toolTip() == label
        assert widget.accessibleName() == label


def test_close_button_uses_the_product_accent_on_hover(title_bar):
    """Kapatma düğmesinin hover rengi.

    ESKİ AD `..._uses_red_hover_style` ve eski beklenti Windows kırmızısıydı
    (`#E81123`). 17 Ağustos 2026'da KULLANICI KARARIYLA değişti: düğme
    ürünün kendi vurgu rengine döner. Beklenti GEVŞETİLMEDİ — hâlâ kuralın
    varlığı VE rengin ne olduğu ölçülüyor, yalnız hangi renk olduğu
    güncellendi. Renk `video_frame.OVERLAY_ACCENT` ile aynı olmak
    zorundadır; başlık çubuğu ayrı bir kimlik kurmaz
    (`tests/test_title_bar_hover_regressions.py`).
    """
    from app.video_frame import OVERLAY_ACCENT

    app, window, bar = title_bar()
    style = bar.styleSheet().lower()
    assert "#titleclose:hover" in style.replace(" ", "")
    assert OVERLAY_ACCENT.lower() in style
    assert "e81123" not in style


# --- Sol komutlar ---

def test_open_button_calls_real_player_open_file(title_bar):
    app, window, bar = title_bar()
    button(bar, "titleOpenFile").click()
    assert "open_file" in window.calls


def test_playlist_button_calls_real_player_show_playlist(title_bar):
    app, window, bar = title_bar()
    button(bar, "titlePlaylist").click()
    assert "show_playlist" in window.calls


def test_overflow_menu_reuses_existing_menu_objects(title_bar):
    app, window, bar = title_bar()
    menu = bar.build_overflow_menu()

    titles = [action.text() for action in menu.actions() if action.menu()]
    assert titles == ["Ortam", "Oynatma", "Ses", "Görüntü", "Alt Yazı",
                      "Araçlar", "Gezinim", "Görünüm", "Yardım"]

    existing = {action.menu() for action in window.menuBar().actions()}
    reused = {action.menu() for action in menu.actions() if action.menu()}
    assert reused == existing, "mevcut QMenu nesneleri yeniden kullanılmalı"
    menu.deleteLater()


def test_overflow_menu_is_not_rebuilt_with_copied_actions(title_bar):
    app, window, bar = title_bar()
    source = window.menuBar().actions()[0].menu()
    marker = source.addAction("Dinamik Aksiyon")
    marker.setCheckable(True)
    marker.setChecked(True)

    menu = bar.build_overflow_menu()
    reused = next(a.menu() for a in menu.actions() if a.text() == "Ortam")

    assert reused is source
    assert marker in reused.actions()
    assert reused.actions()[-1].isChecked() is True
    menu.deleteLater()


# --- Pencere düğmeleri ---

def test_minimize_button_minimises_the_window(title_bar):
    app, window, bar = title_bar()
    button(bar, "titleMinimize").click()
    app.processEvents()
    assert window.isMinimized()
    window.showNormal()
    app.processEvents()


def test_transparency_button_opens_adjustable_slider(title_bar):
    app, window, bar = title_bar()
    window.window_opacity_percent = 100

    button(bar, "titleTransparency").click()
    app.processEvents()

    assert bar.transparency_popup.isVisible()
    assert bar.transparency_slider.minimum() == 35
    assert bar.transparency_slider.maximum() == 100
    bar.transparency_slider.setValue(58)
    assert window.calls[-2:] == ["set_window_opacity_percent", 58]


def test_picture_in_picture_button_calls_product_method(title_bar):
    app, window, bar = title_bar()

    button(bar, "titlePictureInPicture").click()

    assert window.calls[-1] == "toggle_picture_in_picture"


def test_maximize_button_toggles_and_updates_state(title_bar):
    app, window, bar = title_bar()
    maximize = button(bar, "titleMaximize")
    paused_icon = maximize.icon().pixmap(maximize.iconSize()).cacheKey()

    maximize.click()
    app.processEvents()
    assert window.isMaximized()
    assert maximize.accessibleName() == "Geri Yükle"
    assert maximize.toolTip() == "Geri Yükle"
    assert maximize.icon().pixmap(maximize.iconSize()).cacheKey() != paused_icon

    maximize.click()
    app.processEvents()
    assert not window.isMaximized()
    assert maximize.accessibleName() == "Büyüt"


def test_close_button_closes_the_window(title_bar):
    app, window, bar = title_bar()
    button(bar, "titleClose").click()
    app.processEvents()
    assert not window.isVisible()


# --- Taşıma ---

def test_drag_on_empty_area_starts_system_move(title_bar):
    app, window, bar = title_bar()
    calls = []
    bar._start_system_move = lambda: calls.append("move") or True

    bar.mousePressEvent(press_event(bar, (bar.width() // 2, 20)))

    assert calls == ["move"]


def test_drag_on_a_button_does_not_start_system_move(title_bar):
    app, window, bar = title_bar()
    calls = []
    bar._start_system_move = lambda: calls.append("move") or True
    close = button(bar, "titleClose")
    point = close.mapTo(bar, close.rect().center())

    bar.mousePressEvent(press_event(bar, (point.x(), point.y())))

    assert calls == []


def test_right_button_press_does_not_start_system_move(title_bar):
    app, window, bar = title_bar()
    calls = []
    bar._start_system_move = lambda: calls.append("move") or True

    bar.mousePressEvent(press_event(bar, (bar.width() // 2, 20),
                                    Qt.MouseButton.RightButton))

    assert calls == []


def test_double_click_toggles_maximized_state(title_bar):
    app, window, bar = title_bar()
    def empty_title_event():
        point = bar.title_label.mapTo(bar, bar.title_label.rect().center())
        return QMouseEvent(
            QEvent.Type.MouseButtonDblClick, point.toPointF(),
            bar.mapToGlobal(point).toPointF(), Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)

    bar.mouseDoubleClickEvent(empty_title_event())
    app.processEvents()
    assert window.isMaximized()
    assert button(bar, "titleMaximize").accessibleName() == "Geri Yükle"

    bar.mouseDoubleClickEvent(empty_title_event())
    app.processEvents()
    assert not window.isMaximized()
    assert button(bar, "titleMaximize").accessibleName() == "Büyüt"


# --- Frameless resize bölgeleri ---

def test_resize_margin_is_in_reference_range():
    assert 10 <= RESIZE_MARGIN <= 14


@pytest.mark.parametrize("point,expected", [
    ((0, 200), Qt.Edge.LeftEdge),
    ((399, 200), Qt.Edge.RightEdge),
    ((200, 0), Qt.Edge.TopEdge),
    ((200, 299), Qt.Edge.BottomEdge),
    ((0, 0), Qt.Edge.LeftEdge | Qt.Edge.TopEdge),
    ((399, 0), Qt.Edge.RightEdge | Qt.Edge.TopEdge),
    ((0, 299), Qt.Edge.LeftEdge | Qt.Edge.BottomEdge),
    ((399, 299), Qt.Edge.RightEdge | Qt.Edge.BottomEdge),
])
def test_eight_resize_zones_map_to_correct_edges(point, expected):
    rect = QRect(0, 0, 400, 300)
    assert resize_edges_at(rect, QPoint(*point)) == expected


def test_centre_of_window_has_no_resize_edge():
    rect = QRect(0, 0, 400, 300)
    assert resize_edges_at(rect, QPoint(200, 150)) == Qt.Edge(0)


def test_resize_is_blocked_while_maximized(title_bar):
    app, window, bar = title_bar()
    window.showMaximized()
    app.processEvents()
    assert bar.can_resize_window() is False
    window.showNormal()
    app.processEvents()


def test_resize_is_blocked_while_fullscreen(title_bar):
    app, window, bar = title_bar()
    window.showFullScreen()
    app.processEvents()
    assert bar.can_resize_window() is False
    window.showNormal()
    app.processEvents()


def test_resize_is_allowed_in_normal_state(title_bar):
    app, window, bar = title_bar()
    assert bar.can_resize_window() is True


# --- Minimum boyut ---

def test_title_bar_controls_stay_inside_minimum_window(title_bar):
    app, window, bar = title_bar(size=(400, 300))
    app.processEvents()
    bar_rect = QRect(bar.mapToGlobal(QPoint(0, 0)), bar.size())

    for name in LEFT_ORDER + RIGHT_ORDER:
        widget = button(bar, name)
        rect = QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())
        assert bar_rect.contains(rect), f"{name} {rect} başlık dışına taştı"
        assert widget.isVisible()


def test_title_bar_buttons_do_not_overlap_at_minimum_width(title_bar):
    app, window, bar = title_bar(size=(400, 300))
    app.processEvents()
    rects = []
    for name in LEFT_ORDER + RIGHT_ORDER:
        widget = button(bar, name)
        rects.append(QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size()))
    for first, second in zip(rects, rects[1:]):
        assert not first.intersects(second)


def test_repeated_resize_keeps_title_commands_clickable(title_bar):
    app, window, bar = title_bar(size=(480, 300))
    sizes = ((480, 300), (760, 430), (1280, 720), (560, 340),
             (1600, 900), (480, 300))
    commands = {
        "titleOpenFile": "open_file",
        "titlePlaylist": "show_playlist",
        "titlePictureInPicture": "toggle_picture_in_picture",
    }

    for width, height in sizes:
        window.resize(width, height)
        window.showNormal()
        app.processEvents()
        for name, expected in commands.items():
            widget = button(bar, name)
            point = widget.rect().center()
            assert bar.childAt(widget.mapTo(bar, point)) is widget
            window.calls.clear()
            QTest.mouseClick(widget, Qt.MouseButton.LeftButton,
                             Qt.KeyboardModifier.NoModifier, point)
            app.processEvents()
            assert window.calls == [expected]

        maximize = button(bar, "titleMaximize")
        QTest.mouseClick(maximize, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert window.isMaximized()
        QTest.mouseClick(maximize, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert not window.isMaximized()
