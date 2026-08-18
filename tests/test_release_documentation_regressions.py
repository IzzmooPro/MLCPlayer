# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Yayin sureci TEK RESMI BELGEDE tutulur.

OLCULEN SORUN (17 Agustos 2026): kesin yayin sirasi UC yerde birden
yaziliydi -- `CLAUDE.md`, `docs/PACKAGING_PLAN.md` ve
`packaging/prepublish.py` docstring'i. Uc kopya elle esit tutuluyordu;
birini degistiren digerlerini unutabilirdi ve hangisinin dogru oldugu
belirsiz kalirdi.

SOZLESME: ayrintili a-j sirasi YALNIZ `docs/RELEASE_PROCESS.md`
icindedir. Digerleri kritik degismezleri OZETLER ve ona BAGLANIR.

Bu dosya belgeleri OLCER; urun davranisini olcmez.
"""
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RELEASE_DOC = os.path.join(ROOT, "docs", "RELEASE_PROCESS.md")
AUDIT_DOC = os.path.join(ROOT, "docs", "ENGINEERING_AUDIT.md")
ROADMAP_DOC = os.path.join(ROOT, "docs", "ROADMAP.md")
CLAUDE_DOC = os.path.join(ROOT, "CLAUDE.md")
PACKAGING_DOC = os.path.join(ROOT, "docs", "PACKAGING_PLAN.md")
PREPUBLISH = os.path.join(ROOT, "packaging", "prepublish.py")

#: Ayrintili sira isareti: satir basinda `a)` ... `j)`.
STEP_MARKER = re.compile(r"^\s*[a-j]\)", re.MULTILINE)

#: Belge durum sozlugu. "TAMAMLANDI" yalniz test + canli kabul varsa.
STATUS_WORDS = (
    "KANITLANDI", "UYGULANDI", "HEDEF TESTLERLE DOGRULANDI",
    "CANLI KABUL BEKLIYOR", "COMMIT BEKLIYOR", "TAMAMLANDI", "ERTELENDI",
)


#: Turkce -> ASCII katlama. Testin ilk surumu yalniz `ı` ve birkac harfi
#: ceviriyordu; "Amac" ararken belgedeki "Amaç" kacti ve DOGRU belge
#: yanlis raporlandi. Katlama TEK yerde ve TAM yapilir.
_FOLD = str.maketrans({
    "ı": "i", "İ": "I", "ş": "s", "Ş": "S", "ğ": "g", "Ğ": "G",
    "ü": "u", "Ü": "U", "ö": "o", "Ö": "O", "ç": "c", "Ç": "C",
    "â": "a", "Â": "A", "î": "i", "û": "u",
})


def fold(text):
    """ASCII'ye katlanmis metin (buyuk/kucuk duyarsiz karsilastirma icin)."""
    return text.translate(_FOLD)


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


# --- 1. Resmi kaynak var ve kendini oyle tanimliyor --------------------

def test_the_release_process_document_exists():
    assert os.path.isfile(RELEASE_DOC), "docs/RELEASE_PROCESS.md yok"


def test_it_declares_itself_the_single_official_source():
    text = fold(read(RELEASE_DOC)).upper()

    assert "TEK RESM" in text, (
        "belge kendini tek resmi kaynak olarak tanimlamiyor")


@pytest.mark.parametrize("heading", [
    "Amac", "yetki", "prepublish", "annotated", "sekiz", "onay",
])
def test_the_release_document_covers_every_required_topic(heading):
    text = fold(read(RELEASE_DOC)).lower()

    assert fold(heading).lower() in text, (
        f"RELEASE_PROCESS.md '{heading}' konusunu islemiyor")


# --- 2. Ayrintili sira YALNIZ resmi belgede ---------------------------

def test_the_detailed_order_lives_only_in_the_release_document():
    """a-j listesi TEK yerde. Kopya, sessiz ayrisma demektir."""
    assert len(STEP_MARKER.findall(read(RELEASE_DOC))) >= 10, (
        "resmi belgede tam a-j sirasi yok")

    for path in (CLAUDE_DOC, PACKAGING_DOC, PREPUBLISH):
        found = STEP_MARKER.findall(read(path))
        assert len(found) < 8, (
            f"{os.path.basename(path)} ayrintili sirayi TEKRAR ediyor: "
            f"{len(found)} adim isareti")


@pytest.mark.parametrize("path", [CLAUDE_DOC, PACKAGING_DOC, PREPUBLISH])
def test_every_other_place_links_to_the_official_document(path):
    assert "RELEASE_PROCESS.md" in read(path), (
        f"{os.path.basename(path)} resmi belgeye baglanmiyor")


# --- 3. Kritik degismezler ozet olarak KORUNUR ------------------------

@pytest.mark.parametrize("path", [CLAUDE_DOC, PACKAGING_DOC, PREPUBLISH,
                                  RELEASE_DOC])
def test_the_target_master_ban_is_documented(path):
    text = read(path)

    assert "--target master" in text, (
        f"{os.path.basename(path)} `--target master` yasagini yazmiyor")


@pytest.mark.parametrize("flag", ["--verify-tag", "--draft"])
def test_the_release_command_flags_are_mandatory(flag):
    text = read(RELEASE_DOC)

    assert flag in text, f"resmi belgede {flag} yok"


def test_the_tag_is_never_created_before_the_build():
    """Kritik kural: tag ve push build'den ONCE yapilmaz."""
    for path in (RELEASE_DOC, CLAUDE_DOC, PREPUBLISH):
        text = fold(read(path)).upper()
        assert "BUILD" in text and "ONCE" in text, (
            f"{os.path.basename(path)} tag/push sirasini yazmiyor")


# --- 4. Sekiz varlik ve SHA-256 esligi --------------------------------

def test_the_eight_asset_contract_is_recorded():
    text = fold(read(RELEASE_DOC)).lower()

    assert "sekiz" in text or "8 varlik" in text, "sekiz varlik yazmiyor"
    for name in ("MLCPlayer_Setup", "MLCPlayer_InternetVideo",
                 ".sig", "source_mirror"):
        assert name.lower() in text, f"varlik sozlesmesinde eksik: {name}"


def test_the_local_and_remote_digest_match_is_required():
    text = read(RELEASE_DOC).upper()

    assert "SHA-256" in text, "SHA-256 esligi yazmiyor"
    assert "BOYUT" in text or "SIZE" in text, "boyut esligi yazmiyor"


def test_the_remote_annotated_tag_check_is_executable():
    """Uzak dogrulama CALISTIRILABILIR bicimde yazili olmali."""
    text = read(RELEASE_DOC)

    assert "refs/tags/" in text
    assert "^{}" in text, "annotated tag peel (`^{}`) yazilmamis"
    assert "rev-parse HEAD" in text


# --- 5. Yetkilendirme: her adim AYRI onay -----------------------------

def test_each_outward_step_needs_its_own_approval():
    text = fold(read(RELEASE_DOC)).lower()

    for word in ("build", "commit", "push", "tag", "release"):
        assert word in text, f"onay listesinde eksik: {word}"
    assert "ayri" in text, (
        "adimlarin AYRI onay gerektirdigi yazilmamis")


# --- 6. Tarihsel kusur: yalniz KANITLANAN ifadeler --------------------

def test_the_historical_tag_defect_is_recorded_with_evidence():
    text = read(RELEASE_DOC)

    assert "v0.35" in text and "v0.36" in text
    assert "2804c2f" in text and "5b987d1" in text, (
        "tarihsel kusur commit kanitiyla yazilmamis")


def test_no_unproven_claim_about_what_users_installed():
    """OLCULMEYEN sey iddia EDILMEZ.

    Release EXE'lerinin IC surumu bu incelemede olculmedi; belgeler
    kullaniciya ne kuruldugu hakkinda iddiada bulunamaz.
    """
    for path in (RELEASE_DOC, AUDIT_DOC, CLAUDE_DOC, PACKAGING_DOC):
        text = fold(read(path)).lower()
        assert "indirip" not in text, f"{os.path.basename(path)}: kanitsiz iddia"
        assert "kurdu" not in text, f"{os.path.basename(path)}: kanitsiz iddia"


def test_historical_tags_are_declared_untouched():
    text = fold(read(RELEASE_DOC)).lower()

    assert "tasinmaz" in text or "degistirilmez" in text, (
        "gecmis tag'lerin tasinmayacagi yazilmamis")


# --- 6b. Release komutu GERCEKTEN calistirilabilir olmali -------------

MIRROR_PATHS = (
    "source_mirror/mpv-dev-x86_64-20260814-git-7b8915bc1d.7z",
    "source_mirror/yt-dlp.exe",
    "source_mirror/deno-x86_64-pc-windows-msvc.zip",
    "source_mirror/yt-dlp-THIRD_PARTY_LICENSES.txt",
)

INSTALLER_PATHS = (
    "installer_output/MLCPlayer_Setup_vX.Y.exe",
    "installer_output/MLCPlayer_Setup_vX.Y.exe.sig",
    "installer_output/MLCPlayer_InternetVideo_vX.Y.exe",
    "installer_output/MLCPlayer_InternetVideo_vX.Y.exe.sig",
)


@pytest.mark.parametrize("path", INSTALLER_PATHS + MIRROR_PATHS)
def test_the_release_example_lists_all_eight_exact_paths(path):
    """Sekiz varligin TAMAMI kesin yol olarak yazili olmali."""
    assert path in read(RELEASE_DOC), f"release orneginde eksik: {path}"


def test_the_release_example_has_no_unrunnable_placeholder():
    """`<dort kaynak/lisans dosyasi>` gibi bir yer tutucu CALISTIRILAMAZ."""
    text = fold(read(RELEASE_DOC)).lower()

    assert "<dort kaynak" not in text, "calistirilamayan yer tutucu duruyor"
    assert "<kaynak/lisans" not in text


def test_the_release_command_uses_no_backslash_continuation():
    """Ters bolu satir devami Windows PowerShell/cmd'de CALISMAZ.

    Belge Windows icin yazilmistir; kopyalanip calistirilabilmelidir.
    """
    text = read(RELEASE_DOC)
    guilty = [line for line in text.splitlines()
              if line.rstrip().endswith("\\") and "gh release" not in line
              and ("installer_output" in line or "source_mirror" in line
                   or "--" in line)]

    assert guilty == [], f"ters bolu satir devami kullanilmis: {guilty}"


def test_the_release_example_is_powershell_shaped():
    """PowerShell dizi/splat ya da tek satir olmali."""
    text = read(RELEASE_DOC)

    assert "gh release create" in text
    assert ("@(" in text or "$assets" in text
            or "--draft " in text), "PowerShell'de calistirilabilir bicim yok"


# --- 6c. Salt-okunur araclarin TARIFI dogru olmali --------------------

def test_read_only_tools_are_described_accurately():
    """`Git'e dokunmaz` YANLIS: araclar salt-okunur Git sorgusu calistirir.

    `verify_release_ref` ve `prepublish` `git rev-parse`, `git show` ve
    `git status` calistirir. Dogru ifade "durumu DEGISTIRMEZ"tir.
    """
    text = fold(read(RELEASE_DOC)).lower()

    assert "git'e dokunmaz" not in text, "gevsek/yanlis ifade duruyor"
    assert "salt-okunur" in text and "git sorgu" in text, (
        "salt-okunur Git sorgulari calistirdigi yazilmamis")
    assert "degistirmez" in text, "durum degistirmedigi yazilmamis"
    assert "ag kullanmaz" in text or "aga cikmaz" in text


# --- 6c2. `git ls-remote` AGSIZ araclarin ornegi OLAMAZ ---------------

def local_tools_section():
    """Agsiz araclarin CALISTIRDIGI ornekleri listeleyen bolum.

    Sinir, `ls-remote`u DISLAYAN paragrafta biter: o paragrafin adi
    gecirmesi mesrudur, cunku tam da onu haric tuttugunu soyler.
    """
    text = read(RELEASE_DOC)
    start = text.index("Salt-okunur denetimler")
    end = text.index("**`git ls-remote` bu listede")
    return text[start:end]


def step_g_section():
    """Adim (g) blogu: uzak annotated tag dogrulamasi."""
    text = read(RELEASE_DOC)
    start = text.index("    g)")
    return text[start:text.index("    h)")]


def test_the_offline_tool_examples_do_not_include_ls_remote():
    """`git ls-remote` AG KULLANIR; agsiz araclarin ornegi olamaz.

    Bu ifade onceki turda yanlislikla "ag kullanmaz" listesine
    konmustu -- kendi icinde celiskiliydi, cunku ayni belge onu uzak
    dogrulama adiminda kullaniyor.
    """
    section = local_tools_section()

    assert "ls-remote" not in section, (
        "agsiz arac ornekleri arasinda `git ls-remote` duruyor")
    for example in ("git rev-parse", "git show", "git status"):
        assert example in section, f"yerel ornek eksik: {example}"


def test_ls_remote_is_scoped_to_the_remote_verification_step():
    """`ls-remote` YALNIZ adim (g)'de gecer ve ag kullandigi yazilidir."""
    assert "ls-remote" in step_g_section(), (
        "adim (g) uzak tag dogrulamasini `ls-remote` ile yazmiyor")

    text = fold(read(RELEASE_DOC)).lower()
    assert "ls-remote" in text and "ag kullan" in text, (
        "`ls-remote`un ag kullandigi belirtilmemis")


def test_the_offline_tools_are_declared_not_to_call_ls_remote():
    """Uc yerel aracin `ls-remote` CAGIRMADIGI acikca yazili olmali."""
    text = fold(read(RELEASE_DOC))

    for tool in ("prepublish.py", "verify_release_ref.py",
                 "verify_build.py --pre"):
        assert tool in text, f"yerel arac anilmamis: {tool}"
    lowered = text.lower()
    assert "cagrilmaz" in lowered or "cagirmaz" in lowered, (
        "yerel araclarin `ls-remote` cagirmadigi yazilmamis")


# --- 6d. "Ag yok" davranisi ASAMAYA gore ayrilmali -------------------

def test_the_no_network_behaviour_is_split_by_phase():
    """Build asamasinda ag yoklugu ile publish asamasinda AYNI DEGILDIR.

    (b) `check_publishable` uyarir ve devam eder; (g)/(h)/(i) uzak
    dogrulama YAPILAMAZ, yayin DURUR.
    """
    text = fold(read(RELEASE_DOC)).lower()

    assert "ag yok" in text
    # Iki ayri satir/kayit olmali: biri devam eder, biri durur.
    build_phase = "check_publishable" in text and "uyar" in text
    publish_phase = ("uzak" in text and "durur" in text)
    assert build_phase, "build asamasindaki ag yoklugu tarif edilmemis"
    assert publish_phase, "publish asamasindaki ag yoklugu tarif edilmemis"

    # Tek ve genel bir "durmaz" satiri BIRAKILMAMALI.
    rows = [line for line in fold(read(RELEASE_DOC)).splitlines()
            if line.strip().startswith("|") and "Ag yok" in line]
    assert len(rows) >= 2, (
        f"'Ag yok' asamaya gore ayrilmamis; bulunan satir: {rows}")


# --- 7. Denetim kaydi -------------------------------------------------

def test_the_audit_document_exists():
    assert os.path.isfile(AUDIT_DOC), "docs/ENGINEERING_AUDIT.md yok"


@pytest.mark.parametrize("record", ["REL-001", "REL-002", "REL-003",
                                    "REL-004", "TEST-001", "DOC-001"])
def test_every_required_audit_record_is_present(record):
    assert record in read(AUDIT_DOC), f"{record} kaydi yok"


@pytest.mark.parametrize("field", [
    "Kimlik", "Baslik", "Onem", "Durum", "Kanit", "Kok neden",
    "Degisen dosyalar", "Test kaniti", "Canli kabul", "Kalan risk",
    "Commit durumu",
])
def test_the_audit_records_carry_every_field(field):
    text = fold(read(AUDIT_DOC))

    assert field in text, f"denetim kaydinda alan eksik: {field}"


def test_the_baseline_suite_result_is_marked_as_a_baseline():
    """3716/17 GUNCEL sonuc gibi sunulmamali."""
    text = read(AUDIT_DOC)

    assert "3716" in text
    lowered = fold(text).lower()
    assert "baseline" in lowered or "taban" in lowered, (
        "tam paket sonucu taban olarak isaretlenmemis")


def test_the_cover_art_fatal_exception_is_recorded_as_open_risk():
    text = read(AUDIT_DOC)

    assert "0xe24c4a02" in text, "cover-art olumcul istisnasi kaydedilmemis"


# --- 8. Yol haritasi --------------------------------------------------

def test_the_roadmap_exists():
    assert os.path.isfile(ROADMAP_DOC), "docs/ROADMAP.md yok"


@pytest.mark.parametrize("section", [
    "Su anki asama", "Commit oncesi", "Uzak release", "mimari",
    "Performans", "CI", "kabul matrisi", "rehearsal", "release-ready",
])
def test_the_roadmap_covers_every_required_section(section):
    text = fold(read(ROADMAP_DOC))

    assert section in text, f"yol haritasinda bolum eksik: {section}"


@pytest.mark.parametrize("field", ["Durum", "Bagimlilik", "Olcut", "onay"])
def test_every_roadmap_item_declares_its_fields(field):
    text = fold(read(ROADMAP_DOC))

    assert field in text, f"yol haritasi alani eksik: {field}"


# --- 9. Durum sozlugu -------------------------------------------------

def test_the_status_vocabulary_is_declared():
    text = fold(read(AUDIT_DOC))

    for word in STATUS_WORDS:
        assert word in text, f"durum sozlugunde eksik: {word}"


def test_the_completed_status_allows_work_without_live_acceptance():
    """`TAMAMLANDI` tanimi UYGULANABILIR olmali.

    Ilk tanim her is icin canli kabul istiyordu; DOC-001 gibi yalniz
    belge islerinde canli kabul UYGULANMAZ ve o isler hicbir zaman
    tamamlanamazdi.
    """
    text = fold(read(AUDIT_DOC)).lower()

    assert "uygulanabilir" in text, (
        "TAMAMLANDI tanimi 'uygulanabilir kabul' olcutunu icermiyor")
    assert "commit bekleyen" in text, (
        "commit bekleyen isin TAMAMLANDI sayilmadigi yazilmamis")


@pytest.mark.parametrize("rule", [
    "sabit bir kimlik",
    "tek basina kanit",
    "bagimsiz dogrulama",
    "silinmez",
    "ROADMAP",
    "snapshot",
])
def test_the_record_management_rules_are_present(rule):
    """Kayit yonetimi kurallari acikca yazili olmali."""
    text = fold(read(AUDIT_DOC)).lower()

    assert fold(rule).lower() in text, f"kayit kurali eksik: {rule}"


def test_completed_is_not_claimed_without_live_acceptance():
    """`TAMAMLANDI` yalniz test VE canli kabul varsa kullanilir.

    Bu turda hicbir canli build/kabul yapilmadi; bu yuzden REL kayitlari
    `TAMAMLANDI` DIYEMEZ.
    """
    text = read(AUDIT_DOC)
    for record in ("REL-001", "REL-002", "REL-003", "REL-004"):
        start = text.index(record)
        end = text.find("\n## ", start)
        block = text[start:end if end != -1 else len(text)]
        assert "TAMAMLANDI" not in block, (
            f"{record} canli kabul olmadan TAMAMLANDI diyor")


# =====================================================================
# NATIVE-001 kaydinin CANLI KABUL sonucu (18 Agustos 2026)
# =====================================================================
#
# OLCULEN CELISKI (bagimsiz denetim): canli kabul YAPILDI ve BASARISIZ
# oldu; buna ragmen belgelerde "gecerli gercek medya ile canli kosum
# YAPILMADI" ve "hicbir canli olcum yoktur" cumleleri duruyordu. Ayrica
# ROADMAP hem bayat `255 passed` ara sonucunu hem guncel `268 passed`
# sonucunu tasiyordu.
#
# NOT: asagidaki yasaklar YALNIZ NATIVE-001 / ROADMAP'in NATIVE-001
# bolumunu olcer. Baska kayitlarin ("REL-003: Gercek build YAPILMADI"
# gibi) mesru ifadeleri SERBESTTIR.

def native_record():
    """`ENGINEERING_AUDIT.md` icindeki NATIVE-001 kaydi."""
    text = read(AUDIT_DOC)
    start = text.index("## NATIVE-001")
    end = text.find("\n## ", start + 1)
    return text[start:end if end != -1 else len(text)]


def roadmap_native_section():
    """`ROADMAP.md` icindeki NATIVE-001 bolumu.

    Bolum BASLIKTAN baslar: ilk `NATIVE-001` gecisi ust ozettedir ve oradan
    baslamak yanlis (cok kisa) bir blok verir.
    """
    text = read(ROADMAP_DOC)
    start = text.index("## SIRADAKI TEKNIK RISK")
    end = text.find("\n## ", start + 1)
    section = text[start:end if end != -1 else len(text)]
    assert "NATIVE-001" in section, "ROADMAP NATIVE-001 bolumu bulunamadi"
    return section


STALE_CLAIMS = (
    "Geçerli gerçek medya ile canlı koşum YAPILMADI",
    "hiçbir canlı ölçüm yoktur",
    "GECERLI GERCEK MEDYA ILE YAPILMADI",
    "ORTAM EKSIGI",
)


def flat(text):
    """Bosluklari tekillestirir: satir sonuna bolunen cumle de yakalanir."""
    return " ".join(fold(text).lower().split())


@pytest.mark.parametrize("claim", STALE_CLAIMS)
def test_the_native_record_does_not_deny_the_live_run(claim):
    """Canli kosum YAPILDI; "yapilmadi" iddialari bayattir."""
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        assert flat(claim) not in flat(block), (
            f"{label} NATIVE-001 bolumu hala bayat iddiayi tasiyor: {claim}")


def test_the_native_record_states_the_live_acceptance_failed():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        folded = fold(block).upper()
        assert "CANLI KABUL BASARISIZ" in folded, (
            f"{label} canli kabulun BASARISIZ oldugunu yazmiyor")


def test_the_roadmap_carries_only_the_current_deterministic_result():
    """Bayat ara sonuc kalmamali; guncel sonuc bulunmali."""
    section = roadmap_native_section()

    assert "255 passed" not in section, (
        "ROADMAP bayat `255 passed` ara sonucunu hala tasiyor")
    assert "268 passed, 1 deselected" in section, (
        "ROADMAP guncel `268 passed, 1 deselected` sonucunu tasimiyor")


def test_the_native_record_separates_the_two_stage_commit_states():
    """Asama 1 ve Asama 2 commit durumlari AYRI yazilmali."""
    block = fold(native_record()).upper()

    assert "A7CED18" in block, "Asama 1 commit'i (a7ced18) yazilmamis"
    for commit in ("4ED5C79", "5C83C05"):
        assert commit in block, f"Asama 2 commit'i ({commit}) yazilmamis"

    status_line = [line for line in native_record().splitlines()
                   if line.startswith("- **Durum")]
    assert status_line, "NATIVE-001 Durum satiri yok"
    folded = fold(status_line[0]).upper()
    assert "ASAMA 1" in folded and "ASAMA 2" in folded, (
        f"Durum satiri asamalari ayirmiyor: {status_line[0]}")
    assert "CANLI KABUL BASARISIZ" in folded, (
        f"Durum satiri canli kabulun basarisiz oldugunu yazmiyor: "
        f"{status_line[0]}")


def test_the_roadmap_summary_does_not_undercount_local_commits():
    """Ust ozet bayat commit sayisi tasimamali."""
    text = read(ROADMAP_DOC)

    assert fold("dört yerel commit").lower() not in fold(text).lower(), (
        "ROADMAP hala 'dört yerel commit' diyor; sayi guncel degil")


def test_native_record_carries_the_correct_debugger_counts_and_threads():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        flattened = flat(block)
        for fact in ("14 first-chance", "13 tekrar", "0 second-chance",
                     "lua/stats", "lua/ytdl_hook", "lua/select"):
            assert flat(fact) in flattened, f"{label} kaniti eksik: {fact}"


def test_native_record_does_not_misidentify_the_fault_thread():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        assert "MPVEventHandlerThread kaynak thread" not in block, (
            f"{label} fault thread'i yanlis adlandiriyor")
        assert "fault thread: `lua/stats`" in block, (
            f"{label} gercek fault thread'i yazmiyor")


def test_native_record_classifies_the_code_from_primary_sources():
    block = native_record()

    for fact in ("LJ_EXCODE", "0xe24c4a00", "LUA_ERRRUN", "mpv-2.dll"):
        assert fact in block, f"NATIVE-001 siniflandirmasi eksik: {fact}"
    for url in ("github.com/LuaJIT/LuaJIT/blob/v2.1/src/lj_err.c",
                "github.com/LuaJIT/LuaJIT/blob/v2.1/src/lua.h",
                "github.com/mpv-player/mpv/blob/master/DOCS/man/lua.rst"):
        assert url in block, f"NATIVE-001 birincil kaynagi eksik: {url}"


def test_native_record_preserves_the_approval_chain_violation():
    block = flat(native_record())

    assert flat("bağımsız denetime sunulmadan") in block
    assert flat("onay zinciri ihlali") in block


# =====================================================================
# NATIVE-001 commit kapsami: YEDI dosya, IKI commit grubu
# =====================================================================
#
# OLCULEN CELISKI: kayit "ALTI dosya (uc yeni, uc degismis)" diyordu.
# Belge korumasi kendi test dosyasini da degistirdigi icin calisma
# agacinda YEDI dosya var ve bunlar IKI mantiksal commit'e ayrilir.

GATE_FILES = (
    "tests/native_player_shutdown_child.py",
    "tests/native_media_contract.py",
    "tests/native_shutdown_acceptance.py",
    "tests/test_native_shutdown_acceptance_regressions.py",
)

RECORD_FILES = (
    "docs/ENGINEERING_AUDIT.md",
    "docs/ROADMAP.md",
    "tests/test_release_documentation_regressions.py",
)


@pytest.mark.parametrize("name", GATE_FILES + RECORD_FILES)
def test_every_pending_file_is_named_in_the_record(name):
    """Yedi dosyanin her biri kayitta ADIYLA gecmeli."""
    assert name in native_record(), (
        f"NATIVE-001 kaydi bekleyen dosyayi saymiyor: {name}")


def test_the_two_commit_groups_have_the_right_sizes():
    """Kapi grubu DORT, kayit grubu UC dosyadir."""
    assert len(GATE_FILES) == 4
    assert len(RECORD_FILES) == 3
    assert len(set(GATE_FILES + RECORD_FILES)) == 7, "dosya adlari tekrarli"

    block = fold(native_record()).upper()
    assert "DORT" in block or "DÖRT" in fold(native_record()).upper(), (
        "kapi grubunun DORT dosya oldugu yazilmamis")
    assert "YEDI" in block, "toplam YEDI dosya yazilmamis"


def test_the_planned_commit_messages_are_recorded():
    """Commit plani kayitta yazili olmali."""
    block = native_record()

    for subject in ("test: add product shutdown native acceptance gate",
                    "docs: record failed native shutdown acceptance"):
        assert subject in block, f"commit plani eksik: {subject}"


@pytest.mark.parametrize("stale", ["ALTI dosya", "üç yeni, üç değişmiş"])
def test_the_stale_six_file_scope_is_gone(stale):
    for label, section in (("ENGINEERING_AUDIT", native_record()),
                           ("ROADMAP", roadmap_native_section())):
        assert flat(stale) not in flat(section), (
            f"{label} bayat kapsami hala tasiyor: {stale}")


# =====================================================================
# NATIVE-001 ONAY A: exact libmpv PDB uygunluk kapisi
# =====================================================================
#
# OLCULEN OLGU (18 Agustos 2026): workflow run 31755832255 icindeki
# `mpv-x86_64-debug` artifact'i yalniz `mpv.pdb` tasiyor. Bu PDB ayni
# workflow'un mpv.exe dosyasiyla private-symbol denetiminden gecer; repo
# bin/mpv-2.dll dosyasiyla GUID/age bakimindan ESLESMEZ. Yanlis PDB ile
# ONAY B kosumu baslatilamaz.


def test_native_record_names_the_exact_debug_artifact_and_hash():
    block = native_record()

    for fact in (
        "31755832255",
        "9203486934",
        "mpv-x86_64-debug",
        "873EF06F0996F993120F7633099A18CD1011CF4CDBE139CBE21A8F0575866787",
    ):
        assert fact in block, f"ONAY A artifact kaniti eksik: {fact}"


def test_native_record_carries_both_codeview_identities():
    block = native_record()

    for identity in (
        "C2123266-4DC7-8196-4C4C-44205044422E",
        "83981475-63BC-A938-4C4C-44205044422E",
    ):
        assert identity in block, f"CodeView GUID kaydi eksik: {identity}"
    assert "age 1" in block


def test_native_record_proves_the_downloaded_pdb_belongs_to_mpv_exe():
    block = flat(native_record())

    assert "`mpv.exe`" in native_record()
    assert "`symchk /pf`" in native_record()
    assert "`mpv-2.dll`" in native_record()
    assert "mismatched" in block


def test_native_record_does_not_claim_the_exact_libmpv_pdb_was_obtained():
    block = flat(native_record())

    assert "exact `libmpv-2.pdb` elde edilemedi" in native_record()
    assert "yalnız `mpv.pdb`" in native_record()


def test_native_record_blocks_onay_b_without_the_exact_pdb():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        folded = fold(flat(block)).upper()
        assert "ONAY B" in folded, f"{label} ONAY B sinirini yazmiyor"
        assert "ENGELLENDI" in folded, f"{label} ONAY B'yi engellemiyor"


def test_native_record_says_no_native_target_was_started_in_onay_a():
    block = flat(native_record())

    for process in ("CDB hedefi", "Python child", "MLC Player", "mpv",
                    "PyQt", "video"):
        assert flat(process) in block, f"ONAY A calistirmama kaniti eksik: {process}"
    assert flat("çalıştırılmadı") in block


def test_debugger_parser_commit_is_recorded_as_committed():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        folded = fold(flat(block)).upper()
        assert "DDCFC40" in folded, f"{label} debugger commit'ini yazmiyor"
        assert flat("debugger kanıt ayrıştırması") in flat(block)

    assert "debugger kanıt ayrıştırması ve kayıt düzeltmesi **COMMIT BEKLIYOR**" not in native_record()


def test_roadmap_snapshot_has_the_measured_local_commit_count():
    text = fold(flat(read(ROADMAP_DOC))).lower()

    assert "sekiz commit" in text, "ROADMAP guncel ahead=8 olcumunu tasimiyor"
    assert "bes commit" not in text, "ROADMAP hala bayat ahead=5 sayisini tasiyor"
