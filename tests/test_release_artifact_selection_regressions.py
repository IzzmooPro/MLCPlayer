# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Release zinciri YALNIZ MEVCUT SURUMUN artifact'ini secmeli.

KANITLANMIS RISK (olculdu, 17 Agustos 2026):
`installer_output` gecmisteki BIRDEN COK kurulum dosyasini yan yana
tutar; klasor birikimlidir ve eski yayinlar silinmez. Betik imzalanacak
ve final dogrulamasi yapilacak dosyayi jokerle seciyordu:

    for %%F in ("installer_output\\MLCPlayer_Setup_*.exe") do set "SETUP=..."

`for` eslesenleri sirayla gezer ve SON eslesme kazanir; sira dosya
sistemine baglidir, garanti degildir. Gercek cmd ile olculdu: o an en
yeni dosya seciliyordu -- SANS eseri.

ASIL TEHLIKE SIRALAMA DEGIL: Inno adimi yeni EXE'yi URETEMEZSE joker
sessizce ESKI bir dosyayi secer. Zincir "basarili" der, ESKI kurulum
imzalanir ve final raporunda YENI surum gibi gosterilir.

SOZLESME: sonuc dosyalari KESIN yollardir; joker yoktur; her Inno
adimindan sonra beklenen kesin EXE'nin varligi denetlenir.

TESTLER BETIGI CALISTIRMAZ: gercek dosya silinmez, build/imza yapilmaz.
Olculen sey betigin KAYNAK SOZLESMESIDIR.
"""
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "packaging", "build_release.bat")
MAIN_ISS = os.path.join(ROOT, "packaging", "MLCPlayer.iss")
ADDON_ISS = os.path.join(ROOT, "packaging", "MLCPlayer_InternetVideo.iss")


@pytest.fixture(scope="module")
def script():
    with open(SCRIPT, encoding="utf-8") as handle:
        return handle.read()


@pytest.fixture(scope="module")
def commands(script):
    """Yorum ve bos satirlar DISINDAKI gercek komut satirlari.

    `rem` satirlarindaki ornekler sozlesmeyi ihlal etmez; olculen sey
    CALISAN komutlardir.
    """
    lines = []
    for line in script.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith("rem "):
            continue
        lines.append(stripped)
    return lines


# --- 1. Joker YASAK ---------------------------------------------------

@pytest.mark.parametrize("forbidden", [
    "MLCPlayer_Setup_*.exe",
    "MLCPlayer_InternetVideo_*.exe",
])
def test_no_artifact_wildcard_is_used(commands, forbidden):
    """Artifact secimi jokerle YAPILMAZ."""
    guilty = [line for line in commands if forbidden in line]

    assert guilty == [], (
        f"joker hala kullaniliyor ({forbidden}): {guilty}")


def test_no_installer_output_exe_wildcard(commands):
    """`installer_output\\*.exe` bicimi de yasak."""
    pattern = re.compile(r"installer_output\\\*", re.IGNORECASE)
    guilty = [line for line in commands if pattern.search(line)]

    assert guilty == [], f"installer_output joker kullanimi: {guilty}"


def test_no_wildcard_exe_anywhere_in_commands(commands):
    """Genel emniyet: calisan hicbir komutta `*.exe` gecmemeli.

    ISCC arama dongusu `.exe` icerir ama joker TASIMAZ; bu test onu
    yakalamaz.
    """
    guilty = [line for line in commands if "*.exe" in line.lower()]

    assert guilty == [], f"`*.exe` jokeri kullaniliyor: {guilty}"


# --- 2. Toplu silme YASAK ---------------------------------------------

def test_old_versions_are_never_deleted_in_bulk(commands):
    """Eski surum artifact'leri KORUNUR; toplu silme yok."""
    bulk = re.compile(
        r"\b(del|erase)\b.*\*|rmdir\s+/s.*installer_output|"
        r"\bdel\b.*installer_output\\?\s*$",
        re.IGNORECASE)
    guilty = [line for line in commands if bulk.search(line)]

    assert guilty == [], f"toplu silme komutu: {guilty}"


def test_installer_output_folder_is_never_removed(commands):
    """`installer_output` klasoru silinmez."""
    guilty = [line for line in commands
              if re.search(r"rmdir.*installer_output", line, re.IGNORECASE)]

    assert guilty == [], f"installer_output siliniyor: {guilty}"


# --- 3. Surum TEK KEZ okunur ------------------------------------------

def test_the_version_is_read_once_from_app_config(commands):
    """`APP_VERSION` + `WINDOWS_VERSION` betik basinda BIR KEZ alinir."""
    readers = [line for line in commands if "from app.config import" in line]

    assert len(readers) == 1, (
        f"surum {len(readers)} kez okunuyor; tek kaynak olmali: {readers}")
    assert "APP_VERSION" in readers[0]
    assert "WINDOWS_VERSION" in readers[0]


def test_the_version_is_read_before_any_inno_step(script):
    """Surum okuma, ilk ISCC cagrisindan ONCE olmali."""
    read_at = script.find("from app.config import")
    first_iscc = script.find('"%ISCC%"')

    assert read_at != -1 and first_iscc != -1
    assert read_at < first_iscc, "surum ilk Inno adimindan SONRA okunuyor"


# --- 4. Kesin yollar ---------------------------------------------------

def test_exact_artifact_paths_are_defined(commands):
    """`MAIN_SETUP` ve `ADDON_SETUP` kesin yollar olarak tanimlanir."""
    main = [line for line in commands if line.startswith('set "MAIN_SETUP=')]
    addon = [line for line in commands if line.startswith('set "ADDON_SETUP=')]

    assert len(main) == 1, f"MAIN_SETUP tanimi: {main}"
    assert len(addon) == 1, f"ADDON_SETUP tanimi: {addon}"
    assert "installer_output\\MLCPlayer_Setup_" in main[0]
    assert "installer_output\\MLCPlayer_InternetVideo_" in addon[0]
    # Surum DEGISKENDEN gelir; sabit yazilmaz.
    assert "APP_VER" in main[0]
    assert "APP_VER" in addon[0]


def test_signing_uses_the_exact_paths(commands):
    """Imzalama kesin degiskenleri kullanir."""
    signing = [line for line in commands if "sign_release.py" in line]

    assert len(signing) >= 2, f"iki imzalama bekleniyor: {signing}"
    assert any("MAIN_SETUP" in line for line in signing), signing
    assert any("ADDON_SETUP" in line for line in signing), signing


def test_the_final_check_runs_on_the_main_setup(commands):
    """`--final` MAIN_SETUP uzerinde calisir."""
    final = [line for line in commands if "--final" in line]

    assert len(final) == 1, f"tek final dogrulamasi bekleniyor: {final}"
    assert "MAIN_SETUP" in final[0]


def test_the_result_report_prints_both_exact_paths(script):
    """Sonuc raporu iki kesin yolu yazar."""
    tail = script[script.find("DONE"):]

    assert "MAIN_SETUP" in tail, "rapor ana kurulumu kesin yolla yazmiyor"
    assert "ADDON_SETUP" in tail, "rapor addon'u kesin yolla yazmiyor"


# --- 5. Once temizlik: YALNIZ bu surumun dort ciktisi ------------------

def test_only_the_current_version_outputs_are_cleaned(script, commands):
    """Temizlik tam olarak DORT kesin hedefi siler.

    Hedefler `for %%T in (...)` LISTESINDEDIR; `del` satirinin kendisi
    yalnizca dongu degiskenini tasir. Testin ilk surumu sadece `del`
    satirina bakiyordu ve dogru kodu yanlis raporluyordu.
    """
    loop = re.search(r"for %%T in \(([^)]*)\)", script)
    assert loop, "kesin hedef listesi bulunamadi"
    targets = re.findall(r'"([^"]+)"', loop.group(1))

    assert len(targets) == 4, f"dort hedef bekleniyor, bulunan: {targets}"
    assert any("MAIN_SETUP" in t and t.endswith(".sig") for t in targets)
    assert any("ADDON_SETUP" in t and t.endswith(".sig") for t in targets)
    assert any("MAIN_SETUP" in t and not t.endswith(".sig") for t in targets)
    assert any("ADDON_SETUP" in t and not t.endswith(".sig") for t in targets)
    for target in targets:
        assert "*" not in target, f"temizlik hedefinde joker: {target}"

    # Silme YALNIZ bu dongu icinden yapilir; baska bir `del` yok.
    deletes = [line for line in commands
               if re.search(r"\bdel\b", line, re.IGNORECASE)]
    assert deletes == ['del /f /q "%%~T"'], (
        f"dongunun disinda silme komutu var: {deletes}")


def test_the_chain_stops_when_a_stale_output_cannot_be_removed(script):
    """Kesin cikti silinemiyorsa zincir DURUR."""
    section = script[script.find("STEP 2"):script.find("STEP 3")]

    assert "goto :fail" in section, (
        "eski cikti silinemediginde zincir durmuyor")


# --- 5b. build/dist temizligi DOGRULANMALI ----------------------------

@pytest.mark.parametrize("folder", ["build", "dist"])
def test_the_chain_stops_when_a_stale_tree_cannot_be_removed(script, folder):
    """`rmdir` sessizce basarisiz olabilir; sonuc DENETLENMELI.

    Kilitli bir dosya, acik bir Explorer penceresi ya da yetki sorunu
    `rmdir /s /q` komutunu basarisiz birakir. Denetlenmezse zincir ESKI
    `build`/`dist` agaciyla devam eder ve PyInstaller'in urettigi sanilan
    sey aslinda onceki kosumun artigi olabilir.
    """
    section = script[script.find("STEP 2"):script.find("STEP 3")]
    guard = re.search(
        rf'if exist "{folder}"[\s\S]{{0,200}}?goto :fail', section)

    assert guard, f"`{folder}` silinemediginde zincir durmuyor"


def test_the_success_message_comes_after_both_guards(script):
    """Basari mesaji IKI denetimden de SONRA gelmeli."""
    section = script[script.find("STEP 2"):script.find("STEP 3")]
    success = section.find("OK  build")
    assert success != -1, "temizlik basari mesaji bulunamadi"

    for folder in ("build", "dist"):
        guard = re.search(
            rf'if exist "{folder}"[\s\S]{{0,200}}?goto :fail', section)
        assert guard, f"{folder} korumasi yok"
        assert guard.end() < success, (
            f"basari mesaji {folder} denetiminden ONCE geliyor")


def test_only_build_and_dist_trees_are_removed(commands):
    """`rmdir` YALNIZ bu iki hedefte kullanilir; joker yok."""
    removals = [line for line in commands
                if re.search(r"\brmdir\b", line, re.IGNORECASE)]

    assert removals, "build/dist temizligi kayboldu"
    for line in removals:
        assert "*" not in line, f"rmdir jokeri: {line}"
        assert ('"build"' in line or '"dist"' in line), (
            f"beklenmeyen rmdir hedefi: {line}")


def test_installer_output_cleanup_is_unchanged(script):
    """`installer_output` davranisi bu turda DEGISMEDI."""
    section = script[script.find("STEP 2"):script.find("STEP 3")]

    assert 'for %%T in ("!MAIN_SETUP!"' in section, (
        "kesin dort hedef temizligi kayboldu")
    assert "rmdir" not in section.split('for %%T in')[1], (
        "installer_output agaci siliniyor")


# --- 6. Her Inno adimindan sonra KESIN EXE denetimi -------------------

def test_the_main_setup_existence_is_checked_after_inno(script):
    """Ana setup uretilmediyse zincir DURUR (joker eskisini secemez)."""
    guard = re.search(
        r'if not exist "!?MAIN_SETUP!?"[\s\S]{0,200}?goto :fail', script)

    assert guard, "Inno sonrasi MAIN_SETUP varlik denetimi yok"


def test_the_addon_setup_existence_is_checked_after_inno(script):
    """Addon uretilmediyse zincir DURUR."""
    guard = re.search(
        r'if not exist "!?ADDON_SETUP!?"[\s\S]{0,200}?goto :fail', script)

    assert guard, "Inno sonrasi ADDON_SETUP varlik denetimi yok"


def test_the_addon_is_mandatory_not_silently_skipped(commands):
    """Addon EKSIKLIGI sessizce atlanmaz.

    Eski surumde `if defined ADDON_TO_SIGN (...)` vardi: addon hic
    uretilmemisse imzalama ADIMI SESSIZCE atlaniyordu.
    """
    guilty = [line for line in commands
              if re.search(r"if\s+defined\s+ADDON", line, re.IGNORECASE)]

    assert guilty == [], f"addon kosullu/atlanabilir: {guilty}"


# --- 7. Adlandirma ISS dosyalariyla UYUMLU ----------------------------

def test_the_main_name_matches_the_installer_script(commands):
    """`MAIN_SETUP` adi `MLCPlayer.iss` OutputBaseFilename ile ayni."""
    with open(MAIN_ISS, encoding="utf-8") as handle:
        iss = handle.read()
    found = re.search(r"^OutputBaseFilename=(\S+)", iss, re.MULTILINE)
    assert found, "OutputBaseFilename okunamadi"
    prefix = found.group(1).split("{")[0]

    main = next(line for line in commands
                if line.startswith('set "MAIN_SETUP='))
    assert prefix in main, (
        f"betik adi ISS ile uyusmuyor: {prefix!r} vs {main!r}")


def test_the_addon_name_matches_its_installer_script(commands):
    """`ADDON_SETUP` adi addon ISS OutputBaseFilename ile ayni."""
    with open(ADDON_ISS, encoding="utf-8") as handle:
        iss = handle.read()
    found = re.search(r"^OutputBaseFilename=(\S+)", iss, re.MULTILINE)
    assert found, "addon OutputBaseFilename okunamadi"
    prefix = found.group(1).split("{")[0]

    addon = next(line for line in commands
                 if line.startswith('set "ADDON_SETUP='))
    assert prefix in addon, (
        f"addon adi ISS ile uyusmuyor: {prefix!r} vs {addon!r}")


def test_both_installers_write_to_installer_output(commands):
    """Kesin yollar ISS'in OutputDir'i ile ayni klasoru gosterir."""
    for path in (MAIN_ISS, ADDON_ISS):
        with open(path, encoding="utf-8") as handle:
            assert "OutputDir=..\\installer_output" in handle.read(), path

    for prefix in ('set "MAIN_SETUP=', 'set "ADDON_SETUP='):
        line = next(item for item in commands if item.startswith(prefix))
        assert "installer_output\\" in line, line
