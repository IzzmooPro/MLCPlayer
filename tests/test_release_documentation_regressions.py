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
PROJECT_STATUS_DOC = os.path.join(ROOT, "docs", "PROJECT_STATUS.md")
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


def test_final_artifact_process_safety_is_a_pre_tag_gate():
    """Source tests cannot prove the newly compiled installer's behavior."""
    text = fold(read(RELEASE_DOC)).lower()
    build = text.index("b) hedef testler")
    smoke = text.index("final-artifact")
    tag = text.index("yerel annotated tag")

    assert build < smoke < tag
    for phrase in (
            "ayni adli", "hayatta", "silent", "interaktif", "appdata",
            "hash", "byte", "upgrade", "uninstall", "degismemeli"):
        assert phrase in text, f"final-artifact kabulunde eksik: {phrase}"


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
    assert "yerel tag" in text and "temizlikten once" in text, (
        "ag yokken ayni surumun yerel tag korumasi belgelenmemis")


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


def test_the_current_full_suite_checkpoint_is_recorded_everywhere():
    records = {
        "ENGINEERING_AUDIT": read(AUDIT_DOC),
        "ROADMAP": read(ROADMAP_DOC),
        "PROJECT_STATUS": read(PROJECT_STATUS_DOC),
    }

    for label, record in records.items():
        block = flat(record)
        for fact in (
            "20 agustos 2026",
            "b65bd9c",
            "4556 passed / 19 skipped / 0 failed",
            "exit 0",
            "87,60 sn",
        ):
            assert flat(fact) in block, f"{label}: {fact}"


def test_the_current_checkpoint_does_not_invent_a_separate_stderr_result():
    audit = flat(read(AUDIT_DOC))

    assert flat("stdout/stderr ayri yakalanmadi") in audit
    assert flat("stderr bayt sayisi olculmedi") in audit


def test_the_roadmap_summary_has_the_current_local_commit_count():
    summary = flat(read(ROADMAP_DOC).split("---", 1)[0])

    assert flat("origin/master ile eşit (0 ileri / 0 geri)") in summary
    assert "4626 passed / 26 skipped / 0 failed" in summary


def test_the_current_final_artifact_acceptance_is_recorded_everywhere():
    records = {
        "ENGINEERING_AUDIT": read(AUDIT_DOC),
        "ROADMAP": read(ROADMAP_DOC),
        "PROJECT_STATUS": read(PROJECT_STATUS_DOC),
    }

    for label, record in records.items():
        block = flat(record)
        for fact in (
            "89123ca",
            "58.247.692",
            "49.268.645",
            "6010273f154ef370a0a474ac663cd2f08111020854707e954e913e5cb0fd773f",
            "2292cfc93e75ba94dd1eac58ec0d08bc31e79538c86ce696c98808143623c857",
            "121 dosyada 0 boyut/hash farki",
            "ayni adli surec hayatta kaldi",
            "iki kaldirma sirasi",
            "66776f38ae6194bc465d6e8f26438ad368a89ebd9956d18c467cad95b8b2eb9c",
            "fault injection",
            "pass sayilmiyor",
        ):
            assert flat(fact) in block, f"{label}: {fact}"


def test_the_v0_37_windows_build_is_recorded_with_exact_artifacts():
    records = {
        "ENGINEERING_AUDIT": read(AUDIT_DOC),
        "ROADMAP": read(ROADMAP_DOC),
        "PROJECT_STATUS": read(PROJECT_STATUS_DOC),
    }

    for label, record in records.items():
        block = flat(record)
        for fact in (
            "v0.37",
            "6cdacf1",
            "58.255.939",
            "49.268.164",
            "fa0a5f03cbe0f3a42c29fa162648fdabea4efffcbbaef2754d7c2657155474da",
            "05937a59c5f0e29b32d15fecc5080351ce65d55720508fc8901a6d347bfaf67b",
            "main_signature_ok=true",
            "addon_signature_ok=true",
        ):
            assert flat(fact) in block, f"{label}: {fact}"


def test_the_build_record_preserves_limits_and_current_physical_acceptance():
    roadmap = flat(read(ROADMAP_DOC))

    assert flat("FIZIKSEL KABUL MATRISI BASARILI") in roadmap
    assert flat("otomatik tekrar yapilmadi") in roadmap
    assert flat("kilitli klasor hata yolu canli olculmedi") in roadmap


def test_the_build_record_preserves_the_measured_compression_policy():
    status = flat(read(PROJECT_STATUS_DOC))

    for fact in (
        "lzma2/max",
        "solidcompression=yes",
        "upx=false",
        "187,8 mb",
        "55,6 mb",
        "%70",
    ):
        assert flat(fact) in status, fact


def test_the_v0_37_upgrade_and_playback_acceptance_is_recorded_everywhere():
    records = {
        "ENGINEERING_AUDIT": read(AUDIT_DOC),
        "ROADMAP": read(ROADMAP_DOC),
        "PROJECT_STATUS": read(PROJECT_STATUS_DOC),
    }

    for label, record in records.items():
        block = flat(record)
        for fact in (
            "v0.36 -> v0.37",
            "ana installer exit 0",
            "add-on exit 0",
            "goruntu/ses tamam",
            "hakkinda v0.37",
            "kullanici gozlemi",
            "kalan surec 0",
            "2.651.661.814",
            "638811093472871806",
        ):
            assert flat(fact) in block, f"{label}: {fact}"


def test_physical_acceptance_records_the_successful_uninstall_cycle():
    roadmap = flat(read(ROADMAP_DOC))

    assert flat("FIZIKSEL KABUL MATRISI BASARILI") in roadmap
    assert flat("ana program klasoru yok") in roadmap
    assert flat("release-ready madde 7 saglandi") in roadmap


def test_the_empty_install_directory_uninstall_defect_is_recorded_everywhere():
    records = {
        "ENGINEERING_AUDIT": read(AUDIT_DOC),
        "ROADMAP": read(ROADMAP_DOC),
        "PROJECT_STATUS": read(PROJECT_STATUS_DOC),
    }

    for label, record in records.items():
        block = flat(record)
        for fact in (
            "0 oge",
            "0 bayt",
            "uninstall kaydi 0",
            "kalan surec 0",
            "bos program klasoru kaldi",
            "dirifempty",
            "filesandordirs yok",
            "45 passed",
        ):
            assert flat(fact) in block, f"{label}: {fact}"


def test_the_first_rel006_failure_and_successful_second_retest_are_recorded():
    records = {
        "ENGINEERING_AUDIT": read(AUDIT_DOC),
        "ROADMAP": read(ROADMAP_DOC),
        "PROJECT_STATUS": read(PROJECT_STATUS_DOC),
    }

    for label, record in records.items():
        block = flat(record)
        for fact in (
            "332779c",
            "61ae94ae6d53611aedc24880c0f52f4c224717130e688645694fb42a54c9ddf6",
            "308e82bb2ced6d298f467794d21798b1ae9786fb7e05a369fd183539ee43f140",
            "ilk rel-006 canli retest basarisiz",
            "3 bos alt dizin",
            "_internal\\bin",
            "_internal\\licenses",
            "uninstall kaydi 0",
            "kalan surec 0",
            "en derinden yukariya",
            "46 passed",
            "b65bd9c",
            "ikinci rel-006 canli retest",
            "b6f284c6b8db626f99815f31685c785c279ae0fd5a4d967fd3d03e22e5bb5a1b",
            "c0ec451b434ff94e13273709ca708493a29ce45695aef8f90c85ed885f6ce479",
            "ana program klasoru yok",
            "kisayol 0",
            "release-ready madde 7 saglandi",
        ):
            assert flat(fact) in block, f"{label}: {fact}"


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


def project_status_native_section():
    """`PROJECT_STATUS.md` icindeki guncel kapanis bolumu."""
    text = read(PROJECT_STATUS_DOC)
    start = text.index("## Kapanış erişim ihlali")
    end = text.index("## Sürüm numaralandırma", start)
    return text[start:end]


STALE_CLAIMS = (
    "Geçerli gerçek medya ile canlı koşum YAPILMADI",
    "hiçbir canlı ölçüm yoktur",
    "GECERLI GERCEK MEDYA ILE YAPILMADI",
    "ORTAM EKSIGI",
)


def flat(text):
    """Bosluklari tekillestirir: satir sonuna bolunen cumle de yakalanir."""
    return " ".join(fold(text).lower().split())


def plain(text):
    """Markdown vurgusundan bagimsiz semantik metin."""
    return re.sub(r"[`*_]", "", flat(text)).upper()


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
    for fact in ("ESKI KAPIYLA CANLI FAIL", "YANLIS POZITIF",
                 "7D4C07F", "CANLI KABUL BASARILI"):
        assert fact in folded, (
            f"Durum satiri guncel kabul ayrimini yazmiyor ({fact}): "
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
    for url in (
        "github.com/openresty/luajit2/blob/52f52587b37867ab19236eb6917001c2d6b662e7/src/lj_err.c",
        "github.com/openresty/luajit2/blob/52f52587b37867ab19236eb6917001c2d6b662e7/src/lua.h",
        "github.com/mpv-player/mpv/blob/7b8915bc1d04c7e1b61184e00c7fbfaab1911e75/player/lua.c",
    ):
        assert url in block, f"NATIVE-001 birincil kaynagi eksik: {url}"


def test_native_record_uses_the_runtime_builds_exact_source_chain():
    block = native_record()

    for revision in (
        "7b8915bc1d04c7e1b61184e00c7fbfaab1911e75",
        "cd1edc11dc6887a50f705717619d879f5a93a488",
        "52f52587b37867ab19236eb6917001c2d6b662e7",
    ):
        assert revision in block, f"NATIVE-001 exact kaynak kimligi eksik: {revision}"
    for source in ("openresty/luajit2", "v2.1-agentzh", "player/lua.c"):
        assert source in block, f"NATIVE-001 exact kaynak zinciri eksik: {source}"


def test_native_record_does_not_overstate_the_luajit_provenance():
    block = fold(flat(native_record())).upper()

    assert "LUAJIT COMMIT'I ARTIFACT ICINDE SABITLENMEMISTIR" in block
    assert "KRIPTOGRAFIK OLARAK KANITLANMIS SAYILMAZ" in block


def test_native_record_keeps_source_classification_bounded():
    block = fold(flat(native_record())).upper()

    assert "LUAJIT HATA TASIMASI" in block
    assert "ASIL LUA CAGRISINI" in block
    assert "GUVENLI VEYA ZARARSIZ" in block
    assert "KANITLAMAZ" in block


def test_native_record_carries_the_internal_jit_abort_alternative():
    block = fold(flat(native_record())).upper()

    for fact in ("LJ_TRACE_ERR", "LJ_VM_CPCALL", "LUA_ERRRUN",
                 "JIT TRACE ABORT"):
        assert fact in block, f"NATIVE-001 JIT ic yolu eksik: {fact}"
    assert "SCRIPT RUNTIME HATASI ILE JIT TRACE ABORT" in block
    assert "AYIRT ETMEZ" in block


def test_native_record_documents_the_unrun_script_ablation_gate():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        flattened = fold(flat(block)).upper()
        for fact in (
            "MLC_NATIVE_MPV_SCRIPT_ABLATION",
            "DOKUZ BUILT-IN",
            "CALISTIRILMADI",
            "AYRI ONAY B",
        ):
            assert fact in flattened, f"{label} ablation kaydi eksik: {fact}"
        assert "LOAD-SCRIPTS=NO" in flattened, label
        assert "TEK BASINA YETMEZ" in flattened, label


def test_native_record_does_not_claim_that_ablation_is_a_product_fix():
    block = fold(flat(native_record())).upper()

    assert "URUN DUZELTMESI DEGILDIR" in block
    assert "URUN" in block and "MPV_CONFIG" in block and "DEGISMEDI" in block


def test_script_ablation_phase_records_the_latest_deterministic_result():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        flattened = fold(flat(block)).upper()
        assert "608 PASSED, 4 SKIPPED" in flattened, label
        assert "ABLATION ASAMASI" in flattened, label
        assert "CANLI KOSUM YAPILMADI" in flattened, label
        assert "COMMIT EDILDI" in flattened, label
        assert "583BB3D" in flattened, label


@pytest.mark.parametrize("path", [
    "docs/ENGINEERING_AUDIT.md",
    "docs/PROJECT_STATUS.md",
    "docs/ROADMAP.md",
    "tests/native_mpv_trace_contract.py",
    "tests/native_player_shutdown_child.py",
    "tests/test_native_mpv_trace_regressions.py",
    "tests/test_release_documentation_regressions.py",
])
def test_script_ablation_phase_records_its_exact_seven_file_scope(path):
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        assert path in block, f"{label} ablation kapsami eksik: {path}"


def test_script_ablation_live_result_is_recorded_in_all_status_documents():
    documents = (
        ("ENGINEERING_AUDIT", native_record()),
        ("ROADMAP", roadmap_native_section()),
        ("PROJECT_STATUS", project_status_native_section()),
    )
    for label, block in documents:
        flattened = plain(block)
        for fact in (
            "BUILT-IN SCRIPT ABLATION ONAY B",
            "TEK KOSUM",
            "1 PASSED",
            "PYTEST EXIT 0",
            "CHILD STDERR 0 BAYT",
            "0XE24C4A02 SAYISI 0",
            "BUILT-IN LUA MODULU 0",
            "OTOMATIK TEKRAR YAPILMADI",
            "ABLATION SONUC KAYDI COMMIT EDILDI",
        ):
            assert fact in flattened, f"{label} ablation sonucu eksik: {fact}"
        assert "29e017a" in block, label


def test_script_ablation_live_record_carries_artifact_integrity_evidence():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        flattened = flat(block)
        for fact in (
            "611 passed, 4 skipped",
            "2.367.767 bayt",
            "32.416 satır",
            "8F3E1EB01A9EB506D9977880E0DB9EE0F5A07381426CA920593A57A6FF42C1D1",
            "CC316FB8DE055F8F578F89A50CA220E4E75ABE925B22C2A7B36AF189F772D72F",
            "E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855",
            "2.651.661.814",
            "638811093472871806",
        ):
            assert flat(fact) in flattened, (
                f"{label} ablation kaniti eksik: {fact}")


def test_script_ablation_live_record_keeps_the_interpretation_bounded():
    documents = (
        ("ENGINEERING_AUDIT", native_record()),
        ("ROADMAP", roadmap_native_section()),
        ("PROJECT_STATUS", project_status_native_section()),
    )
    for label, block in documents:
        flattened = plain(block)
        assert "KOK NEDEN ACIK" in flattened, label
        assert "URUN DUZELTMESI DEGILDIR" in flattened, label
        assert "BELIRLI BIR SCRIPT" in flattened, label
        assert "KANITLAMAZ" in flattened, label

    roadmap = plain(roadmap_native_section())
    assert "ONCE HAZIRLANAN BUILT-IN SCRIPT ABLATION KOSUMU" not in roadmap
    assert "SCRIPT-BISECTION" in roadmap
    assert "YENI NATIVE KOSUM YAPILMADI" in roadmap
    assert "AYRI KULLANICI ONAYI" in roadmap


def test_native_record_documents_the_deterministic_script_bisection_gate():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        for exact in (
            "MLC_NATIVE_MPV_SCRIPT_BISECTION",
            "stats_ytdl",
            "select",
            "stats",
            "ytdl_hook",
            "MPV_CONFIG",
        ):
            assert exact in block, f"{label} bisection adi eksik: {exact}"
        flattened = plain(block)
        for fact in (
            "ILK ASAMA BUTCESI 2",
            "SECILMEYEN LUA MODULU",
            "SECILEN LUA MODULU GORULMEDI",
            "YENI NATIVE KOSUM YAPILMADI",
            "645 PASSED, 4 SKIPPED",
            "COMMIT EDILDI",
        ):
            assert fact in flattened, f"{label} bisection kaydi eksik: {fact}"
        assert "06bd5f5" in block, label
        assert "URUN" in flattened and "DEGISMEDI" in flattened, label


def test_script_bisection_record_does_not_treat_one_negative_as_exclusion():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        flattened = plain(block)
        assert "TEK NEGATIF" in flattened, label
        assert "ELEME KANITI DEGILDIR" in flattened, label
        assert "HER GERCEK KOSUM AYRI KULLANICI ONAYI" in flattened, label


def test_stats_ytdl_bisection_result_is_recorded_in_all_status_documents():
    documents = (
        ("ENGINEERING_AUDIT", native_record()),
        ("ROADMAP", roadmap_native_section()),
        ("PROJECT_STATUS", project_status_native_section()),
    )
    for label, block in documents:
        assert "stats_ytdl" in block, label
        assert "ytdl_hook 7" in flat(block), label
        flattened = plain(block)
        for fact in (
            "BISECTION ONAY B",
            "TEK KOSUM",
            "1 PASSED",
            "PYTEST EXIT 0",
            "CHILD STDERR 0 BAYT",
            "0XE24C4A02 SAYISI 0",
            "STATS 6",
            "SELECT 0",
            "OTOMATIK TEKRAR YAPILMADI",
            "SONUC KAYDI COMMIT EDILDI",
        ):
            assert fact in flattened, f"{label} stats_ytdl sonucu eksik: {fact}"
        assert "dc31bf9" in block, label


def test_stats_ytdl_record_carries_exact_artifact_evidence():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        flattened = flat(block)
        for fact in (
            "648 passed, 4 skipped",
            "2.316.712 bayt",
            "31.672 satır",
            "8B2E8B35453ECCC7EC5E81D11E70CA2A6AD09053110EBE65C3CBA370A6FDB9BB",
            "0F9C71848625D6936FD9E844D871564DE338139668FDA3A70B8CB1532A3280BF",
            "E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855",
            "2.651.661.814",
            "638811093472871806",
        ):
            assert flat(fact) in flattened, (
                f"{label} stats_ytdl artifact kaniti eksik: {fact}")


def test_stats_ytdl_record_discards_the_bad_regex_and_bounds_the_result():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        flattened = plain(block)
        assert "ILK REGEX SAYIMI GECERSIZ" in flattened, label
        assert "KANIT OLARAK KULLANILMADI" in flattened, label
        assert "GRUB" in flattened and "ELEMEZ" in flattened, label
        assert "SELECT PROFILI AYRI ONAY B" in flattened, label
        assert "SELECT KOSUMU YAPILMADI" in flattened, label


def test_select_bisection_result_is_recorded_in_all_status_documents():
    documents = (
        ("ENGINEERING_AUDIT", native_record()),
        ("ROADMAP", roadmap_native_section()),
        ("PROJECT_STATUS", project_status_native_section()),
    )
    for label, block in documents:
        assert "select" in block, label
        flattened = plain(block)
        for fact in (
            "SELECT BISECTION ONAY B",
            "TEK KOSUM",
            "1 PASSED",
            "PYTEST EXIT 0",
            "CHILD STDERR 0 BAYT",
            "0XE24C4A02 SAYISI 0",
            "SELECT 6",
            "STATS 0",
            "YTDL HOOK 0",
            "OTOMATIK TEKRAR YAPILMADI",
            "SONUC KAYDI COMMIT EDILDI",
        ):
            assert fact in flattened, f"{label} select sonucu eksik: {fact}"
        assert "6f00ee3" in block, label


def test_select_record_carries_exact_artifact_evidence():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        flattened = flat(block)
        for fact in (
            "651 passed, 4 skipped",
            "2.309.579 bayt",
            "31.548 satır",
            "D83214B45DBF615D8009D0537C58E322F1504569BBE5E7B07DA3C97E8CC659A2",
            "B4942757310F5040616FF229C0D3A184D84F04D159492AE55D97269CE103C711",
            "E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855",
            "2.651.661.814",
            "638811093472871806",
        ):
            assert flat(fact) in flattened, (
                f"{label} select artifact kaniti eksik: {fact}")


def test_select_record_closes_the_initial_budget_without_overclaiming():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        flattened = plain(block)
        assert "ILK IKI PROFILLIK BUTCE TAMAMLANDI" in flattened, label
        assert "HICBIR GRUP ELENMEDI" in flattened, label
        assert "KOK NEDEN ACIK" in flattened, label
        assert "YENI NATIVE KOSUM YETKILENDIRILMEDI" in flattened, label
        assert "SALT-OKUNUR KANIT SENTEZI" in flattened


def test_select_result_is_recorded_as_committed_everywhere():
    for label, block in (
        ("ENGINEERING_AUDIT", native_record()),
        ("ROADMAP", roadmap_native_section()),
        ("PROJECT_STATUS", project_status_native_section()),
    ):
        flattened = plain(block)
        assert "SELECT SONUC KAYDI COMMIT EDILDI" in flattened, label
        assert "6f00ee3" in block, label
        assert "SELECT SONUC KAYDI COMMIT BEKLIYOR" not in flattened, label


def test_evidence_synthesis_records_the_next_interaction_profile():
    for label, block in (
        ("ENGINEERING_AUDIT", native_record()),
        ("ROADMAP", roadmap_native_section()),
        ("PROJECT_STATUS", project_status_native_section()),
    ):
        flattened = plain(block)
        for fact in (
            "OBSERVEDTRIO",
            "STATS + YTDLHOOK + SELECT",
            "YENI NATIVE KOSUM YAPILMADI",
            "AYRI ONAY B",
            "TEK POZITIF KOSUM",
            "KESIN KOK NEDEN",
            "KANITLAMAZ",
            "TEK NEGATIF KOSUM",
            "ELEMEZ",
            "719 PASSED, 4 SKIPPED",
            "COMMIT EDILDI",
        ):
            assert fact in flattened, f"{label} kanit sentezi eksik: {fact}"


def test_evidence_synthesis_preserves_the_measured_comparison():
    for label, block in (
        ("ENGINEERING_AUDIT", native_record()),
        ("ROADMAP", roadmap_native_section()),
    ):
        flattened = plain(block)
        for fact in (
            "11",
            "13",
            "CONSOLE",
            "AUTOPROFILES",
            "POSITIONING",
            "COMMANDS",
            "AYRI LUA STATE",
            "ILK TRACE KISMI",
            "TAM RAW KANIT DEGILDIR",
        ):
            assert fact in flattened, f"{label} karsilastirma kaniti eksik: {fact}"


def test_observed_trio_single_live_result_is_recorded_without_false_acceptance():
    documents = (
        ("ENGINEERING_AUDIT", native_record()),
        ("ROADMAP", roadmap_native_section()),
        ("PROJECT_STATUS", project_status_native_section()),
    )
    for label, block in documents:
        flattened = plain(block)
        for fact in (
            "OBSERVEDTRIO BISECTION ONAY B",
            "TEK KOSUM",
            "PYTEST EXIT 0",
            "1 PASSED",
            "15",
            "0XE24C4A02",
            "SHUTDOWN KABULU BASARISIZ",
            "PYTEST PASS URUN KABULU DEGILDIR",
            "SELECT 6",
            "STATS 6",
            "YTDLHOOK 7",
            "DIGER BILINEN BUILT-IN MODULLER 0",
            "OTOMATIK TEKRAR YAPILMADI",
            "CDB KULLANILMADI",
            "BU TEK ORNEKTE",
            "YETERLI",
            "KESIN KOK NEDEN",
            "KANITLAMAZ",
            "721 PASSED, 4 SKIPPED",
        ):
            assert fact in flattened, f"{label} observed_trio sonucu eksik: {fact}"


def test_observed_trio_record_carries_exact_artifact_evidence():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        flattened = flat(block)
        for fact in (
            "2.332.921 bayt",
            "31.715 satır",
            "147ED1F9D889D69F030DB996757C47E7F6973E979213F4D2559FB9118FFFBD53",
            "19.755 bayt",
            "DF1E20C0BF19D210C6CCA86029D26AA8A267E19D97EE8E68E3AD6836356032DC",
            "999 bayt",
            "43D92579AD85D88B34EFC0ECBFDEA113D62FB6FA1BB5502FF5E66DEC24070B1D",
            "2.651.661.814",
            "638811093472871806",
        ):
            assert flat(fact) in flattened, (
                f"{label} observed_trio artifact kaniti eksik: {fact}")


def test_observed_trio_checkpoint_is_recorded_as_committed_everywhere():
    for label, block in (
        ("ENGINEERING_AUDIT", native_record()),
        ("ROADMAP", roadmap_native_section()),
        ("PROJECT_STATUS", project_status_native_section()),
    ):
        flattened = plain(block)
        assert "OBSERVEDTRIO SONUC KAYDI COMMIT EDILDI" in flattened, label
        assert "4e26d24" in block, label
        assert "OBSERVEDTRIO SONUC KAYDI COMMIT BEKLIYOR" not in flattened


def test_pair_bisection_budget_is_recorded_without_native_overclaim():
    for label, block in (
        ("ENGINEERING_AUDIT", native_record()),
        ("ROADMAP", roadmap_native_section()),
        ("PROJECT_STATUS", project_status_native_section()),
    ):
        flattened = plain(block)
        for fact in (
            "STATSSELECT",
            "YTDLSELECT",
            "IKILI PROFIL BUTCESI 2",
            "HER GERCEK KOSUM AYRI ONAY B",
            "YENI NATIVE KOSUM YAPILMADI",
            "TEK NEGATIF KOSUM CIFTTEN BIRINI ELEMEZ",
            "TEK POZITIF KOSUM TEK CLIENTI KESIN KOK NEDEN YAPMAZ",
            "729 PASSED, 4 SKIPPED",
            "IKILI PROFIL DEGISIKLIKLERI COMMIT EDILDI",
        ):
            assert fact in flattened, f"{label} ikili profil kaydi eksik: {fact}"


def test_pair_bisection_gate_checkpoint_is_recorded_as_committed():
    for label, block in (
        ("ENGINEERING_AUDIT", native_record()),
        ("ROADMAP", roadmap_native_section()),
        ("PROJECT_STATUS", project_status_native_section()),
    ):
        flattened = plain(block)
        assert "IKILI PROFIL DEGISIKLIKLERI COMMIT EDILDI" in flattened, label
        assert "dedef7c" in block, label
        assert "IKILI PROFIL DEGISIKLIKLERI COMMIT BEKLIYOR" not in flattened


def test_stats_select_single_live_result_is_recorded_without_overclaim():
    for label, block in (
        ("ENGINEERING_AUDIT", native_record()),
        ("ROADMAP", roadmap_native_section()),
        ("PROJECT_STATUS", project_status_native_section()),
    ):
        flattened = plain(block)
        for fact in (
            "STATSSELECT BISECTION ONAY B",
            "TEK KOSUM",
            "PYTEST EXIT 0",
            "1 PASSED",
            "SHUTDOWN KABULU BASARISIZ",
            "0XE24C4A02 SAYISI 1",
            "STATS 6",
            "SELECT 6",
            "YTDLHOOK 0",
            "DIGER BILINEN BUILT-IN MODULLER 0",
            "OTOMATIK TEKRAR YAPILMADI",
            "CDB KULLANILMADI",
            "BU TEK ORNEKTE YETERLI",
            "TEK CLIENTI KESIN KOK NEDEN YAPMAZ",
            "YTDLSELECT KOSUMU YAPILMADI",
            "AYRI ONAY B",
            "732 PASSED, 4 SKIPPED",
        ):
            assert fact in flattened, f"{label} stats_select sonucu eksik: {fact}"


def test_stats_select_record_carries_exact_artifact_evidence():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        flattened = flat(block)
        for fact in (
            "2.322.628 bayt",
            "31.761 satır",
            "24AA35E57316D748BF5C4AFC0DC4E113B70E8DEC1648B1828F2FC2FE3346A2CB",
            "1.718 bayt",
            "A6CD855ECE8BC2529AD740398D97B8A88B0DB3351BDF7D0E3F8C8E54BCD642F5",
            "994 bayt",
            "38FFCF3AB4035E481B7F431CE1E3BCACFE2114DE1CE84FE3BBA1BD5BBF434702",
            "2.651.661.814",
            "638811093472871806",
        ):
            assert flat(fact) in flattened, (
                f"{label} stats_select artifact kaniti eksik: {fact}")


def test_ytdl_select_single_live_result_is_recorded_without_overclaim():
    for label, block in (
        ("ENGINEERING_AUDIT", native_record()),
        ("ROADMAP", roadmap_native_section()),
        ("PROJECT_STATUS", project_status_native_section()),
    ):
        flattened = plain(block)
        for fact in (
            "YTDLSELECT BISECTION ONAY B",
            "TEK KOSUM",
            "PYTEST EXIT 0",
            "1 PASSED",
            "SHUTDOWN KABULU BASARISIZ",
            "0XE24C4A02 SAYISI 8",
            "YTDLHOOK 7",
            "SELECT 6",
            "STATS 0",
            "DIGER BILINEN BUILT-IN MODULLER 0",
            "OTOMATIK TEKRAR YAPILMADI",
            "CDB KULLANILMADI",
            "BU TEK ORNEKTE YETERLI",
            "TEK CLIENTI KESIN KOK NEDEN YAPMAZ",
        ):
            assert fact in flattened, f"{label} ytdl_select sonucu eksik: {fact}"


def test_ytdl_select_record_carries_exact_artifact_evidence():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        flattened = flat(block)
        for fact in (
            "2.337.261 bayt",
            "31.762 satır",
            "05A001E5229E54BDDAFF3D9A15C6EE0F6B31C7D5D9E6EDB8E0AA857846098B93",
            "10.236 bayt",
            "24BDBE901FE706F0EEB96E6F64B80FA2ED870C8CF4E4CF0D0468813B381D8429",
            "993 bayt",
            "32C5E9AFA784046E53402D59C0C3936987AEE67B35194FE10ECA28FA5F3FB3D7",
            "2.651.661.814",
            "638811093472871806",
        ):
            assert flat(fact) in flattened, (
                f"{label} ytdl_select artifact kaniti eksik: {fact}")


def test_pair_budget_closes_with_a_bounded_common_client_observation():
    for label, block in (
        ("ENGINEERING_AUDIT", native_record()),
        ("ROADMAP", roadmap_native_section()),
        ("PROJECT_STATUS", project_status_native_section()),
    ):
        flattened = plain(block)
        for fact in (
            "IKILI PROFIL BUTCESI TAMAMLANDI",
            "IKI IKILI DE TEK POZITIF",
            "ORTAK CLIENT SELECT",
            "SELECTI KESIN KOK NEDEN YAPMAZ",
            "ONCEKI SELECT TEK NEGATIF",
            "ELEME KANITI DEGILDIR",
            "YENI NATIVE KOSUM YETKILENDIRILMEDI",
            "735 PASSED, 4 SKIPPED",
        ):
            assert fact in flattened, f"{label} ikili butce sonucu eksik: {fact}"


def test_project_status_marks_the_old_harmless_conclusion_as_superseded():
    text = read(PROJECT_STATUS_DOC)
    start = text.index("## Kapanış erişim ihlali")
    block = fold(flat(text[start:start + 2500])).upper()

    assert "GECERSIZ KILINDI" in block or "YURURLUKTEN KALDIRILDI" in block
    assert "0XE24C4A02 KODU ZARARSIZDIR" not in block
    assert "URETIMDE ETKISI GORUNMEZ" not in block


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

    assert flat("origin/master ile eşit (0 ileri / 0 geri)") in text
    assert "33 commit" not in text, "ROADMAP hala bayat ahead=33 durumunu tasiyor"


def test_v0_38_candidate_baseline_is_recorded_in_all_status_documents():
    records = {
        "ENGINEERING_AUDIT": read(AUDIT_DOC),
        "ROADMAP": read(ROADMAP_DOC),
        "PROJECT_STATUS": read(PROJECT_STATUS_DOC),
    }

    for label, record in records.items():
        block = flat(record)
        for fact in (
            "v0.38 aday tabanı",
            "aceccf4..7ee2437 aralığında 8 aday-tabanı commiti",
            "7ee2437",
            "4626 passed / 26 skipped / 0 failed",
            "32370784900",
            "kurulu v0.37",
            "v0.38 build yapılmadı",
        ):
            assert flat(fact) in block, f"{label}: {fact}"


# =====================================================================
# NATIVE-001 PDB'siz mpv trace tani kapisi
# =====================================================================


def test_native_record_names_the_pdb_free_trace_gate_files():
    block = native_record()

    for path in (
        "tests/native_mpv_trace_contract.py",
        "tests/native_windows_exception_contract.py",
        "tests/test_native_mpv_trace_regressions.py",
        "tests/native_player_shutdown_child.py",
        "tests/test_native_shutdown_acceptance_regressions.py",
        "docs/ENGINEERING_AUDIT.md",
        "docs/ROADMAP.md",
        "tests/test_release_documentation_regressions.py",
    ):
        assert path in block, f"PDB'siz trace kapsami kayitsiz: {path}"


def test_native_record_carries_both_trace_opt_ins():
    block = native_record()

    for variable in ("MLC_NATIVE_SHUTDOWN_ACCEPTANCE",
                     "MLC_NATIVE_MPV_TRACE", "MLC_NATIVE_MPV_TRACE_LOG"):
        assert variable in block, f"trace ortam sozlesmesi eksik: {variable}"


def test_native_record_keeps_trace_out_of_the_product_config():
    block = native_record()

    assert "Ürün kodu ve normal `MPV_CONFIG` değişmedi" in block
    for option in ("log_file", "msg_level", "msg_time", "msg_module"):
        assert option in block, f"trace secenegi kayitsiz: {option}"


def test_native_record_carries_the_narrow_select_product_candidate():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        flattened = fold(flat(block)).upper()
        for fact in (
            "load_select=False",
            "9a91e18",
            "CANLI KABUL BASARISIZ",
            "KESIN KOK NEDEN",
            "MADDE 8",
            "ACIK",
        ):
            assert fold(fact).upper() in flattened, (
                f"{label} dar urun adayi sinirini yazmiyor: {fact}")


def test_native_record_carries_the_select_candidate_test_evidence():
    block = flat(native_record())

    assert "none is false" in block
    assert "288 passed, 1 skipped, 2 deselected" in block
    assert "6 passed" in block
    assert "4511 passed, 19 skipped, exit 0; 115,85 sn" in block


def test_native_record_carries_the_failed_select_off_live_result():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        flattened = flat(block)
        for fact in (
            "pytest exit 1",
            "child exit **0**",
            "3427 karakter",
            "tam **2** adet",
            "load_select=false",
            "yeterli degildir",
            "otomatik tekrar",
        ):
            assert flat(fact) in flattened, (
                f"{label} select-off canli kaniti eksik: {fact}")


def test_select_off_result_does_not_claim_a_definitive_root_cause():
    flattened = flat(native_record())

    assert "select bu kosumda olayin olusmasi icin **gerekli degildir**" in flattened
    assert "baska client/etkilesimlerin kesin kok neden oldugunu kanitlamaz" in flattened


def test_native_record_explains_the_cpython_faulthandler_false_positive():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        flattened = plain(block)
        for fact in (
            "cpython v3.14.3",
            "addvectoredexceptionhandler",
            "exception_continue_search",
            "issue #75882",
            "0xe24c4a00 | lua_errrun(2)",
            "14 first-chance",
            "0 second-chance",
            "yanlis pozitif",
        ):
            assert plain(fact) in flattened, (
                f"{label} faulthandler kaynak kanitini yazmiyor: {fact}")


def test_native_record_keeps_the_revised_gate_fail_closed():
    block = flat(native_record())

    for fact in (
        "truncated rapor",
        "farkli windows kodu",
        "ek stderr",
        "stdout fatal",
        "bozuk utf-8",
        "nonzero exit",
        "eksik/bozuk marker",
        "thread sizintisi",
        "537 passed, 2 deselected",
    ):
        assert flat(fact) in block, fact


def test_revised_gate_records_the_single_live_pass_without_inventing_streams():
    block = flat(native_record())

    assert "geriye donuk pass ilan edilmedi" in block
    for fact in (
        "duzeltilmis kapi onay b",
        "canli kabul basarili",
        "7d4c07f",
        "pytest **exit 0 / 1 passed / 1,96 sn**",
        "2.651.661.814",
        "638811093472871806",
        "stderr'inin bos oldugu veya `0xe24c4a02` sayisi **olculmedi**",
    ):
        assert flat(fact) in block, fact
    assert "release-ready madde 8" in block
    assert "bilincli kabul edildi" in block


def test_native_summary_separates_the_explained_trace_from_the_open_lua_error():
    audit = plain(native_record())
    roadmap = plain(roadmap_native_section())

    for label, block in (("ENGINEERING_AUDIT", audit), ("ROADMAP", roadmap)):
        assert "YANLIS POZITIF" in block, label
        assert "CANLI KABUL BASARILI" in block, label
        assert "LUA" in block and "BILINMIYOR" in block, label
        assert "BILINCLI KABUL EDILDI" in block, label
    assert "YANILTICI WINDOWS FATAL EXCEPTION CIKTISININ MEKANIZMASI BULUNDU" in audit


def test_native_residual_risk_is_consciously_accepted_in_every_current_record():
    records = {
        "ENGINEERING_AUDIT": native_record(),
        "ROADMAP": roadmap_native_section(),
        "PROJECT_STATUS": read(PROJECT_STATUS_DOC),
    }

    for label, record in records.items():
        block = fold(flat(record)).upper()
        assert "BILINCLI KABUL EDILDI" in block, label
        assert "KULLANICI KARARI" in block, label
        assert "18 AGUSTOS 2026" in block, label


def test_native_risk_acceptance_is_narrow_and_does_not_weaken_the_gate():
    block = flat(native_record())

    for fact in (
        "exact `0xe24c4a02`",
        "tam cpython raporu",
        "child exit 0",
        "eksiksiz marker/results",
        "ek stderr yok",
        "diger exception kodlari",
        "nonzero exit",
        "kapanis kusuru",
        "fail kalir",
    ):
        assert flat(fact) in block, fact


def test_native_risk_acceptance_keeps_unknowns_and_evidence_separate():
    block = flat(native_record())

    for fact in (
        "0 second-chance",
        "1 passed / 1,96 sn",
        "kullaniciya gorunen cokme, donma veya veri kaybi olculmedi",
        "lua runtime error kosulu bilinmiyor",
        "kok neden tamamen cozuldu denmez",
    ):
        assert flat(fact) in block, fact


def test_native_risk_acceptance_records_when_the_decision_must_be_reopened():
    block = flat(native_record())

    for trigger in (
        "nonzero exit",
        "eksik veya bozuk marker/results",
        "farkli fatal veya exception kodu",
        "ek stderr",
        "thread sizintisi",
        "cokme, donma veya veri kaybi",
        "python, mpv veya luajit surumu degisirse",
    ):
        assert flat(trigger) in block, trigger


def test_release_ready_criterion_eight_is_satisfied_by_conscious_acceptance():
    roadmap = flat(read(ROADMAP_DOC))

    assert flat("8. `0xe24c4a02` riski") in roadmap
    assert flat("SAGLANDI - BILINCLI KABUL") in roadmap
    assert flat("kriter 8 acik") not in roadmap


def test_pairwise_bisection_results_are_recorded_as_committed():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        flattened = flat(block)
        assert "cc94ff7" in flattened, label
        assert "iki ikili sonuc kaydi **commit bekliyor**" not in flattened


def test_native_record_separates_diagnostic_success_from_product_acceptance():
    block = flat(native_record())

    assert flat("tanı başarısı ürün kabulü değildir") in block
    assert flat("stderr veya kapanış sorununu aklamaz") in block


def test_native_record_has_the_current_trace_test_results():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        flattened = flat(block)
        assert "54 passed, 1 skipped" in flattened, label
        assert "476 passed, 4 skipped" in flattened, label


def test_native_record_carries_the_single_live_trace_result():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        flattened = fold(flat(block)).upper()
        for fact in (
            "ONAY B",
            "TEK KOSUM",
            "PYTEST EXIT 1",
            "OTOMATIK TEKRAR YAPILMADI",
            "TANI SONUCSUZ",
        ):
            expected = fold(flat(fact)).upper()
            assert expected in flattened, (
                f"{label} canli trace kaniti eksik: {fact}")


def test_native_record_carries_the_trace_artifact_evidence():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        flattened = flat(block)
        for fact in (
            "2.341.534 bayt",
            "31.858 satır",
            "125D0F347EF3DC1D3E5BFFB718E5BBB506FF46062C57A5FBD498896E6A007FB8",
            "14.799 karakter",
            "0xe24c4a02",
        ):
            assert flat(fact) in flattened, (
                f"{label} trace artifact kaniti eksik: {fact}")


def test_native_record_does_not_turn_an_empty_trace_parse_into_success():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        flattened = fold(flat(block)).upper()
        assert fold(flat("Lua hata/traceback kaydı yok")).upper() in flattened, label
        assert "TANI SONUCSUZ" in flattened, label
        assert "KOK NEDEN" in flattened and "ACIK" in flattened, label


def test_native_record_preserves_media_and_process_safety_evidence():
    block = flat(native_record())

    assert "2.651.661.814" in block
    assert "638811093472871806" in block
    assert flat("boyut ve mtime değişmedi") in block
    assert flat("artık child/pytest süreci yok") in block
    assert "cdb" in block and flat("kullanılmadı") in block
    assert flat("Ürün kodu değiştirilmedi") in block


def test_native_record_discloses_the_raw_child_stream_evidence_gap():
    block = fold(flat(native_record())).upper()

    assert "RAW CHILD STDOUT/STDERR" in block
    assert "KALICI AYRI ARTIFACT" in block
    assert "YAZILMADI" in block
    assert "MARKER" in block and "IDDIASI" in block


def test_native_record_marks_the_trace_gate_commit_as_committed():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        flattened = fold(flat(block)).upper()
        assert "4F5BC87" in flattened, label
        assert "PDB'SIZ TRACE KAPISI" in flattened, label
        assert "COMMIT EDILDI" in flattened, label


def test_native_record_says_the_raw_stream_gap_is_closed_for_future_runs():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        flattened = fold(flat(block)).upper()
        for fact in (
            "RAW_STDOUT",
            "RAW_STDERR",
            ".CHILD_STDOUT.BIN",
            ".CHILD_STDERR.BIN",
            "331 PASSED, 2 SKIPPED",
            "CANLI KOSUM TEKRARLANMADI",
        ):
            assert fact in flattened, f"{label} raw stream duzeltmesi eksik: {fact}"


def test_native_record_does_not_retroactively_upgrade_the_failed_run():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        flattened = fold(flat(block)).upper()
        assert "ONAY B" in flattened and "TANI SONUCSUZ" in flattened, label
        assert "ONAY B SONUC KAYDI" in flattened
        assert "COMMIT BEKLIYOR" in flattened


def test_native_record_carries_the_raw_artifact_live_run_result():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        flattened = fold(flat(block)).upper()
        for fact in (
            "C251ABD",
            "IKINCI PDB'SIZ TRACE ONAY B",
            "TEK KOSUM",
            "PYTEST EXIT 1",
            "OTOMATIK TEKRAR YAPILMADI",
            "TANI SONUCSUZ",
            "11 AYRI",
            "0XE24C4A02",
        ):
            assert fact in flattened, f"{label} ikinci ONAY B kaniti eksik: {fact}"


def test_native_record_carries_all_three_new_artifact_hashes():
    hashes = (
        "C5532F519D26496873AD52A77CDC6B391DCA7361035DFDF4C3954A660012B720",
        "C2D866AB63CDD91BFD3EE61A6F291D263BDBC3EB57FEE9C1B3D64FA869A4B0F5",
        "CF5BC570743E015FEFEC28250D49C83CDB0100230133A798D8297038679D0011",
    )
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        for digest in hashes:
            assert digest in block, f"{label} artifact SHA-256 eksik: {digest}"


def test_native_record_preserves_the_successful_shutdown_markers():
    block = fold(flat(native_record())).upper()
    for fact in (
        "DURATION=2782.27",
        "POSITION=0.04",
        "STOP=1",
        "TERMINATE=1",
        "VISIBLE=FALSE",
        "APP.EXEC=0",
        "MPV THREAD=0",
        "RESULTS FAILURES=NONE",
        "MAIN RETURNED 0",
    ):
        assert fact in block, f"raw stdout kapanis kaniti eksik: {fact}"


def test_native_record_discloses_the_trace_overflow_limit():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        flattened = fold(flat(block)).upper()
        assert "LOG MESSAGE BUFFER OVERFLOW" in flattened, label
        assert "155 MESAJ" in flattened, label
        assert "TUM MPV LOG MESAJLARININ KORUNDUGUNU KANITLAMAZ" in flattened, label


def test_native_record_carries_the_overflow_prevention_contract():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        flattened = fold(flat(block)).upper()
        for fact in (
            "LOGLEVEL=WARN",
            "MSG_LEVEL=ALL=TRACE",
            "337 PASSED, 2 SKIPPED",
            "CANLI KOSUM TEKRARLANMADI",
            "OVERFLOW",
            "FAIL-CLOSED",
        ):
            assert fact in flattened, f"{label} overflow onlemi eksik: {fact}"


def test_native_record_links_the_primary_mpv_logging_contracts():
    block = native_record()

    assert "https://mpv.io/manual/master/#options" in block
    assert "github.com/mpv-player/mpv/blob/master/include/mpv/client.h" in block
    assert "mpv_request_log_messages" in block


def test_native_record_carries_the_overflow_free_live_result():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        flattened = fold(flat(block)).upper()
        for fact in (
            "0AC71F8",
            "UCUNCU PDB'SIZ TRACE ONAY B",
            "TEK KOSUM",
            "PYTEST EXIT 1",
            "OVERFLOW=0",
            "MESSAGES SKIPPED=0",
            "13 AYRI",
            "TANI SONUCSUZ",
            "OTOMATIK TEKRAR YAPILMADI",
        ):
            assert fact in flattened, f"{label} ucuncu ONAY B kaniti eksik: {fact}"


def test_native_record_carries_the_overflow_free_artifact_hashes():
    hashes = (
        "27E6407134BCC6609FBAC41F29F8B6A1E35692A5BB34906B2C904F4A39F18C30",
        "5BBFA4F383DB321919FCFB0EF6A5141C44194BD0FC26469970DADA79241ACEE4",
        "3CDAAC57BD4B7027DF99B77B1F34D6B5B6B18C29965D1E43ADF75AC6B9889A10",
    )
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        for digest in hashes:
            assert digest in block, f"{label} ucuncu kosum SHA-256 eksik: {digest}"


def test_native_record_keeps_the_overflow_interpretation_bounded():
    for label, block in (("ENGINEERING_AUDIT", native_record()),
                         ("ROADMAP", roadmap_native_section())):
        flattened = fold(flat(block)).upper()
        assert "OVERFLOW OLAYLAR ICIN GEREKLI BIR KOSUL DEGILDI" in flattened, label
        assert "KOK NEDEN" in flattened and "ACIK" in flattened, label
        assert "KULLANICIYA GORUNEN ETKI" in flattened, label


def test_native_record_preserves_the_failed_mpv_import_probe():
    block = flat(native_record())

    assert flat("mpv import denemesi OSError ile durdu") in block
    assert flat("libmpv yüklenmedi ve MPV instance oluşturulmadı") in block
