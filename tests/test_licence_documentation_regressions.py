# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Herkese açık lisans belgeleri GERÇEĞİ anlatmalıdır.

KIRMIZI KANIT (17 Ağustos 2026). `README.tr.md` içindeki "Yayın öncesi
açık maddeler" listesi PUBLIC bir depoda duruyor ve artık YANLIŞTI:

- "GPLv3'ün önerdiği dosya başı telif/lisans bildirimlerinin eklenmesi"
  maddesi hâlâ AÇIK görünüyordu; oysa 228 Python dosyası + 5 betik SPDX
  başlığı taşıyor.
- Başlık "dağıtımdan önce kapatılmalıdır" diyor ama `v0.33` YAYINDA.
  Yani liste bir kontrol listesi değil, kapanmamış bir söz gibi duruyor.

`README.md` tarafında da iki eksik vardı: kullandığımız SPDX kimliği
(`GPL-3.0-only`) hiç geçmiyordu ve mpv için gösterilen tek belge
`bin/RUNTIME_MANIFEST.txt`ti — o PROVENANCE dosyasıdır, künye değil.
Künye `licenses/mpv-NOTICE.txt`tir ve karşılık gelen kaynağa giden yolu
orada tarif ediyoruz.

NEDEN AYRI BİR `LICENSING.md` AÇILMADI: konsolidasyon zaten README'nin
lisans bölümünde. Beşinci bir yer eklemek bilgiyi ÇOĞALTIR ve ayrışma
riskini artırır; bugün ayrışan da tam olarak bu oldu.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def licence_section(name):
    text = (ROOT / name).read_text(encoding="utf-8")
    marker = "## Licence" if name == "README.md" else "## Lisans"
    assert marker in text, f"{name}: lisans bölümü yok"
    return text.split(marker, 1)[1]


def open_items_section():
    text = (ROOT / "README.tr.md").read_text(encoding="utf-8")
    marker = "### Yayın öncesi açık maddeler"
    assert marker in text, "açık maddeler bölümü yok"
    body = text.split(marker, 1)[1]
    # Bir sonraki başlığa kadar.
    for stop in ("\n## ", "\n### "):
        if stop in body:
            body = body.split(stop, 1)[0]
    # YALNIZ açık kısım. "Kapanan maddeler" alt listesi aynı konuları
    # ADIYLA anar; onu da taramak kapananları açık sanmaya yol açıyordu.
    return body.split("**Kapanan maddeler:**", 1)[0]


# ── Kapanan maddeler AÇIK gösterilemez ───────────────────────────────────

def test_the_per_file_notices_are_not_listed_as_open():
    """228 dosya + 5 betik SPDX taşıyor; madde KAPANDI."""
    body = open_items_section()
    assert "dosya başı" not in body.lower(), (
        "kapanan madde hâlâ açık gösteriliyor")


def test_the_about_window_notice_is_not_listed_as_open():
    """Hakkında penceresi lisansı, garanti reddini ve kaynağı gösteriyor."""
    body = open_items_section().lower()
    assert "hakkında penceresi" not in body


def test_the_list_does_not_claim_these_block_distribution():
    """`v0.33` YAYINDA; "dağıtımdan önce kapatılmalıdır" artık doğru değil."""
    body = open_items_section()
    assert "dağıtımdan önce kapatılmalıdır" not in body


# ── Gerçekten açık olanlar DURMALI ───────────────────────────────────────

def test_the_closed_items_are_recorded_as_closed():
    """Kapananlar sessizce SİLİNMEZ; neyin ne zaman kapandığı kalmalı."""
    text = (ROOT / "README.tr.md").read_text(encoding="utf-8")
    assert "**Kapanan maddeler:**" in text
    closed = text.split("**Kapanan maddeler:**", 1)[1].lower()
    for topic in ("dosya başı", "hakkında penceresi", "karşılık gelen kaynak"):
        assert topic in closed, topic


def test_the_genuinely_open_items_are_still_listed():
    """Kapanmayanlar sessizce silinmemeli; üçü de kullanıcı/hukukçu işi."""
    body = open_items_section().lower()
    for topic in ("patent", "opensubtitles"):
        assert topic in body, topic


# ── README lisans bölümü ─────────────────────────────────────────────────

def test_the_readme_names_the_spdx_identifier():
    """Kaynak dosyalarda kullandığımız kimlik belgede de görünmeli."""
    assert "GPL-3.0-only" in licence_section("README.md")


def test_the_readme_points_at_the_mpv_notice_not_just_the_manifest():
    """`RUNTIME_MANIFEST` provenance'tır; künye `licenses/mpv-NOTICE.txt`."""
    section = licence_section("README.md")
    assert "licenses/mpv-NOTICE.txt" in section


def test_the_readme_states_how_to_get_the_corresponding_source():
    """GPLv3 §6: ikiliyi dağıtan, kaynağa erişimi de tarif etmelidir."""
    section = licence_section("README.md").lower()
    assert "corresponding source" in section


def test_both_readmes_agree_on_the_licence():
    for name in ("README.md", "README.tr.md"):
        section = licence_section(name)
        assert "GPL" in section and "3" in section, name
