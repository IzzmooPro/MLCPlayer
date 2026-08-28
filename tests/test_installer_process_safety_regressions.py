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
PACKAGING_PLAN = ROOT / "docs" / "PACKAGING_PLAN.md"


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
    assert 'CloseApplicationsFilter="MLC Player.exe,*.dll"' in iss
    assert "RestartApplications=no" in iss
    assert "taskkill" not in code.lower()
    assert '/F /IM "MLC Player.exe"' not in code


def test_restart_manager_filter_matches_the_canonical_packaging_plan():
    iss = read(MAIN_ISS)
    plan = read(PACKAGING_PLAN)
    expected = 'CloseApplicationsFilter="MLC Player.exe,*.dll"'
    setup_contract = plan.split("Planlanan temel ayarlar:", 1)[1].split(
        "```ini", 1
    )[1].split("```", 1)[0]

    assert expected in iss
    assert setup_contract.count(expected) == 1
    assert "CloseApplicationsFilter=MLC Player.exe" not in plan


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


def test_main_installer_mode_detection_is_numeric_and_fail_closed():
    iss = read(MAIN_ISS)
    code = executable_lines(iss).split("[Code]", 1)[1]

    assert "function InitializeSetup(): Boolean" in code
    assert "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{EB0DD5CF-F20B-4B23-A1C9-2C23A83A8758}_is1" in code
    assert "RegQueryStringValue(HKLM64" in code
    assert "InstallLocation" in code
    assert "FileExists(InstalledExePath)" in code
    assert "GetPackedVersion(InstalledExePath, InstalledVersion)" in code
    assert "StrToVersion('{#MyAppNumericVersion}', PackageVersion)" in code
    assert "ComparePackedVersion(InstalledVersion, PackageVersion)" in code
    assert "CustomMessage('CDowngradeBlocked')" in code
    assert "CustomMessage('CVersionStateUnknown')" in code
    assert "Result := False" in code
    assert code.count("Exit;") >= 4
    assert "CompareText(InstalledVersion" not in code
    assert "ignoreversion" in iss


def test_main_installer_revalidates_the_effective_target_before_install():
    iss = read(MAIN_ISS)
    code = executable_lines(iss).split("[Code]", 1)[1]

    assert "function ValidateInstallTarget(): String" in code
    validation = code.split("function ValidateInstallTarget(): String", 1)[1]
    validation = validation.split("function PrepareToInstall", 1)[0]
    assert "WizardDirValue" in validation
    assert "PathIsRooted(TargetDir)" in validation
    assert "PathSame(TargetDir, RegisteredInstallDir)" in validation
    assert "FileExists(TargetExePath)" in validation
    assert "DirectoryHasEntries(TargetDir)" in validation
    assert "GetPackedVersion(TargetExePath, TargetVersion)" in validation
    assert "ComparePackedVersion(TargetVersion, PackageVersion)" in validation
    assert "SamePackedVersion(TargetVersion, RegisteredInstalledVersion)" in validation
    assert "CustomMessage('CDowngradeBlocked')" in validation
    assert "CustomMessage('CTargetLocationMismatch')" in validation
    assert "CustomMessage('CTargetAlreadyOccupied')" in validation
    assert "CustomMessage('CTargetNotEmpty')" in validation

    prepare = code.split("function PrepareToInstall", 1)[1]
    prepare = prepare.split("end;", 1)[0]
    assert "Result := ValidateInstallTarget" in prepare


def test_main_installer_rejects_a_running_player_before_restart_manager_waits():
    """Maintenance must fail fast before Inno enters its long RM shutdown."""
    iss = read(MAIN_ISS)
    code = executable_lines(iss).split("[Code]", 1)[1]
    prepare = code.split("function PrepareToInstall", 1)[1]
    prepare = prepare.split("procedure SetInstallPhase", 1)[0]

    validation = prepare.index("Result := ValidateInstallTarget")
    early_exit = prepare.index("if Result <> '' then", validation)
    maintenance = prepare.index(
        "CurrentInstallMode <> InstallModeFirst", early_exit)
    mutex = prepare.index(
        "CheckForMutexes('{#PlayerLifecycleMutex}')", maintenance)
    message = prepare.index("CustomMessage('CClosePlayerBeforeInstall')", mutex)

    assert validation < early_exit < maintenance < mutex < message
    assert re.search(
        r"if\s*\(CurrentInstallMode\s*<>\s*InstallModeFirst\)\s*and\s*"
        r"CheckForMutexes\s*\(\s*'\{#PlayerLifecycleMutex\}'\s*\)\s*then\s*"
        r"Result\s*:=\s*CustomMessage\s*\(\s*"
        r"'CClosePlayerBeforeInstall'\s*\)\s*;",
        prepare,
        re.IGNORECASE,
    ), "running-player rejection must remain scoped to maintenance/upgrade"
    assert "CloseApplications=yes" in iss
    assert 'CloseApplicationsFilter="MLC Player.exe,*.dll"' in iss
    assert "force" not in prepare.lower()
    assert "taskkill" not in prepare.lower()
    assert "Sleep(" not in prepare


def test_target_directory_enumeration_fails_closed():
    iss = read(MAIN_ISS)
    code = executable_lines(iss).split("[Code]", 1)[1]
    helper = code.split("function DirectoryHasEntries", 1)[1]
    helper = helper.split("function ValidateInstallTarget", 1)[0]

    assert re.search(r"Result\s*:=\s*True;[\s\S]*?if not DirExists", helper)
    assert re.search(
        r"if not DirExists\(Directory\) then[\s\S]*?Result\s*:=\s*False;[\s\S]*?Exit;",
        helper,
    )
    assert re.search(r"if not FindFirst\([\s\S]*?then\s+Exit;", helper)
    assert re.search(r"until not FindNext\(FindRec\);\s+Result\s*:=\s*False;", helper)


def test_finish_actions_have_exact_order_defaults_and_user_context():
    iss = read(MAIN_ISS)
    section = iss.split("[Run]", 1)[1].split("\n[", 1)[0]
    lines = [line for line in section.splitlines() if line.startswith("Filename:")]

    assert len(lines) == 3, lines
    assert 'Filename: "{app}\\{#MyAppExeName}"' in lines[0]
    assert 'Filename: "ms-settings:defaultapps"' in lines[1]
    assert 'Filename: "{#MyAppUrl}"' in lines[2]

    for line in lines:
        assert "postinstall" in line
        assert "skipifsilent" in line
        assert "runasoriginaluser" in line
        assert "noerror" not in line
    assert "unchecked" not in lines[0]
    assert "unchecked" in lines[1]
    assert "unchecked" in lines[2]
    assert "shellexec" not in lines[0]
    assert "shellexec" in lines[1]
    assert "shellexec" in lines[2]
