; SPDX-FileCopyrightText: 2026 MLC Player contributors
; SPDX-License-Identifier: GPL-3.0-only
#define MyAppName "MLC Player"
; SÜRÜM TEK KAYNAK: app/config.py → APP_VERSION. Burası onun kopyasıdır ve
; tests/test_version_consistency.py ikisini birbirine bağlar; elle ayrışamaz.
#define MyAppVersion "v0.33"
#define MyAppPublisher "IzzmooPro"
#define MyAppUrl "https://github.com/IzzmooPro/MLCPlayer"
#define MyAppExeName "MLC Player.exe"

[Setup]
AppId={{EB0DD5CF-F20B-4B23-A1C9-2C23A83A8758}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
; Depo adresi: "Uygulamalar ve Özellikler" listesinde ve kurulum bilgisinde
; görünür; GPLv3 kaynak yükümlülüğünün de adresidir.
AppPublisherURL={#MyAppUrl}
AppSupportURL={#MyAppUrl}/issues
AppUpdatesURL={#MyAppUrl}/releases/latest
DefaultDirName={autopf}\MLC Player
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
OutputDir=..\installer_output
OutputBaseFilename=MLCPlayer_Setup_{#MyAppVersion}
; LisansFile BİLEREK YOK — "kabul ediyorum" sayfası KALDIRILDI.
; GPL bir EULA değildir: GPLv3 madde 9 açıkça programı almak veya
; çalıştırmak için lisansı kabul etmenin GEREKMEDİĞİNİ söyler; lisans
; dağıtım ve değiştirmeyi düzenler. Referans VLC kurulumunda da böyle bir
; onay sayfası yoktur. Yükümlülük metnin KULLANICIYA ULAŞMASIDIR; bu
; [Files] bölümünde korunur: LICENSE kurulum köküne kopyalanır.

; Tek görsel kimlik: setup, kaldırıcı ve kısayollar aynı logoyu kullanır.
SetupIconFile=..\assets\mlc-player-icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

; Sihirbaz görselleri ürünün kendi ikonundan üretilir
; (packaging\make_wizard_images.py). Aksi hâlde sol taraf boş gri kalıyordu.
; Çoklu boyut yüksek DPI'da bulanıklığı önler; Inno 24-bit BMP ister.
WizardImageFile=wizard\wizard-large.bmp,wizard\wizard-large-1.bmp,wizard\wizard-large-2.bmp
WizardSmallImageFile=wizard\wizard-small.bmp,wizard\wizard-small-1.bmp,wizard\wizard-small-2.bmp
WizardImageStretch=yes
; Boydan boya sol panel YALNIZ hoş geldiniz ve son sayfada görünür; Inno 6
; modern stilde hoş geldiniz sayfasını VARSAYILAN OLARAK KAPATIR. Kapalıyken
; büyük görsel hiç çizilmiyordu (ölçüldü: kullanıcı yalnız sağ üstteki küçük
; logoyu gördü). Referans VLC kurulumundaki markalı şeridin karşılığı budur.
DisableWelcomePage=no
; Kurulum dili Windows'un dilinden seçilir; kullanıcıya dil sorulmaz.
; Program içindeki dil AYRI bir tercihtir ve ayarlardan değiştirilir.
ShowLanguageDialog=no

; ASIL SIKIŞTIRMA BURADA. onedir çıktısı ~268 MB; solid LZMA2 ile tek
; kurulum dosyası belirgin biçimde küçülür. EXE tarafında UPX BİLEREK
; kullanılmaz: deno/yt-dlp zaten paketlenmiş ikililer, Qt DLL'lerinde
; bozulma riski var ve antivirüs yanlış-pozitifi ihtimali yüksek.
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

; AppMutex BİLEREK YOK (bkz. referans proje): Inno başlangıçta gereksiz
; "uygulamayı kapatın" uyarısı gösteriyordu. Restart Manager çalışan
; uygulamayı sessizce kapatır.
CloseApplications=yes
CloseApplicationsFilter="MLC Player.exe"
RestartApplications=no
SetupMutex=MLCPlayer_SetupMutex
UsePreviousAppDir=yes
UsePreviousTasks=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
VersionInfoVersion=0.33.0.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Kurulumu
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion=0.33.0.0

[Languages]
; DİL WINDOWS'TAN SEÇİLİR, KULLANICIYA SORULMAZ (`ShowLanguageDialog=no`).
; İngilizce ilk sırada: sistem dili listede yoksa Inno İLK dile düşer ve
; Türkçe kurulum ekranı, Türkçe bilmeyen kullanıcı için çıkmaz sokaktır.
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[CustomMessages]
; Bizim yazdığımız metinler .isl dosyalarında YOKTUR; her dil için burada
; verilir. Verilmezse Inno İngilizce kurulumda Türkçe cümle gösterirdi.
english.DesktopIcon=Create a desktop shortcut
english.LaunchApp=Launch %1
english.OpenRepository=Open the MLC Player page on GitHub
turkish.DesktopIcon=Masaüstü kısayolu oluştur
turkish.LaunchApp=%1 uygulamasını başlat
turkish.OpenRepository=MLC Player GitHub sayfasını aç
german.DesktopIcon=Desktopverknüpfung erstellen
german.LaunchApp=%1 starten
german.OpenRepository=MLC Player auf GitHub öffnen
spanish.DesktopIcon=Crear un acceso directo en el escritorio
spanish.LaunchApp=Iniciar %1
spanish.OpenRepository=Abrir la página de MLC Player en GitHub
french.DesktopIcon=Créer un raccourci sur le Bureau
french.LaunchApp=Lancer %1
french.OpenRepository=Ouvrir la page MLC Player sur GitHub
italian.DesktopIcon=Crea un collegamento sul desktop
italian.LaunchApp=Avvia %1
italian.OpenRepository=Apri la pagina di MLC Player su GitHub
russian.DesktopIcon=Создать ярлык на рабочем столе
russian.LaunchApp=Запустить %1
russian.OpenRepository=Открыть страницу MLC Player на GitHub
brazilianportuguese.DesktopIcon=Criar um atalho na área de trabalho
brazilianportuguese.LaunchApp=Iniciar %1
brazilianportuguese.OpenRepository=Abrir a página do MLC Player no GitHub

[Tasks]
; Varsayılan İŞARETLİ; kullanıcı istemezse kaldırır.
Name: "desktopicon"; Description: "{cm:DesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; onedir: PyInstaller çıktısının TAMAMI kurulur (exe + _internal\).
; `_internal\bin` içindeki mpv-2.dll, yt-dlp.exe ve deno.exe olmadan
; program çalışmaz; alt klasörler birlikte taşınır.
Source: "..\dist\MLC Player\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; GPLv3 metni ve README kurulum KÖKÜNDE de dursun: kullanıcı `_internal`
; içine bakmak zorunda kalmadan lisansa ulaşabilmelidir.
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.tr.md"; DestDir: "{app}"; Flags: ignoreversion

[Registry]
; ÖLÇÜLEN KUSUR: EXE sürüm kaynağı düzeltildikten SONRA bile Windows
; "Birlikte aç" listesinde "MLC Player.exe" yazmaya devam etti. Kurulu
; exe'nin FileDescription alanı DOĞRUYDU ('MLC Player'); Explorer listeyi
; önbelleğe alıyor ve adı çıkarımla buluyor. Burada ad AÇIKÇA kaydedilir,
; böylece çıkarıma ve önbelleğe bağımlı kalmaz.
;
; `uninsdeletekey`: kaldırmada bu anahtarlar da silinir — kaldırma
; kabulünde "artık kayıt kalmasın" ölçütü korunur.
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "{#MyAppName}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
; Desteklenen türler: "Birlikte aç" listesinde program bu uzantılarda önerilir.
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".mkv"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".mp4"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".avi"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".mov"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".webm"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".ts"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".m4v"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".mp3"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".flac"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".m4a"; ValueData: ""

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchApp,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
; Kurulum sonu sayfasında GitHub sayfasına gitme seçeneği. VARSAYILAN
; İŞARETSİZ: kullanıcı istemeden tarayıcı açılmaz.
Filename: "{#MyAppUrl}"; Description: "{cm:OpenRepository}"; Flags: shellexec nowait postinstall skipifsilent unchecked

[Code]
// Inno Setup 7 BUG ATLATMASI — SİLME!
// [Code] bölümü OLMAYAN kurulumlarda kaldırıcı "PathRedir: Not initialized"
// iç hatası veriyor. Bu zararsız fonksiyon bölümün var olmasını garanti eder.
function InitializeUninstall(): Boolean;
begin
  Result := True;
end;

// Kurulumdan HEMEN ÖNCE çalışan uygulamayı KESİN kapat. MLC Player küçük
// resim üretimi için AYNI exe'yi `--thumbnail-worker` ile yeniden başlatır;
// asılı kalan bu alt süreçler de aynı görüntü adını taşır ve burada
// sonlandırılır. Aksi halde `_internal` dosyaları kilitli kalabilir.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM "MLC Player.exe"',
       '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;
