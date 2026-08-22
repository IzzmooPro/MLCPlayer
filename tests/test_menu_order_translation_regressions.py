# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Menü sekme SIRASI çeviriye bağlı OLMAMALIDIR.

KIRMIZI KANIT. `setup_menu()` sekmeleri istenen sıraya sokarken menüleri
GÖRÜNEN metinlerine göre buluyordu:

    menu_order = ["Ortam", "Oynatma", "Ses", ...]
    top_menus = {action.text(): action for action in menu_bar.actions()}

Menü başlıkları B1 turunda `tr()` ile sarmalandığı için İngilizce arayüzde
`action.text()` artık `Media`/`Playback` döner; `top_menus.get("Ortam")`
`None` verir ve sıralama SESSİZCE hiç uygulanmaz. Türkçe arayüzde sorun
görünmez — bu yüzden kusur ancak ikinci dil yüklenince ortaya çıkar.

Çözüm: sıra KAYNAK metinlere değil, menülerin OLUŞTURULMA kimliğine
bağlanır. Menü nesneleri zaten elimizdedir; metin üzerinden geri arama
yapılmaz.
"""

import subprocess
from pathlib import Path

import pytest
from PyQt6.QtCore import QTranslator
from PyQt6.QtWidgets import QApplication, QMainWindow

ROOT = Path(__file__).resolve().parent.parent
ENGLISH_TS = ROOT / "translations" / "mlcplayer_en.ts"

#: Ürünün istediği sekme sırası, KAYNAK dilde.
EXPECTED_TURKISH = ["Ortam", "Oynatma", "Ses", "Görüntü", "Alt Yazı",
                    "Araçlar", "Gezinim", "Görünüm", "Yardım"]


class MenuPlayer(QMainWindow):
    """`setup_menu()` için en küçük gerçek pencere."""

    def __init__(self):
        super().__init__()
        self.__dict__["calls"] = []
        self.loop_file = False
        self.loop_playlist = False
        self.shuffle = False
        self.speed_actions = {}
        self.recent_files = []
        self.current_file = ""

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)

        def recorder(*args, **kwargs):
            self.__dict__["calls"].append(name)
        return recorder


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def english(qt_app, tmp_path):
    """Gerçek İngilizce çeviriyi yükler ve test sonunda kaldırır."""
    target = tmp_path / "mlcplayer_en.qm"
    result = subprocess.run(["pyside6-lrelease", str(ENGLISH_TS), "-qm",
                             str(target)], capture_output=True, text=True,
                            timeout=120)
    assert result.returncode == 0, result.stderr
    translator = QTranslator()
    assert translator.load(str(target))
    qt_app.installTranslator(translator)
    yield translator
    qt_app.removeTranslator(translator)


def _top_level_labels(window):
    return [action.text() for action in window.menuBar().actions()
            if action.menu()]


def _menu(window, label):
    return next(action.menu() for action in window.menuBar().actions()
                if action.text() == label)


def test_the_turkish_menu_order_is_unchanged(qt_app):
    """Kaynak dilde davranış AYNEN korunmalıdır."""
    from app.menu_actions import setup_menu

    window = MenuPlayer()
    try:
        setup_menu(window)
        assert _top_level_labels(window) == EXPECTED_TURKISH
    finally:
        window.close()
        window.deleteLater()


def test_picture_in_picture_is_available_from_video_menu(qt_app):
    """Üst çubuk düğmesi yanında taşma menüsünden de PiP açılabilmelidir."""
    from app.menu_actions import setup_menu

    window = MenuPlayer()
    try:
        setup_menu(window)
        video_menu = _menu(window, "Görüntü")
        action = next(action for action in video_menu.actions()
                      if action.text() == "Resim İçinde Resim")

        action.trigger()

        assert window.calls[-1] == "toggle_picture_in_picture"
    finally:
        window.close()
        window.deleteLater()


def test_the_menu_order_survives_translation(qt_app, english):
    """İNGİLİZCE arayüzde de sıra aynı olmalıdır (etiketler çevrilir)."""
    from app import i18n
    from app.menu_actions import setup_menu

    window = MenuPlayer()
    try:
        setup_menu(window)
        labels = _top_level_labels(window)
        expected = [i18n.tr(name) for name in EXPECTED_TURKISH]
        # Çevirinin gerçekten yüklendiğini KANITLA; yoksa test hiçbir şey
        # ölçmeden yeşil geçerdi.
        assert expected != EXPECTED_TURKISH, "İngilizce çeviri yüklenmedi"
        assert labels == expected
    finally:
        window.close()
        window.deleteLater()


def test_the_order_is_not_derived_from_visible_text():
    """Kaynakta metinle geri arama kalırsa kusur sessizce geri döner."""
    source = (ROOT / "app" / "menu_actions.py").read_text(encoding="utf-8")
    assert "top_menus" not in source, (
        "sekme sırası görünen metinden türetiliyor")
