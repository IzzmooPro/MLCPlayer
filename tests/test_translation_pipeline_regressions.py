"""Çeviri boru hattı: metin çıkarma → `.ts` → `.qm` → çalışan arayüz.

AŞAMA B. Menü metinleri `tr()` ile sarmalandı. Kaynak dil TÜRKÇE olduğu için
çeviri yüklü değilken davranış DEĞİŞMEZ; bu testler hem o güvenceyi hem de
çevirinin gerçekten uygulandığını ölçer.

TUZAK (ölçüldü): `pylupdate6` yalnız `QCoreApplication.translate(...)`
biçimini tanır ve `app/i18n.tr()` sarmalayıcısını GÖREMEZ. Bu yüzden çıkarma
`packaging/extract_translations.py` ile AST üzerinden yapılır.
"""

import importlib.util
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PyQt6.QtCore import QTranslator

from app import i18n

ROOT = Path(__file__).resolve().parent.parent
TRANSLATIONS = ROOT / "translations"
ENGLISH_TS = TRANSLATIONS / "mlcplayer_en.ts"


def _extractor():
    path = ROOT / "packaging" / "extract_translations.py"
    spec = importlib.util.spec_from_file_location("mlc_extract", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── Kaynak dil güvencesi ─────────────────────────────────────────────────

def test_wrapping_did_not_change_the_turkish_interface(qt_app):
    """ASIL GÜVENCE: çeviri yokken `tr()` kaynağı aynen döndürür.

    453 assert bu metinlere bakıyor; bozulursa paket toptan kırılır.
    """
    for text in ("Dosya Aç", "Oynatma Listesini Göster", "Çıkış",
                 "Güncellemeleri Denetle", "Altyazı Ekle"):
        assert i18n.tr(text) == text


# ── Çıkarma ──────────────────────────────────────────────────────────────

def test_the_extractor_finds_the_wrapped_menu_strings():
    texts, _dynamic = _extractor().collect()
    for expected in ("Dosya Aç", "Ortam", "Yardım", "Tam Ekran"):
        assert expected in texts, f"çıkarılmadı: {expected}"


def test_every_wrapped_call_carries_a_literal_string():
    """`tr(degisken)` çevrilemez ve kullanıcıya kaynak dilde görünür."""
    _texts, dynamic = _extractor().collect()
    assert dynamic == [], f"sabit metin taşımayan tr() çağrıları: {dynamic}"


def test_the_translation_files_are_up_to_date():
    """Metin eklenip `.ts` güncellenmezse çeviri sessizce eksik kalır."""
    assert _extractor().update(check_only=True) == 0, (
        "python packaging/extract_translations.py çalıştırılmalı")


def test_the_source_language_has_no_translation_file():
    assert not (TRANSLATIONS / "mlcplayer_tr.ts").exists()


@pytest.mark.parametrize("code", [c for c in i18n.SUPPORTED_LANGUAGES
                                  if c != i18n.SOURCE_LANGUAGE])
def test_every_supported_language_has_a_source_file(code):
    assert (TRANSLATIONS / f"mlcplayer_{code}.ts").is_file(), code


# ── İngilizce: boru hattının kanıtı ──────────────────────────────────────

def test_english_is_fully_translated():
    """İlk dil eksiksiz olmalı; yarım çeviri karışık arayüz demektir."""
    tree = ET.parse(ENGLISH_TS)
    unfinished = [m.findtext("source") for m in tree.iter("message")
                  if (m.find("translation") is not None
                      and m.find("translation").get("type") == "unfinished")]
    assert unfinished == [], f"çevrilmemiş: {unfinished[:5]}"


def test_the_compiled_english_translation_actually_applies(qt_app, tmp_path):
    """`.ts` derlenip yüklendiğinde arayüz GERÇEKTEN İngilizce olur."""
    target = tmp_path / "mlcplayer_en.qm"
    result = subprocess.run(["pyside6-lrelease", str(ENGLISH_TS), "-qm",
                             str(target)], capture_output=True, text=True,
                            timeout=120)
    assert result.returncode == 0, result.stderr
    assert target.is_file()

    translator = QTranslator()
    assert translator.load(str(target))
    qt_app.installTranslator(translator)
    try:
        assert i18n.tr("Dosya Aç") == "Open File"
        assert i18n.tr("Çıkış") == "Exit"
    finally:
        qt_app.removeTranslator(translator)
    # Kaldırıldıktan sonra kaynak dile DÖNER.
    assert i18n.tr("Dosya Aç") == "Dosya Aç"


# ── Paketleme ────────────────────────────────────────────────────────────

def test_compiled_translations_are_packaged():
    """`.qm` pakete girmezse kurulu sürüm hep Türkçe açılır."""
    spec = (ROOT / "MLCPlayer.spec").read_text(encoding="utf-8")
    assert "'translations'" in spec and ".qm" in spec


def test_source_files_are_tracked_but_compiled_ones_are_not():
    """`.ts` insan tarafından düzenlenir ve depoda durur; `.qm` üretilmiştir."""
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "*.qm" in ignore
    assert "*.ts" not in ignore


@pytest.fixture
def qt_app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])
