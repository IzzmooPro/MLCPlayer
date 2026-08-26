# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Release tag'i ile tag ICINDEKI kaynak surumunun butunlugu.

KANITLANMIS TARIHSEL KUSUR (salt-okunur olculdu, 17 Agustos 2026):

    v0.35 -> commit 2804c2f3   APP_VERSION = "v0.34"
    v0.36 -> commit 5b987d1a   APP_VERSION = "v0.35"

Iki tag da BIR SURUM GERIDE bir commit'e isaret ediyor: etiket, surum
yukseltme commit'inden ONCE atilmis. Yani tag adi, tag icindeki kaynak
surumu ve kurulumu ureten commit birbirinden AYRILMIS.

Bu dosya `packaging/verify_release_ref.py` sozlesmesini olcer. Arac
TAG OLUSTURMAZ VE DEGISTIRMEZ; yalnizca okur.

TESTLER GERCEK DEPO GECMISINE BAGLI DEGILDIR: her senaryo icin kucuk bir
gecici Git deposu kurulur. Global Git kimligi KULLANILMAZ ve DEGISTIRILMEZ;
commit gereken yerde yalniz o komut icin `git -c user.name=... -c
user.email=...` verilir.
"""
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "packaging"))

import verify_release_ref

#: Turkce -> ASCII katlama (karsilastirmalar icin).
_FOLD = str.maketrans({
    "ı": "i", "İ": "I", "ş": "s", "Ş": "S", "ğ": "g", "Ğ": "G",
    "ü": "u", "Ü": "U", "ö": "o", "Ö": "O", "ç": "c", "Ç": "C",
})


def fold(text):
    return text.translate(_FOLD)


CONFIG_TEMPLATE = '''# ornek
APP_NAME = "MLC Player"
APP_VERSION = "{version}"
WINDOW_WIDTH = 800
'''

def windows_form(version):
    """`v0.37` -> `0.37.0.0`. Urun kodundan BAGIMSIZ, testin kendi olcusu."""
    parts = version.lstrip("v").split(".")
    return ".".join((parts + ["0", "0", "0"])[:4])


#: Gercek `MLCPlayer.iss` bicimi: tirnaksiz, `=` ayirici. `VersionInfo
#: ProductName` alani BILEREK burada; `VersionInfoProductVersion`
#: deseninin onunla karismadigi da olculur.
ISS_TEMPLATE = '''; ornek
#define MyAppName "MLC Player"
#define MyAppVersion "{version}"
AppVersion={{#MyAppVersion}}
VersionInfoVersion={windows}
VersionInfoCompany=MLC
VersionInfoProductName={{#MyAppName}}
VersionInfoProductVersion={windows}
'''


def iss_text(version, file_version=None, product_version=None,
             drop_field=None):
    """Installer metni. Alanlar TEK TEK ayristirilabilsin diye parametrik."""
    text = ISS_TEMPLATE.format(version=version, windows=windows_form(version))
    if file_version is not None:
        text = text.replace(f"VersionInfoVersion={windows_form(version)}",
                            f"VersionInfoVersion={file_version}")
    if product_version is not None:
        text = text.replace(
            f"VersionInfoProductVersion={windows_form(version)}",
            f"VersionInfoProductVersion={product_version}")
    if drop_field:
        text = "\n".join(line for line in text.splitlines()
                         if not line.startswith(f"{drop_field}=")) + "\n"
    return text


def git(repo, *args, identity=False):
    """Gecici depoda git calistirir. Kalici config YAZMAZ."""
    command = ["git"]
    if identity:
        # YALNIZ bu komut icin kimlik; global/yerel config'e yazilmaz.
        command += ["-c", "user.name=MLC Test",
                    "-c", "user.email=test@example.invalid"]
    command += list(args)
    result = subprocess.run(command, cwd=repo, capture_output=True, text=True)
    assert result.returncode == 0, (
        f"{' '.join(args)} basarisiz: {result.stderr.strip()}")
    return result.stdout.strip()


def write_sources(repo, version):
    os.makedirs(os.path.join(repo, "app"), exist_ok=True)
    os.makedirs(os.path.join(repo, "packaging"), exist_ok=True)
    with open(os.path.join(repo, "app", "config.py"), "w",
              encoding="utf-8") as handle:
        handle.write(CONFIG_TEMPLATE.format(version=version))
    with open(os.path.join(repo, "packaging", "MLCPlayer.iss"), "w",
              encoding="utf-8") as handle:
        handle.write(iss_text(version))


def commit(repo, message):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message, identity=True)


@pytest.fixture
def repo(tmp_path):
    """Bos bir gecici depo (calisma agaci temiz)."""
    path = str(tmp_path / "depo")
    os.makedirs(path)
    git(path, "init", "-q")
    return path


def build_repo(repo, version, tag=None, tag_version=None, annotated=False):
    """`version` ile bir commit olusturur; istenirse tag atar.

    `tag_version` verilirse ONCE o surumle commit atilip TAG ORAYA konur,
    sonra `version` ile ikinci bir commit gelir. Tarihsel kusurun birebir
    modeli budur: tag surum yukseltmesinden ONCEKI commit'te kalir.
    """
    if tag_version is not None:
        write_sources(repo, tag_version)
        commit(repo, f"surum {tag_version}")
        if tag:
            if annotated:
                git(repo, "tag", "-a", tag, "-m", tag, identity=True)
            else:
                git(repo, "tag", tag)
        write_sources(repo, version)
        commit(repo, f"surum {version}")
        return
    write_sources(repo, version)
    commit(repo, f"surum {version}")
    if tag:
        if annotated:
            git(repo, "tag", "-a", tag, "-m", tag, identity=True)
        else:
            git(repo, "tag", tag)


# --- 1. Dogru durum ---------------------------------------------------

def test_a_matching_tag_passes(repo, capsys):
    """Tag adi = kaynak surumu = installer surumu, commit = HEAD."""
    build_repo(repo, "v0.37", tag="v0.37")

    assert verify_release_ref.verify("v0.37", repo) is True
    assert "OK" in capsys.readouterr().out


def test_an_annotated_tag_also_passes(repo):
    """Annotated tag da `^{commit}` ile guvenle cozulur."""
    build_repo(repo, "v0.37", tag="v0.37", annotated=True)

    assert verify_release_ref.verify("v0.37", repo) is True


# --- 2. Tarihsel kusurun birebir modeli -------------------------------

def test_a_tag_one_version_behind_its_source_fails(repo, capsys):
    """ASIL KIRMIZI: v0.36 tag'i APP_VERSION v0.35 tasiyor.

    Depodaki v0.35 ve v0.36 tam olarak boyleydi.
    """
    build_repo(repo, "v0.36", tag="v0.36", tag_version="v0.35")

    passed = verify_release_ref.verify("v0.36", repo)
    output = capsys.readouterr().out

    assert passed is False
    assert "APP_VERSION" in output
    assert "v0.35" in output and "v0.36" in output


def test_a_tag_on_an_older_commit_fails_when_head_moved_on(repo, capsys):
    """Tag surumu DOGRU ama commit eski; HEAD ileride."""
    build_repo(repo, "v0.37", tag="v0.37")
    write_sources(repo, "v0.37")
    with open(os.path.join(repo, "notlar.txt"), "w", encoding="utf-8") as f:
        f.write("sonraki is\n")
    commit(repo, "tag sonrasi calisma")

    passed = verify_release_ref.verify("v0.37", repo)
    output = capsys.readouterr().out

    assert passed is False
    assert "HEAD" in output


def test_the_head_check_has_no_bypass(repo):
    """HEAD karsilastirmasi ATLANAMAZ.

    Onceki surumde `require_head=False` ve `--skip-head-check` vardi.
    Bypass'i olan bir butunluk denetimi, tam da kacirdigi durumda
    kapatilabilir demektir; kaldirildi.
    """
    build_repo(repo, "v0.37", tag="v0.37")
    with open(os.path.join(repo, "notlar.txt"), "w", encoding="utf-8") as f:
        f.write("sonraki is\n")
    commit(repo, "tag sonrasi calisma")

    assert verify_release_ref.verify("v0.37", repo) is False
    with pytest.raises(TypeError):
        verify_release_ref.verify("v0.37", repo, require_head=False)


def test_the_skip_head_check_flag_is_rejected(repo):
    """`--skip-head-check` artik TANINMAYAN argumandir: exit 1."""
    build_repo(repo, "v0.37", tag="v0.37")

    assert verify_release_ref.main(["--tag", "v0.37"], repo) == 0
    assert verify_release_ref.main(
        ["--tag", "v0.37", "--skip-head-check"], repo) == 1


def test_the_usage_text_offers_no_bypass(repo, capsys):
    """Kullanim metni bypass ONERMEZ."""
    verify_release_ref.main([], repo)

    output = capsys.readouterr().out
    assert "usage" in output.lower()
    assert "skip-head-check" not in output
    assert "--tag" in output


# --- 3. Installer surumunun ayrismasi ---------------------------------

def test_a_diverged_installer_version_fails(repo, capsys):
    """`MyAppVersion` ayrisirsa yakalanir."""
    write_sources(repo, "v0.37")
    with open(os.path.join(repo, "packaging", "MLCPlayer.iss"), "w",
              encoding="utf-8") as handle:
        handle.write(iss_text("v0.36"))
    commit(repo, "installer ayristi")
    git(repo, "tag", "v0.37")

    passed = verify_release_ref.verify("v0.37", repo)
    output = capsys.readouterr().out

    assert passed is False
    assert "MyAppVersion" in output


# --- 3b. Windows surum alanlari ---------------------------------------

@pytest.mark.parametrize("tag, expected", [
    ("v0.37", "0.37.0.0"),
    ("v1.2.3", "1.2.3.0"),
    ("v1.2.3.4", "1.2.3.4"),
    ("v10", "10.0.0.0"),
])
def test_the_windows_version_is_derived_from_the_tag(tag, expected):
    assert verify_release_ref.windows_version_for_tag(tag) == expected


@pytest.mark.parametrize("tag", [
    "", "v", "0.37", "vabc", "v0.a", "v-1.2", "v1.2.3.4.5",
    "v1..2", "v 1.2", "v1.2 ", "vv1.2", "v+1.2",
])
def test_a_malformed_tag_has_no_windows_version(tag):
    """FAIL-CLOSED: bicimi bozuk tag'den surum TURETILMEZ."""
    assert verify_release_ref.windows_version_for_tag(tag) is None


def test_matching_windows_version_fields_pass(repo):
    """Iki alan da dogruysa gecer."""
    build_repo(repo, "v0.37", tag="v0.37")

    assert verify_release_ref.verify("v0.37", repo) is True


def test_matching_numeric_define_and_real_iss_macros_pass(repo):
    """Gerçek ISS alanları numeric define'ı kullanır; tag kapısı bunu çözmeli."""
    write_sources(repo, "v0.37")
    installer = '''; gerçek kaynak biçimi
#define MyAppName "MLC Player"
#define MyAppVersion "v0.37"
#define MyAppNumericVersion "0.37.0.0"
AppVersion={#MyAppVersion}
VersionInfoVersion={#MyAppNumericVersion}
VersionInfoProductVersion={#MyAppNumericVersion}
'''
    with open(os.path.join(repo, "packaging", "MLCPlayer.iss"), "w",
              encoding="utf-8") as handle:
        handle.write(installer)
    commit(repo, "gercek numeric macro bicimi")
    git(repo, "tag", "v0.37")

    assert verify_release_ref.verify("v0.37", repo) is True


def test_an_outdated_numeric_define_behind_real_iss_macros_fails(repo, capsys):
    """Makro cozumu eski numeric define'i sessizce kabul etmez."""
    write_sources(repo, "v0.37")
    installer = '''#define MyAppVersion "v0.37"
#define MyAppNumericVersion "0.36.0.0"
VersionInfoVersion={#MyAppNumericVersion}
VersionInfoProductVersion={#MyAppNumericVersion}
'''
    with open(os.path.join(repo, "packaging", "MLCPlayer.iss"), "w",
              encoding="utf-8") as handle:
        handle.write(installer)
    commit(repo, "eski numeric define")
    git(repo, "tag", "v0.37")

    passed = verify_release_ref.verify("v0.37", repo)
    output = capsys.readouterr().out

    assert passed is False
    assert "0.36.0.0" in output and "0.37.0.0" in output


def test_a_missing_numeric_define_behind_real_iss_macros_fails(repo, capsys):
    """Makro kullanilip define eksikse kapinin davranisi fail-closed kalir."""
    write_sources(repo, "v0.37")
    installer = '''#define MyAppVersion "v0.37"
VersionInfoVersion={#MyAppNumericVersion}
VersionInfoProductVersion={#MyAppNumericVersion}
'''
    with open(os.path.join(repo, "packaging", "MLCPlayer.iss"), "w",
              encoding="utf-8") as handle:
        handle.write(installer)
    commit(repo, "numeric define yok")
    git(repo, "tag", "v0.37")

    passed = verify_release_ref.verify("v0.37", repo)
    output = capsys.readouterr().out

    assert passed is False
    assert "MyAppNumericVersion okunamadi" in output


def test_an_outdated_version_info_version_fails(repo, capsys):
    """KANITLANMIS BOSLUK: `VersionInfoVersion` ayrissa bile geciyordu."""
    write_sources(repo, "v0.37")
    with open(os.path.join(repo, "packaging", "MLCPlayer.iss"), "w",
              encoding="utf-8") as handle:
        handle.write(iss_text("v0.37", file_version="0.36.0.0"))
    commit(repo, "eski dosya surumu")
    git(repo, "tag", "v0.37")

    passed = verify_release_ref.verify("v0.37", repo)
    output = capsys.readouterr().out

    assert passed is False
    assert "VersionInfoVersion" in output
    assert "0.36.0.0" in output and "0.37.0.0" in output


def test_an_outdated_version_info_product_version_fails(repo, capsys):
    """Urun surumu alani da denetlenir."""
    write_sources(repo, "v0.37")
    with open(os.path.join(repo, "packaging", "MLCPlayer.iss"), "w",
              encoding="utf-8") as handle:
        handle.write(iss_text("v0.37", product_version="0.36.0.0"))
    commit(repo, "eski urun surumu")
    git(repo, "tag", "v0.37")

    passed = verify_release_ref.verify("v0.37", repo)
    output = capsys.readouterr().out

    assert passed is False
    assert "VersionInfoProductVersion" in output


@pytest.mark.parametrize("field", ["VersionInfoVersion",
                                   "VersionInfoProductVersion"])
def test_a_missing_windows_version_field_fails(repo, capsys, field):
    """Alan EKSIKSE sessizce gecilmez."""
    write_sources(repo, "v0.37")
    with open(os.path.join(repo, "packaging", "MLCPlayer.iss"), "w",
              encoding="utf-8") as handle:
        handle.write(iss_text("v0.37", drop_field=field))
    commit(repo, f"{field} yok")
    git(repo, "tag", "v0.37")

    passed = verify_release_ref.verify("v0.37", repo)
    output = capsys.readouterr().out

    assert passed is False
    assert field in output


def test_the_product_name_field_is_not_mistaken_for_a_version(repo):
    """`VersionInfoProductName` ile `...ProductVersion` KARISMAMALI.

    Ikisi de `VersionInfoProduct` ile baslar; gevsek bir desen ad alanini
    surum sanip yanlis sonuc uretebilirdi.
    """
    build_repo(repo, "v0.37", tag="v0.37")
    text = verify_release_ref.file_at_tag(
        "v0.37", "packaging/MLCPlayer.iss", repo)
    assert "VersionInfoProductName" in text

    assert verify_release_ref.verify("v0.37", repo) is True


def test_a_tag_whose_shape_is_rejected_fails_verification(repo):
    """Bicimi bozuk tag dogrulamayi DURDURUR (fail-closed)."""
    write_sources(repo, "vabc")
    commit(repo, "bozuk bicim")
    git(repo, "tag", "vabc")

    assert verify_release_ref.verify("vabc", repo) is False


# --- 4. Eksik / bozuk girdiler (fail-closed) --------------------------

def test_a_missing_tag_fails(repo, capsys):
    build_repo(repo, "v0.37")

    passed = verify_release_ref.verify("v0.37", repo)

    assert passed is False
    assert "v0.37" in capsys.readouterr().out


def test_a_missing_config_file_at_the_tag_fails(repo, capsys):
    """Tag icinde `app/config.py` yoksa SESSIZCE gecilmez."""
    os.makedirs(os.path.join(repo, "packaging"), exist_ok=True)
    with open(os.path.join(repo, "packaging", "MLCPlayer.iss"), "w",
              encoding="utf-8") as handle:
        handle.write(iss_text("v0.37"))
    commit(repo, "config yok")
    git(repo, "tag", "v0.37")

    assert verify_release_ref.verify("v0.37", repo) is False
    assert "config.py" in capsys.readouterr().out


def test_an_unreadable_version_constant_fails(repo, capsys):
    """`APP_VERSION` okunamiyorsa fail-closed."""
    write_sources(repo, "v0.37")
    with open(os.path.join(repo, "app", "config.py"), "w",
              encoding="utf-8") as handle:
        handle.write("APP_NAME = 'MLC Player'\n")
    commit(repo, "surum sabiti yok")
    git(repo, "tag", "v0.37")

    assert verify_release_ref.verify("v0.37", repo) is False
    assert "APP_VERSION" in capsys.readouterr().out


def test_a_failing_git_command_is_fail_closed(repo, monkeypatch, capsys):
    """Git komutu duserse arac BASARILI DEMEZ."""
    build_repo(repo, "v0.37", tag="v0.37")

    def broken(*args, **kwargs):
        raise OSError("git yok")

    monkeypatch.setattr(verify_release_ref.subprocess, "run", broken)

    assert verify_release_ref.verify("v0.37", repo) is False


def test_a_directory_that_is_not_a_repository_fails(tmp_path):
    """Depo olmayan bir dizinde fail-closed."""
    plain = str(tmp_path / "duz")
    os.makedirs(plain)

    assert verify_release_ref.verify("v0.37", plain) is False


# --- 5. Guvenlik ve salt-okunurluk ------------------------------------

def test_git_is_never_invoked_through_a_shell(repo, monkeypatch):
    """`shell=True` YOK ve komutlar ARGUMAN LISTESI ile verilir."""
    build_repo(repo, "v0.37", tag="v0.37")
    seen = []
    original = verify_release_ref.subprocess.run

    def recording(command, **kwargs):
        seen.append((command, kwargs))
        return original(command, **kwargs)

    monkeypatch.setattr(verify_release_ref.subprocess, "run", recording)
    verify_release_ref.verify("v0.37", repo)

    assert seen, "hic git cagrisi yapilmadi"
    for command, kwargs in seen:
        assert isinstance(command, (list, tuple)), (
            f"komut dize olarak verilmis: {command!r}")
        assert kwargs.get("shell") is not True, "shell=True kullanildi"
        assert command[0] == "git"


def test_the_tool_only_reads_and_never_writes_tags(repo, monkeypatch):
    """Arac TAG OLUSTURMAZ/SILMEZ ve checkout DEGISTIRMEZ."""
    build_repo(repo, "v0.37", tag="v0.37")
    seen = []
    original = verify_release_ref.subprocess.run

    def recording(command, **kwargs):
        seen.append(list(command))
        return original(command, **kwargs)

    monkeypatch.setattr(verify_release_ref.subprocess, "run", recording)
    verify_release_ref.verify("v0.37", repo)

    forbidden = {"tag", "checkout", "switch", "reset", "commit", "push",
                 "clean", "restore", "stash"}
    for command in seen:
        assert not (forbidden & set(command[1:])), (
            f"salt-okunur olmayan git komutu: {command}")


def test_the_tag_commit_is_resolved_through_the_commit_peel(repo, monkeypatch):
    """Cozumleme `^{commit}` ile yapilmali (annotated tag guvenligi)."""
    build_repo(repo, "v0.37", tag="v0.37", annotated=True)
    seen = []
    original = verify_release_ref.subprocess.run

    def recording(command, **kwargs):
        seen.append(list(command))
        return original(command, **kwargs)

    monkeypatch.setattr(verify_release_ref.subprocess, "run", recording)
    verify_release_ref.verify("v0.37", repo)

    assert any(any(arg.endswith("^{commit}") for arg in command)
               for command in seen), "tag `^{commit}` ile cozulmedi"


# --- 5b. Kodlama: depo dosyalari UTF-8'dir, YEREL kodlama DEGIL -------

def test_non_ascii_repository_files_are_decoded_as_utf8(repo):
    """OLCULEN KUSUR (gercek depoda, 17 Agustos 2026).

    `subprocess.run(text=True)` YEREL kodlamayi kullanir. Bu makinede o
    `cp1254`tur; `packaging/MLCPlayer.iss` ise Turkce metin tasiyan gecerli
    bir UTF-8 dosyasidir ("DEGISIN" -> `\\xc4\\x9e` bayti). Okuma thread'i
    `UnicodeDecodeError` ile dustu, `stdout` `None` oldu ve arac
    `AttributeError` ile CoKTU -- yani gecerli bir tag'i dogrulayamiyordu.

    Gecici depo fixture'lari saf ASCII oldugu icin bunu KACIRDI; kusuru
    gercek depo ortaya cikardi.
    """
    write_sources(repo, "v0.37")
    with open(os.path.join(repo, "packaging", "MLCPlayer.iss"), "w",
              encoding="utf-8") as handle:
        handle.write(iss_text("v0.37"))
        # GERCEK Turkce karakter SART. "Ğ" UTF-8'de \xc4\x9e'dir ve
        # 0x9e bayti `cp1254`te TANIMSIZDIR; ASCII bir yorum bu kusuru
        # yeniden URETMEZ (ilk denemede tam olarak bu oldu).
        handle.write("; BU SATIRI DEĞİŞTİRMEYİN\n")
    commit(repo, "turkce icerik")
    git(repo, "tag", "v0.37")

    assert verify_release_ref.verify("v0.37", repo) is True


def test_invalid_utf8_anywhere_in_the_file_is_fail_closed(repo, capsys):
    """GECERSIZ UTF-8 baytina RAGMEN gecilmez.

    Surum satirlari DOGRU ve saf ASCII; bozukluk dosyanin BASKA bir
    yerinde. `errors="replace"` ile okuyan bir surumde bu durum SESSIZCE
    gecerdi: bozuk baytlar U+FFFD'ye donusur, regex surum satirini yine
    bulur ve dogrulama YESIL derdi. Yani dosya bozukken "butunluk saglam"
    raporlanirdi.

    Cozumleme artik `errors="strict"`tir: cozulemeyen icerik OKUNAMAZ
    sayilir ve dogrulama durur.
    """
    write_sources(repo, "v0.37")
    path = os.path.join(repo, "packaging", "MLCPlayer.iss")
    with open(path, "rb") as handle:
        raw = handle.read()
    assert b'#define MyAppVersion "v0.37"' in raw
    # 0xFF UTF-8'de HICBIR konumda gecerli degildir.
    with open(path, "wb") as handle:
        handle.write(raw + b"; bozuk bayt: \xff\xfe\n")
    commit(repo, "gecersiz utf-8")
    git(repo, "tag", "v0.37")

    passed = verify_release_ref.verify("v0.37", repo)
    output = capsys.readouterr().out

    assert passed is False, "gecersiz UTF-8 tasiyan dosya kabul edildi"
    assert "MLCPlayer.iss" in output


def test_git_output_is_decoded_explicitly_not_by_locale(repo):
    """Cozumleme sozlesmesi: donen deger `str` ve icerik BOZULMAMIS."""
    write_sources(repo, "v0.37")
    with open(os.path.join(repo, "app", "config.py"), "a",
              encoding="utf-8") as handle:
        handle.write('# ölçüm: DEĞİŞİKLİK yapılmasın\n')
    commit(repo, "turkce yorum")
    git(repo, "tag", "v0.37")

    text = verify_release_ref.file_at_tag("v0.37", "app/config.py", repo)

    assert isinstance(text, str)
    assert 'APP_VERSION = "v0.37"' in text
    assert "DEĞİŞİKLİK" in text, "Turkce icerik bozuldu"


# --- 5c. Kanit disiplini: modul aciklamasi --------------------------

def module_docstring(module):
    return module.__doc__ or ""


def test_the_module_docstring_makes_no_unproven_claim():
    """OLCULMEYEN sey IDDIA EDILMEZ.

    Ilk surum iki kanitlanmamis sey soyluyordu: etiketin surum
    yukseltmeden ONCE atildigi (mekanizma; olculmedi) ve kullanicinin
    icinde eski surum yazan bir program KURABILECEGI (release EXE ic
    surumu hic acilmadi).
    """
    text = fold(module_docstring(verify_release_ref)).lower()

    assert "indirip" not in text, "kanitsiz indirme iddiasi duruyor"
    assert "kurabil" not in text, "kanitsiz kurulum iddiasi duruyor"
    assert "kurdu" not in text


def test_the_module_docstring_separates_inference_from_evidence():
    text = fold(module_docstring(verify_release_ref)).upper()

    assert "CIKARIM" in text, "cikarim ayrica isaretlenmemis"
    assert "KANIT DEGIL" in text, "cikarimin kanit olmadigi yazilmamis"


def test_the_module_docstring_records_what_was_not_measured():
    """Release EXE'lerinin IC surumunun olculmedigi yazili olmali."""
    text = fold(module_docstring(verify_release_ref)).upper()

    assert "OLCULMEDI" in text, "olculmeyen sey belirtilmemis"
    assert "EXE" in text


def test_the_module_docstring_keeps_the_measured_facts():
    """Kanitlanan olgular KALIR; sadelestirme onlari silmemeli."""
    text = module_docstring(verify_release_ref)

    for fact in ("v0.35", "v0.36", "2804c2f", "5b987d1",
                 "v0.34", "targetCommitish"):
        assert fact in text, f"olculen olgu kayboldu: {fact}"


def test_the_prepublish_header_uses_the_same_evidence_boundary():
    """Kardes test dosyasi da AYNI kanit/cikarim sinirini tasimali."""
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "test_prepublish_regressions.py")
    with open(path, encoding="utf-8") as handle:
        header = handle.read().split('"""')[1]
    text = fold(header).upper()

    assert "CIKARIM" in text, "prepublish basligi cikarimi isaretlemiyor"
    assert "KANIT DEGIL" in text
    assert "OLCULMEDI" in text


# --- 6. Giris noktasi -------------------------------------------------

def test_main_requires_an_explicit_tag(repo):
    """Tag adi ACIKCA verilmeli; tahmin edilmez."""
    assert verify_release_ref.main([], repo) == 1


def test_main_returns_zero_on_success(repo):
    build_repo(repo, "v0.37", tag="v0.37")

    assert verify_release_ref.main(["--tag", "v0.37"], repo) == 0


def test_main_returns_one_on_mismatch(repo):
    build_repo(repo, "v0.36", tag="v0.36", tag_version="v0.35")

    assert verify_release_ref.main(["--tag", "v0.36"], repo) == 1
