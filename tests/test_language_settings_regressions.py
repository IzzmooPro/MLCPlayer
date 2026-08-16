"""Program dili: Windows'tan algılanır, kullanıcı ayarlardan değiştirir.

AŞAMA A — ALTYAPI. Bu turda HİÇBİR ürün metni değişmez; yalnız dilin
seçilmesi, saklanması ve yüklenmesi kurulur.

NEDEN BÖYLE: 38 ürün dosyasında Türkçe arayüz metni var ve 105 test
dosyasındaki 453 assert doğrudan bu metinlere bakıyor. Kaynak dil TÜRKÇE
KALIR; `tr()` çeviri yüklü değilken kaynağı döndürdüğü için mevcut davranış
ve testler DEĞİŞMEZ. Diğer diller üstüne eklenir.
"""

from pathlib import Path

import pytest
from PyQt6.QtCore import QLocale

from app import i18n

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    """Gerçek kullanıcı ayarına dokunulmaz (CLAUDE.md kuralı)."""
    from PyQt6.QtCore import QSettings
    store = QSettings(str(tmp_path / "dil.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(i18n, "_settings", lambda: store)
    return store


# ── Desteklenen diller ───────────────────────────────────────────────────

def test_turkish_is_the_source_language():
    """Kaynak dil değişirse 453 assert'in tamamı kırılır."""
    assert i18n.SOURCE_LANGUAGE == "tr"


def test_the_supported_set_matches_the_installer():
    """Kurulum 8 dil sunuyorsa program da aynı 8 dili sunmalıdır."""
    assert set(i18n.SUPPORTED_LANGUAGES) == {
        "en", "tr", "de", "es", "fr", "it", "ru", "pt_BR"}


def test_every_language_has_a_name_in_its_own_tongue():
    """Ayar menüsünde kullanıcı kendi dilini tanıyabilmelidir."""
    for code in i18n.SUPPORTED_LANGUAGES:
        name = i18n.language_name(code)
        assert name and name != code, code


# ── Windows'tan algılama ─────────────────────────────────────────────────

@pytest.mark.parametrize("system,expected", [
    ("tr_TR", "tr"),
    ("en_US", "en"),
    ("en_GB", "en"),
    ("de_DE", "de"),
    ("pt_BR", "pt_BR"),
    ("pt_PT", "en"),      # Portekiz Portekizcesi YOK -> yedek dile düşer
    ("ja_JP", "en"),      # desteklenmeyen dil -> yedek
])
def test_the_system_language_decides_the_default(system, expected):
    assert i18n.detect_language(QLocale(system)) == expected


def test_the_fallback_is_english_not_turkish():
    """Dili listede olmayan kullanıcıya Türkçe arayüz vermek çıkmaz sokaktır."""
    assert i18n.FALLBACK_LANGUAGE == "en"
    assert i18n.detect_language(QLocale("ko_KR")) == "en"


# ── Kullanıcı tercihi ────────────────────────────────────────────────────

def test_no_stored_preference_means_follow_windows(isolated_settings):
    assert i18n.stored_language() == ""
    assert i18n.effective_language(QLocale("de_DE")) == "de"


def test_a_stored_preference_wins_over_windows(isolated_settings):
    i18n.store_language("ru")
    assert i18n.stored_language() == "ru"
    assert i18n.effective_language(QLocale("de_DE")) == "ru"


def test_an_unknown_stored_value_is_ignored(isolated_settings):
    """Elle bozulmuş ayar programı kilitlememeli."""
    isolated_settings.setValue(i18n.SETTINGS_KEY, "klingon")
    assert i18n.effective_language(QLocale("de_DE")) == "de"


def test_following_windows_can_be_restored(isolated_settings):
    i18n.store_language("ru")
    i18n.store_language("")           # "Sistem dili" seçeneği
    assert i18n.stored_language() == ""
    assert i18n.effective_language(QLocale("fr_FR")) == "fr"


# ── Çeviri yükleme ───────────────────────────────────────────────────────

def test_the_source_language_loads_no_translator():
    """Türkçe kaynak dildir; çeviri dosyası aranmaz."""
    assert i18n.translation_file("tr") == ""


def test_other_languages_look_for_their_own_file():
    assert i18n.translation_file("de").endswith("mlcplayer_de.qm")
    assert i18n.translation_file("pt_BR").endswith("mlcplayer_pt_BR.qm")


def test_a_missing_translation_never_breaks_the_program(tmp_path, monkeypatch):
    """Çeviri dosyası yoksa program Türkçe açılır, ÇÖKMEZ.

    Aşama A'da .qm dosyaları henüz üretilmedi; bu yol bugünkü gerçektir.
    """
    monkeypatch.setattr(i18n, "translations_directory", lambda: str(tmp_path))
    assert i18n.install_translator(None, "de") is False


def test_the_language_change_needs_a_restart_notice():
    """Qt widget arayüzünde canlı dil değişimi her pencereyi yeniden kurmayı
    gerektirir; bu turda RİSK ALINMAZ ve kullanıcıya açıkça söylenir."""
    assert i18n.RESTART_REQUIRED_MESSAGE
    assert "yeniden" in i18n.RESTART_REQUIRED_MESSAGE.lower()


# ── Ayar menüsü ve açılış bağlantısı ─────────────────────────────────────

def test_the_menu_offers_system_plus_every_language(qt_app_for_menu):
    """Kullanıcı dili programın kendi ayarından değiştirebilmelidir."""
    from app.menu_actions import build_language_menu

    menu = build_language_menu(None)
    actions = [a for a in menu.actions() if not a.isSeparator()]
    assert len(actions) == len(i18n.SUPPORTED_LANGUAGES) + 1
    assert actions[0].text().startswith("Sistem dili")
    codes = [a.data() for a in actions if a.data()]
    assert codes == list(i18n.SUPPORTED_LANGUAGES)


def test_the_menu_marks_the_current_choice(qt_app_for_menu, isolated_settings):
    from app.menu_actions import build_language_menu

    i18n.store_language("de")
    actions = [a for a in build_language_menu(None).actions()
               if not a.isSeparator()]
    checked = [a.text() for a in actions if a.isChecked()]
    assert checked == [i18n.language_name("de")]


def test_the_startup_path_applies_the_language():
    """Dil, pencereler kurulmadan ÖNCE uygulanmalı; sonra menüler geç kalır."""
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "apply_language(app)" in source
    assert source.index("apply_language(app)") < source.index("MPVPlayer()")


@pytest.fixture
def qt_app_for_menu():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])
