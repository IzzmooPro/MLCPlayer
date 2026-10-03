# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""İzlenen dosyalar geliştiricinin gerçek profil yolunu taşımaz.

Ölçülen kusur (3 Ekim 2026): bir test çıktısı olan `second_launch.py`,
makinenin mutlak profil yolunu taşıyarak 16 Ağustos 2026'da commit edilmiş
ve herkese açık `master`a ulaşmıştı; depo geçmişi daha önce tam da bu ad
için yeniden yazılmıştı. Test bir ad SABİTLEMEZ (sabitlemek adı yayımlardı):
çalıştığı makinenin profil yolunu çalışma anında okur.

`docs/VERIFICATION_LEDGER.json` append-only olduğu için eski kayıtlar kapsam
dışıdır; o yollar kullanıcı kararıyla yerinde bırakıldı. Ledger için yalnız
HEAD sonrası eklenen kayıtlar denetlenir.
"""
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LEDGER = "docs/VERIFICATION_LEDGER.json"
_GENERIC_PROFILES = {"runneradmin", "user", "public", "default", "administrator"}


def _profile_markers():
    profile = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    name = Path(profile).name
    if not name or name.lower() in _GENERIC_PROFILES:
        return []
    slash, back = "/", "\\"
    return [
        f"{back}users{back}{name}".lower(),
        f"{slash}users{slash}{name}".lower(),
        f"{back * 2}users{back * 2}{name}".lower(),
    ]


def _tracked():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                         encoding="utf-8", check=True).stdout
    return [line for line in out.splitlines() if line]


def test_tracked_text_files_do_not_contain_the_local_profile_path():
    markers = _profile_markers()
    if not markers:
        pytest.skip("generic profile; nothing personal to look for")
    offenders = []
    for relative in _tracked():
        if relative == LEDGER:
            continue
        try:
            text = (ROOT / relative).read_bytes().decode("utf-8").lower()
        except (OSError, UnicodeDecodeError):
            continue
        if any(marker in text for marker in markers):
            offenders.append(relative)
    assert offenders == []


def test_new_ledger_entries_do_not_contain_the_local_profile_path():
    markers = _profile_markers()
    if not markers:
        pytest.skip("generic profile; nothing personal to look for")
    committed = subprocess.run(
        ["git", "show", f"HEAD:{LEDGER}"], cwd=ROOT, capture_output=True,
        encoding="utf-8")
    if committed.returncode != 0:
        pytest.skip("no committed ledger to compare against")
    old_ids = {entry["id"] for entry in json.loads(committed.stdout)["entries"]}
    current = json.loads((ROOT / LEDGER).read_text(encoding="utf-8"))
    for entry in current["entries"]:
        if entry["id"] in old_ids:
            continue
        text = json.dumps(entry, ensure_ascii=False).lower()
        assert not any(marker in text for marker in markers), entry["id"]
