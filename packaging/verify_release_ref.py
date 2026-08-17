# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Release tag'i ile tag ICINDEKI kaynak surumunun butunlugunu dogrular.

OLCULEN OLGULAR (salt-okunur, 17 Agustos 2026):

    v0.35 tag snapshot'inda  APP_VERSION = "v0.34"
    v0.36 tag snapshot'inda  APP_VERSION = "v0.35"
    v0.35 -> 2804c2f = 45de83c^   (bump commit'inin EBEVEYNI)
    v0.36 -> 5b987d1 = 8284771^   (bump commit'inin EBEVEYNI)
    release metadata: targetCommitish = master

Yani tag adi ile tag icindeki kaynak surumu AYRISMIS durumda.

CIKARIM (KANIT DEGIL): bu, bump commit'i uzaga ulasmadan release
olusturuldugunda beklenen sonuctur. Etiketin ne zaman atildigi
GOZLENMEDI; yukaridaki dizilim tek basina zamanlamayi kanitlamaz.

OLCULMEDI: release EXE'lerinin IC surumu acilip bakilmadi. Paketlerin
icerigi hakkinda bu dosyada bir iddia YOKTUR.

Bu arac gelecekteki release'ler icin o ayrismayi MEKANIK olarak yakalar.

SALT-OKUNURDUR. Tag OLUSTURMAZ, DEGISTIRMEZ, SILMEZ; checkout'a
DOKUNMAZ. Kaynak dosyalari import EDILMEZ (import etmek calisma agacini
okur, tag'i degil); icerik `git show <tag>:<yol>` ile okunur.

Kullanim:
    python packaging/verify_release_ref.py --tag v0.37

Cikis kodu 0 = butunluk saglam, 1 = ayrisma var.
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONFIG_PATH = "app/config.py"
INSTALLER_PATH = "packaging/MLCPlayer.iss"

#: `APP_VERSION = "v0.37"` — tirnak tipi serbest.
APP_VERSION_PATTERN = re.compile(
    r'^\s*APP_VERSION\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)
#: `#define MyAppVersion "v0.37"`
INSTALLER_VERSION_PATTERN = re.compile(
    r'^\s*#define\s+MyAppVersion\s+["\']([^"\']+)["\']', re.MULTILINE)

#: Windows surum alanlari: `VersionInfoVersion=0.37.0.0` (tirnaksiz).
#:
#: DESENLER TAM AD ISTER (`\s*=`). Ayni dosyada `VersionInfoProductName`
#: alani da vardir ve `VersionInfoProduct` on ekini paylasir; gevsek bir
#: desen ADI SURUM sanabilirdi.
WINDOWS_VERSION_FIELDS = (
    ("VersionInfoVersion",
     re.compile(r'^\s*VersionInfoVersion\s*=\s*(\S+)\s*$', re.MULTILINE)),
    ("VersionInfoProductVersion",
     re.compile(r'^\s*VersionInfoProductVersion\s*=\s*(\S+)\s*$',
                re.MULTILINE)),
)

#: Kabul edilen tag bicimi: `v` + 1-4 sayisal parca. Isaret, harf, bosluk
#: ve bos parca REDDEDILIR.
TAG_SHAPE = re.compile(r'^v(\d+(?:\.\d+){0,3})$')


def windows_version_for_tag(tag):
    """Tag'den dort parcali Windows surumu. Bicim bozuksa `None`.

        v0.37    -> 0.37.0.0
        v1.2.3   -> 1.2.3.0
        v1.2.3.4 -> 1.2.3.4

    FAIL-CLOSED: `lstrip("v")` gibi gevsek bir ayiklama `vv1.2` ve `v-1.2`
    gibi girdileri sessizce kabul ederdi. Bicim ACIKCA dogrulanir; uretilen
    deger `app/config.py::WINDOWS_VERSION` kuraliyla aynidir.
    """
    if not isinstance(tag, str):
        return None
    found = TAG_SHAPE.match(tag)
    if not found:
        return None
    parts = found.group(1).split(".")
    return ".".join((parts + ["0", "0", "0"])[:4])


def fail(message, log=print):
    log(f"  ERROR: {message}")
    return False


def run_git(args, cwd=None):
    """`git` calistirir. ARGUMAN LISTESI kullanilir; `shell=True` YOKTUR.

    Doner: `(basarili, stdout)`. Git yoksa, depo degilse, komut duserse ya
    da cikti UTF-8 olarak cozulemezse `(False, "")` doner — cagiran
    FAIL-CLOSED davranir.

    CIKTI BAYT OLARAK ALINIR ve cozumleme BU THREAD'de yapilir. Iki ayri
    kusur bunu gerektirdi:

    1. `text=True` YEREL kodlamayi kullanir; bu makinede o `cp1254`tur ve
       depo dosyalari UTF-8'dir. Cozumleme `subprocess`in okuma
       THREAD'inde patlar, `stdout` sessizce `None` olur ve arac gecerli
       bir tag'i dogrulayamadan coker (olculdu).
    2. `errors="replace"` bunu susturur ama YENI bir acik yaratir: bozuk
       baytlar U+FFFD'ye doner, surum satiri yine bulunur ve arac bozuk
       bir dosya icin "butunluk saglam" der (olculdu: test geciyordu).

    Bu yuzden `errors="strict"`: cozulemeyen icerik OKUNAMAZ sayilir.
    Hata BU THREAD'de yakalanir, yani sessizce kaybolamaz.
    """
    try:
        result = subprocess.run(
            ["git"] + list(args),
            cwd=cwd or ROOT,
            capture_output=True,
        )
    except (OSError, ValueError):
        return False, ""
    if result.returncode != 0:
        return False, ""
    raw = result.stdout
    if raw is None:
        return False, ""
    try:
        return True, raw.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError:
        return False, ""


def tag_commit(tag, cwd=None):
    """Tag'in isaret ettigi COMMIT.

    `^{commit}` sart: annotated tag once bir TAG NESNESINE cozulur ve
    ham `rev-parse <tag>` o nesnenin sha'sini verir; commit ile
    karsilastirmak sessizce YANLIS sonuc uretir. Peel iki tag turunde de
    dogru commit'i verir.
    """
    ok, output = run_git(["rev-parse", "--verify", "--quiet",
                          f"{tag}^{{commit}}"], cwd)
    return output if (ok and output) else None


def head_commit(cwd=None):
    ok, output = run_git(["rev-parse", "--verify", "--quiet", "HEAD^{commit}"],
                         cwd)
    return output if (ok and output) else None


def file_at_tag(tag, path, cwd=None):
    """Tag ICINDEKI dosya icerigi. Calisma agaci OKUNMAZ."""
    ok, output = run_git(["show", f"{tag}:{path}"], cwd)
    return output if ok else None


def extract(pattern, text):
    if not text:
        return None
    found = pattern.search(text)
    return found.group(1).strip() if found else None


def verify(tag, cwd=None, log=print):
    """Tag butunlugunu dogrular. Doner: `True`/`False`.

    Denetlenenler:
      1. tag mevcut ve bir commit'e cozuluyor,
      2. tag adi == tag icindeki `APP_VERSION`,
      3. tag icindeki `MyAppVersion` de ayni,
      4. tag commit'i == HEAD.

    HEAD KARSILASTIRMASININ BYPASS'I YOKTUR. Onceki surumde
    `require_head=False` ve `--skip-head-check` vardi; kapatilabilen bir
    butunluk denetimi, tam da yakalamasi gereken durumda kapatilir.
    """
    if not tag:
        return fail("tag adi verilmedi", log)

    commit = tag_commit(tag, cwd)
    if not commit:
        return fail(f"tag bulunamadi veya bir commit'e cozulmuyor: {tag}", log)

    ok = True

    config_text = file_at_tag(tag, CONFIG_PATH, cwd)
    if config_text is None:
        ok = fail(f"{tag} icinde okunamadi: {CONFIG_PATH}", log) and ok
    else:
        source_version = extract(APP_VERSION_PATTERN, config_text)
        if not source_version:
            ok = fail(f"{tag} icindeki {CONFIG_PATH} dosyasinda APP_VERSION "
                      "okunamadi", log) and ok
        elif source_version != tag:
            ok = fail(f"tag adi ile kaynak surumu AYRISMIS: tag {tag}, "
                      f"APP_VERSION {source_version}", log) and ok

    installer_text = file_at_tag(tag, INSTALLER_PATH, cwd)
    if installer_text is None:
        ok = fail(f"{tag} icinde okunamadi: {INSTALLER_PATH}", log) and ok
    else:
        installer_version = extract(INSTALLER_VERSION_PATTERN, installer_text)
        if not installer_version:
            ok = fail(f"{tag} icindeki {INSTALLER_PATH} dosyasinda "
                      "MyAppVersion okunamadi", log) and ok
        elif installer_version != tag:
            ok = fail(f"tag adi ile installer surumu AYRISMIS: tag {tag}, "
                      f"MyAppVersion {installer_version}", log) and ok

    # Windows dort parcali surum alanlari. `MyAppVersion` dogru olsa bile
    # bunlar ayrisabilir; eskiden denetlenmiyorlardi.
    expected_windows = windows_version_for_tag(tag)
    if expected_windows is None:
        ok = fail(f"tag bicimi Windows surumune cevrilemiyor: {tag} "
                  "(beklenen bicim: v0.37 / v1.2.3 / v1.2.3.4)", log) and ok
    elif installer_text is not None:
        for field, pattern in WINDOWS_VERSION_FIELDS:
            found = pattern.search(installer_text)
            if not found:
                ok = fail(f"{tag} icindeki {INSTALLER_PATH} dosyasinda "
                          f"{field} okunamadi", log) and ok
                continue
            value = found.group(1).strip()
            if value != expected_windows:
                ok = fail(f"{field} AYRISMIS: beklenen {expected_windows}, "
                          f"bulunan {value}", log) and ok

    head = head_commit(cwd)
    if not head:
        ok = fail("HEAD bir commit'e cozulmuyor", log) and ok
    elif head != commit:
        ok = fail(f"tag commit'i HEAD ile ayni DEGIL: {tag} "
                  f"{commit[:8]}, HEAD {head[:8]}", log) and ok

    if ok:
        log(f"  OK  {tag}  commit {commit[:8]}  "
            f"kaynak ve installer surumu tag ile ayni")
    return ok


def main(argv=None, cwd=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    tag = ""
    index = 0
    while index < len(argv):
        item = argv[index]
        if item == "--tag" and index + 1 < len(argv):
            tag = argv[index + 1]
            index += 2
            continue
        if item.startswith("--tag="):
            tag = item.split("=", 1)[1]
            index += 1
            continue
        print(f"  ERROR: taninmayan arguman: {item}")
        return 1

    if not tag:
        print("usage: verify_release_ref.py --tag <vX.Y>")
        return 1
    return 0 if verify(tag, cwd) else 1


if __name__ == "__main__":
    sys.exit(main())
