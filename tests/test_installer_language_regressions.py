# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Kurulum dili Windows'tan seçilir; kullanıcıya sorulmaz.

KULLANICI KARARI: kurulum sırasında dil sorulmasın, Windows'un dili
kullanılsın; programın kendi dili AYRI bir tercihtir ve ayarlardan
değiştirilir.

TUZAK: `[Languages]` altına birden çok dil eklenip `ShowLanguageDialog`
kapatılmazsa Inno kurulumun BAŞINDA dil seçme penceresi açar. Ayrıca kendi
yazdığımız metinler (`Masaüstü kısayolu oluştur` gibi) dil dosyalarında
YOKTUR; `[CustomMessages]` verilmezse İngilizce kurulumda Türkçe cümle çıkar.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MAIN = ROOT / "packaging" / "MLCPlayer.iss"
ADDON = ROOT / "packaging" / "MLCPlayer_InternetVideo.iss"

#: Birinci ve ikinci dalga (kullanıcı onaylı). Hepsi soldan sağa yazılır.
EXPECTED = ("english", "turkish", "german", "spanish", "french", "italian",
            "russian", "brazilianportuguese")


def _read(path):
    return path.read_text(encoding="utf-8-sig")


def _languages(text):
    section = text.split("[Languages]", 1)[1]
    section = section.split("[", 1)[0]
    return re.findall(r'^Name: "([^"]+)"', section, re.MULTILINE)


@pytest.mark.parametrize("path", [MAIN, ADDON])
def test_the_language_dialog_is_disabled(path):
    assert re.search(r"^ShowLanguageDialog=no\s*$", _read(path), re.MULTILINE), (
        f"{path.name}: kurulum dili kullanıcıya soruluyor")


@pytest.mark.parametrize("path", [MAIN, ADDON])
def test_all_agreed_languages_are_present(path):
    found = _languages(_read(path))
    assert set(EXPECTED) <= set(found), f"{path.name}: eksik {set(EXPECTED) - set(found)}"


@pytest.mark.parametrize("path", [MAIN, ADDON])
def test_english_is_first(path):
    """Sistem dili listede yoksa Inno İLK dile düşer.

    Türkçe ilk sırada olsaydı, dili listede olmayan bir kullanıcı Türkçe
    kurulum ekranıyla karşılaşırdı.
    """
    assert _languages(_read(path))[0] == "english", path.name


def test_our_own_strings_exist_for_every_language():
    """`[CustomMessages]` eksikse İngilizce kurulumda Türkçe metin çıkar."""
    text = _read(MAIN)
    section = text.split("[CustomMessages]", 1)[1].split("\n[", 1)[0]
    for language in EXPECTED:
        for key in ("DesktopIcon", "LaunchApp", "OpenRepository"):
            assert f"{language}.{key}=" in section, f"eksik: {language}.{key}"


def test_the_addon_error_is_translated():
    section = _read(ADDON).split("[CustomMessages]", 1)[1].split("\n[", 1)[0]
    for language in EXPECTED:
        assert f"{language}.PlayerRequired=" in section, language


def test_no_hardcoded_turkish_in_user_facing_entries():
    """Görev/çalıştırma açıklamaları dil dosyasından gelmelidir."""
    text = _read(MAIN)
    for line in text.splitlines():
        if line.startswith(("Name: \"desktopicon\"", "Filename:")):
            assert not re.search(r"[şğıöçüŞĞİÖÇÜ]", line), (
                f"sabit Türkçe metin: {line}")


def test_the_player_language_is_a_separate_preference():
    """Kurulum dili programın dilini BELİRLEMEZ; ikisi ayrı tercihtir."""
    assert "ayarlardan" in _read(MAIN).lower() or \
        "AYRI" in _read(MAIN), "karar belgelenmemiş"
