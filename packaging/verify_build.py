# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Release zincirinin dogrulama adimlari (build_release.bat tarafindan cagrilir).

`--pre`  : PyInstaller calismadan ONCE kaynak dosyalar ve runtime hash'leri
`--post` : dist agaci eksiksiz mi
`--final`: kurulum dosyasi olustu mu + boyut raporu

Cikis kodu 0 = basarili, 1 = basarisiz. Hicbir adim "muhtemelen tamamdir"
demez; her sey acikca olculur.
"""
import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist", "MLC Player")
MANIFEST = os.path.join(ROOT, "bin", "RUNTIME_MANIFEST.txt")

# Sources that must reach PyInstaller.
SOURCE_FILES = (
    os.path.join("bin", "mpv-2.dll"),
    os.path.join("bin", "yt-dlp.exe"),
    os.path.join("bin", "deno.exe"),
    os.path.join("licenses", "yt-dlp-LICENSE.txt"),
    os.path.join("licenses", "yt-dlp-THIRD_PARTY_LICENSES.txt"),
    os.path.join("licenses", "deno-LICENSE.txt"),
    os.path.join("assets", "mlc-player-icon.ico"),
    # GPLv3: the licence text and the README MUST ACCOMPANY the
    # distribution. The spec places them in the `dist` tree, and setup also
    # copies them to the install root and shows them on the wizard screen.
    # If either is missing the build stops BEFORE it starts.
    "LICENSE",
    "README.md",
    "MLCPlayer.spec",
    "main.py",
)

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
    os.path.join("_internal", "bin", "mpv-2.dll"),
    os.path.join("_internal", "assets", "mlc-player-icon.ico"),
)


def fail(message):
    print(f"  ERROR: {message}")
    return False


def digest(path):
    sha = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest().lower()


def manifest_hashes():
    """`bin/RUNTIME_MANIFEST.txt` icindeki dosya -> SHA-256 eslemesi."""
    entries = {}
    with open(MANIFEST, encoding="utf-8") as handle:
        for line in handle:
            if line.lstrip().startswith("#"):
                continue
            parts = [part.strip() for part in line.split("|")]
            if len(parts) >= 4 and parts[0].endswith((".exe", ".dll", ".txt")):
                entries[parts[0]] = parts[-1].lower()
    return entries


def check_pre():
    ok = True
    print("[1/3] Source files and runtime hashes")
    for relative in SOURCE_FILES:
        path = os.path.join(ROOT, relative)
        if not os.path.isfile(path):
            ok = fail(f"missing file: {relative}") and ok
    if not ok:
        return False

    expected = manifest_hashes()
    for name in ("yt-dlp.exe", "deno.exe"):
        path = os.path.join(ROOT, "bin", name)
        want = expected.get(name, "")
        if not want:
            ok = fail(f"no manifest entry: {name}") and ok
            continue
        got = digest(path)
        if got != want:
            ok = fail(f"{name} SHA-256 DOES NOT MATCH "
                      f"(beklenen {want[:16]}..., gercek {got[:16]}...)") and ok
        else:
            print(f"  OK  {name}  ({os.path.getsize(path):,} bytes)")
    return ok


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
    if mode == "--post":
        return 0 if check_post() else 1
    if mode == "--final":
        target = sys.argv[2] if len(sys.argv) > 2 else ""
        return 0 if check_final(target) else 1
    print("usage: verify_build.py --pre | --post | --final <installer.exe>")
    return 1


if __name__ == "__main__":
    sys.exit(main())
