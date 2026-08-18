; SPDX-FileCopyrightText: 2026 MLC Player contributors
; SPDX-License-Identifier: GPL-3.0-only
; MLC Player - "Internet Videosu" ek paketi
;
; NEDEN AYRI: `yt-dlp.exe` (17,4 MB) ve `deno.exe` (92,9 MB) birlikte ana
; paketin ucte birini kapliyordu ve YALNIZ URL'den oynatmada gerekiyorlar.
; Yerel dosya oynatan kullanici bu 110 MB'i indirmek zorunda degildir.
;
; NEDEN INDIRME DEGIL EK PAKET: urun degismezi (app/runtime_binaries.py)
; "ilk calistirmada veya URL acilirken bilesen INDIRILMEZ" der. Ek paket bu
; karari bozmadan boyut sorununu cozer: indirme kullanicinin ACIK eylemidir.
;
; Bu kurulum ana programin klasorune yazar; MLC Player kurulu degilse
; calismayi REDDEDER (yanlis yere dosya birakmaz).

#define MyAppName "MLC Player"
#define AddonName "MLC Player Internet Videosu"
#define MyAppUrl "https://github.com/IzzmooPro/MLCPlayer"
; Ana programin AppId'si: kurulum yerini ONDAN okuruz.
#define PlayerAppId "{EB0DD5CF-F20B-4B23-A1C9-2C23A83A8758}"

[Setup]
; Ek paketin KENDI kimligi; ayri kaldirilabilir.
AppId={{7C4F2A61-9B3D-4E58-9C2A-5D8E1F0B7A34}
AppName={#AddonName}
AppVersion={#AddonVersion}
AppVerName={#AddonName} {#AddonVersion}
AppPublisher=IzzmooPro
AppPublisherURL={#MyAppUrl}
DefaultDirName={code:PlayerDirectory}
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableWelcomePage=no
; Dil Windows'tan secilir; kullaniciya sorulmaz.
ShowLanguageDialog=no
PrivilegesRequired=admin
OutputDir=..\installer_output
OutputBaseFilename=MLCPlayer_InternetVideo_{#AddonVersion}
SetupIconFile=..\assets\mlc-player-icon.ico
UninstallDisplayIcon={app}\MLC Player.exe
WizardImageFile=wizard\wizard-large.bmp,wizard\wizard-large-1.bmp,wizard\wizard-large-2.bmp
WizardSmallImageFile=wizard\wizard-small.bmp,wizard\wizard-small-1.bmp,wizard\wizard-small-2.bmp
WizardImageStretch=yes
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
VersionInfoVersion={#AddonNumericVersion}
VersionInfoCompany=IzzmooPro
VersionInfoDescription={#AddonName}
VersionInfoProductName={#AddonName}
VersionInfoProductVersion={#AddonNumericVersion}
; Calisan oynatici dosyalari kilitleyebilir.
CloseApplications=yes
CloseApplicationsFilter="MLC Player.exe"
RestartApplications=no

[Languages]
; Ana kurulumla AYNI dil kumesi; dil Windows'tan secilir (ShowLanguageDialog=no).
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[CustomMessages]
english.PlayerRequired=MLC Player must be installed first.%nThis add-on adds the internet video components to an existing installation.
turkish.PlayerRequired=Önce MLC Player kurulmalıdır.%nBu ek paket internet videosu bileşenlerini mevcut kuruluma ekler.
german.PlayerRequired=MLC Player muss zuerst installiert werden.%nDiese Erweiterung ergänzt eine vorhandene Installation.
spanish.PlayerRequired=Primero debe instalarse MLC Player.%nEste complemento se añade a una instalación existente.
french.PlayerRequired=MLC Player doit d'abord être installé.%nCe module complète une installation existante.
italian.PlayerRequired=MLC Player deve essere installato prima.%nQuesto componente si aggiunge a un'installazione esistente.
russian.PlayerRequired=Сначала необходимо установить MLC Player.%nЭто дополнение добавляется к существующей установке.
brazilianportuguese.PlayerRequired=O MLC Player precisa ser instalado primeiro.%nEste complemento é adicionado a uma instalação existente.

[Files]
; Ikililer ana paketin bin dizinine gider; urun onlari YALNIZ orada arar.
Source: "..\bin\yt-dlp.exe"; DestDir: "{app}\_internal\bin"; Flags: ignoreversion
Source: "..\bin\deno.exe"; DestDir: "{app}\_internal\bin"; Flags: ignoreversion
; Lisans metinleri ikililerle BIRLIKTE dagitilir (GPLv3/MIT yukumlulugu).
Source: "..\licenses\yt-dlp-LICENSE.txt"; DestDir: "{app}\_internal\licenses"; Flags: ignoreversion
Source: "..\licenses\yt-dlp-THIRD_PARTY_LICENSES.txt"; DestDir: "{app}\_internal\licenses"; Flags: ignoreversion
Source: "..\licenses\deno-LICENSE.txt"; DestDir: "{app}\_internal\licenses"; Flags: ignoreversion

[UninstallDelete]
; OLCULEN KUSUR (19 Agustos 2026): ana program once, ek paket sonra
; kaldirildiginda butun dosyalar ve iki uninstall kaydi gidiyor ama ortak
; `{app}` klasoru 0 bayt / 0 oge olarak kaliyor. Yalniz GERCEKTEN BOSSA
; kaldir; `filesandordirs` kullanmak baska dosyalari silebilirdi.
Type: dirifempty; Name: "{app}"

[Code]
function PlayerDirectory(Param: String): String;
var
  Location: String;
begin
  // Ana programin kurulum yeri kayittan okunur; tahmin EDILMEZ.
  if RegQueryStringValue(HKLM,
      'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{#PlayerAppId}_is1',
      'InstallLocation', Location) then
    Result := RemoveBackslashUnlessRoot(Location)
  else
    Result := ExpandConstant('{autopf}\MLC Player');
end;

function InitializeSetup(): Boolean;
var
  Location: String;
begin
  // MLC Player kurulu degilse ek paketin gidecegi yer YOKTUR.
  Result := RegQueryStringValue(HKLM,
      'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{#PlayerAppId}_is1',
      'InstallLocation', Location);
  if not Result then
    MsgBox(ExpandConstant('{cm:PlayerRequired}'), mbCriticalError, MB_OK);
end;

function InitializeUninstall(): Boolean;
begin
  Result := True;
end;
