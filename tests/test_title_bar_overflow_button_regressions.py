# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Üç nokta düğmesi menü kapandıktan sonra "seçili" görünmemeli.

ÖLÇÜLEN KUSUR: `show_overflow_menu()` menüyü bloklayıcı `menu.exec()` ile
açıyor. Menü kapandığında imleç hâlâ düğmenin üzerindeyse genel
`QPushButton:hover` kuralı gri arka planı SÜRDÜRÜYOR ve düğme hâlâ
aktif/seçiliymiş gibi duruyor. `setDown(False)` tek başına yetmez: sorun
basılı durum değil, menü-aktif ile hover durumunun AYRIŞMAMASIDIR.

Sözleşme:
- Menü açıkken `menuOpen=true` (aktif görünüm meşrudur).
- Menü hangi yolla kapanırsa kapansın (seçim, dışarı tıklama, Escape,
  istisna) aktif görünüm temizlenir.
- Kapanışta imleç hâlâ düğmedeyse hover GEÇİCİ olarak bastırılır
  (`menuDismissed=true`) ve bu bastırma yalnız GERÇEK `Leave` olayına
  kadar sürer; sonraki `Enter`'da normal hover geri gelir.
- Kalıcı `_overflow_menu`, menü eylemleri ve miras yapısı DEĞİŞMEZ.
- Yeni timer, polling veya gecikme YOKTUR.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QEvent, QPoint, Qt
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget)

from app import title_bar as title_bar_module
from app.title_bar import TitleBar

MENU_LABELS = ("Ortam", "Görünüm", "Görüntü", "Oynatma", "Ses", "Alt Yazı",
               "Yardım")


@pytest.fixture
def bar_factory():
    created = []
    # QApplication referansı TUTULMALI: yalnız yerel değişkende kalırsa test
    # bitince toplanır ve bütün widget'lar C++ tarafında yok edilir.
    app_ref = []

    def factory():
        app = QApplication.instance() or QApplication([])
        if not app_ref:
            app_ref.append(app)
        window = QMainWindow()
        window.central_widget = QWidget(window)
        window.setCentralWidget(window.central_widget)
        window.main_layout = QVBoxLayout(window.central_widget)
        for name in ("open_file", "show_playlist"):
            setattr(window, name, lambda: None)
        for label in MENU_LABELS:
            window.menuBar().addMenu(label)
        window.menuBar().hide()
        bar = TitleBar(window)
        window.title_bar = bar
        window.main_layout.addWidget(bar)
        window.resize(1280, 720)
        window.show()
        app.processEvents()
        created.append(window)
        return app, window, bar

    yield factory

    app = QApplication.instance()
    for window in created:
        window.close()
        window.deleteLater()
    if app is not None:
        app.processEvents()


def fake_cursor(module, monkeypatch, inside):
    """Gerçek imleç ölçümünü belirlenimci kılar.

    Ürün `underMouse()` yerine gerçek `QCursor.pos()` ölçümü kullanmalıdır;
    offscreen'de sentetik olay `underMouse()`u güvenilir kılmaz.
    """
    class FakeCursor:
        @staticmethod
        def pos():
            button = module._probe_button
            point = QPoint(5, 5) if inside else QPoint(-50, -50)
            return button.mapToGlobal(point)

    monkeypatch.setattr(module, "QCursor", FakeCursor)


def open_menu(bar, monkeypatch, cursor_inside=False, raises=False):
    """Menüyü bloklamadan açar; `exec` sırasındaki durumu kaydeder."""
    seen = {}
    menu = bar.build_overflow_menu()
    title_bar_module._probe_button = bar.more_button
    fake_cursor(title_bar_module, monkeypatch, cursor_inside)

    def fake_exec(origin=None):
        seen["menuOpen"] = bar.more_button.property("menuOpen")
        seen["isDown"] = bar.more_button.isDown()
        if raises:
            raise RuntimeError("menü açılamadı")
        return None

    monkeypatch.setattr(menu, "exec", fake_exec)
    return seen, menu


def send(widget, event_type):
    QApplication.instance().sendEvent(widget, QEvent(event_type))


# --- a) exec sırasında aktif görünüm ------------------------------------

def test_the_button_is_active_while_the_menu_is_open(bar_factory, monkeypatch):
    _app, _window, bar = bar_factory()
    seen, _menu = open_menu(bar, monkeypatch)

    bar.show_overflow_menu()

    assert seen["menuOpen"] == "true", "menü açıkken aktif görünüm yok"


# --- b) normal dönüşte temizlik -----------------------------------------

def test_a_normal_close_clears_the_active_look(bar_factory, monkeypatch):
    _app, _window, bar = bar_factory()
    open_menu(bar, monkeypatch, cursor_inside=False)

    bar.show_overflow_menu()

    assert bar.more_button.property("menuOpen") == "false"
    assert bar.more_button.isDown() is False
    assert bar.more_button.property("menuDismissed") == "false"


# --- c) istisnada da temizlik -------------------------------------------

def test_an_exception_still_clears_the_active_look(bar_factory, monkeypatch):
    _app, _window, bar = bar_factory()
    open_menu(bar, monkeypatch, cursor_inside=True, raises=True)

    with pytest.raises(RuntimeError):
        bar.show_overflow_menu()

    assert bar.more_button.property("menuOpen") == "false"
    assert bar.more_button.isDown() is False


# --- d) imleç düğmedeyken kapanış ---------------------------------------

def test_a_close_under_the_cursor_suppresses_the_hover_look(bar_factory,
                                                            monkeypatch):
    _app, _window, bar = bar_factory()
    open_menu(bar, monkeypatch, cursor_inside=True)

    bar.show_overflow_menu()

    assert bar.more_button.property("menuOpen") == "false"
    assert bar.more_button.property("menuDismissed") == "true", (
        "imleç düğmedeyken hover bastırılmadı; düğme gri kalır")


def test_a_close_away_from_the_cursor_needs_no_suppression(bar_factory,
                                                           monkeypatch):
    _app, _window, bar = bar_factory()
    open_menu(bar, monkeypatch, cursor_inside=False)

    bar.show_overflow_menu()

    assert bar.more_button.property("menuDismissed") == "false"


# --- e) f) gerçek Leave / Enter döngüsü ---------------------------------

def test_a_real_leave_restores_the_normal_hover(bar_factory, monkeypatch):
    _app, _window, bar = bar_factory()
    open_menu(bar, monkeypatch, cursor_inside=True)
    bar.show_overflow_menu()
    assert bar.more_button.property("menuDismissed") == "true"

    send(bar.more_button, QEvent.Type.Leave)

    assert bar.more_button.property("menuDismissed") == "false"


def test_a_new_enter_after_the_leave_is_a_normal_hover(bar_factory,
                                                       monkeypatch):
    _app, _window, bar = bar_factory()
    open_menu(bar, monkeypatch, cursor_inside=True)
    bar.show_overflow_menu()

    send(bar.more_button, QEvent.Type.Leave)
    send(bar.more_button, QEvent.Type.Enter)

    assert bar.more_button.property("menuDismissed") == "false"
    assert bar.more_button.property("menuOpen") == "false"


# --- g) ikinci açılış temiz başlar --------------------------------------

def test_the_second_opening_starts_from_a_clean_state(bar_factory,
                                                      monkeypatch):
    _app, _window, bar = bar_factory()
    open_menu(bar, monkeypatch, cursor_inside=True)
    bar.show_overflow_menu()
    assert bar.more_button.property("menuDismissed") == "true"

    seen, _menu = open_menu(bar, monkeypatch, cursor_inside=False)
    bar.show_overflow_menu()

    assert seen["menuOpen"] == "true", "ikinci açılışta aktif görünüm yok"
    assert bar.more_button.property("menuDismissed") == "false"


# --- h) kalıcı menü ve eylemler değişmedi -------------------------------

def test_the_persistent_menu_and_its_actions_are_unchanged(bar_factory,
                                                           monkeypatch):
    _app, _window, bar = bar_factory()
    first = bar.build_overflow_menu()
    count = len(first.actions())

    open_menu(bar, monkeypatch, cursor_inside=True)
    bar.show_overflow_menu()
    open_menu(bar, monkeypatch, cursor_inside=False)
    bar.show_overflow_menu()

    second = bar.build_overflow_menu()
    assert second is first, "kalıcı menü nesnesi değişti"
    assert len(second.actions()) == count == len(MENU_LABELS), (
        f"eylemler birikti: {len(second.actions())}")


# --- Yasak altyapı ------------------------------------------------------

def test_no_timer_or_delay_was_added():
    import inspect

    source = inspect.getsource(title_bar_module)
    start = source.index("def show_overflow_menu")
    block = source[start:start + 1500]
    for forbidden in ("QTimer", "singleShot", "sleep", "threading"):
        assert forbidden not in block, f"yasak altyapı: {forbidden}"


def test_the_style_separates_the_menu_state_from_plain_hover(bar_factory):
    """Görünüm kararı GERÇEK stil sayfasında açık durumlarla ayrılmalı."""
    _app, _window, bar = bar_factory()
    style = bar.styleSheet()

    assert '#titleMore[menuOpen="true"]' in style
    assert '#titleMore[menuDismissed="true"]:hover' in style, (
        "bastırma düz hover kuralını yenmiyor")
