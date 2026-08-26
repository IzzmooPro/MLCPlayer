# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Sürüm tek kaynaktan gelir: `app/config.py` → `APP_VERSION`.

Yayın öncesi kusur: üç ayrı yerde üç ayrı sürüm vardı — `config.VERSION`
"1.1" (hiçbir yerde kullanılmıyordu), Hakkında penceresinde düz metin
"Sürüm 1.1", installer'da ise "v1.0" ve `VersionInfoVersion=1.0.0.0`.
Kurulum dosyasının adı da buradan türediği için yanlış sürümle üretilen
bir setup, ilk GitHub etiketiyle çelişirdi.

Bu test üç yüzeyi tek kaynağa bağlar: ürün sabiti, Hakkında metni ve
installer betiği. Qt gerektirmez; kaynak dosyaları okur.
"""

import re
from pathlib import Path

from app.config import APP_VERSION, WINDOWS_VERSION

ROOT = Path(__file__).resolve().parent.parent
ISS_PATH = ROOT / "packaging" / "MLCPlayer.iss"
MENU_ACTIONS_PATH = ROOT / "app" / "menu_actions.py"


def _iss_text():
    return ISS_PATH.read_text(encoding="utf-8-sig")


def test_app_version_has_release_format():
    """`v<major>.<minor>` biçimi; installer adı ve etiket bundan türer."""
    assert re.fullmatch(r"v\d+\.\d+", APP_VERSION), APP_VERSION


def test_current_release_target_is_v0_40():
    """Bu yayin turunun acikca onaylanan hedefi sessizce ayrismamali."""
    assert APP_VERSION == "v0.40"
    assert WINDOWS_VERSION == "0.40.0.0"


def test_windows_version_is_derived_from_app_version():
    """Windows sürüm alanları dört sayılıdır ve elle yazılmaz."""
    assert re.fullmatch(r"\d+\.\d+\.\d+\.\d+", WINDOWS_VERSION), WINDOWS_VERSION
    numeric = APP_VERSION.lstrip("v")
    assert WINDOWS_VERSION.startswith(numeric + ".")


def test_installer_define_matches_app_version():
    match = re.search(r'#define\s+MyAppVersion\s+"([^"]+)"', _iss_text())
    assert match, "MLCPlayer.iss içinde MyAppVersion tanımı yok"
    assert match.group(1) == APP_VERSION


def test_installer_version_info_matches_app_version():
    text = _iss_text()
    define = re.search(r'#define\s+MyAppNumericVersion\s+"([^"]+)"', text)
    assert define, "MLCPlayer.iss içinde MyAppNumericVersion tanımı yok"
    assert define.group(1) == WINDOWS_VERSION
    for key in ("VersionInfoVersion", "VersionInfoProductVersion"):
        match = re.search(rf"^{key}=(.+)$", text, re.MULTILINE)
        assert match, f"MLCPlayer.iss içinde {key} yok"
        assert match.group(1).strip() == "{#MyAppNumericVersion}", key


def test_installer_output_name_derives_from_define():
    """Setup adı sabit yazılmaz; sürüm tanımından türer."""
    match = re.search(r"^OutputBaseFilename=(.+)$", _iss_text(), re.MULTILINE)
    assert match
    assert match.group(1).strip() == "MLCPlayer_Setup_{#MyAppVersion}"


def test_about_dialog_has_no_hardcoded_version():
    """Hakkında penceresi sürümü düz metin yazmaz, sabitten okur."""
    source = MENU_ACTIONS_PATH.read_text(encoding="utf-8")
    hardcoded = re.findall(r"Sürüm\s+v?\d+\.\d+", source)
    assert not hardcoded, hardcoded
    assert "APP_VERSION" in source
