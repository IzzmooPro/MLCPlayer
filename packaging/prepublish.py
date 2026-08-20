# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Yayin oncesi KAPI: her sey yerinde mi, YUKLEMEDEN once.

KESIN YAYIN SIRASI BURADA TEKRARLANMAZ. Tek resmi kaynak:

    docs/RELEASE_PROCESS.md

Bu kapi o siradaki (e) adimidir: build BITTIKTEN ve yerel ANNOTATED tag
atildiktan SONRA, push ve release'den ONCE calisir.

NEDEN AYRI BIR KAPI: `build_release.bat` tag'den tamamen habersizdir
(`git`/`gh` gecmez) ve build sirasinda tag HENUZ YOKTUR -- olmamalidir
da, cunku tag TEST EDILMIS ve BUILD EDILMIS HEAD'i isaretler. Zincire
baglanirsa her kosumda kirmizi verir ve kapatilir.

Resmi belgeden cikmayan degismezler:
  - TAG VE PUSH BUILD'DEN ONCE YAPILMAZ
  - `--target master` KULLANILMAZ; `--verify-tag --draft` zorunludur
  - build, commit, push, tag ve release AYRI onay ister

DENETLENENLER
    1. `verify_release_ref` : tag <-> kaynak surumu <-> HEAD butunlugu
    2. Git calisma agaci TAMAMEN temiz (staged / tracked / untracked)
    3. Dort surumlu installer artifact'i mevcut
    4. Iki `.sig` KRIPTOGRAFIK olarak dogru (yalniz varlik degil)
    5. Corresponding-source sozlesmesinde acik engel yok
    6. Sozlesmedeki her kaynak arsivi mevcut ve ozeti dogru
    7. Beklenen varlik listesi sozlesmeden dinamik olarak turetiliyor

FAIL-CLOSED ve AG KULLANMAZ. Hicbir Git YAZMA komutu calistirmaz: tag
olusturmaz, push etmez, release acmaz. Calisan tek sey `git status` ve
`verify_release_ref`in salt-okunur sorgulari.

Kullanim:
    python packaging/prepublish.py --tag v0.37
"""
import hashlib
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fetch_sources                                   # noqa: E402
import verify_release_ref                              # noqa: E402
from app import release_signature                      # noqa: E402

INSTALLER_DIR = "installer_output"
MIRROR_DIR = "source_mirror"
SOURCE_CONTRACT = os.path.join("packaging", "corresponding_sources.json")

#: Surumlu installer govdeleri. Her birinin `.sig`i de zorunludur.
INSTALLER_STEMS = ("MLCPlayer_Setup", "MLCPlayer_InternetVideo")


def fail(message, log=print):
    log(f"  ERROR: {message}")
    return False


def digest(path):
    sha = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest().lower()


def installer_assets(tag, root=None):
    """Dort surumlu artifact: iki EXE + iki `.sig`."""
    root = root or ROOT
    paths = []
    for stem in INSTALLER_STEMS:
        exe = os.path.join(root, INSTALLER_DIR, f"{stem}_{tag}.exe")
        paths.append(exe)
        paths.append(exe + ".sig")
    return paths


def mirror_assets(root=None):
    """Gercek kaynak arsivleri source sozlesmesinden turer."""
    root = root or ROOT
    contract = os.path.join(root, SOURCE_CONTRACT)
    return [os.path.join(root, MIRROR_DIR, item.name)
            for item in fetch_sources.plan(contract)]


def expected_assets(tag, root=None):
    """Yayina yuklenecek yerel varliklarin dinamik tam listesi."""
    return installer_assets(tag, root) + mirror_assets(root)


def working_tree_is_clean(root=None, log=print):
    """Staged, tracked ve IGNORE EDILMEYEN untracked degisiklik olmamali.

    `git status --porcelain` ignore edilen dosyalari zaten disarida
    birakir; `installer_output` ve `source_mirror` bu yuzden kapiyi
    kapatmaz.
    """
    ok, output = verify_release_ref.run_git(["status", "--porcelain"], root)
    if not ok:
        return fail("git durumu okunamadi (depo degil mi?)", log)
    if output:
        entries = [line.strip() for line in output.splitlines() if line.strip()]
        fail(f"calisma agaci temiz DEGIL ({len(entries)} girdi):", log)
        for entry in entries[:20]:
            log(f"         {entry}")
        return False
    return True


def signature_is_valid(exe_path, log=print):
    """`.sig` KRIPTOGRAFIK olarak dogrulanir; varlik denetimi YETMEZ.

    Imzalanan veri EXE'nin onaltilik SHA-256 metnidir (bkz.
    `packaging/sign_release.py::sign`). Baska bir EXE'nin gecerli imzasi
    da bu yuzden REDDEDILIR.
    """
    sig_path = exe_path + ".sig"
    name = os.path.basename(exe_path)
    try:
        with open(sig_path, encoding="ascii") as handle:
            signature = handle.read().strip()
    except OSError as exc:
        return fail(f"{name}.sig okunamadi: {exc}", log)
    except UnicodeError as exc:
        # `.sig` saf ASCII base64'tur. ASCII disi bayt `UnicodeDecodeError`
        # firlatir ve bu bir `OSError` DEGILDIR; yalniz `OSError` yakalamak
        # araci traceback ile dusururdu (olculdu).
        return fail(f"{name}.sig ASCII base64 degil: {exc}", log)
    try:
        release_signature.verify(digest(exe_path), signature)
    except release_signature.SignatureError as exc:
        return fail(f"{name} imza dogrulamasi BASARISIZ: {exc}", log)
    except Exception as exc:                       # fail-closed
        return fail(f"{name} imzasi dogrulanamadi: {type(exc).__name__}", log)
    return True


def mirror_matches_manifest(root=None, log=print):
    """Kaynak sozlesmesi hazir ve arsivler dogrulanmis olmali."""
    root = root or ROOT
    manifest_path = os.path.join(root, SOURCE_CONTRACT)
    try:
        open_blockers = fetch_sources.blockers(manifest_path)
        planned = fetch_sources.plan(manifest_path)
    except (OSError, ValueError, TypeError) as exc:
        return fail(f"kaynak sozlesmesi okunamadi: {exc}", log)

    if open_blockers:
        fail("release kaynak kapisi KAPALI:", log)
        for reason in open_blockers:
            log(f"         {reason}")
        return False

    ok = True
    for item in planned:
        path = os.path.join(root, MIRROR_DIR, item.name)
        if not os.path.isfile(path):
            ok = fail(f"kaynak aynasi eksik: {item.name}", log) and ok
            continue
        actual_size = os.path.getsize(path)
        if actual_size != item.size:
            ok = fail(f"{item.name} boyut UYUSMUYOR "
                      f"(beklenen {item.size:,}, gercek {actual_size:,})",
                      log) and ok
            continue
        actual = digest(path)
        if actual != item.sha256:
            ok = fail(f"{item.name} SHA-256 UYUSMUYOR "
                      f"(beklenen {item.sha256[:16]}..., "
                      f"gercek {actual[:16]}...)", log) and ok
    return ok


def run(tag, root=None, log=print):
    """Kapiyi calistirir. Doner: `True` (yayina hazir) / `False`."""
    root = root or ROOT
    if not tag:
        return fail("tag adi verilmedi", log)

    ok = True

    log("[1/4] Tag butunlugu")
    if not verify_release_ref.verify(tag, root, log=log):
        ok = False

    log("[2/4] Calisma agaci")
    if working_tree_is_clean(root, log):
        log("  OK  calisma agaci temiz")
    else:
        ok = False

    log("[3/4] Installer artifact'leri ve imzalar")
    for path in installer_assets(tag, root):
        if not os.path.isfile(path):
            ok = fail(f"eksik varlik: {os.path.basename(path)}", log) and ok
    for stem in INSTALLER_STEMS:
        exe = os.path.join(root, INSTALLER_DIR, f"{stem}_{tag}.exe")
        if os.path.isfile(exe) and os.path.isfile(exe + ".sig"):
            if signature_is_valid(exe, log):
                log(f"  OK  {os.path.basename(exe)} imzasi gecerli")
            else:
                ok = False

    log("[4/4] Kaynak/lisans aynasi")
    if mirror_matches_manifest(root, log):
        log("  OK  ayna manifest ile ayni")
    else:
        ok = False

    try:
        assets = expected_assets(tag, root)
    except (OSError, ValueError, TypeError) as exc:
        fail(f"kaynak varlik listesi olusturulamadi: {exc}", log)
        ok = False
        assets = installer_assets(tag, root)
    log(f"  Yuklenecek varliklar ({len(assets)}):")
    for path in assets:
        mark = "OK " if os.path.isfile(path) else "YOK"
        log(f"    [{mark}] {os.path.basename(path)}")

    if ok:
        log(f"  OK  {tag} yayina hazir  ({len(assets)} varlik)")
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
        print("usage: prepublish.py --tag <vX.Y>")
        return 1
    return 0 if run(tag, cwd) else 1


if __name__ == "__main__":
    sys.exit(main())
