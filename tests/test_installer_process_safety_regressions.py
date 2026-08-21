# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Installer çalışan süreçleri yalnız kendi kaynakları üzerinden kapatır.

Ad-temelli ``taskkill /F /IM`` aynı ada sahip ilgisiz bir programı da zorla
kapatabilir ve kaydedilmemiş veri kaybına yol açabilir. Inno Setup'ın Restart
Manager yolu kurulumun gerçekten güncellediği kaynakları hedeflemelidir.
"""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent.parent
MAIN_ISS = ROOT / "packaging" / "MLCPlayer.iss"
ADDON_ISS = ROOT / "packaging" / "MLCPlayer_InternetVideo.iss"
SINGLE_INSTANCE = ROOT / "app" / "single_instance.py"


def read(path):
    return path.read_text(encoding="utf-8-sig")


def executable_lines(iss):
    """Return ISS source without full-line comments.

    Safety rationale may name a forbidden command.  The regression must reject
    an executable command, not documentation explaining why it is forbidden.
    """
    return "\n".join(
        line for line in iss.splitlines()
        if not line.lstrip().startswith((";", "//")))


def test_main_installer_never_force_kills_processes_by_image_name():
    iss = read(MAIN_ISS)
    code = executable_lines(iss)

    assert "CloseApplications=yes" in iss
    assert 'CloseApplicationsFilter="MLC Player.exe"' in iss
    assert "RestartApplications=no" in iss
    assert "taskkill" not in code.lower()
    assert '/F /IM "MLC Player.exe"' not in code


def test_main_uninstaller_blocks_while_the_installed_player_is_running():
    """AppMutex must live until process exit, not only window shutdown."""
    iss = read(MAIN_ISS)
    runtime = read(SINGLE_INSTANCE)

    match = re.search(
        r'^#define\s+PlayerLifecycleMutex\s+"([^\r\n"]+)"$',
        iss,
        re.MULTILINE,
    )
    assert match, "main uninstaller has no running-app mutex identity"
    mutex_name = match.group(1)

    assert f'INSTALLER_APP_MUTEX = "{mutex_name}"' in runtime
    assert "_ensure_installer_lifecycle_mutex()" in runtime
    assert re.search(
        r"CreateMutexW\s*\(\s*None\s*,\s*False\s*,\s*"
        r"INSTALLER_APP_MUTEX\s*\)",
        runtime,
    )
    assert "_INSTALLER_APP_MUTEX_HANDLE = handle" in runtime
    assert re.search(
        r"function\s+InitializeUninstall\s*\(\s*\)\s*:\s*Boolean;"
        r"[\s\S]*?CheckForMutexes\s*\(\s*"
        r"'\{#PlayerLifecycleMutex\}'\s*\)",
        iss,
        re.IGNORECASE,
    )
    assert "AppMutex=" not in executable_lines(iss)


def test_addon_registers_the_actual_player_and_runtime_resources():
    iss = read(ADDON_ISS)
    code = executable_lines(iss)

    assert "CloseApplications=yes" in iss
    assert 'CloseApplicationsFilter="yt-dlp.exe,deno.exe"' in iss
    assert "procedure RegisterExtraCloseApplicationsResources" in iss
    assert re.search(
        r"RegisterExtraCloseApplicationsResource\s*\(\s*"
        r"ExpandConstant\s*\(\s*'\{app\}\\MLC Player\.exe'\s*\)\s*\)",
        code,
    )
    assert "taskkill" not in code.lower()
