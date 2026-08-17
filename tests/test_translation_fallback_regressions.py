"""Yarım çevrilmiş dilde YEDEK DİL: Türkçe değil, İNGİLİZCE olmalı.

KIRMIZI KANIT (VLC incelemesinden çıktı, 17 Ağustos 2026). VLC'de yedek
davranışı gettext'in kendisinden gelir: bir dizge çevrilmemişse KAYNAK
metin, yani İNGİLİZCE görünür. Gerçek `po/tr.po` ölçüldü: 7684 dizgeden
1833'ü `fuzzy`, 486'sı boş — yani Türkçe VLC'nin yaklaşık dörtte biri
İngilizce çıkar ve kullanıcı bunu anlar.

BİZDE DURUM FARKLI ve daha kötüdür: kaynak dilimiz TÜRKÇE. Qt de aynı
kuralı uygular (çeviri yoksa kaynağı döndür), ama bizim kaynağımız
Türkçe olduğu için yarım çevrilmiş bir Almanca arayüz Almanca + TÜRKÇE
karışımı olur. Alman kullanıcı için Türkçe metin, İngilizce metinden
kesinlikle kötüdür — `app/i18n.py` zaten `FALLBACK_LANGUAGE = "en"`
diyor ama bu YALNIZ dil SEÇİMİNDE uygulanıyordu, dizge düzeyinde
uygulanmıyordu.

Çözüm Qt'nin kendi sözleşmesiyle: hedef dilin çevirmeni İngilizce
çevirmenin ÜSTÜNE kurulur. `QCoreApplication` çevirmenleri son kurulandan
geriye doğru tarar; hedef dilde eksik olan dizge İngilizceye düşer,
İngilizcede de yoksa kaynak Türkçeye düşer.
"""

import subprocess
from pathlib import Path

import pytest

from app import i18n

ROOT = Path(__file__).resolve().parent.parent
ENGLISH_TS = ROOT / "translations" / "mlcplayer_en.ts"

#: Bu dizgeler gerçek üründendir ve İngilizce `.ts` dosyasında ÇEVRİLİDİR.
TRANSLATED_IN_GERMAN = "Çıkış"
MISSING_IN_GERMAN = "Dosya Aç"


def _compile(ts_path, qm_path):
    result = subprocess.run(
        ["pyside6-lrelease", str(ts_path), "-qm", str(qm_path)],
        capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    assert qm_path.is_file()


def _partial_german_ts(path):
    """Tek dizgesi çevrili, biri bilerek eksik bırakılmış Almanca dosya.

    Gerçek durumu taklit eder: `translations/mlcplayer_de.ts` bugün
    tamamen `unfinished`.
    """
    path.write_text(
        "<?xml version='1.0' encoding='utf-8'?>\n"
        '<TS version="2.1" language="de" sourcelanguage="tr">\n'
        "    <context>\n"
        "        <name>MLCPlayer</name>\n"
        "        <message>\n"
        f"            <source>{TRANSLATED_IN_GERMAN}</source>\n"
        "            <translation>Beenden</translation>\n"
        "        </message>\n"
        "        <message>\n"
        f"            <source>{MISSING_IN_GERMAN}</source>\n"
        '            <translation type="unfinished" />\n'
        "        </message>\n"
        "    </context>\n"
        "</TS>\n", encoding="utf-8")


@pytest.fixture
def qt_app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def translations(tmp_path, monkeypatch):
    """Gerçek `translations/` dizinine dokunmadan izole bir kopya kurar."""
    _compile(ENGLISH_TS, tmp_path / "mlcplayer_en.qm")
    _partial_german_ts(tmp_path / "de.ts")
    _compile(tmp_path / "de.ts", tmp_path / "mlcplayer_de.qm")
    monkeypatch.setattr(i18n, "translations_directory", lambda: str(tmp_path))
    return tmp_path


@pytest.fixture(autouse=True)
def clean_translators(qt_app):
    """Kurulan çevirmenler testten sonra KALMAZ; sonraki testler Türkçe görür."""
    yield
    i18n.remove_translators(qt_app)
    assert i18n.tr(MISSING_IN_GERMAN) == MISSING_IN_GERMAN


# ── Asıl kırmızı ─────────────────────────────────────────────────────────

def test_a_missing_german_string_shows_english_not_turkish(qt_app,
                                                           translations):
    """Yarım çevrilmiş Almanca arayüzde eksik dizge İNGİLİZCE görünür."""
    assert i18n.install_translator(qt_app, "de") is True
    assert i18n.tr(TRANSLATED_IN_GERMAN) == "Beenden"
    assert i18n.tr(MISSING_IN_GERMAN) == "Open File"


def test_the_target_language_still_wins_over_english(qt_app, translations):
    """Yedek zinciri hedef dili EZMEZ; sıra yanlışsa her şey İngilizce olur."""
    i18n.install_translator(qt_app, "de")
    assert i18n.tr(TRANSLATED_IN_GERMAN) != "Exit"


def test_english_itself_needs_no_second_translator(qt_app, translations):
    """`en` seçiliyken tek çevirmen kurulur; aynı dosya iki kez yüklenmez."""
    assert i18n.install_translator(qt_app, "en") is True
    assert i18n.tr(MISSING_IN_GERMAN) == "Open File"
    assert len(getattr(qt_app, "_mlc_translators", [])) == 1


def test_the_source_language_installs_nothing(qt_app, translations):
    """Türkçe kaynak dildir; çeviri dosyası yoktur ve aranmaz."""
    assert i18n.install_translator(qt_app, "tr") is False
    assert getattr(qt_app, "_mlc_translators", []) == []


def test_a_language_without_a_file_still_falls_back_to_english(qt_app,
                                                               translations):
    """Rusça `.qm` yok: kullanıcı Türkçe değil İngilizce görmelidir."""
    assert i18n.install_translator(qt_app, "ru") is True
    assert i18n.tr(MISSING_IN_GERMAN) == "Open File"


def test_a_second_install_does_not_stack_translators(qt_app, translations):
    """Aynı uygulamaya iki kez kurulursa eski zincir BIRAKILMAZ."""
    i18n.install_translator(qt_app, "de")
    i18n.install_translator(qt_app, "de")
    assert len(qt_app._mlc_translators) == 2


def test_apply_language_reports_the_chain_was_loaded(qt_app, translations,
                                                     monkeypatch):
    """Açılış yolu (`main.py`) aynı zinciri kurar."""
    monkeypatch.setattr(i18n, "stored_language", lambda: "de")
    code, loaded = i18n.apply_language(qt_app)
    assert (code, loaded) == ("de", True)
    assert i18n.tr(MISSING_IN_GERMAN) == "Open File"
