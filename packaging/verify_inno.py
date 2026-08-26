# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Inno kaynaklarini pahali paketleme baslamadan compiler ile dogrular."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import APP_VERSION, WINDOWS_VERSION  # noqa: E402


MAIN_ISS = "packaging/MLCPlayer.iss"
ADDON_ISS = "packaging/MLCPlayer_InternetVideo.iss"


def _field(pattern, text):
    found = re.search(pattern, text, re.MULTILINE)
    return found.group(1).strip() if found else None


def validate_main_source(text, log=print):
    """Kanonik surum ve installer alanlarini tek build kapisinda baglar."""
    expected = (
        (r'^\s*#define\s+MyAppVersion\s+"([^"]+)"',
         APP_VERSION, "MyAppVersion"),
        (r'^\s*#define\s+MyAppNumericVersion\s+"([^"]+)"',
         WINDOWS_VERSION, "MyAppNumericVersion"),
        (r'^\s*VersionInfoVersion\s*=\s*(\S+)\s*$',
         "{#MyAppNumericVersion}", "VersionInfoVersion"),
        (r'^\s*VersionInfoProductVersion\s*=\s*(\S+)\s*$',
         "{#MyAppNumericVersion}", "VersionInfoProductVersion"),
        (r'^\s*OutputBaseFilename\s*=\s*(\S+)\s*$',
         "MLCPlayer_Setup_{#MyAppVersion}", "OutputBaseFilename"),
    )
    ok = True
    for pattern, wanted, name in expected:
        value = _field(pattern, text)
        if value != wanted:
            log(f"  ERROR: {name} ayrismis: beklenen {wanted}, bulunan {value}")
            ok = False
    return ok


def validate_working_tree(log=print):
    try:
        text = (ROOT / MAIN_ISS).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        log(f"  ERROR: {MAIN_ISS} okunamadi: {exc}")
        return False
    return validate_main_source(text, log=log)


def find_iscc():
    candidates = []
    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(variable)
        if not base:
            continue
        candidates.extend(
            str(Path(base) / f"Inno Setup {major}" / "ISCC.exe")
            for major in (7, 6)
        )
    return next((path for path in candidates if os.path.isfile(path)), None)


def _compile(iscc, script, defines=(), log=print):
    command = [iscc, "/Q", "/O-", "/DMLCCompilePreflight=1"]
    command.extend(f"/D{name}={value}" for name, value in defines)
    command.append(script)
    try:
        result = subprocess.run(
            command,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        log(f"  ERROR: Inno compiler calistirilamadi: {exc}")
        return False
    if result.returncode != 0:
        detail = (result.stdout or "") + (result.stderr or "")
        log(f"  ERROR: Inno compile-only preflight basarisiz: {script}")
        if detail.strip():
            log(detail.strip())
        return False
    log(f"  OK  Inno compile-only: {script}")
    return True


def verify(scope, iscc=None, log=print):
    if scope not in ("main", "all"):
        log(f"  ERROR: bilinmeyen Inno preflight kapsami: {scope}")
        return False
    if not validate_working_tree(log=log):
        return False
    compiler = iscc or find_iscc()
    if not compiler:
        log("  ERROR: ISCC.exe bulunamadi")
        return False
    if not _compile(compiler, MAIN_ISS, log=log):
        return False
    if scope == "all":
        defines = (
            ("AddonVersion", APP_VERSION),
            ("AddonNumericVersion", WINDOWS_VERSION),
        )
        if not _compile(compiler, ADDON_ISS, defines=defines, log=log):
            return False
    return True


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("scope", choices=("main", "all"))
    parser.add_argument("--iscc")
    args = parser.parse_args(argv)
    return 0 if verify(args.scope, iscc=args.iscc) else 1


if __name__ == "__main__":
    sys.exit(main())
