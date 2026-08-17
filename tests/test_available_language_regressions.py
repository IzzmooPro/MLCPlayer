# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dil menüsü YALNIZ gerçekten çevrilmiş dilleri sunar.

KULLANICI KARARI (17 Ağustos 2026): şimdilik Türkçe + İngilizce ile devam
edilecek; kalan altı dil sonraya bırakıldı.

KIRMIZI KANIT (ölçüldü). `translations/*.ts` tamamlanma oranları:

    mlcplayer_en.ts     401/401
    mlcplayer_de.ts       0/401      (es, fr, it, ru, pt_BR de aynı)

Menü ise sabit `SUPPORTED_LANGUAGES` listesinden sekiz dili sunuyordu.
Kullanıcı `Deutsch` seçiyor, programı yeniden başlatıyor ve karşısına
UYARISIZ İngilizce çıkıyor. Menü tutamayacağı bir söz veriyordu.

Çözüm: sunulan liste sabitten değil ÇEVİRİ DOSYALARINDAN türer. Bir dilin
`.qm` dosyası yoksa ya da yüklendiğinde BOŞ ise o dil sunulmaz. Bir dil
tamamlandığında menüye kendiliğinden girer; kod değişmez.

`SUPPORTED_LANGUAGES` KALDIRILMAZ: kurulum sihirbazı hâlâ sekiz dildedir
(Inno'nun kendi çevirileri eksiksizdir) ve `.ts` dosyaları o küme için
üretilir. Değişen yalnız UYGULAMA ARAYÜZÜNÜN sunduğu kümedir.
"""

import subprocess
from pathlib import Path

import pytest
from PyQt6.QtCore import QLocale

from app import i18n

ROOT = Path(__file__).resolve().parent.parent
TRANSLATIONS = ROOT / "translations"


@pytest.fixture
def qt_app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    from PyQt6.QtCore import QSettings
    store = QSettings(str(tmp_path / "dil.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(i18n, "_settings", lambda: store)
    return store


def _release_compiler():
    """Yayın zincirinin KENDİ derleyicisi; testte ikinci bir kopya yazılmaz."""
    import importlib.util
    path = ROOT / "packaging" / "compile_translations.py"
    spec = importlib.util.spec_from_file_location("mlc_compile_avail", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _compile(ts_path, qm_path):
    result = subprocess.run(
        ["pyside6-lrelease", str(ts_path), "-qm", str(qm_path)],
        capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    return qm_path


@pytest.fixture
def only_english(tmp_path, monkeypatch):
    """Gerçek durum: yalnız İngilizce derlenmiş, Almanca dosyası YOK."""
    _compile(TRANSLATIONS / "mlcplayer_en.ts", tmp_path / "mlcplayer_en.qm")
    monkeypatch.setattr(i18n, "translations_directory", lambda: str(tmp_path))
    i18n.forget_available_languages()
    yield tmp_path
    i18n.forget_available_languages()


@pytest.fixture
def english_and_empty_german(tmp_path, monkeypatch):
    """Almanca `.qm` VAR ama içi BOŞ — dosyanın varlığı yetmez."""
    _compile(TRANSLATIONS / "mlcplayer_en.ts", tmp_path / "mlcplayer_en.qm")
    _compile(TRANSLATIONS / "mlcplayer_de.ts", tmp_path / "mlcplayer_de.qm")
    monkeypatch.setattr(i18n, "translations_directory", lambda: str(tmp_path))
    i18n.forget_available_languages()
    yield tmp_path
    i18n.forget_available_languages()


# ── Kullanılabilir dil kümesi ────────────────────────────────────────────

def test_the_source_language_is_always_available(qt_app, only_english):
    """Türkçe kaynak dildir; çeviri dosyası aranmaz."""
    assert i18n.SOURCE_LANGUAGE in i18n.available_languages()


def test_a_language_without_a_file_is_not_offered(qt_app, only_english):
    assert i18n.available_languages() == ("tr", "en")


def test_an_empty_translation_file_is_not_offered(qt_app,
                                                  english_and_empty_german):
    """DOSYANIN VARLIĞI YETMEZ: boş `.qm` kullanıcıyı İngilizceye düşürür."""
    assert "de" not in i18n.available_languages()
    assert (TRANSLATIONS.parent / "translations").is_dir()


def test_the_real_project_currently_offers_turkish_and_english(
        qt_app, tmp_path, monkeypatch):
    """Bugünkü GERÇEK depo durumu; altı dil tamamlanınca bu test değişir.

    Ölçüm depodaki `.ts` KAYNAKLARINDAN üretilir, diskte duran bir `.qm`
    kalıntısından değil: `.qm` `.gitignore` içindedir ve temiz bir kopyada
    hiç bulunmaz.
    """
    module = _release_compiler()
    module.compile_all(str(TRANSLATIONS), str(tmp_path))
    monkeypatch.setattr(i18n, "translations_directory", lambda: str(tmp_path))
    i18n.forget_available_languages()
    try:
        assert i18n.available_languages() == ("tr", "en")
    finally:
        i18n.forget_available_languages()


def test_the_installer_set_is_not_narrowed():
    """Kurulum sihirbazı sekiz dilde KALIR; `.ts` dosyaları da öyle."""
    assert len(i18n.SUPPORTED_LANGUAGES) == 8
    for code in i18n.SUPPORTED_LANGUAGES:
        if code == i18n.SOURCE_LANGUAGE:
            continue
        assert (TRANSLATIONS / f"mlcplayer_{code}.ts").is_file(), code


# ── Menü ─────────────────────────────────────────────────────────────────

def test_the_menu_only_offers_available_languages(qt_app, only_english):
    from app.menu_actions import build_language_menu

    actions = [a for a in build_language_menu(None).actions()
               if not a.isSeparator()]
    codes = [a.data() for a in actions if a.data()]
    assert codes == ["tr", "en"]
    assert actions[0].text().startswith("Sistem dili")


# ── Algılama ve kayıtlı tercih ───────────────────────────────────────────

def test_an_unavailable_system_language_falls_back_to_english(qt_app,
                                                              only_english):
    """Alman Windows'ta arayüz İngilizcedir; `de` diye RAPOR EDİLMEZ."""
    assert i18n.detect_language(QLocale("de_DE")) == "en"
    assert i18n.detect_language(QLocale("tr_TR")) == "tr"


def test_a_stored_but_unavailable_preference_is_not_honoured(qt_app,
                                                            only_english,
                                                            isolated_settings):
    """Karşılanamayan tercih sistem diliymiş gibi davranır."""
    isolated_settings.setValue(i18n.SETTINGS_KEY, "de")
    assert i18n.stored_language() == ""
    assert i18n.effective_language(QLocale("tr_TR")) == "tr"


def test_the_stored_value_itself_is_not_erased(qt_app, only_english,
                                               isolated_settings):
    """Almanca tamamlanınca kullanıcının eski tercihi KENDİLİĞİNDEN döner."""
    isolated_settings.setValue(i18n.SETTINGS_KEY, "de")
    i18n.stored_language()
    assert isolated_settings.value(i18n.SETTINGS_KEY) == "de"
