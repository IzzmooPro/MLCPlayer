"""Hakkında penceresi lisansı, garanti reddini ve kaynak adresini gösterir.

KIRMIZI KANIT (17 Ağustos 2026). Pencere yalnız şunları taşıyordu: ürün
adı, sürüm, bir cümlelik tanım, özellik listesi ve `© 2025`. Lisans adı
YOK, garanti reddi YOK, kaynak kodun adresi YOK.

Bu üçü keyfî değildir:

- GPLv3, etkileşimli bir programın uygun TELİF UYARISINI ve GARANTİ
  REDDİNİ göstermesini bekler. `LICENSE` dosyası pakette duruyordu ama
  kullanıcının onu açması gerekiyordu.
- GPLv3 §6 karşılık gelen KAYNAĞA erişim ister. Kurulu programda o adrese
  giden hiçbir iz yoktu.
- Telif YILI da çelişiyordu: README `2026`, pencere `2025`.

VLC'nin Hakkında penceresinde ayrı bir "License" sekmesi vardır; aynı
işlevi tek bir blokla veriyoruz. Metinler `tr()` ile sarmalanır — bunlar
kullanıcıya GÖRÜNEN metinlerdir.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


class AboutPlayer:
    """`show_about()` yalnız `QMessageBox.about()` çağırır; pencere sahte."""

    def __init__(self):
        self.shown = []


@pytest.fixture
def about_text(monkeypatch):
    from app import menu_actions

    captured = {}

    def fake_about(parent, title, text):
        captured["title"] = title
        captured["text"] = text

    monkeypatch.setattr(menu_actions.QMessageBox, "about", fake_about)
    menu_actions.show_about(AboutPlayer())
    assert captured, "show_about() hiçbir pencere göstermedi"
    return captured


# ── Lisans ───────────────────────────────────────────────────────────────

def test_the_licence_is_named(about_text):
    """Kullanıcı hangi lisans altında olduğunu pencerede görmelidir."""
    assert "GPL" in about_text["text"]
    assert "3" in about_text["text"]


def test_the_warranty_disclaimer_is_shown(about_text):
    """GPLv3'ün beklediği GARANTİ REDDİ; `LICENSE` dosyasına havale edilmez."""
    text = about_text["text"].lower()
    assert "garanti" in text or "warranty" in text


def test_the_source_address_is_reachable_from_the_window(about_text):
    """GPLv3 §6: karşılık gelen kaynağa giden yol kurulu programda olmalı."""
    from app.updater import GITHUB_URL

    assert GITHUB_URL in about_text["text"]


def test_the_third_party_components_are_mentioned(about_text):
    """mpv/FFmpeg ana pakette dağıtılıyor; künyeye yol gösterilmelidir."""
    text = about_text["text"]
    assert "mpv" in text.lower()
    assert "licenses" in text.lower() or "NOTICE" in text


# ── Telif ────────────────────────────────────────────────────────────────

def test_the_copyright_year_matches_the_readme(about_text):
    """İki yerde iki farklı yıl yazmak dikkatsizlik izlenimi verir."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    match = re.search(r"Copyright \(C\) (\d{4})", readme)
    assert match, "README'de telif satırı yok"
    assert match.group(1) in about_text["text"]


def test_the_window_still_describes_the_product(about_text):
    """Lisans bloğu eklenirken tanıtım İÇERİĞİ kaybolmamalı."""
    text = about_text["text"]
    assert "MLC Player" in text
    assert "Media Launch Codec Player" in text


# ── Çeviri ───────────────────────────────────────────────────────────────

def test_the_licence_sentences_are_translatable():
    """Kullanıcıya görünen her cümle katalogda olmalı."""
    import importlib.util

    path = ROOT / "packaging" / "extract_translations.py"
    spec = importlib.util.spec_from_file_location("mlc_extract_about", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    texts, _dynamic = module.collect()

    marker = [text for text in texts
              if "garanti" in text.lower() or "warranty" in text.lower()]
    assert marker, "garanti reddi çeviri kataloğunda yok"
