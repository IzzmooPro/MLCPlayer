# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Ana pakette dağıtılan `mpv-2.dll` için künye ve kaynak erişimi.

KIRMIZI KANIT (ölçüldü, 17 Ağustos 2026). Ana paket `bin/mpv-2.dll`
dosyasını dağıtıyor. Bu ikili GPLv3'tür ve FFmpeg içerir
(`--enable-gpl --enable-version3`). Buna rağmen kurulan pakette:

- mpv/FFmpeg için HİÇBİR künye yok — kullanıcı ne dağıtıldığını göremiyor,
- `bin/RUNTIME_MANIFEST.txt` (sürüm + kaynak URL + SHA-256) PAKETE
  GİRMİYOR; yalnız depoda duruyor,
- `licenses/` klasörü yalnız İnternet Videosu EK PAKETİNDE var, çünkü
  yt-dlp ve deno oradaydı. Ama mpv ANA pakette.

Sonuç: GPLv3'ün karşılık gelen kaynak yükümlülüğü için kullanıcıya
gösterilen tek yer depoydu; kurulu programın yanında hiçbir iz yoktu.

`README.tr.md` içindeki "Yayın öncesi açık maddeler" listesi bunu zaten
kaydediyordu ve madde v0.33 yayımlanana kadar AÇIK kaldı.

Bu dosya künyenin var olduğunu, manifest ile ÇELİŞMEDİĞİNİ ve her ikisinin
de pakete girdiğini kilitler. Künye elle yazılır ama sürüm/URL/özet
manifestten kopyalanır; ayrışırsa test kırılır.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
NOTICE = ROOT / "licenses" / "mpv-NOTICE.txt"
MANIFEST = ROOT / "bin" / "RUNTIME_MANIFEST.txt"
SPEC = ROOT / "MLCPlayer.spec"


def _manifest_row(name):
    """`dosya | surum | kaynak_url | boyut | SHA-256` satırını ayrıştırır."""
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("#") or "|" not in line:
            continue
        parts = [part.strip() for part in line.split("|")]
        if parts[0] == name:
            return parts
    raise AssertionError(f"manifestte satır yok: {name}")


@pytest.fixture(scope="module")
def notice():
    assert NOTICE.is_file(), (
        "ana pakette dağıtılan mpv/FFmpeg için künye dosyası yok")
    return NOTICE.read_text(encoding="utf-8")


# ── Künyenin içeriği ─────────────────────────────────────────────────────

def test_the_notice_names_the_exact_build(notice):
    """Sürüm manifestten gelir; 'bir mpv sürümü' demek künye değildir."""
    version = _manifest_row("mpv-2.dll")[1]
    assert version in notice, version


def test_the_notice_carries_the_source_url_and_digest(notice):
    """Karşılık gelen kaynağa GİDEN adres ve doğrulanabilir özet."""
    _name, _version, url, _size, digest = _manifest_row("mpv-2.dll")
    assert url in notice, url
    assert digest.lower() in notice.lower(), digest


def test_the_notice_states_the_licence_and_where_its_text_is(notice):
    """GPLv3 metni kök `LICENSE` ile AYNIDIR; ikinci kopya taşınmaz."""
    assert "GPLv3" in notice
    assert "LICENSE" in notice


def test_the_notice_points_at_the_upstream_sources(notice):
    """Yalnız derlenmiş arşiv değil, KAYNAK depoları da gösterilir."""
    for source in ("github.com/mpv-player/mpv",
                   "ffmpeg.org",
                   "github.com/shinchiro/mpv-winbuild-cmake"):
        assert source in notice, source


def test_the_notice_does_not_claim_a_nonfree_build(notice):
    """Ölçülen gerçek: bu yapı `--enable-nonfree` TAŞIMAZ."""
    assert "--enable-gpl" in notice
    assert "--enable-version3" in notice
    assert "--enable-nonfree" not in notice.replace(
        "--enable-nonfree taşımaz", "").replace(
        "--enable-nonfree TASIMAZ", "")


# ── Pakete gerçekten giriyor mu ──────────────────────────────────────────

def test_the_main_package_ships_the_notice():
    spec = SPEC.read_text(encoding="utf-8")
    assert "licenses/mpv-NOTICE.txt" in spec, (
        "künye ana pakete girmiyor")


def test_the_main_package_ships_the_runtime_manifest():
    """Kaynak URL ve özetler kurulu programın yanında da bulunmalıdır."""
    spec = SPEC.read_text(encoding="utf-8")
    assert "bin/RUNTIME_MANIFEST.txt" in spec, (
        "runtime manifesti ana pakete girmiyor")


# ── Manifest ile künye ayrışmasın ────────────────────────────────────────

def test_every_binary_in_the_main_package_has_a_licence_text():
    """Ana pakette dağıtılan HER üçüncü taraf ikilisi künyelenmelidir.

    Ana paket yalnız `mpv-2.dll` taşır; `yt-dlp.exe` ve `deno.exe` ek
    pakettedir ve lisans metinleri de ORADA dağıtılır
    (`packaging/MLCPlayer_InternetVideo.iss`).
    """
    spec = SPEC.read_text(encoding="utf-8")
    shipped = set(re.findall(r"\('bin/([^']+)'", spec))
    assert shipped == {"mpv-2.dll", "RUNTIME_MANIFEST.txt"}, shipped

    addon = (ROOT / "packaging" / "MLCPlayer_InternetVideo.iss").read_text(
        encoding="utf-8", errors="replace")
    for name in ("yt-dlp.exe", "deno.exe"):
        assert name in addon, name
    for licence in ("yt-dlp-LICENSE.txt", "yt-dlp-THIRD_PARTY_LICENSES.txt",
                    "deno-LICENSE.txt"):
        assert licence in addon, licence
