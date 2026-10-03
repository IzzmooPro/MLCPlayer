# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Main uninstall offers bounded, explicit MLC-owned data cleanup."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MAIN_ISS = ROOT / "packaging" / "MLCPlayer.iss"


def _iss():
    return MAIN_ISS.read_text(encoding="utf-8-sig")


def test_uninstall_choices_preserve_user_data_by_default():
    text = _iss()
    code = text.split("[Code]", 1)[1]

    assert "procedure InitializeUninstallCleanupChoices" in code
    assert "RemoveAddonSelected := AddonIsInstalled;" in code
    assert "DeleteSettingsSelected := False;" in code
    assert "DeleteCacheSelected := False;" in code
    assert "UninstallSilent" in code
    assert "PURGEUSERDATA" not in code
    assert "UninstallCleanupAccount" in code
    assert "if UninstallSilent then\n    Result := True" in code


def test_interactive_uninstall_has_three_real_choice_controls():
    text = _iss()
    code = text.split("[Code]", 1)[1]

    assert "function ShowUninstallCleanupChoices: Boolean" in code
    for variable in (
        "RemoveAddonCheckBox",
        "DeleteSettingsCheckBox",
        "DeleteCacheCheckBox",
    ):
        assert f"{variable} := TNewCheckBox.Create" in code
        assert f"{variable}.Checked" in code
    assert "ShowModal() = mrOk" in code
    assert "Result := ShowUninstallCleanupChoices;" in code


def test_uninstall_removes_machine_product_registry_parent():
    text = _iss()
    registry = text.split("[Registry]", 1)[1].split("[Icons]", 1)[0]
    active_lines = [
        line.strip() for line in registry.splitlines()
        if line.strip() and not line.lstrip().startswith(";")
    ]
    parent = (
        'Root: HKLM; Subkey: "Software\\MLCPlayer"; '
        'Flags: dontcreatekey uninsdeletekey'
    )
    child = (
        'Root: HKLM; Subkey: "Software\\MLCPlayer\\UninstallCleanup"; '
        'Flags: dontcreatekey uninsdeletekey'
    )

    assert active_lines.count(parent) == 1
    assert active_lines.count(child) == 1
    # Inno uninstall entries run in reverse source order: child first, parent last.
    assert active_lines.index(parent) < active_lines.index(child)


def test_selected_full_cleanup_covers_every_product_owned_store():
    text = _iss()
    code = text.split("[Code]", 1)[1]

    for owned_target in (
        "{userappdata}\\MLCPlayer",
        "{localappdata}\\MLCPlayer",
        "MLCPlayerUpdate_*",
        "Software\\MLCPlayer",
        "MLCPlayer/OpenSubtitles/default",
        "MLCPlayer/OpenSubtitles.ApiKey/default",
    ):
        assert owned_target in code
    assert "StoredSubtitleUsername" in code
    assert "UserSettingsKey = 'Software\\MLCPlayer'" in code
    assert "RegDeleteKeyIncludingSubkeys(HKCU, UserSettingsKey)" in code
    assert "CredDeleteW" in code
    assert "DeleteOwnedUserDataInRegisteredSession" in code
    assert "CleanupUserSid" in code
    assert "CleanupTaskName" in code
    assert "CleanupHelperHash" in code
    assert "GetSHA256OfFile(CandidateHelper)" in code
    assert "RegGetSubkeyNames(HKU" in code
    assert "CleanupInstallId" in code
    assert "CleanupIdentityCount" in code
    assert "ProfileImagePath" in code
    assert "ExpectedHelper" in code
    assert "for I := 0 to CleanupIdentityCount - 1 do" in code
    assert "schtasks.exe" in code
    assert '"succeeded":true' in code


def test_credential_cleanup_matches_the_product_username_lifecycle():
    source = (ROOT / "app" / "subtitle_settings.py").read_text(encoding="utf-8")
    code = _iss().split("[Code]", 1)[1]

    # A username switch is transactional: a former target must be deleted
    # before the new username is committed to QSettings. Therefore the current
    # stored name (or default) identifies the only password target that can
    # remain for a successful product settings save.
    assert "previous_username != new_username" in source
    assert "self.credentials.delete_password(previous_username)" in source
    assert "return rejected(cleanup_ok=False" in source
    assert "StoredSubtitleUsername" in code
    assert "MLCPlayer/OpenSubtitles/default" in code


def test_cleanup_paths_are_exact_and_never_wildcard_the_install_directory():
    text = _iss()
    code = text.split("[Code]", 1)[1]

    assert 'Name: "{app}\\*"' not in text
    assert "DelTree(ExpandConstant('{app}')" not in code
    assert "DelTree(" not in code
    assert "DeleteOwnedUserData" in code
    assert "RemoveEmptyOwnedDirectory" in code
    assert "IsOwnedThumbnailName" in code
    assert "IsOwnedUpdateFileName" in code
    assert "{localappdata}\\python" not in code
    assert "IsReparsePoint" in code
    assert "FileAttributeReparsePoint" in code
    assert "CleanupFailed" in code
    assert "function PathAncestorsAreSafe" in code
    assert "PathAncestorsAreSafe(RoamingRoot)" in code
    assert "PathAncestorsAreSafe(LogDirectory)" in code
    assert "PathAncestorsAreSafe(LocalRoot)" in code
    assert "PathAncestorsAreSafe(CacheDirectory)" in code
    assert "PathAncestorsAreSafe(ThumbnailDirectory)" in code
    assert "PathAncestorsAreSafe(BaseDirectory)" in code
    assert "if DeleteSettingsSelected and" in code
    assert "if DeleteCacheSelected and" in code
    assert "user settings profile path" in code
    assert "user cache profile path" in code
    assert "if DeleteSettingsSelected or DeleteCacheSelected then" in code
    assert "DeleteOwnedUserDataInRegisteredSession" in code


def test_user_cleanup_helper_is_packaged_and_removed_for_every_uninstall_mode():
    text = _iss()
    code = text.split("[Code]", 1)[1]
    build = (ROOT / "packaging" / "build_release.bat").read_text(
        encoding="utf-8-sig")

    assert 'Source: "..\\output\\dist\\MLCUserCleanup.exe"' in text
    assert "AppData\\Local\\Programs\\MLC Player\\UninstallCleanup" in code
    assert "ExpectedLegacyCleanupHelperForSid" in code
    assert "AppData\\Local\\MLCPlayer\\UninstallCleanup" in code
    assert "{commonappdata}\\MLCPlayer\\UninstallCleanup" not in text
    assert "Permissions: users-modify" not in text
    assert "'ipc\\' + Nonce + '.request.json'" in code
    assert "packaging/MLCUserCleanup.spec" in build
    assert "RemoveCleanupInfrastructure" in code
    assert "DeleteOwnedUserDataInRegisteredSession" in code
    assert "RemoveCleanupInfrastructure" in code
    assert "SelectCleanupIdentity(I)" in code
    assert "if UninstallSilent then\n    Result := True" in code


def test_cleanup_choices_work_before_player_has_ever_provisioned_a_helper():
    code = _iss().split("[Code]", 1)[1]
    dialog = code.split("function ShowUninstallCleanupChoices", 1)[1].split(
        "function InitializeUninstall", 1)[0]
    post_uninstall = code.split("procedure CurUninstallStepChanged", 1)[1].split(
        "function InitializeUninstall", 1)[0]

    assert "DeleteSettingsCheckBox.Enabled := True;" in dialog
    assert "DeleteCacheCheckBox.Enabled := True;" in dialog
    assert "(CleanupIdentityCount = 0)" not in post_uninstall
    assert "DeleteOwnedUserData;" in post_uninstall
    assert "ExecAsOriginalUser" not in code


def test_cleanup_dialog_discloses_every_account_scope_it_processes():
    text = _iss()
    code = text.split("[Code]", 1)[1]

    assert "kaldırma hesabına ve burada listelenen kayıtlı MLC hesaplarına" in text
    assert "Listelenen hesaplara ait tüm MLC Player verilerini" in text
    assert "CleanupAccountDisplay := ExpandConstant('{username}');" in code
    assert "CleanupAccountDisplay + ', ' +" in code
    assert "for I := 0 to CleanupIdentityCount - 1 do" in code


def test_uninstaller_accepts_only_exact_current_or_legacy_helper_layouts():
    code = _iss().split("[Code]", 1)[1]

    assert "CurrentSuffix := '\\Programs\\MLC Player\\UninstallCleanup\\v1\\MLCUserCleanup.exe'" in code
    assert "LegacySuffix := '\\MLCPlayer\\UninstallCleanup\\v1\\MLCUserCleanup.exe'" in code
    assert "ExpectedLegacyCleanupHelperForSid" in code
    assert "PathSame(CandidateHelper, ExpectedLegacyHelper)" in code
    assert "FileExists(ExpectedHelper) or FileExists(ExpectedLegacyHelper)" in code


def test_cleanup_helper_rejects_reparse_points_through_the_profile_chain():
    code = _iss().split("[Code]", 1)[1]

    for directory in (
        "V1Directory", "CleanupDirectory", "ProductDirectory",
        "ProgramsDirectory", "LocalDirectory", "AppDataDirectory",
        "ProfileDirectory",
    ):
        assert f"IsReparsePoint({directory})" in code


def test_validated_cleanup_infrastructure_is_removed_on_every_runtime_failure():
    code = _iss().split("[Code]", 1)[1]
    procedure = code.split(
        "procedure DeleteOwnedUserDataInRegisteredSession;", 1)[1].split(
        "procedure CurUninstallStepChanged", 1)[0]

    for failure in (
        "user cleanup IPC directory", "user cleanup request",
        "user cleanup task start", "user cleanup timeout",
    ):
        block = procedure.split(f"MarkCleanupFailure('{failure}');", 1)[1]
        assert block.lstrip().startswith("RemoveCleanupInfrastructure;\n    Exit;")

    assert "else\n    MarkCleanupFailure('user cleanup helper path');" in code


def test_runtime_nonce_hashes_use_the_unicode_inno_api():
    code = _iss().split("[Code]", 1)[1]

    # The hash input is a normal Unicode String expression.
    assert code.count("GetSHA256OfUnicodeString(") == 2
    assert "GetSHA256OfString(" not in code


def test_runtime_datetime_hash_seed_uses_char_separators():
    code = _iss().split("[Code]", 1)[1]

    # GetDateTimeString expects Char separators. An empty String compiles but
    # raises Runtime error: Type Mismatch when the post-install hook runs.
    assert "GetDateTimeString('yyyymmddhhnnsszzz', '', '')" not in code
    assert code.count(
        "GetDateTimeString('yyyymmddhhnnsszzz', '-', ':')"
    ) == 2


def test_cleanup_dialog_never_focuses_a_disabled_or_hidden_checkbox():
    code = _iss().split("[Code]", 1)[1]

    assert "RemoveAddonCheckBox.Visible and RemoveAddonCheckBox.Enabled" in code
    assert "else if DeleteSettingsCheckBox.Enabled then" in code
    assert "Form.ActiveControl := ContinueButton;" in code


def test_cleanup_dialog_is_compact_and_visually_joined_to_button_row():
    code = _iss().split("[Code]", 1)[1]

    assert "CreateCustomForm(ScaleX(470), ScaleY(292)" in code
    assert "BodyLabel.Font.Style := [fsBold]" in code
    assert "ButtonSeparator := TBevel.Create(Form)" in code
    assert "ButtonSeparator.Shape := bsTopLine" in code


def test_uninstaller_rechecks_selected_settings_under_the_exact_user_sid():
    code = _iss().split("[Code]", 1)[1]

    assert "UserRegistryKey := CleanupUserSid + '\\' + UserSettingsKey" in code
    assert code.count("RegKeyExists(HKU, UserRegistryKey)") == 2
    assert "RegDeleteKeyIncludingSubkeys(HKU, UserRegistryKey)" in code


def test_addon_removal_is_path_validated_and_fail_closed():
    code = _iss().split("[Code]", 1)[1]

    assert "function ReadValidatedAddonUninstaller" in code
    assert "PathSame(ExtractFileDir(UninstallerPath), ExpandConstant('{app}'))" in code
    assert "PathSame(UninstallerPath, ExpandConstant('{uninstallexe}'))" in code
    assert "'InstallLocation', RegisteredInstallDirectory" in code
    assert "Exec(UninstallerPath" in code
    assert "if ExitCode <> 0 then" in code
    assert "RaiseException(CustomMessage('UninstallAddonFailed'))" in code
    assert "RegKeyExists(HKLM, AddonUninstallKey)" in code
    assert "{app}\\_internal\\bin\\yt-dlp.exe" in code
    assert "{app}\\_internal\\bin\\deno.exe" in code


def test_cleanup_copy_exists_for_every_installer_language():
    text = _iss()
    languages = (
        "english",
        "turkish",
        "german",
        "spanish",
        "french",
        "italian",
        "russian",
        "brazilianportuguese",
    )
    keys = (
        "UninstallCleanupTitle",
        "UninstallCleanupBody",
        "UninstallCleanupAccount",
        "UninstallRemoveAddon",
        "UninstallDeleteSettings",
        "UninstallDeleteCache",
        "UninstallCleanupNote",
        "UninstallAddonFailed",
        "UninstallCleanupFailed",
    )

    for language in languages:
        for key in keys:
            assert re.search(
                rf"^{language}\.{key}=.+$", text, re.MULTILINE
            ), (language, key)
