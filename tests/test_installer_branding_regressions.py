# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Kurulum sihirbazı markalıdır ve depoyu gösterir.

ÖLÇÜLEN EKSİK (kullanıcı bildirimi): kurulum sihirbazının sol tarafı boş
gri duruyordu ve programın bir adresi yoktu. Referans olarak bakılan VLC
kurulumunda hem markalı şerit hem de "web sitesine git" seçeneği var.

Görseller `packaging/make_wizard_images.py` ile ürünün kendi ikonundan
üretilir; bu testler üretimin ve `.iss` bağının kopmasını engeller.
"""

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ISS = ROOT / "packaging" / "MLCPlayer.iss"
WIZARD_DIR = ROOT / "packaging" / "wizard"
PACKAGING_PLAN = ROOT / "docs" / "PACKAGING_PLAN.md"
SEPARATE_UX_PLAN = ROOT / "docs" / "INSTALLER_UX_PLAN.md"
REPO_URL = "https://github.com/IzzmooPro/MLCPlayer"


def _iss():
    return ISS.read_text(encoding="utf-8-sig")


def _generator():
    path = ROOT / "packaging" / "make_wizard_images.py"
    spec = importlib.util.spec_from_file_location("mlc_wizard_images", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_installer_ux_contract_is_consolidated_into_the_packaging_plan():
    text = PACKAGING_PLAN.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    assert not SEPARATE_UX_PLAN.exists()
    assert "## Güncel installer UX sözleşmesi" in text
    assert "A — Sinematik Gece" in text
    assert "B — Windows ile Uyumlu" in text
    assert "C — Dengeli Hibrit" in text
    for clause in (
        "Windows dilinden otomatik seçilir",
        "lisans kabulü zorunlu tutulmaz",
        "Hedef klasör görünür ve değiştirilebilir",
        "Dosya ilişkilendirmeleri sessizce ele geçirilmez",
        "Telemetri, reklam ve analiz yoktur",
        "İnternet Video özelliği ayrı ve isteğe bağlıdır",
        "Kurulumdan önce özet ekranı gösterilir",
        "GitHub sayfasını açma varsayılan kapalıdır",
        "Kullanıcı ayarı, önbelleği veya geçmişi silen bir seçenek",
        "Private görsel yolları Git'e eklenmez",
        "Build için ayrıca açık onay alınır",
        "Gerçek Windows kurulum/güncelleme/kaldırma deneyi için ayrıca açık onay",
    ):
        assert clause in normalized


def test_installer_visual_direction_c_is_selected_without_claiming_acceptance():
    text = PACKAGING_PLAN.read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    assert "### Seçilen görsel yön — C Dengeli Hibrit" in text
    assert "C — Dengeli Hibrit** yönünü açıkça seçti" in normalized
    assert "A ve B yalnız karşılaştırma referansı" in normalized
    assert "uygulama hedefi değildir" in normalized
    assert "gerçek Inno piksel çıktısı" in normalized
    assert (
        "build ve fiziksel kurulum ayrıca tasarlanıp doğrulanmadan kabul edilmiş sayılmaz"
        in normalized
    )
    assert "Seçim installer veya ürün kodunu değiştirme yetkisi değildir" in normalized


def test_visual_direction_c_has_one_complete_screen_contract():
    """Tasarım kararı, gerçek Inno uygulamasından ayrı ve test edilebilir kalır."""
    text = PACKAGING_PLAN.read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    assert text.count("### C ekran sözleşmesi") == 1
    screen_ids = (
        "C-WELCOME",
        "C-PREFERENCES",
        "C-SUMMARY",
        "C-PROGRESS",
        "C-FINISH",
    )
    for screen_id in screen_ids:
        assert len(re.findall(rf"^`{screen_id}`$", text, re.MULTILINE)) == 1, screen_id

    blocks = {}
    for index, screen_id in enumerate(screen_ids):
        start = text.index(f"`{screen_id}`\n")
        end_marker = (
            f"`{screen_ids[index + 1]}`\n"
            if index + 1 < len(screen_ids)
            else "#### Negatif durum ve kullanıcı metni"
        )
        end = text.index(end_marker, start + 1)
        blocks[screen_id] = " ".join(text[start:end].split())
        for field in ("message key", "Varsayılan", "İlk odak", "Tab sırası", "Geçiş"):
            assert field in blocks[screen_id], (screen_id, field)

    exact_anchors = {
        "C-WELCOME": (
            "C.WelcomeInstallBody",
            "C.WelcomeReinstallBody",
            "C.WelcomeUpgradeBody",
            "Kurmak veya çalıştırmak için lisans kabulü gerekmez",
        ),
        "C-PREFERENCES": (
            "Kurulum konumunu ve kısayol seçimini gözden geçirin.",
            "WizardDirValue",
            "ilk kurulumda işaretli, yükseltmede önceki seçim",
            "Internet Video için kur/indir seçim kutusu gösterilmez",
        ),
        "C-SUMMARY": (
            "Başlangıç güncelleme denetimi: GitHub release bilgisi, sessiz",
            "Kullanıcı ayarları, geçmiş ve önbellek: Korunacak",
            "Kuruluma başlamak için `Kur`'u seçin.",
            "Ayarları gözden geçirmek veya değiştirmek için `Önceki`'yi seçin.",
            "ReadyLabel",
        ),
        "C-PROGRESS": (
            "Dosyalar hazırlanıyor",
            "İptal` tek etkileşimli kontroldür",
            "sahte yüzde gösterilmez",
        ),
        "C-FINISH": (
            "MLC Player'ı aç” işaretli",
            "Windows Varsayılan Uygulamalar ayarını aç” işaretsiz",
            "GitHub sayfasını aç” işaretsiz",
            "Player → Windows Ayarları → GitHub",
        ),
    }
    for screen_id, anchors in exact_anchors.items():
        for anchor in anchors:
            assert anchor in blocks[screen_id], (screen_id, anchor)

    for clause in (
        "Windows UAC tarafından yönetilir",
        "MLC Player kapatılamadı",
        "Kurulumdan vazgeçildi",
        "Kurulum geri alındı",
        "Hedef klasöre yazılamadı",
        "Önceki hedef ve tercihler korundu",
        "Varsayılan uygulama değiştirilmedi",
        "Yeniden başlatma gerekiyor",
        "EV-20260826-007",
        "gerçek Inno uygulamasını, build'i veya fiziksel kurulumu kanıtlamaz",
        "C.DowngradeBlocked",
        "Built-in `wpWelcome`, `wpSelectDir`, `wpReady`, `wpInstalling` ve `wpFinished`",
        "dekoratif veya etkisiz tercih kabul edilmez",
        "baştan paralel bir custom wizard/state modeli kurulmaz",
    ):
        assert clause in normalized

    assert "C:\\Users\\" not in text
    assert "C.UpdateAtStartup" not in blocks["C-PREFERENCES"]
    assert "Başlangıçta güncellemeleri denetle (önerilen)" not in blocks["C-PREFERENCES"]


def test_finish_actions_are_real_and_do_not_overpromise_windows_defaults():
    """Finish tasarım sözleşmesi exact hedef taşır; Windows yetkisi abartılmaz."""
    text = PACKAGING_PLAN.read_text(encoding="utf-8")
    finish_start = text.index("`C-FINISH`\n")
    finish_end = text.index("#### Negatif durum ve kullanıcı metni", finish_start)
    finish = " ".join(text[finish_start:finish_end].split())
    acceptance_start = text.index("#### Uygulama ve kabul kapıları", finish_end)
    acceptance_end = text.index("### Görsel seçimden sonra uygulama sırası", acceptance_start)
    acceptance = " ".join(text[acceptance_start:acceptance_end].split())

    for clause in (
        "exact `{app}\\{#MyAppExeName}` installed executable",
        "ms-settings:defaultapps",
        "varsayılan yapıldı denmez",
        "{#MyAppUrl}",
        "Eylem çalıştırılamazsa",
        "optional eylem hatası kurulumu başarısız saymaz",
        "sonraki seçili eylemi düşürmez",
    ):
        assert clause in finish

    for clause in (
        "Finish action/readback ölçütleri",
        "process-start sonucu",
        "görünür Settings sayfası",
        "Seçili olmayan her yolun hiç çalışmadığı",
    ):
        assert clause in acceptance

    contract = " ".join(text[text.index("### C ekran sözleşmesi"):acceptance_end].split())
    for forbidden_key in (
        "C.UpdateAtStartup",
        "C.InternetVideoInstall",
        "C.FileAssociations",
    ):
        assert forbidden_key not in contract


def test_installer_c_reuses_builtin_pages_and_native_state():
    """Implementation tek directory/task state'i ve beş built-in sayfa kullanır."""
    text = _iss()
    code = text.split("[Code]", 1)[1]

    for event in (
        "procedure InitializeWizard",
        "procedure CurPageChanged",
        "function ShouldSkipPage",
        "function UpdateReadyMemo",
    ):
        assert event in code
    for page in ("wpWelcome", "wpSelectDir", "wpReady", "wpInstalling", "wpFinished"):
        assert page in code

    assert "CreateCustomPage" not in code
    assert "CreateInputDirPage" not in code
    skip_body = code.split("function ShouldSkipPage", 1)[1].split("end;", 1)[0]
    assert re.search(r"Result\s*:=\s*PageID\s*=\s*wpSelectTasks", skip_body)
    assert "WizardForm.TasksList.Parent := WizardForm.SelectDirPage" in code
    assert "SelectDirPage.Surface" not in code
    assert "SelectDirPage.SurfaceWidth" not in code
    assert "SelectDirPage.SurfaceHeight" not in code
    assert "WizardDirValue" in code
    assert "WizardIsTaskSelected('desktopicon')" in code
    assert "WizardSelectTasks" not in code
    assert "WizardForm.DirEdit.TabOrder" in code
    assert "WizardForm.DirBrowseButton.TabOrder" in code
    assert "WizardForm.TasksList.TabOrder" in code
    assert "WizardForm.ActiveControl := WizardForm.DirEdit" in code
    assert "WizardForm.ActiveControl := WizardForm.NextButton" in code
    assert "WizardForm.ActiveControl := WizardForm.NextButton" in code
    assert "WizardForm.FinishedButton" not in code
    assert "WizardForm.PageNameLabel.Caption" in code
    assert "WizardForm.PageDescriptionLabel.Caption" in code
    assert "CustomMessage('CFinishBody')" in code
    assert "CustomMessage('CFinishDescription')" in code
    assert "WizardForm.FinishedLabel.AdjustHeight" in code


def test_installer_c_summary_and_progress_use_live_engine_state():
    text = _iss()
    code = text.split("[Code]", 1)[1]

    ready = code.split("function UpdateReadyMemo", 1)[1].split(
        "procedure CurPageChanged", 1
    )[0]
    assert "WizardDirValue" in ready
    assert "WizardIsTaskSelected('desktopicon')" in ready
    assert "CustomMessage('CSummaryLocation')" in ready
    assert "CustomMessage('CSummaryDesktopYes')" in ready
    assert "CustomMessage('CSummaryDesktopNo')" in ready

    assert "procedure SetInstallPhase" in code
    assert "CustomMessage('CPhasePreparing')" in code
    assert "CustomMessage('CPhaseInstalling')" in code
    assert "CustomMessage('CPhaseIntegrating')" in code
    assert "CurProgress" not in code
    assert "TTimer" not in code
    assert re.search(
        r"^Source: .*BeforeInstall: BeforeInstallMainPayload$",
        text,
        re.MULTILINE,
    )
    before_payload = code.split("procedure BeforeInstallMainPayload", 1)[1].split(
        "procedure InitializeWizard", 1
    )[0]
    assert "VerifyLegacyRootRuntimeRemoved;" in before_payload
    assert "SetInstallPhase('installing');" in before_payload
    assert before_payload.index("VerifyLegacyRootRuntimeRemoved;") < (
        before_payload.index("SetInstallPhase('installing');")
    )
    assert re.search(r'^Name: "\{group\}.*BeforeInstall: SetInstallPhase\(\'integrating\'\)', text, re.MULTILINE)
    assert "InstallPhaseLabel.Caption := Caption" in code
    assert "WizardForm.StatusLabel.Caption := Caption" not in code


def test_installer_summary_instruction_matches_install_button_once():
    text = _iss()
    plan = PACKAGING_PLAN.read_text(encoding="utf-8")
    normalized_plan = " ".join(plan.split())
    code = text.split("[Code]", 1)[1]
    ready = code.split("function UpdateReadyMemo", 1)[1].split(
        "procedure CurPageChanged", 1
    )[0]
    ready_page = code.split("wpReady:", 1)[1].split("wpInstalling:", 1)[0]

    assert (
        "turkish.CSummaryAction=Kuruluma başlamak için Kur'u seçin. "
        "Ayarları gözden geçirmek veya değiştirmek için Önceki'yi seçin."
        in text
    )
    assert "Kuruluma başlamak için `Kur`'u seçin." in normalized_plan
    assert (
        "Ayarları gözden geçirmek veya değiştirmek için `Önceki`'yi seçin."
        in normalized_plan
    )
    assert "`ReadyLabel`" in normalized_plan
    assert "Son satır “Kur'a basarak başlayın.”dır." not in normalized_plan
    assert "CustomMessage('CSummaryAction')" not in ready
    assert (
        "WizardForm.ReadyLabel.Caption := CustomMessage('CSummaryAction')"
        in ready_page
    )
    assert code.count(
        "WizardForm.ReadyLabel.Caption := CustomMessage('CSummaryAction')"
    ) == 1
    assert "WizardForm.ReadyLabel.AdjustHeight" in ready_page
    assert (
        "WizardForm.ReadyMemo.Top := WizardForm.ReadyLabel.Top +"
        in ready_page
    )
    assert (
        "WizardForm.ReadyMemo.Height := WizardForm.ReadyPage.ClientHeight -"
        in ready_page
    )


def test_upgrade_removes_only_forbidden_root_dll_leftovers_before_copy():
    text = _iss()
    assert text.count("\n[InstallDelete]\n") == 1
    assert text.index("\n[InstallDelete]\n") < text.index("\n[Files]\n")
    cleanup = text.split("\n[InstallDelete]\n", 1)[1].split(
        "\n[Files]\n", 1
    )[0]
    api_sets = (
        "api-ms-win-core-console-l1-1-0.dll",
        "api-ms-win-core-datetime-l1-1-0.dll",
        "api-ms-win-core-debug-l1-1-0.dll",
        "api-ms-win-core-errorhandling-l1-1-0.dll",
        "api-ms-win-core-fibers-l1-1-0.dll",
        "api-ms-win-core-fibers-l1-1-1.dll",
        "api-ms-win-core-file-l1-1-0.dll",
        "api-ms-win-core-file-l1-2-0.dll",
        "api-ms-win-core-file-l2-1-0.dll",
        "api-ms-win-core-handle-l1-1-0.dll",
        "api-ms-win-core-heap-l1-1-0.dll",
        "api-ms-win-core-interlocked-l1-1-0.dll",
        "api-ms-win-core-kernel32-legacy-l1-1-1.dll",
        "api-ms-win-core-libraryloader-l1-1-0.dll",
        "api-ms-win-core-localization-l1-2-0.dll",
        "api-ms-win-core-memory-l1-1-0.dll",
        "api-ms-win-core-namedpipe-l1-1-0.dll",
        "api-ms-win-core-processenvironment-l1-1-0.dll",
        "api-ms-win-core-processthreads-l1-1-0.dll",
        "api-ms-win-core-processthreads-l1-1-1.dll",
        "api-ms-win-core-profile-l1-1-0.dll",
        "api-ms-win-core-rtlsupport-l1-1-0.dll",
        "api-ms-win-core-string-l1-1-0.dll",
        "api-ms-win-core-synch-l1-1-0.dll",
        "api-ms-win-core-synch-l1-2-0.dll",
        "api-ms-win-core-sysinfo-l1-1-0.dll",
        "api-ms-win-core-sysinfo-l1-2-0.dll",
        "api-ms-win-core-timezone-l1-1-0.dll",
        "api-ms-win-core-util-l1-1-0.dll",
        "api-ms-win-crt-conio-l1-1-0.dll",
        "api-ms-win-crt-convert-l1-1-0.dll",
        "api-ms-win-crt-environment-l1-1-0.dll",
        "api-ms-win-crt-filesystem-l1-1-0.dll",
        "api-ms-win-crt-heap-l1-1-0.dll",
        "api-ms-win-crt-locale-l1-1-0.dll",
        "api-ms-win-crt-math-l1-1-0.dll",
        "api-ms-win-crt-multibyte-l1-1-0.dll",
        "api-ms-win-crt-private-l1-1-0.dll",
        "api-ms-win-crt-process-l1-1-0.dll",
        "api-ms-win-crt-runtime-l1-1-0.dll",
        "api-ms-win-crt-stdio-l1-1-0.dll",
        "api-ms-win-crt-string-l1-1-0.dll",
        "api-ms-win-crt-time-l1-1-0.dll",
        "api-ms-win-crt-utility-l1-1-0.dll",
    )
    legacy_names = (*api_sets, "icudt78.dll", "icuuc.dll", "ucrtbase.dll")
    expected = {
        rf'Type: files; Name: "{{app}}\_internal\{name}"; '
        "Check: IsMaintenanceInstall"
        for name in legacy_names
    }
    assert {line.strip() for line in cleanup.splitlines() if line.strip()} == expected
    assert len(expected) == 47
    assert "recursesubdirs" not in cleanup
    assert "filesandordirs" not in cleanup
    assert r"{app}\_internal\PyQt6" not in cleanup
    assert "DelTree" not in text
    assert "userappdata" not in cleanup.casefold()
    assert "localappdata" not in cleanup.casefold()

    helper = text.split("function IsMaintenanceInstall", 1)[1].split(
        "function ", 1
    )[0]
    assert "CurrentInstallMode <> InstallModeFirst" in helper

    assert 'CloseApplicationsFilter="MLC Player.exe,*.dll"' in text
    assert text.count("function IsForbiddenRootRuntimeName") == 1
    classifier = text.split("function IsForbiddenRootRuntimeName", 1)[1].split(
        "procedure VerifyLegacyRootRuntimeRemoved", 1
    )[0]
    for token in (
        "LowerName = 'ucrtbase.dll'",
        "Pos('api-ms-win-', LowerName) = 1",
        "IsIcuRuntimeStem(Stem, 'icuuc')",
        "IsIcuRuntimeStem(Stem, 'icuin')",
        "IsIcuRuntimeStem(Stem, 'icudt')",
    ):
        assert token in classifier
    assert "procedure VerifyLegacyRootRuntimeRemoved" in text
    verify = text.split("procedure VerifyLegacyRootRuntimeRemoved", 1)[1].split(
        "function DirectoryHasEntries", 1
    )[0]
    assert "ExpandConstant('{app}\\_internal')" in verify
    assert "RaiseException(" in verify
    assert "Exception.CreateFmt" not in text
    assert not re.search(r"^\s*raise\b", text, re.MULTILINE | re.IGNORECASE)
    assert text.count("procedure BeforeInstallMainPayload") == 1
    before_payload = text.split("procedure BeforeInstallMainPayload", 1)[1].split(
        "procedure InitializeWizard", 1
    )[0]
    ordered_cleanup = (
        "VerifyLegacyRootRuntimeRemoved;",
        "LegacyCleanupVerified := True;",
        "SetInstallPhase('installing');",
    )
    positions = [before_payload.index(token) for token in ordered_cleanup]
    assert positions == sorted(positions)
    assert "if not LegacyCleanupVerified then" in before_payload
    files = text.split("\n[Files]\n", 1)[1].split("\n[Registry]\n", 1)[0]
    assert "BeforeInstall: BeforeInstallMainPayload" in files


def test_installer_c_summary_memo_is_clean_wrapped_and_grouped():
    """Ready özeti yatay kaydırma üretmez ve okunabilir gruplara ayrılır."""
    text = _iss()
    code = text.split("[Code]", 1)[1]
    init = code.split("procedure InitializeWizard", 1)[1].split(
        "procedure UpdateWelcomePage", 1
    )[0]
    ready = code.split("function UpdateReadyMemo", 1)[1].split(
        "procedure CurPageChanged", 1
    )[0]

    assert "WizardForm.ReadyMemo.Color := clWindow" in init
    assert "WizardForm.ReadyMemo.ReadOnly := True" in init
    assert "WizardForm.ReadyMemo.WordWrap := True" in init
    assert "WizardForm.ReadyMemo.ScrollBars := ssVertical" in init
    assert (
        "WizardForm.ReadyMemo.Anchors := [akLeft, akTop, akRight, akBottom]"
        in init
    )
    assert "WizardForm.ReadyMemo.BorderStyle := bsNone" not in init
    assert "WizardForm.ReadyMemo.ScrollBars := ssBoth" not in init
    assert "WizardForm.ReadyMemo.ScrollBars := ssHorizontal" not in init
    assert "WizardForm.ReadyMemo.Text :=" not in code
    assert "WizardForm.ReadyMemo.Lines" not in code
    assert "WizardForm.ReadyMemo.Parent" not in code
    assert "WizardForm.ReadyMemo.Enabled := False" not in code
    assert "WizardForm.ReadyMemo.TabStop := False" not in code
    assert "WizardForm.ReadyMemo.Visible := False" not in code
    assert "TNewMemo.Create" not in code
    assert "TRichEditViewer" not in code

    ordered_keys = (
        "CSummaryLocation",
        "CSummaryDesktopYes",
        "CSummaryDesktopNo",
        "CSummaryOpenWith",
        "CSummaryUpdate",
        "CSummaryAddon",
        "CSummaryUserData",
    )
    positions = [ready.index(key) for key in ordered_keys]
    assert positions == sorted(positions)
    assert "CSummaryAction" not in ready
    for separator in (
        "NewLine + NewLine;",
        "CustomMessage('CSummaryOpenWith') + NewLine + NewLine +",
        "CustomMessage('CSummaryAddon') + NewLine + NewLine +",
    ):
        assert separator in ready


def test_installer_progress_has_bounded_native_brand_accent():
    """Progress yalnız dekoratif marka vurgusu ekler; native engine korunur."""
    text = _iss()
    code = text.split("[Code]", 1)[1]
    initialize = code.split("procedure InitializeWizard", 1)[1].split(
        "procedure UpdateWelcomePage", 1
    )[0]
    guarded = re.search(
        r"if not HighContrastActive then\s*begin(?P<body>.*?)\n  end;",
        initialize,
        re.DOTALL,
    )
    assert guarded
    guard_body = guarded.group("body")

    for clause in (
        "InstallAccentBar := TPanel.Create(WizardForm)",
        "InstallAccentBar.Parent := WizardForm.InstallingPage",
        "InstallAccentBar.Caption := ''",
        "InstallAccentBar.Left := 0",
        "InstallAccentBar.Top := WizardForm.InstallingPage.ClientHeight - ScaleY(4)",
        "InstallAccentBar.Width := WizardForm.InstallingPage.ClientWidth",
        "InstallAccentBar.Height := ScaleY(4)",
        "InstallAccentBar.Anchors := [akLeft, akRight, akBottom]",
        "InstallAccentBar.BevelOuter := bvNone",
        "InstallAccentBar.ParentBackground := False",
        "InstallAccentBar.Color := CInstallerAccent",
        "InstallAccentBar.TabStop := False",
        "InstallAccentBar.Enabled := False",
        "InstallAccentBar.BringToFront",
        "InstallPhaseLabel.Font.Style := [fsBold]",
        "InstallPhaseLabel.Font.Color := CInstallerAccent",
    ):
        assert clause in guard_body

    assert "CInstallerAccent = $002050F0" in code
    assert _generator().ACCENT == (240, 80, 32)
    native_assignments = {
        line.strip() for line in initialize.splitlines()
        if re.match(
            r"\s*WizardForm\.(?:StatusLabel|FilenameLabel|ProgressGauge|CancelButton)"
            r"\.[A-Za-z]+\s*:=",
            line,
        )
    }
    expected_assignments = {
        "WizardForm.StatusLabel.Top := WizardForm.StatusLabel.Top + ScaleY(20);",
        "WizardForm.FilenameLabel.Top := WizardForm.FilenameLabel.Top + ScaleY(20);",
        "WizardForm.ProgressGauge.Top := WizardForm.ProgressGauge.Top + ScaleY(20);",
    }
    assert native_assignments == expected_assignments

    installing = code.split("wpInstalling:", 1)[1].split("wpFinished:", 1)[0]
    assert "WizardForm.ActiveControl := WizardForm.CancelButton" in installing
    for forbidden in (
        "WizardSetBackImage",
        "TBitmapImage.Create",
        "WizardForm.WizardBitmapImage",
        "WizardForm.WizardSmallBitmapImage",
        "TNewProgressBar.Create",
        "WizardForm.ProgressGauge.Parent :=",
        "WizardForm.ProgressGauge.Visible := False",
        "WizardForm.ProgressGauge.Position :=",
        "WizardForm.ProgressGauge.Min :=",
        "WizardForm.ProgressGauge.Max :=",
        "WizardForm.ProgressGauge.Enabled := False",
        "WizardForm.StatusLabel.Parent :=",
        "WizardForm.StatusLabel.Visible := False",
        "WizardForm.FilenameLabel.Parent :=",
        "WizardForm.FilenameLabel.Visible := False",
        "WizardForm.CancelButton.Parent :=",
        "WizardForm.CancelButton.Visible := False",
        "WizardForm.CancelButton.Enabled := False",
        "InstallAccentBar.OnClick",
        "InstallAccentBar.OnKey",
        "TTimer",
        "CurProgress",
        "CVisualShell",
    ):
        assert forbidden not in code


def test_pascal_continuations_cannot_look_like_inno_syntax():
    """Inno, Code içindeki satır başı karakter kodu veya array'i section sanmaz."""
    code = _iss().split("[Code]", 1)[1]
    offenders = [
        line for line in code.splitlines()
        if re.match(r"^\s*(?:#(?:\$[0-9A-Fa-f]+|\d)|\[)", line)
    ]
    assert offenders == []


def test_wizard_images_referenced_by_the_installer_exist():
    """`.iss` var olmayan bir görsel gösterirse derleme sessizce bozulur."""
    text = _iss()
    for key in ("WizardImageFile", "WizardSmallImageFile"):
        match = re.search(rf"^{key}=(.+)$", text, re.MULTILINE)
        assert match, f"{key} tanımlı değil"
        for relative in match.group(1).split(","):
            path = ISS.parent / relative.strip().replace("\\", "/")
            assert path.is_file(), f"eksik görsel: {path}"


def test_wizard_images_are_24_bit_bmp():
    """Inno PNG kabul etmez; yanlış biçim derlemede hata verir."""
    for path in WIZARD_DIR.glob("*.bmp"):
        header = path.read_bytes()[:2]
        assert header == b"BM", f"{path.name} BMP değil"


def test_wizard_images_use_the_product_identity():
    """Görseller ikondan ÖLÇÜLEN marka renklerini taşır."""
    generator = _generator()
    image = generator.large_image(164, 314)
    assert image.getpixel((2, 2)) == generator.BACKGROUND
    # Alt şerit vurgu rengidir.
    assert image.getpixel((2, 313)) == generator.ACCENT


def test_inner_pages_have_no_second_logo():
    """KULLANICI KARARI: sağ üstteki küçük logo KALDIRILDI.

    Inno'da küçük görseli kapatan anahtar yoktur; verilmezse Inno KENDİ
    varsayılan görselini koyar. Bu yüzden başlık zeminiyle aynı renkte düz
    bir görsel verilir — dosya var olmalı ama üzerinde logo OLMAMALIDIR.
    """
    generator = _generator()
    image = generator.small_image(55, 55)
    colours = image.getcolors(maxcolors=16)
    assert colours == [(55 * 55, generator.HEADER_BACKGROUND)], (
        f"küçük görsel düz değil: {colours}")


def test_windows_gets_the_friendly_name_explicitly():
    """ÖLÇÜLEN KUSUR: sürüm kaynağı doğruyken bile liste ".exe" gösterdi.

    Kurulu exe'nin `FileDescription` alanı 'MLC Player' idi, buna rağmen
    Explorer "Birlikte aç" listesinde dosya adını gösterdi (önbellek +
    çıkarım). Ad artık AÇIKÇA kaydedilir.
    """
    text = _iss()
    assert "[Registry]" in text, "kayıt bölümü yok"
    assert re.search(
        r'ValueName: "FriendlyAppName"; ValueData: "\{#MyAppName\}"', text), (
        "FriendlyAppName açıkça yazılmıyor")


def test_registry_entries_are_removed_on_uninstall():
    """Kaldırma kabulünün ölçütü: geride kayıt KALMAZ."""
    for line in _iss().splitlines():
        if line.startswith("Root: HK") and "FriendlyAppName" in line:
            assert "uninsdeletekey" in line, line


def test_legacy_per_user_open_with_tree_is_removed_but_never_created():
    """Eski HKCU kaydı yalnız varsa temizlenir; kurulum onu üretmez."""
    expected = (
        'Root: HKCU; Subkey: "Software\\Classes\\Applications\\'
        '{#MyAppExeName}"; Flags: dontcreatekey uninsdeletekey'
    )
    lines = [line.strip() for line in _iss().splitlines()
             if line.strip() and not line.lstrip().startswith(";")]

    assert expected in lines, (
        "ürüne ait eski HKCU Birlikte Aç ağacı fail-closed temizlenmiyor")
    assert not any(
        line.startswith('Root: HKCU; Subkey: "Software\\Classes\\Applications"')
        for line in lines
    ), "Applications üst ağacı gibi paylaşılan bir kayıt hedeflenemez"


def test_installer_points_at_the_repository():
    text = _iss()
    for key in ("AppPublisherURL", "AppSupportURL", "AppUpdatesURL"):
        match = re.search(rf"^{key}=(.+)$", text, re.MULTILINE)
        assert match, f"{key} yok"
    assert f'#define MyAppUrl "{REPO_URL}"' in text
    assert "mailto:" not in text, "e-posta adresi kurulumda görünmemeli"


def test_the_branded_panel_page_is_enabled():
    """Boydan boya sol panel YALNIZ hoş geldiniz/son sayfada çizilir.

    Inno 6 modern stilde hoş geldiniz sayfası VARSAYILAN KAPALIDIR; kapalıyken
    büyük görsel hiç görünmüyordu (ölçüldü: kullanıcı yalnız sağ üstteki
    küçük logoyu gördü).
    """
    assert re.search(r"^DisableWelcomePage=no\s*$", _iss(), re.MULTILINE)


def test_no_license_acceptance_page():
    """GPL bir EULA DEĞİLDİR; onay sayfası gereksiz sürtünmedir.

    GPLv3 madde 9: programı almak veya çalıştırmak için lisansı kabul etmek
    gerekmez. Yükümlülük metnin kullanıcıya ULAŞMASIDIR — o da [Files]
    bölümünde LICENSE kopyalanarak karşılanır.
    """
    text = _iss()
    assert not re.search(r"^LicenseFile=", text, re.MULTILINE), (
        "lisans onay sayfası geri gelmiş")
    assert re.search(r'Source: "\.\.\\LICENSE"', text), (
        "LICENSE artık kuruluma girmiyor; GPLv3 yükümlülüğü kalkar")


def test_finish_page_offers_the_repository_without_forcing_it():
    """Tarayıcı KENDİLİĞİNDEN açılmaz; seçenek işaretsiz gelir."""
    # Adres `.iss` içinde TEK kaynaktan (`{#MyAppUrl}`) gelir; düz URL
    # aranmaz, aksi hâlde test tek kaynak kuralını cezalandırırdı.
    run_lines = [line for line in _iss().splitlines()
                 if line.startswith("Filename:") and "{#MyAppUrl}" in line]
    assert run_lines, "GitHub seçeneği yok"
    assert "unchecked" in run_lines[0], "seçenek varsayılan işaretli olmamalı"
    assert "shellexec" in run_lines[0]
