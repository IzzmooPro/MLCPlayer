# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""İnternet videosu bileşenleri AYRI ek paketle gelir.

ÖLÇÜLEN SORUN: kurulu paket 304,7 MB idi ve bunun 110,3 MB'ı yalnız URL'den
oynatmada kullanılan iki dosyaydı (`deno.exe` 92,9 MB, `yt-dlp.exe` 17,4 MB).
Yerel dosya oynatan kullanıcı bu yükü taşımak zorunda değildir.

DEĞİŞMEZ KORUNDU: `app/runtime_binaries.py` "URL açılırken bileşen
İNDİRİLMEZ" der. Bu yüzden çözüm otomatik indirme DEĞİL, kullanıcının açık
eylemiyle kurulan ek pakettir.
"""

import re
from pathlib import Path

from app import runtime_binaries as runtime

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "MLCPlayer.spec"
ADDON_ISS = ROOT / "packaging" / "MLCPlayer_InternetVideo.iss"
CHAIN = ROOT / "packaging" / "build_release.bat"


def test_the_base_package_does_not_carry_the_internet_binaries():
    """110 MB ana paketten çıktı; aksi hâlde bölmenin anlamı kalmaz."""
    spec = SPEC.read_text(encoding="utf-8")
    for entry in ("('bin/yt-dlp.exe', 'bin')", "('bin/deno.exe', 'bin')"):
        assert entry not in spec, f"ana pakete geri girmiş: {entry}"
    # mpv çekirdektir ve KALIR.
    assert "('bin/mpv-2.dll', 'bin')" in spec


def test_the_addon_installs_both_binaries_and_their_licences():
    iss = ADDON_ISS.read_text(encoding="utf-8-sig")
    for name in ("yt-dlp.exe", "deno.exe"):
        assert f"..\\bin\\{name}" in iss, f"ek pakette {name} yok"
    # GPLv3/MIT: lisans metni ikiliyle BİRLİKTE dağıtılmalıdır.
    for licence in ("yt-dlp-LICENSE.txt", "yt-dlp-THIRD_PARTY_LICENSES.txt",
                    "deno-LICENSE.txt"):
        assert licence in iss, f"lisans metni eksik: {licence}"


def test_the_addon_writes_into_the_players_own_folder():
    """Ürün ikilileri YALNIZ kendi `bin` dizininde arar."""
    iss = ADDON_ISS.read_text(encoding="utf-8-sig")
    assert '{app}\\_internal\\bin' in iss
    assert "DefaultDirName={code:PlayerDirectory}" in iss


def test_the_addon_refuses_to_run_without_the_player():
    """Oynatıcı kurulu değilse dosyalar rastgele bir yere bırakılmamalı."""
    iss = ADDON_ISS.read_text(encoding="utf-8-sig")
    assert "function InitializeSetup" in iss
    # Uyarı metni artık ÇEVRİLEBİLİR: sabit Türkçe cümle yerine dil
    # dosyasından gelir (bkz. tests/test_installer_language_regressions.py).
    assert "{cm:PlayerRequired}" in iss
    assert "english.PlayerRequired=" in iss


def test_the_addon_has_its_own_identity():
    """Ayrı kaldırılabilmeli; ana programın kaydını ezmemeli."""
    iss = ADDON_ISS.read_text(encoding="utf-8-sig")
    player_id = "EB0DD5CF-F20B-4B23-A1C9-2C23A83A8758"
    match = re.search(r"^AppId=\{\{([0-9A-Fa-f-]+)", iss, re.MULTILINE)
    assert match, "ek paketin AppId'si yok"
    assert match.group(1).upper() != player_id, "ana programla aynı kimlik"


def test_the_chain_builds_and_signs_the_addon():
    chain = CHAIN.read_text(encoding="utf-8", errors="ignore")
    assert "MLCPlayer_InternetVideo.iss" in chain, "zincir ek paketi üretmiyor"
    assert "ADDON_TO_SIGN" in chain, "ek paket imzalanmıyor"


def test_the_product_still_handles_the_missing_runtime_safely():
    """Bileşen yokken program çalışmaya devam eder, yalnız URL yolu kapanır."""
    assert runtime.internet_video_ready("C:\\yok-boyle-bir-dizin") is False
    assert runtime.missing_runtime_components("C:\\yok") == ("yt-dlp", "deno")
    assert runtime.ytdl_script_opt("C:\\yok") == ""


def test_the_message_points_at_the_addon_without_leaking_details():
    message = runtime.INTERNET_VIDEO_MISSING_MESSAGE
    assert "ek paket" in message.lower(), "kullanıcı ne yapacağını bilmeli"
    for forbidden in ("Traceback", "pip install", "yt-dlp", "deno", "C:\\",
                      "http"):
        assert forbidden not in message


def test_the_no_silent_download_invariant_is_still_written_down():
    """Ek paket kararı, 'kendiliğinden indirme yok' değişmezini bozmaz."""
    source = (ROOT / "app" / "runtime_binaries.py").read_text(encoding="utf-8")
    assert "INDIRILMEZ" in source
    assert "ek paket" in source.lower()
