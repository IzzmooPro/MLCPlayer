"""Compiles the `.ts` translation sources into `.qm` binaries.

WHY IT IS A SEPARATE STEP. `.qm` files are BUILD OUTPUT and live in
`.gitignore`; `MLCPlayer.spec` collects them from the `translations/`
folder. But nothing in the chain compiled them: on a clean checkout
`packaging/build_release.bat` left that folder empty, the package shipped
with no translations, and the user silently got Turkish only. This script
closes that gap and runs BEFORE PyInstaller inside `build_release.bat`.

EMPTY TRANSLATIONS ARE NOT COMPILED. A `.ts` file that is entirely
`unfinished` produces a valid but EMPTY `.qm`. Packaging that is
pointless: `app.i18n.available_languages()` rejects an empty translation
anyway, and carrying a dead file inside the package helps nobody. Skipped
languages are REPORTED, not swallowed.

Usage:
    python packaging/compile_translations.py
"""

import os
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANSLATIONS_DIR = os.path.join(ROOT, "translations")

#: Qt's compiler. It comes with PySide6; `lrelease`, NOT `pylupdate6`.
COMPILER = "pyside6-lrelease"


def translated_count(ts_path):
    """How many strings in a `.ts` file are ACTUALLY translated.

    Broken XML produces no count; the file is skipped and the caller
    reports it.
    """
    try:
        tree = ET.parse(ts_path)
    except ET.ParseError:
        return 0
    count = 0
    for message in tree.iter("message"):
        node = message.find("translation")
        if node is None:
            continue
        if node.get("type") != "unfinished" and (node.text or "").strip():
            count += 1
    return count


def compile_one(ts_path, qm_path):
    """Compiles one file. Returns `True` on success."""
    result = subprocess.run([COMPILER, ts_path, "-qm", qm_path],
                            capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        sys.stderr.write(result.stderr or "")
        return False
    return os.path.isfile(qm_path)


def compile_all(source_dir=TRANSLATIONS_DIR, target_dir=None):
    """Compiles every `.ts` file.

    Returns `(written_qm_paths, skipped_file_names)`.
    """
    target_dir = target_dir or source_dir
    os.makedirs(target_dir, exist_ok=True)
    written = []
    skipped = []
    for name in sorted(os.listdir(source_dir)):
        if not name.endswith(".ts"):
            continue
        ts_path = os.path.join(source_dir, name)
        if translated_count(ts_path) == 0:
            # A language with no translations: shipping an empty `.qm`
            # helps nobody.
            skipped.append(name)
            continue
        qm_path = os.path.join(target_dir, name[:-3] + ".qm")
        if compile_one(ts_path, qm_path):
            written.append(qm_path)
        else:
            skipped.append(name)
    return written, skipped


def main():
    try:
        written, skipped = compile_all()
    except FileNotFoundError:
        print(f"[ERROR] {COMPILER} not found. Install it with: pip install pyside6")
        return 1
    for path in written:
        print(f"[OK] {os.path.basename(path)}")
    for name in skipped:
        print(f"[SKIPPED] {name} (no translations)")
    if not written:
        print("[ERROR] No translation could be compiled; the package would "
              "ship without translations.")
        return 1
    print(f"[INFO] {len(written)} translations compiled, {len(skipped)} skipped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
