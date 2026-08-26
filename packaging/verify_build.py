# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Release zincirinin dogrulama adimlari (build_release.bat tarafindan cagrilir).

`--pre`  : Tam yerel release icin tum kaynaklar ve runtime hash'leri
`--pre-main`: Hosted ana paket icin yalniz ana paket kaynak/runtime girdileri
`--post` : dist agaci eksiksiz mi
`--final`: kurulum dosyasi olustu mu + boyut raporu

Cikis kodu 0 = basarili, 1 = basarisiz. Hicbir adim "muhtemelen tamamdir"
demez; her sey acikca olculur.
"""
import hashlib
import os
import sys

from pyinstaller_binary_policy import is_forbidden_root_destination

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist", "MLC Player")
MANIFEST = os.path.join(ROOT, "bin", "RUNTIME_MANIFEST.txt")

# Paketlenen runtime ikilileri -- TEK kaynak.
#
# OLCULEN KUSUR (17 Agustos 2026): burada IKI ayri liste vardi. `mpv-2.dll`
# yalnizca VARLIK denetimine giriyor, SHA-256 dogrulamasi ise ayri bir
# demette (`yt-dlp.exe`, `deno.exe`) yapiliyordu ve mpv orada YOKTU. Bozuk
# ya da yanlis surum bir DLL on-kontrolden gecip release zincirine
# girebiliyordu; paketin %59'u o dosyadir.
#
# Hem `SOURCE_FILES` hem hash dogrulamasi ARTIK buradan turer; ikinci bir
# liste tutulmadigi icin bir runtime yeniden unutulamaz.
MAIN_RUNTIME_FILES = ("mpv-2.dll",)
ADDON_RUNTIME_FILES = ("yt-dlp.exe", "deno.exe")
RUNTIME_FILES = MAIN_RUNTIME_FILES + ADDON_RUNTIME_FILES

# Sources that must reach the main PyInstaller package.
MAIN_SOURCE_FILES = tuple(
    os.path.join("bin", name) for name in MAIN_RUNTIME_FILES) + (
    os.path.join("licenses", "mpv-NOTICE.txt"),
    os.path.join("licenses", "THIRD_PARTY_NOTICES.txt"),
    os.path.join("licenses", "Qt-LGPL-3.0.txt"),
    os.path.join("licenses", "Qt-RELINKING.txt"),
    os.path.join("licenses", "Python-LICENSE.txt"),
    os.path.join("licenses", "PyQt6_sip-LICENSE.txt"),
    os.path.join("licenses", "cffi-LICENSE.txt"),
    os.path.join("licenses", "cryptography-LICENSE.txt"),
    os.path.join("licenses", "OpenSSL-LICENSE.txt"),
    os.path.join("licenses", "pycparser-LICENSE.txt"),
    os.path.join("licenses", "python-mpv-LICENSE-GPL.txt"),
    os.path.join("licenses", "python-mpv-LICENSE-LGPL.txt"),
    os.path.join("assets", "mlc-player-icon.ico"),
    os.path.join("assets", "mlc-player-icon-transparent.ico"),
    "LICENSE",
    "README.md",
    "README.tr.md",
    "MLCPlayer.spec",
    os.path.join("packaging", "pyinstaller_binary_policy.py"),
    os.path.join("packaging", "run_pyinstaller.py"),
    "main.py",
)

# Optional add-on inputs. The established full release preflight remains the
# union of both sets, while hosted unsigned main builds never need these bytes.
ADDON_SOURCE_FILES = tuple(
    os.path.join("bin", name) for name in ADDON_RUNTIME_FILES) + (
    os.path.join("licenses", "yt-dlp-LICENSE.txt"),
    os.path.join("licenses", "yt-dlp-THIRD_PARTY_LICENSES.txt"),
    os.path.join("licenses", "deno-LICENSE.txt"),
)
SOURCE_FILES = MAIN_SOURCE_FILES + ADDON_SOURCE_FILES

# Files that must be ABSENT from the package (deliberately excluded).
FORBIDDEN_IN_DIST = (
    os.path.join("_internal", "PyQt6", "Qt6", "bin", "opengl32sw.dll"),
    os.path.join("_internal", "PyQt6", "Qt6", "bin", "Qt6Pdf.dll"),
    os.path.join("_internal", "numpy"),
    os.path.join("_internal", "PIL"),
    os.path.join("_internal", "PyQt6", "Qt6", "translations"),
)

# Files that must be PRESENT inside dist.
REQUIRED_IN_DIST = (
    "MLC Player.exe",
    os.path.join("_internal", "PyQt6", "QtCore.pyd"),
    os.path.join("_internal", "PyQt6", "QtGui.pyd"),
    os.path.join("_internal", "PyQt6", "QtWidgets.pyd"),
    os.path.join("_internal", "PyQt6", "Qt6", "bin", "Qt6Core.dll"),
    os.path.join("_internal", "PyQt6", "Qt6", "bin", "Qt6Gui.dll"),
    os.path.join("_internal", "PyQt6", "Qt6", "bin", "Qt6Widgets.dll"),
    os.path.join("_internal", "bin", "mpv-2.dll"),
    os.path.join("_internal", "bin", "RUNTIME_MANIFEST.txt"),
    os.path.join("_internal", "licenses", "mpv-NOTICE.txt"),
    os.path.join("_internal", "licenses", "THIRD_PARTY_NOTICES.txt"),
    os.path.join("_internal", "licenses", "Qt-LGPL-3.0.txt"),
    os.path.join("_internal", "licenses", "Qt-RELINKING.txt"),
    os.path.join("_internal", "licenses", "Python-LICENSE.txt"),
    os.path.join("_internal", "licenses", "PyQt6_sip-LICENSE.txt"),
    os.path.join("_internal", "licenses", "cffi-LICENSE.txt"),
    os.path.join("_internal", "licenses", "cryptography-LICENSE.txt"),
    os.path.join("_internal", "licenses", "OpenSSL-LICENSE.txt"),
    os.path.join("_internal", "licenses", "pycparser-LICENSE.txt"),
    os.path.join("_internal", "licenses", "python-mpv-LICENSE-GPL.txt"),
    os.path.join("_internal", "licenses", "python-mpv-LICENSE-LGPL.txt"),
    os.path.join("_internal", "assets", "mlc-player-icon.ico"),
    os.path.join("_internal", "assets", "mlc-player-icon-transparent.ico"),
    os.path.join("_internal", "translations", "mlcplayer_en.qm"),
    os.path.join("_internal", "LICENSE"),
    os.path.join("_internal", "README.md"),
    os.path.join("_internal", "README.tr.md"),
)


def fail(message, log=print):
    """Hata YAZAR ve `False` doner.

    OLCULEN KUSUR (17 Agustos 2026): `log=` verilse bile hatalar kosulsuz
    `print` ile stdout'a gidiyordu; cagiran mesajlari TOPLAYAMIYORDU.
    Varsayilan `print` oldugu icin mevcut cagirilar degismeden calisir.
    """
    log(f"  ERROR: {message}")
    return False


def digest(path):
    sha = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest().lower()


def manifest_entries(manifest=None):
    """`RUNTIME_MANIFEST.txt` icindeki dosya -> (boyut, SHA-256) eslemesi.

    Bicim: `ad | surum | url | boyut | sha256`. Boyut okunamazsa `None`
    donulur; cagiran bunu "kayit eksik" sayar ve SESSIZCE gecmez.
    """
    entries = {}
    with open(manifest or MANIFEST, encoding="utf-8") as handle:
        for line in handle:
            if line.lstrip().startswith("#"):
                continue
            parts = [part.strip() for part in line.split("|")]
            if len(parts) >= 5 and parts[0].endswith((".exe", ".dll", ".txt")):
                try:
                    size = int(parts[3])
                except ValueError:
                    size = None
                entries[parts[0]] = (size, parts[4].lower())
    return entries


def verify_runtime_binaries(root=None, manifest=None, log=print,
                            runtime_files=None):
    """Secilen runtime'lari manifest'e karsi dogrular.

    Boyut ONCE denetlenir: yanlis boyut zaten yanlis dosyadir ve 119 MB'lik
    bir DLL'in ozetini bosuna hesaplamaya gerek yoktur.

    `root`/`manifest` disaridan verilebilir; testler gercek 119 MB'lik
    DLL'i kopyalamadan kucuk fixture dosyalariyla ayni yolu kullanir.
    """
    root = root or ROOT
    runtime_files = RUNTIME_FILES if runtime_files is None else runtime_files
    try:
        expected = manifest_entries(manifest)
    except OSError as exc:
        return fail(f"manifest okunamadi: {exc}", log)
    except UnicodeError as exc:
        # Manifest UTF-8 okunur; gecersiz bayt `UnicodeDecodeError`
        # firlatir ve bu bir `OSError` DEGILDIR. Yalniz `OSError`
        # yakalamak araci traceback ile dusururdu (olculdu).
        return fail(f"manifest UTF-8 olarak cozulemedi: {exc}", log)
    except (ValueError, TypeError) as exc:
        return fail(f"manifest bozuk: {exc}", log)
    ok = True
    for name in runtime_files:
        path = os.path.join(root, "bin", name)
        want_size, want_hash = expected.get(name, (None, ""))
        if not want_hash or want_size is None:
            ok = fail(f"no manifest entry: {name}", log) and ok
            continue
        if not os.path.isfile(path):
            ok = fail(f"missing runtime: bin/{name}", log) and ok
            continue
        got_size = os.path.getsize(path)
        if got_size != want_size:
            ok = fail(f"{name} SIZE DOES NOT MATCH "
                      f"(beklenen {want_size:,}, gercek {got_size:,})",
                      log) and ok
            continue
        got_hash = digest(path)
        if got_hash != want_hash:
            ok = fail(f"{name} SHA-256 DOES NOT MATCH "
                      f"(beklenen {want_hash[:16]}..., "
                      f"gercek {got_hash[:16]}...)", log) and ok
        else:
            log(f"  OK  {name}  ({got_size:,} bytes)")
    return ok


def check_pre():
    ok = True
    print("[1/3] Source files and runtime hashes")
    for relative in SOURCE_FILES:
        path = os.path.join(ROOT, relative)
        if not os.path.isfile(path):
            ok = fail(f"missing file: {relative}") and ok
    if not ok:
        return False

    # UC runtime'in TAMAMI boyut + SHA-256 ile dogrulanir (bkz.
    # `RUNTIME_FILES`); ikinci bir liste yoktur.
    return verify_runtime_binaries(ROOT, MANIFEST) and ok


def check_pre_main():
    """Hosted ana paket girdilerini add-on dosyalarina baglamadan dogrula."""
    ok = True
    print("[1/3] Main-package source files and runtime hashes")
    for relative in MAIN_SOURCE_FILES:
        path = os.path.join(ROOT, relative)
        if not os.path.isfile(path):
            ok = fail(f"missing file: {relative}") and ok
    if not ok:
        return False
    return verify_runtime_binaries(
        ROOT, MANIFEST, runtime_files=MAIN_RUNTIME_FILES) and ok


def check_post():
    ok = True
    print("[2/3] dist tree")
    if not os.path.isdir(DIST):
        return fail("dist\\MLC Player was not created")
    for relative in REQUIRED_IN_DIST:
        path = os.path.join(DIST, relative)
        if not os.path.exists(path):
            ok = fail(f"missing from the package: {relative}") and ok
    for relative in FORBIDDEN_IN_DIST:
        if os.path.exists(os.path.join(DIST, relative)):
            ok = fail(f"file that should be excluded is in the package: {relative}") and ok
    internal = os.path.join(DIST, "_internal")
    if os.path.isdir(internal):
        for name in os.listdir(internal):
            path = os.path.join(internal, name)
            if os.path.isfile(path) and is_forbidden_root_destination(name):
                ok = fail(
                    f"foreign root binary is in the package: _internal/{name}") and ok
    if ok:
        total = sum(os.path.getsize(os.path.join(base, name))
                    for base, _dirs, files in os.walk(DIST) for name in files)
        print(f"  OK  package complete  ({total / 1048576:.1f} MB)")
    return ok


def check_final(installer):
    print("[3/3] Installer")
    if not os.path.isfile(installer):
        return fail(f"the installer was not created: {installer}")
    size = os.path.getsize(installer)
    folder = sum(os.path.getsize(os.path.join(base, name))
                 for base, _dirs, files in os.walk(DIST) for name in files)
    print(f"  OK  {os.path.basename(installer)}  {size / 1048576:.1f} MB")
    if folder:
        print(f"      installed size {folder / 1048576:.1f} MB  "
              f"(compressed by {100 - size * 100 / folder:.0f}%)")
    return True


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "--pre":
        return 0 if check_pre() else 1
    if mode == "--pre-main":
        return 0 if check_pre_main() else 1
    if mode == "--post":
        return 0 if check_post() else 1
    if mode == "--final":
        target = sys.argv[2] if len(sys.argv) > 2 else ""
        return 0 if check_final(target) else 1
    print("usage: verify_build.py --pre | --pre-main | --post | "
          "--final <installer.exe>")
    return 1


if __name__ == "__main__":
    sys.exit(main())
