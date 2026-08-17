# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Paketlenen EXE kendi adını ve sürümünü TAŞIR.

ÖLÇÜLEN KUSUR (16 Ağustos 2026, kullanıcı bildirimi): Windows "Birlikte aç"
listesinde program **"MLC Player.exe"** olarak görünüyordu. Sebep: EXE'de
sürüm kaynağı (VS_VERSION_INFO) yoktu; Windows `FileDescription` alanını
bulamayınca dosya adına düşer. Ölçüm: paketlenen exe'nin ProductVersion
alanı BOŞTU.
"""

import importlib.util
import re
from pathlib import Path

import pytest

from app.config import APP_VERSION, WINDOWS_VERSION

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "MLCPlayer.spec"


def _load_version_resource():
    """Yol üzerinden yüklenir: `packaging` adı kurulu bir dağıtımla çakışır."""
    path = ROOT / "packaging" / "version_resource.py"
    spec = importlib.util.spec_from_file_location("mlc_version_resource", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


version_resource = _load_version_resource()


def test_windows_shows_the_product_name_not_the_file_name():
    """`FileDescription` Windows'un listede gösterdiği alandır."""
    text = version_resource.render(APP_VERSION, WINDOWS_VERSION)
    assert "StringStruct('FileDescription', 'MLC Player')" in text
    assert ".exe" not in re.search(
        r"StringStruct\('FileDescription', '([^']*)'\)", text).group(1)


def test_resource_versions_come_from_the_single_source():
    text = version_resource.render(APP_VERSION, WINDOWS_VERSION)
    assert f"StringStruct('FileVersion', '{APP_VERSION}')" in text
    assert f"StringStruct('ProductVersion', '{APP_VERSION}')" in text
    numbers = version_resource.version_numbers(WINDOWS_VERSION)
    assert text.count(str(numbers)) == 2, "filevers ve prodvers aynı olmalı"


@pytest.mark.parametrize("windows_version,expected", [
    ("0.2.0.0", (0, 2, 0, 0)),
    ("1.0.0.0", (1, 0, 0, 0)),
    ("0.10", (0, 10, 0, 0)),
])
def test_version_numbers_always_have_four_parts(windows_version, expected):
    assert version_resource.version_numbers(windows_version) == expected


def test_string_table_and_translation_agree_on_the_language():
    """ÖLÇÜLEN TUZAK: uyuşmazsa kaynak EXE'ye girer ama Windows ÇÖZEMEZ.

    İlk denemede `StringTable` anahtarı `040E` (Macarca), `Translation` ise
    `1055` (Türkçe) idi. EXE'de 1404 baytlık kaynak vardı, buna rağmen
    `FileDescription` boş görünüyordu.
    """
    text = version_resource.render(APP_VERSION, WINDOWS_VERSION)
    table_key = re.search(r"StringTable\(\s*'([0-9A-Fa-f]{8})'", text).group(1)
    language, charset = re.search(
        r"VarStruct\('Translation', \[(\d+), (\d+)\]\)", text).groups()
    assert table_key[:4].upper() == f"{int(language):04X}", (table_key, language)
    assert table_key[4:].upper() == f"{int(charset):04X}", (table_key, charset)


def test_spec_hands_the_resource_to_pyinstaller():
    """Kaynak üretilse bile spec vermezse EXE'ye GİRMEZ."""
    spec = SPEC.read_text(encoding="utf-8")
    assert "version_resource" in spec, "spec sürüm kaynağını üretmiyor"
    assert re.search(r"^\s*version=", spec, re.MULTILINE), (
        "EXE() çağrısına version= verilmemiş")
