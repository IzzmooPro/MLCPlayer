#define MyAppName "MLC Player"
; SÜRÜM TEK KAYNAK: app/config.py → APP_VERSION. Burası onun kopyasıdır ve
; tests/test_version_consistency.py ikisini birbirine bağlar; elle ayrışamaz.
#define MyAppVersion "v0.3"
#define MyAppPublisher "IzzmooPro"
#define MyAppUrl "https://github.com/IzzmooPro/MLCPlayer"
#define MyAppExeName "MLC Player.exe"

[Setup]
AppId={{EB0DD5CF-F20B-4B23-A1C9-2C23A83A8758}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion} sürümü
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
; GPLv3: lisans metni kurulum sırasında GÖSTERİLİR ve pakete girer.
; Metin gnu.org kanonik hâlidir, değiştirilmemiştir (35.149 bayt).
LicenseFile=..\LICENSE

; Tek görsel kimlik: setup, kaldırıcı ve kısayollar aynı logoyu kullanır.
SetupIconFile=..\assets\mlc-player-icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

; Sihirbaz görselleri ürünün kendi ikonundan üretilir
; (packaging\make_wizard_images.py). Aksi hâlde sol taraf boş gri kalıyordu.
; Çoklu boyut yüksek DPI'da bulanıklığı önler; Inno 24-bit BMP ister.
WizardImageFile=wizard\wizard-large.bmp,wizard\wizard-large-1.bmp,wizard\wizard-large-2.bmp
WizardSmallImageFile=wizard\wizard-small.bmp,wizard\wizard-small-1.bmp,wizard\wizard-small-2.bmp
WizardImageStretch=yes

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
VersionInfoVersion=0.3.0.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Kurulumu
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion=0.3.0.0

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
; Varsayılan İŞARETLİ; kullanıcı istemezse kaldırır.
Name: "desktopicon"; Description: "Masaüstü kısayolu oluştur"; GroupDescription: "Ek görevler:"

[Files]
; onedir: PyInstaller çıktısının TAMAMI kurulur (exe + _internal\).
; `_internal\bin` içindeki mpv-2.dll, yt-dlp.exe ve deno.exe olmadan
; program çalışmaz; alt klasörler birlikte taşınır.
Source: "..\dist\MLC Player\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; GPLv3 metni ve README kurulum KÖKÜNDE de dursun: kullanıcı `_internal`
; içine bakmak zorunda kalmadan lisansa ulaşabilmelidir.
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName} uygulamasını başlat"; Flags: nowait postinstall skipifsilent
; Kurulum sonu sayfasında GitHub sayfasına gitme seçeneği. VARSAYILAN
; İŞARETSİZ: kullanıcı istemeden tarayıcı açılmaz.
Filename: "{#MyAppUrl}"; Description: "MLC Player GitHub sayfasını aç"; Flags: shellexec nowait postinstall skipifsilent unchecked

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
