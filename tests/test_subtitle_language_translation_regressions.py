"""Altyazı Merkezi'nin dil seçimi ÇEVİRİYE bağlı OLMAMALIDIR.

KIRMIZI KANIT. `SubtitleSearchController._language_code()` seçilen dili
GÖRÜNEN metinden çözüyordu:

    LANGUAGE_CODES.get(self.dialog.language_box.currentText(),
                       DEFAULT_LANGUAGE_CODE)

`LANGUAGE_CODES` anahtarları Türkçedir (`"Almanca": "de"`). Kutu metinleri
çevrildiği anda `currentText()` `German` döner, sözlük ıskalar ve fonksiyon
SESSİZCE `DEFAULT_LANGUAGE_CODE = "tr"`ye düşer: Alman arayüzünde Almanca
altyazı arayan kullanıcıya TÜRKÇE altyazı gelir. Hata mesajı yoktur.

Bu, menü sırası kusuruyla AYNI sınıftandır
(`tests/test_menu_order_translation_regressions.py`): görünen metin
kimlik olarak kullanılamaz.

Çözüm: dil KODU `QComboBox` öğesinin `data()` alanında taşınır ve
`currentData()` ile okunur. Etiket serbestçe çevrilir.
"""

import subprocess
from pathlib import Path

import pytest
from PyQt6.QtCore import QTranslator
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
ENGLISH_TS = ROOT / "translations" / "mlcplayer_en.ts"


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def english(qt_app, tmp_path):
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


class _Box:
    """`QComboBox` yerine geçen en küçük yüzey: metin + veri."""

    def __init__(self, text, data):
        self._text = text
        self._data = data

    def currentText(self):
        return self._text

    def currentData(self):
        return self._data


class _Dialog:
    def __init__(self, box):
        self.language_box = box


def _controller(dialog):
    from app.subtitle_search_controller import SubtitleSearchController
    controller = SubtitleSearchController.__new__(SubtitleSearchController)
    controller.dialog = dialog
    return controller


# ── Asıl kırmızı ─────────────────────────────────────────────────────────

def test_a_translated_language_label_still_resolves_to_its_code():
    """Etiket İngilizceye çevrilmiş olsa da kod DOĞRU çözülmelidir."""
    controller = _controller(_Dialog(_Box("German", "de")))

    assert controller._language_code() == "de"


def test_the_code_does_not_come_from_the_visible_text():
    """Metin bozuk/beklenmedik olsa bile veri alanı kazanır."""
    controller = _controller(_Dialog(_Box("قصاصة", "es")))

    assert controller._language_code() == "es"


def test_a_box_without_data_falls_back_safely():
    """Veri yoksa ürün çökmez; belgelenmiş varsayılana düşer."""
    from app.subtitle_search_controller import DEFAULT_LANGUAGE_CODE

    controller = _controller(_Dialog(_Box("", None)))

    assert controller._language_code() == DEFAULT_LANGUAGE_CODE


# ── Kutunun kendisi ──────────────────────────────────────────────────────

def test_the_dialog_box_carries_a_code_for_every_language(qt_app):
    from PyQt6.QtWidgets import QComboBox

    from app.subtitle_center import LANGUAGE_CHOICES, populate_language_box

    box = QComboBox()
    populate_language_box(box)
    try:
        assert box.count() == len(LANGUAGE_CHOICES)
        codes = [box.itemData(index) for index in range(box.count())]
        assert codes == [code for code, _label in LANGUAGE_CHOICES]
    finally:
        box.deleteLater()


def test_the_labels_are_translated_but_the_codes_are_not(qt_app, english):
    from PyQt6.QtWidgets import QComboBox

    from app.subtitle_center import populate_language_box

    box = QComboBox()
    populate_language_box(box)
    try:
        labels = [box.itemText(index) for index in range(box.count())]
        assert "German" in labels, labels
        assert "Almanca" not in labels, labels
        assert box.itemData(labels.index("German")) == "de"
    finally:
        box.deleteLater()


# ── Kalıcı ayar: depo biçimi çeviriden ETKİLENMEZ ────────────────────────
#
# İKİNCİ KIRMIZI. `SubtitleSettingsController` varsayılan dili QSettings'e
# GÖRÜNEN metinle yazıyor (`settings_language_box.currentText()`) ve geri
# yüklerken `setCurrentText(values["language"])` diyordu. Arayüz çevrildiği
# anda ikisi de kırılır: kayıt `German` olur (eski kurulumlar `Almanca`
# taşır, eşleşmez) ve geri yükleme hiçbir öğeyi bulamayıp listenin ilk
# öğesinde kalır — kullanıcının tercihi SESSİZCE Türkçeye döner.
#
# Depo biçimi DEĞİŞTİRİLMEZ (eski kurulumlar bozulmasın): kayıt hâlâ
# KAYNAK dildeki etikettir. Yalnız kutuya yazma/okuma yolu kimliğe
# (koda) bağlanır.

def test_the_stored_language_is_read_back_after_translation(qt_app, english):
    from PyQt6.QtWidgets import QComboBox

    from app.subtitle_center import (current_language_label,
                                     populate_language_box,
                                     select_language_label)

    box = QComboBox()
    populate_language_box(box)
    try:
        assert select_language_label(box, "Almanca") is True
        # Kullanıcı `German` görür ama depoya giden değer DEĞİŞMEZ.
        assert box.currentText() == "German"
        assert current_language_label(box) == "Almanca"
    finally:
        box.deleteLater()


def test_an_unknown_stored_language_leaves_the_box_alone(qt_app):
    from PyQt6.QtWidgets import QComboBox

    from app.subtitle_center import populate_language_box, select_language_label

    box = QComboBox()
    populate_language_box(box)
    box.setCurrentIndex(2)
    try:
        assert select_language_label(box, "Klingonca") is False
        assert box.currentIndex() == 2
    finally:
        box.deleteLater()


def test_the_controller_round_trips_the_source_label(qt_app, english):
    """Ürün yolu: yükle → kaydet zinciri kaynak etiketi KORUR."""
    from PyQt6.QtWidgets import QComboBox

    from app.subtitle_center import populate_language_box
    from app.subtitle_settings_controller import SubtitleSettingsController

    box = QComboBox()
    populate_language_box(box)
    try:
        SubtitleSettingsController._select_language(box, "Fransızca")
        assert box.currentText() == "French"
        assert SubtitleSettingsController._selected_language(box) == "Fransızca"
    finally:
        box.deleteLater()
