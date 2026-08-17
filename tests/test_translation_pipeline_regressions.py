"""Çeviri boru hattı: metin çıkarma → `.ts` → `.qm` → çalışan arayüz.

AŞAMA B. Menü metinleri `tr()` ile sarmalandı. Kaynak dil TÜRKÇE olduğu için
çeviri yüklü değilken davranış DEĞİŞMEZ; bu testler hem o güvenceyi hem de
çevirinin gerçekten uygulandığını ölçer.

TUZAK (ölçüldü): `pylupdate6` yalnız `QCoreApplication.translate(...)`
biçimini tanır ve `app/i18n.tr()` sarmalayıcısını GÖREMEZ. Bu yüzden çıkarma
`packaging/extract_translations.py` ile AST üzerinden yapılır.
"""

import importlib.util
import os
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


def _compiler():
    path = ROOT / "packaging" / "compile_translations.py"
    spec = importlib.util.spec_from_file_location("mlc_compile", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


# ── Modül düzeyi sabitler: işaretle şimdi, çevir sonra ───────────────────
#
# VLC'de aynı ayrım vardır (17 Ağustos 2026'da depoda görüldü):
# `#define INPUT_AUDIOTRACK_LANG_TEXT N_("Audio language")` metni yalnız
# ÇIKARMA için işaretler, çeviri kullanım anında `vlc_gettext()` ile olur.
# Bize gereken de budur: `URL_LOADING_TEXT` gibi sabitler import anında
# hesaplanır, o an henüz QApplication ve çevirmen YOKTUR; sabiti `tr()` ile
# sarmalamak metni sonsuza dek Türkçeye dondururdu.

def test_a_marked_constant_is_not_translated_at_import_time():
    """`tr_mark()` metni AYNEN döndürür; yalnız çıkarma için işaretler."""
    assert i18n.tr_mark("Bağlantı açılıyor…") == "Bağlantı açılıyor…"


def test_marked_constants_reach_the_translation_files():
    texts, _dynamic = _extractor().collect()
    assert "Bağlantı açılıyor…" in texts, "işaretlenen sabit çıkarılmadı"


def test_a_marked_constant_is_translated_when_it_is_used(qt_app, tmp_path):
    """Kullanım anında çeviri UYGULANIR; sabit Türkçe kalmaz."""
    target = tmp_path / "mlcplayer_en.qm"
    result = subprocess.run(["pyside6-lrelease", str(ENGLISH_TS), "-qm",
                             str(target)], capture_output=True, text=True,
                            timeout=120)
    assert result.returncode == 0, result.stderr
    translator = QTranslator()
    assert translator.load(str(target))
    qt_app.installTranslator(translator)
    try:
        from app import media_controls
        assert (i18n.translate_marked(media_controls.URL_FAILED_TITLE)
                != media_controls.URL_FAILED_TITLE)
    finally:
        qt_app.removeTranslator(translator)


def test_the_user_facing_url_constants_are_marked():
    """İşaretlenmemiş sabit hiçbir dilde çevrilemez."""
    texts, _dynamic = _extractor().collect()
    from app import media_controls
    for constant in (media_controls.URL_LOADING_TEXT,
                     media_controls.URL_INVALID_TITLE,
                     media_controls.URL_INVALID_MESSAGE,
                     media_controls.URL_FAILED_TITLE,
                     media_controls.URL_FAILED_MESSAGE):
        assert constant in texts, constant


# ── Paketleme ────────────────────────────────────────────────────────────

def test_the_release_chain_compiles_the_translations():
    """`.qm` ÜRETİLMEZSE paket çevirisiz çıkar — sessizce.

    KIRMIZI KANIT: `.qm` `.gitignore` içindedir (üretilmiş dosyadır) ve
    `MLCPlayer.spec` onları `translations/` içinden TOPLAR, ama zinciri
    kuran hiçbir adım onları DERLEMİYORDU. Temiz bir kopyada
    `build_release.bat` çalıştırıldığında klasör boş olur; kullanıcı hiçbir
    uyarı almadan yalnız Türkçe görür ve `available_languages()` İngilizceyi
    bile sunamaz.
    """
    chain = (ROOT / "packaging" / "build_release.bat").read_text(
        encoding="utf-8", errors="replace")
    assert "compile_translations.py" in chain, (
        "yayın zinciri çevirileri derlemiyor")
    # Derleme PyInstaller'ın GERÇEK koşumundan ÖNCE olmalı; sonra olursa
    # pakete girmez. Ölçüt `--version` ön kontrolü DEĞİL, spec ile yapılan
    # asıl çağrıdır (o kontrol dosyanın başında yer alır).
    build_call = 'PyInstaller "%SPEC%"'
    assert build_call in chain
    assert chain.index("compile_translations.py") < chain.index(build_call)


def test_the_compiler_skips_untranslated_languages(tmp_path):
    """Boş `.qm` üretmek anlamsızdır; dil zaten sunulamaz."""
    module = _compiler()
    written, skipped = module.compile_all(str(TRANSLATIONS), str(tmp_path))
    assert "mlcplayer_en.qm" in [os.path.basename(p) for p in written]
    assert any("mlcplayer_de" in name for name in skipped), skipped
    assert not (tmp_path / "mlcplayer_de.qm").exists()


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
