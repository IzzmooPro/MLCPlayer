; SPDX-FileCopyrightText: 2026 MLC Player contributors
; SPDX-License-Identifier: GPL-3.0-only
#define MyAppName "MLC Player"
; SÜRÜM TEK KAYNAK: app/config.py → APP_VERSION. Burası onun kopyasıdır ve
; tests/test_version_consistency.py ikisini birbirine bağlar; elle ayrışamaz.
#define MyAppVersion "v0.39"
#define MyAppNumericVersion "0.39.0.0"
#define MyAppPublisher "IzzmooPro"
#define MyAppUrl "https://github.com/IzzmooPro/MLCPlayer"
#define MyAppExeName "MLC Player.exe"
#define PlayerLifecycleMutex "MLCPlayer-Running"

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
; "uygulamayı kapatın" uyarısı gösteriyordu. Restart Manager interaktif
; kurulumda etkilenen uygulamayı gösterip onay ister; sessiz kurulumda ise
; CloseApplications=yes sözleşmesine göre kapatmayı dener.
CloseApplications=yes
CloseApplicationsFilter="MLC Player.exe"
RestartApplications=no
SetupMutex=MLCPlayer_SetupMutex
UsePreviousAppDir=yes
UsePreviousTasks=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
VersionInfoVersion={#MyAppNumericVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Kurulumu
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppNumericVersion}

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

english.CWelcomeTitle=Welcome to MLC Player
english.CWelcomeInstallBody=This wizard will install MLC Player %1 on your computer.
english.CWelcomeReinstallBody=This wizard will reinstall MLC Player %1.
english.CWelcomeUpgradeBody=This wizard will update MLC Player from %1 to %2.
english.CWelcomeLicenseInfo=MLC Player is an open-source media player distributed under GPLv3. You do not need to accept the licence to install or run it. The Internet Video add-on is not included in this package.
english.CDowngradeBlocked=A newer version of MLC Player is installed on this computer. An older version cannot be installed automatically.
english.CVersionStateUnknown=The installed MLC Player version could not be verified. Setup stopped without making changes.
english.CTargetLocationMismatch=The selected folder does not match the registered MLC Player installation location. Use the registered folder or uninstall the existing version first.
english.CTargetAlreadyOccupied=The selected folder already contains an unregistered MLC Player executable. Setup stopped without overwriting it.
english.CTargetNotEmpty=The selected folder is not empty and is not a registered MLC Player installation. Choose an empty folder or remove the leftover files first.
english.CPreferencesTitle=Installation preferences
english.CPreferencesBody=Review the installation location and shortcut option.
english.CInstallLocation=Installation location
english.COpenWithInfo=MLC Player will be added to the Open with list for supported file types. Your default app will not change.
english.CPrivacyInfo=MLC Player quietly checks the public release information on GitHub at startup. There is no telemetry, advertising or analytics.
english.CAddonInfo=The Internet Video add-on is not included in this package and is installed separately.
english.CSummaryTitle=Ready to install
english.CSummaryBody=Review your selections.
english.CSummaryLocation=Location: %1
english.CSummaryDesktopYes=Desktop shortcut: Will be created
english.CSummaryDesktopNo=Desktop shortcut: Will not be created
english.CSummaryOpenWith=Open with list: Will be added (default app will not change)
english.CSummaryUpdate=Startup update check: Public GitHub release information
english.CSummaryAddon=Internet Video add-on: Not included
english.CSummaryUserData=User settings, history and cache: Will be preserved
english.CSummaryAction=Select Install to begin.
english.CProgressTitle=Installing MLC Player
english.CProgressBody=Please wait.
english.CPhasePreparing=Preparing files
english.CPhaseInstalling=Installing MLC Player
english.CPhaseIntegrating=Integrating with Windows
english.CFinishTitle=Installation complete
english.CFinishBody=MLC Player is ready to use.
english.CFinishDescription=MLC Player has been installed on your computer. You can change the default app in Windows Settings.
english.OpenDefaultApps=Open Windows Default Apps settings

turkish.CWelcomeTitle=MLC Player'a hoş geldiniz
turkish.CWelcomeInstallBody=Bu sihirbaz MLC Player %1 sürümünü bilgisayarınıza kurar.
turkish.CWelcomeReinstallBody=Bu sihirbaz MLC Player %1 sürümünü yeniden kurar.
turkish.CWelcomeUpgradeBody=Bu sihirbaz MLC Player'ı %1 sürümünden %2 sürümüne günceller.
turkish.CWelcomeLicenseInfo=MLC Player, GPLv3 kapsamında dağıtılan açık kaynaklı bir medya oynatıcıdır. Kurmak veya çalıştırmak için lisansı kabul etmeniz gerekmez. Internet Video eklentisi bu pakete dahil değildir.
turkish.CDowngradeBlocked=Bu bilgisayarda daha yeni bir MLC Player sürümü yüklü. Daha eski bir sürüm otomatik olarak kurulamaz.
turkish.CVersionStateUnknown=Yüklü MLC Player sürümü doğrulanamadı. Kurulum değişiklik yapmadan durduruldu.
turkish.CTargetLocationMismatch=Seçilen klasör kayıtlı MLC Player kurulum konumuyla eşleşmiyor. Kayıtlı klasörü kullanın veya önce mevcut sürümü kaldırın.
turkish.CTargetAlreadyOccupied=Seçilen klasörde kayıtlı olmayan bir MLC Player çalıştırılabilir dosyası var. Kurulum bu dosyanın üzerine yazmadan durduruldu.
turkish.CTargetNotEmpty=Seçilen klasör boş değil ve kayıtlı bir MLC Player kurulumu değil. Boş bir klasör seçin veya önce kalan dosyaları kaldırın.
turkish.CPreferencesTitle=Kurulum tercihleri
turkish.CPreferencesBody=Kurulum konumunu ve kısayol seçeneğini gözden geçirin.
turkish.CInstallLocation=Kurulum konumu
turkish.COpenWithInfo=MLC Player desteklenen dosya türleri için Birlikte aç listesine eklenir. Varsayılan uygulamanız değişmez.
turkish.CPrivacyInfo=MLC Player açılışta GitHub'daki herkese açık sürüm bilgisini sessizce denetler. Telemetri, reklam veya analiz yoktur.
turkish.CAddonInfo=Internet Video eklentisi bu pakete dahil değildir ve ayrı kurulur.
turkish.CSummaryTitle=Kuruluma hazır
turkish.CSummaryBody=Seçimlerinizi kontrol edin.
turkish.CSummaryLocation=Konum: %1
turkish.CSummaryDesktopYes=Masaüstü kısayolu: Oluşturulacak
turkish.CSummaryDesktopNo=Masaüstü kısayolu: Oluşturulmayacak
turkish.CSummaryOpenWith=Birlikte aç listesi: Eklenecek (varsayılan uygulama değişmez)
turkish.CSummaryUpdate=Açılış güncelleme denetimi: Herkese açık GitHub sürüm bilgisi
turkish.CSummaryAddon=Internet Video eklentisi: Dahil değil
turkish.CSummaryUserData=Kullanıcı ayarları, geçmiş ve önbellek: Korunacak
turkish.CSummaryAction=Başlamak için Kur'u seçin.
turkish.CProgressTitle=MLC Player kuruluyor
turkish.CProgressBody=Lütfen bekleyin.
turkish.CPhasePreparing=Dosyalar hazırlanıyor
turkish.CPhaseInstalling=MLC Player kuruluyor
turkish.CPhaseIntegrating=Windows ile bütünleştiriliyor
turkish.CFinishTitle=Kurulum tamamlandı
turkish.CFinishBody=MLC Player kullanıma hazır.
turkish.CFinishDescription=MLC Player bilgisayarınıza kuruldu. Varsayılan uygulamayı Windows Ayarları'ndan değiştirebilirsiniz.
turkish.OpenDefaultApps=Windows Varsayılan Uygulamalar ayarını aç

german.CWelcomeTitle=Willkommen bei MLC Player
german.CWelcomeInstallBody=Dieser Assistent installiert MLC Player %1 auf Ihrem Computer.
german.CWelcomeReinstallBody=Dieser Assistent installiert MLC Player %1 erneut.
german.CWelcomeUpgradeBody=Dieser Assistent aktualisiert MLC Player von %1 auf %2.
german.CWelcomeLicenseInfo=MLC Player ist ein unter GPLv3 vertriebener Open-Source-Mediaplayer. Für die Installation oder Ausführung müssen Sie die Lizenz nicht akzeptieren. Die Internet Video-Erweiterung ist in diesem Paket nicht enthalten.
german.CDowngradeBlocked=Auf diesem Computer ist eine neuere Version von MLC Player installiert. Eine ältere Version kann nicht automatisch installiert werden.
german.CVersionStateUnknown=Die installierte MLC Player-Version konnte nicht überprüft werden. Das Setup wurde ohne Änderungen beendet.
german.CTargetLocationMismatch=Der ausgewählte Ordner stimmt nicht mit dem registrierten Installationsordner von MLC Player überein. Verwenden Sie den registrierten Ordner oder deinstallieren Sie zuerst die vorhandene Version.
german.CTargetAlreadyOccupied=Der ausgewählte Ordner enthält bereits eine nicht registrierte ausführbare MLC Player-Datei. Das Setup wurde beendet, ohne sie zu überschreiben.
german.CTargetNotEmpty=Der ausgewählte Ordner ist nicht leer und keine registrierte MLC Player-Installation. Wählen Sie einen leeren Ordner oder entfernen Sie zuerst die verbliebenen Dateien.
german.CPreferencesTitle=Installationseinstellungen
german.CPreferencesBody=Prüfen Sie den Installationsordner und die Verknüpfungsoption.
german.CInstallLocation=Installationsordner
german.COpenWithInfo=MLC Player wird für unterstützte Dateitypen zur Liste Öffnen mit hinzugefügt. Ihre Standard-App wird nicht geändert.
german.CPrivacyInfo=MLC Player prüft beim Start im Hintergrund die öffentlichen Versionsinformationen auf GitHub. Es gibt keine Telemetrie, Werbung oder Analyse.
german.CAddonInfo=Die Internet Video-Erweiterung ist in diesem Paket nicht enthalten und wird separat installiert.
german.CSummaryTitle=Bereit zur Installation
german.CSummaryBody=Prüfen Sie Ihre Auswahl.
german.CSummaryLocation=Speicherort: %1
german.CSummaryDesktopYes=Desktopverknüpfung: Wird erstellt
german.CSummaryDesktopNo=Desktopverknüpfung: Wird nicht erstellt
german.CSummaryOpenWith=Liste Öffnen mit: Wird hinzugefügt (Standard-App bleibt unverändert)
german.CSummaryUpdate=Update-Prüfung beim Start: Öffentliche GitHub-Versionsinformationen
german.CSummaryAddon=Internet Video-Erweiterung: Nicht enthalten
german.CSummaryUserData=Benutzereinstellungen, Verlauf und Cache: Bleiben erhalten
german.CSummaryAction=Wählen Sie Installieren, um zu beginnen.
german.CProgressTitle=MLC Player wird installiert
german.CProgressBody=Bitte warten.
german.CPhasePreparing=Dateien werden vorbereitet
german.CPhaseInstalling=MLC Player wird installiert
german.CPhaseIntegrating=Integration in Windows
german.CFinishTitle=Installation abgeschlossen
german.CFinishBody=MLC Player ist einsatzbereit.
german.CFinishDescription=MLC Player wurde auf Ihrem Computer installiert. Die Standard-App können Sie in den Windows-Einstellungen ändern.
german.OpenDefaultApps=Windows-Einstellungen für Standard-Apps öffnen

spanish.CWelcomeTitle=Bienvenido a MLC Player
spanish.CWelcomeInstallBody=Este asistente instalará MLC Player %1 en su equipo.
spanish.CWelcomeReinstallBody=Este asistente reinstalará MLC Player %1.
spanish.CWelcomeUpgradeBody=Este asistente actualizará MLC Player de %1 a %2.
spanish.CWelcomeLicenseInfo=MLC Player es un reproductor multimedia de código abierto distribuido bajo la GPLv3. No necesita aceptar la licencia para instalarlo o ejecutarlo. El complemento Internet Video no está incluido en este paquete.
spanish.CDowngradeBlocked=Hay una versión más reciente de MLC Player instalada en este equipo. No se puede instalar automáticamente una versión anterior.
spanish.CVersionStateUnknown=No se pudo verificar la versión instalada de MLC Player. La instalación se detuvo sin realizar cambios.
spanish.CTargetLocationMismatch=La carpeta seleccionada no coincide con la ubicación de instalación registrada de MLC Player. Use la carpeta registrada o desinstale primero la versión existente.
spanish.CTargetAlreadyOccupied=La carpeta seleccionada ya contiene un ejecutable de MLC Player no registrado. La instalación se detuvo sin sobrescribirlo.
spanish.CTargetNotEmpty=La carpeta seleccionada no está vacía y no es una instalación registrada de MLC Player. Elija una carpeta vacía o elimine primero los archivos restantes.
spanish.CPreferencesTitle=Preferencias de instalación
spanish.CPreferencesBody=Revise la ubicación de instalación y la opción de acceso directo.
spanish.CInstallLocation=Ubicación de instalación
spanish.COpenWithInfo=MLC Player se añadirá a la lista Abrir con para los tipos de archivo compatibles. Su aplicación predeterminada no cambiará.
spanish.CPrivacyInfo=MLC Player consulta discretamente al iniciarse la información pública de versiones en GitHub. No hay telemetría, publicidad ni análisis.
spanish.CAddonInfo=El complemento Internet Video no está incluido en este paquete y se instala por separado.
spanish.CSummaryTitle=Listo para instalar
spanish.CSummaryBody=Revise sus selecciones.
spanish.CSummaryLocation=Ubicación: %1
spanish.CSummaryDesktopYes=Acceso directo en el escritorio: Se creará
spanish.CSummaryDesktopNo=Acceso directo en el escritorio: No se creará
spanish.CSummaryOpenWith=Lista Abrir con: Se añadirá (la aplicación predeterminada no cambiará)
spanish.CSummaryUpdate=Comprobación de actualizaciones al iniciar: Información pública de versiones de GitHub
spanish.CSummaryAddon=Complemento Internet Video: No incluido
spanish.CSummaryUserData=Configuración, historial y caché del usuario: Se conservarán
spanish.CSummaryAction=Seleccione Instalar para comenzar.
spanish.CProgressTitle=Instalando MLC Player
spanish.CProgressBody=Espere, por favor.
spanish.CPhasePreparing=Preparando archivos
spanish.CPhaseInstalling=Instalando MLC Player
spanish.CPhaseIntegrating=Integrando con Windows
spanish.CFinishTitle=Instalación completada
spanish.CFinishBody=MLC Player está listo para usarse.
spanish.CFinishDescription=MLC Player se ha instalado en su equipo. Puede cambiar la aplicación predeterminada en Configuración de Windows.
spanish.OpenDefaultApps=Abrir la configuración de aplicaciones predeterminadas de Windows

french.CWelcomeTitle=Bienvenue dans MLC Player
french.CWelcomeInstallBody=Cet assistant va installer MLC Player %1 sur votre ordinateur.
french.CWelcomeReinstallBody=Cet assistant va réinstaller MLC Player %1.
french.CWelcomeUpgradeBody=Cet assistant va mettre à jour MLC Player de %1 vers %2.
french.CWelcomeLicenseInfo=MLC Player est un lecteur multimédia open source distribué sous GPLv3. Vous n'avez pas besoin d'accepter la licence pour l'installer ou l'exécuter. L'extension Internet Video n'est pas incluse dans ce paquet.
french.CDowngradeBlocked=Une version plus récente de MLC Player est installée sur cet ordinateur. Une version antérieure ne peut pas être installée automatiquement.
french.CVersionStateUnknown=La version installée de MLC Player n'a pas pu être vérifiée. L'installation s'est arrêtée sans apporter de modifications.
french.CTargetLocationMismatch=Le dossier sélectionné ne correspond pas à l'emplacement d'installation enregistré de MLC Player. Utilisez le dossier enregistré ou désinstallez d'abord la version existante.
french.CTargetAlreadyOccupied=Le dossier sélectionné contient déjà un exécutable MLC Player non enregistré. L'installation s'est arrêtée sans l'écraser.
french.CTargetNotEmpty=Le dossier sélectionné n'est pas vide et ne correspond pas à une installation enregistrée de MLC Player. Choisissez un dossier vide ou supprimez d'abord les fichiers restants.
french.CPreferencesTitle=Préférences d'installation
french.CPreferencesBody=Vérifiez l'emplacement d'installation et l'option de raccourci.
french.CInstallLocation=Emplacement d'installation
french.COpenWithInfo=MLC Player sera ajouté à la liste Ouvrir avec pour les types de fichiers pris en charge. Votre application par défaut ne changera pas.
french.CPrivacyInfo=Au démarrage, MLC Player vérifie discrètement les informations publiques de version sur GitHub. Il n'y a ni télémétrie, ni publicité, ni analyse.
french.CAddonInfo=L'extension Internet Video n'est pas incluse dans ce paquet et s'installe séparément.
french.CSummaryTitle=Prêt pour l'installation
french.CSummaryBody=Vérifiez vos choix.
french.CSummaryLocation=Emplacement : %1
french.CSummaryDesktopYes=Raccourci sur le Bureau : Sera créé
french.CSummaryDesktopNo=Raccourci sur le Bureau : Ne sera pas créé
french.CSummaryOpenWith=Liste Ouvrir avec : Sera ajoutée (l'application par défaut ne changera pas)
french.CSummaryUpdate=Recherche de mise à jour au démarrage : Informations publiques de version GitHub
french.CSummaryAddon=Extension Internet Video : Non incluse
french.CSummaryUserData=Paramètres, historique et cache utilisateur : Seront conservés
french.CSummaryAction=Sélectionnez Installer pour commencer.
french.CProgressTitle=Installation de MLC Player
french.CProgressBody=Veuillez patienter.
french.CPhasePreparing=Préparation des fichiers
french.CPhaseInstalling=Installation de MLC Player
french.CPhaseIntegrating=Intégration à Windows
french.CFinishTitle=Installation terminée
french.CFinishBody=MLC Player est prêt à l'emploi.
french.CFinishDescription=MLC Player a été installé sur votre ordinateur. Vous pouvez modifier l'application par défaut dans les Paramètres Windows.
french.OpenDefaultApps=Ouvrir les paramètres des applications par défaut de Windows

italian.CWelcomeTitle=Benvenuto in MLC Player
italian.CWelcomeInstallBody=Questa procedura guidata installerà MLC Player %1 nel computer.
italian.CWelcomeReinstallBody=Questa procedura guidata reinstallerà MLC Player %1.
italian.CWelcomeUpgradeBody=Questa procedura guidata aggiornerà MLC Player dalla versione %1 alla %2.
italian.CWelcomeLicenseInfo=MLC Player è un lettore multimediale open source distribuito sotto GPLv3. Non è necessario accettare la licenza per installarlo o eseguirlo. Il componente aggiuntivo Internet Video non è incluso in questo pacchetto.
italian.CDowngradeBlocked=In questo computer è installata una versione più recente di MLC Player. Non è possibile installare automaticamente una versione precedente.
italian.CVersionStateUnknown=Non è stato possibile verificare la versione installata di MLC Player. L'installazione è stata interrotta senza apportare modifiche.
italian.CTargetLocationMismatch=La cartella selezionata non corrisponde al percorso di installazione registrato di MLC Player. Usa la cartella registrata o disinstalla prima la versione esistente.
italian.CTargetAlreadyOccupied=La cartella selezionata contiene già un eseguibile MLC Player non registrato. L'installazione è stata interrotta senza sovrascriverlo.
italian.CTargetNotEmpty=La cartella selezionata non è vuota e non è un'installazione registrata di MLC Player. Scegli una cartella vuota o rimuovi prima i file rimasti.
italian.CPreferencesTitle=Preferenze di installazione
italian.CPreferencesBody=Controlla il percorso di installazione e l'opzione del collegamento.
italian.CInstallLocation=Percorso di installazione
italian.COpenWithInfo=MLC Player verrà aggiunto all'elenco Apri con per i tipi di file supportati. L'app predefinita non verrà modificata.
italian.CPrivacyInfo=All'avvio MLC Player controlla discretamente le informazioni pubbliche sulle versioni in GitHub. Non sono presenti telemetria, pubblicità o analisi.
italian.CAddonInfo=Il componente aggiuntivo Internet Video non è incluso in questo pacchetto e viene installato separatamente.
italian.CSummaryTitle=Pronto per l'installazione
italian.CSummaryBody=Controlla le selezioni.
italian.CSummaryLocation=Percorso: %1
italian.CSummaryDesktopYes=Collegamento sul desktop: Verrà creato
italian.CSummaryDesktopNo=Collegamento sul desktop: Non verrà creato
italian.CSummaryOpenWith=Elenco Apri con: Verrà aggiunto (l'app predefinita non cambierà)
italian.CSummaryUpdate=Controllo aggiornamenti all'avvio: Informazioni pubbliche sulle versioni GitHub
italian.CSummaryAddon=Componente aggiuntivo Internet Video: Non incluso
italian.CSummaryUserData=Impostazioni, cronologia e cache utente: Verranno conservate
italian.CSummaryAction=Seleziona Installa per iniziare.
italian.CProgressTitle=Installazione di MLC Player
italian.CProgressBody=Attendere.
italian.CPhasePreparing=Preparazione dei file
italian.CPhaseInstalling=Installazione di MLC Player
italian.CPhaseIntegrating=Integrazione con Windows
italian.CFinishTitle=Installazione completata
italian.CFinishBody=MLC Player è pronto per l'uso.
italian.CFinishDescription=MLC Player è stato installato nel computer. Puoi modificare l'app predefinita nelle Impostazioni di Windows.
italian.OpenDefaultApps=Apri le impostazioni delle app predefinite di Windows

russian.CWelcomeTitle=Добро пожаловать в MLC Player
russian.CWelcomeInstallBody=Этот мастер установит MLC Player %1 на ваш компьютер.
russian.CWelcomeReinstallBody=Этот мастер переустановит MLC Player %1.
russian.CWelcomeUpgradeBody=Этот мастер обновит MLC Player с версии %1 до %2.
russian.CWelcomeLicenseInfo=MLC Player — медиаплеер с открытым исходным кодом, распространяемый по лицензии GPLv3. Для установки или запуска принимать лицензию не требуется. Дополнение Internet Video не входит в этот пакет.
russian.CDowngradeBlocked=На этом компьютере установлена более новая версия MLC Player. Автоматическая установка более старой версии невозможна.
russian.CVersionStateUnknown=Не удалось проверить установленную версию MLC Player. Установка остановлена без внесения изменений.
russian.CTargetLocationMismatch=Выбранная папка не совпадает с зарегистрированным расположением MLC Player. Используйте зарегистрированную папку или сначала удалите существующую версию.
russian.CTargetAlreadyOccupied=В выбранной папке уже находится незарегистрированный исполняемый файл MLC Player. Установка остановлена без его перезаписи.
russian.CTargetNotEmpty=Выбранная папка не пуста и не является зарегистрированной установкой MLC Player. Выберите пустую папку или сначала удалите оставшиеся файлы.
russian.CPreferencesTitle=Параметры установки
russian.CPreferencesBody=Проверьте папку установки и параметр ярлыка.
russian.CInstallLocation=Папка установки
russian.COpenWithInfo=MLC Player будет добавлен в список Открыть с помощью для поддерживаемых типов файлов. Приложение по умолчанию не изменится.
russian.CPrivacyInfo=При запуске MLC Player незаметно проверяет общедоступные сведения о версиях на GitHub. Телеметрия, реклама и аналитика отсутствуют.
russian.CAddonInfo=Дополнение Internet Video не входит в этот пакет и устанавливается отдельно.
russian.CSummaryTitle=Всё готово к установке
russian.CSummaryBody=Проверьте выбранные параметры.
russian.CSummaryLocation=Папка: %1
russian.CSummaryDesktopYes=Ярлык на рабочем столе: Будет создан
russian.CSummaryDesktopNo=Ярлык на рабочем столе: Не будет создан
russian.CSummaryOpenWith=Список Открыть с помощью: Будет добавлен (приложение по умолчанию не изменится)
russian.CSummaryUpdate=Проверка обновлений при запуске: Общедоступные сведения о версиях GitHub
russian.CSummaryAddon=Дополнение Internet Video: Не входит
russian.CSummaryUserData=Настройки, история и кэш пользователя: Будут сохранены
russian.CSummaryAction=Нажмите Установить, чтобы начать.
russian.CProgressTitle=Установка MLC Player
russian.CProgressBody=Подождите.
russian.CPhasePreparing=Подготовка файлов
russian.CPhaseInstalling=Установка MLC Player
russian.CPhaseIntegrating=Интеграция с Windows
russian.CFinishTitle=Установка завершена
russian.CFinishBody=MLC Player готов к использованию.
russian.CFinishDescription=MLC Player установлен на ваш компьютер. Приложение по умолчанию можно изменить в параметрах Windows.
russian.OpenDefaultApps=Открыть параметры приложений по умолчанию Windows

brazilianportuguese.CWelcomeTitle=Bem-vindo ao MLC Player
brazilianportuguese.CWelcomeInstallBody=Este assistente instalará o MLC Player %1 no seu computador.
brazilianportuguese.CWelcomeReinstallBody=Este assistente reinstalará o MLC Player %1.
brazilianportuguese.CWelcomeUpgradeBody=Este assistente atualizará o MLC Player da versão %1 para a %2.
brazilianportuguese.CWelcomeLicenseInfo=O MLC Player é um reprodutor de mídia de código aberto distribuído sob a GPLv3. Você não precisa aceitar a licença para instalá-lo ou executá-lo. O complemento Internet Video não está incluído neste pacote.
brazilianportuguese.CDowngradeBlocked=Há uma versão mais recente do MLC Player instalada neste computador. Uma versão anterior não pode ser instalada automaticamente.
brazilianportuguese.CVersionStateUnknown=Não foi possível verificar a versão instalada do MLC Player. A instalação foi interrompida sem fazer alterações.
brazilianportuguese.CTargetLocationMismatch=A pasta selecionada não corresponde ao local de instalação registrado do MLC Player. Use a pasta registrada ou desinstale primeiro a versão existente.
brazilianportuguese.CTargetAlreadyOccupied=A pasta selecionada já contém um executável não registrado do MLC Player. A instalação foi interrompida sem substituí-lo.
brazilianportuguese.CTargetNotEmpty=A pasta selecionada não está vazia e não é uma instalação registrada do MLC Player. Escolha uma pasta vazia ou remova primeiro os arquivos restantes.
brazilianportuguese.CPreferencesTitle=Preferências de instalação
brazilianportuguese.CPreferencesBody=Revise o local de instalação e a opção de atalho.
brazilianportuguese.CInstallLocation=Local de instalação
brazilianportuguese.COpenWithInfo=O MLC Player será adicionado à lista Abrir com para os tipos de arquivo compatíveis. O aplicativo padrão não será alterado.
brazilianportuguese.CPrivacyInfo=Ao iniciar, o MLC Player verifica discretamente as informações públicas de versão no GitHub. Não há telemetria, publicidade nem análise.
brazilianportuguese.CAddonInfo=O complemento Internet Video não está incluído neste pacote e é instalado separadamente.
brazilianportuguese.CSummaryTitle=Pronto para instalar
brazilianportuguese.CSummaryBody=Revise suas escolhas.
brazilianportuguese.CSummaryLocation=Local: %1
brazilianportuguese.CSummaryDesktopYes=Atalho na área de trabalho: Será criado
brazilianportuguese.CSummaryDesktopNo=Atalho na área de trabalho: Não será criado
brazilianportuguese.CSummaryOpenWith=Lista Abrir com: Será adicionada (o aplicativo padrão não será alterado)
brazilianportuguese.CSummaryUpdate=Verificação de atualizações ao iniciar: Informações públicas de versão do GitHub
brazilianportuguese.CSummaryAddon=Complemento Internet Video: Não incluído
brazilianportuguese.CSummaryUserData=Configurações, histórico e cache do usuário: Serão preservados
brazilianportuguese.CSummaryAction=Selecione Instalar para começar.
brazilianportuguese.CProgressTitle=Instalando o MLC Player
brazilianportuguese.CProgressBody=Aguarde.
brazilianportuguese.CPhasePreparing=Preparando arquivos
brazilianportuguese.CPhaseInstalling=Instalando o MLC Player
brazilianportuguese.CPhaseIntegrating=Integrando com o Windows
brazilianportuguese.CFinishTitle=Instalação concluída
brazilianportuguese.CFinishBody=O MLC Player está pronto para uso.
brazilianportuguese.CFinishDescription=O MLC Player foi instalado no seu computador. Você pode alterar o aplicativo padrão nas Configurações do Windows.
brazilianportuguese.OpenDefaultApps=Abrir as configurações de aplicativos padrão do Windows
ClosePlayerBeforeUninstall=MLC Player is still running. Close it completely, then start uninstall again.
turkish.ClosePlayerBeforeUninstall=MLC Player hâlâ çalışıyor. Programı tamamen kapatıp kaldırmayı yeniden başlatın.

[Tasks]
; Varsayılan İŞARETLİ; kullanıcı istemezse kaldırır.
Name: "desktopicon"; Description: "{cm:DesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; onedir: PyInstaller çıktısının TAMAMI kurulur (exe + _internal\).
; `_internal\bin` içindeki mpv-2.dll çekirdek runtime'dır. yt-dlp ve deno
; bilinçli olarak ana pakette yoktur; yalnız Internet Videosu ek paketindedir.
Source: "..\dist\MLC Player\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; BeforeInstall: SetInstallPhase('installing')
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
; Eski yönetici-olmayan sürümler aynı ürüne ait kullanıcı düzeyi ağacı HKCU'da
; bırakabiliyordu. Yalnız TAM ürün anahtarı varsa uninstall loguna al; kurulumda
; anahtarı oluşturma/değiştirme ve paylaşılan `Applications` üst ağacına dokunma.
Root: HKCU; Subkey: "Software\Classes\Applications\{#MyAppExeName}"; Flags: dontcreatekey uninsdeletekey
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
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; BeforeInstall: SetInstallPhase('integrating')
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Description: "{cm:LaunchApp,{#MyAppName}}"; Flags: nowait postinstall skipifsilent runasoriginaluser
Filename: "ms-settings:defaultapps"; Description: "{cm:OpenDefaultApps}"; Flags: shellexec nowait postinstall skipifsilent unchecked runasoriginaluser
; Kurulum sonu sayfasında GitHub sayfasına gitme seçeneği. VARSAYILAN
; İŞARETSİZ: kullanıcı istemeden tarayıcı açılmaz.
Filename: "{#MyAppUrl}"; Description: "{cm:OpenRepository}"; Flags: shellexec nowait postinstall skipifsilent unchecked runasoriginaluser

[Code]
const
  InstallModeFirst = 0;
  InstallModeReinstall = 1;
  InstallModeUpgrade = 2;

var
  CurrentInstallMode: Integer;
  InstalledVersionText: String;
  RegisteredInstallDir: String;
  RegisteredInstalledVersion: Int64;
  PreferencesInfoLabel: TNewStaticText;
  InstallPhaseLabel: TNewStaticText;
  CurrentInstallPhase: String;

function InitializeSetup(): Boolean;
var
  UninstallKey: String;
  InstalledDir: String;
  InstalledExePath: String;
  InstalledVersion: Int64;
  PackageVersion: Int64;
  Comparison: Integer;
  Major: Word;
  Minor: Word;
  Revision: Word;
  Build: Word;
begin
  Result := False;
  CurrentInstallMode := InstallModeFirst;
  InstalledVersionText := '';
  RegisteredInstallDir := '';

  if not StrToVersion('{#MyAppNumericVersion}', PackageVersion) then
  begin
    MsgBox(CustomMessage('CVersionStateUnknown'), mbCriticalError, MB_OK);
    Exit;
  end;

  UninstallKey := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{EB0DD5CF-F20B-4B23-A1C9-2C23A83A8758}_is1';
  if not RegKeyExists(HKLM64, UninstallKey) then
  begin
    Result := True;
    Exit;
  end;

  if not RegQueryStringValue(HKLM64, UninstallKey, 'InstallLocation',
    InstalledDir) then
  begin
    MsgBox(CustomMessage('CVersionStateUnknown'), mbCriticalError, MB_OK);
    Exit;
  end;

  InstalledDir := RemoveBackslashUnlessRoot(Trim(InstalledDir));
  InstalledExePath := AddBackslash(InstalledDir) + '{#MyAppExeName}';
  if (InstalledDir = '') or (not FileExists(InstalledExePath)) or
     (not GetPackedVersion(InstalledExePath, InstalledVersion)) then
  begin
    MsgBox(CustomMessage('CVersionStateUnknown'), mbCriticalError, MB_OK);
    Exit;
  end;

  RegisteredInstallDir := InstalledDir;
  RegisteredInstalledVersion := InstalledVersion;
  UnpackVersionComponents(InstalledVersion, Major, Minor, Revision, Build);
  InstalledVersionText := 'v' + IntToStr(Major) + '.' + IntToStr(Minor);
  Comparison := ComparePackedVersion(InstalledVersion, PackageVersion);
  if Comparison > 0 then
  begin
    MsgBox(CustomMessage('CDowngradeBlocked'), mbCriticalError, MB_OK);
    Exit;
  end;

  if Comparison = 0 then
    CurrentInstallMode := InstallModeReinstall
  else
    CurrentInstallMode := InstallModeUpgrade;
  Result := True;
end;

function DirectoryHasEntries(Directory: String): Boolean;
var
  FindRec: TFindRec;
begin
  Result := True;
  if not DirExists(Directory) then
  begin
    Result := False;
    Exit;
  end;

  if not FindFirst(AddBackslash(Directory) + '*', FindRec) then
    Exit;

  try
    repeat
      if (FindRec.Name <> '.') and (FindRec.Name <> '..') then
        Exit;
    until not FindNext(FindRec);
    Result := False;
  finally
    FindClose(FindRec);
  end;
end;

function ValidateInstallTarget(): String;
var
  TargetDir: String;
  TargetExePath: String;
  TargetVersion: Int64;
  PackageVersion: Int64;
begin
  Result := '';
  TargetDir := RemoveBackslashUnlessRoot(Trim(WizardDirValue));
  if (TargetDir = '') or (not PathIsRooted(TargetDir)) or
     (not StrToVersion('{#MyAppNumericVersion}', PackageVersion)) then
  begin
    Result := CustomMessage('CVersionStateUnknown');
    Exit;
  end;

  if (CurrentInstallMode <> InstallModeFirst) and
     (not PathSame(TargetDir, RegisteredInstallDir)) then
  begin
    Result := CustomMessage('CTargetLocationMismatch');
    Exit;
  end;

  TargetExePath := AddBackslash(TargetDir) + '{#MyAppExeName}';
  if CurrentInstallMode = InstallModeFirst then
  begin
    if FileExists(TargetExePath) then
      Result := CustomMessage('CTargetAlreadyOccupied')
    else if DirectoryHasEntries(TargetDir) then
      Result := CustomMessage('CTargetNotEmpty');
    Exit;
  end;

  if (not FileExists(TargetExePath)) or
     (not GetPackedVersion(TargetExePath, TargetVersion)) then
  begin
    Result := CustomMessage('CVersionStateUnknown');
    Exit;
  end;

  if not SamePackedVersion(TargetVersion, RegisteredInstalledVersion) then
  begin
    Result := CustomMessage('CVersionStateUnknown');
    Exit;
  end;

  if ComparePackedVersion(TargetVersion, PackageVersion) > 0 then
    Result := CustomMessage('CDowngradeBlocked');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := ValidateInstallTarget;
end;

procedure SetInstallPhase(Phase: String);
var
  Caption: String;
begin
  if CurrentInstallPhase = Phase then
    Exit;

  if Phase = 'preparing' then
    Caption := CustomMessage('CPhasePreparing')
  else if Phase = 'installing' then
    Caption := CustomMessage('CPhaseInstalling')
  else if Phase = 'integrating' then
    Caption := CustomMessage('CPhaseIntegrating')
  else
    Exit;

  CurrentInstallPhase := Phase;
  InstallPhaseLabel.Caption := Caption;
end;

procedure InitializeWizard();
begin
  WizardForm.ReadyMemo.Color := clWindow;
  WizardForm.ReadyMemo.ReadOnly := True;
  WizardForm.ReadyMemo.WordWrap := True;
  WizardForm.ReadyMemo.ScrollBars := ssVertical;
  WizardForm.ReadyMemo.Anchors := [akLeft, akTop, akRight, akBottom];

  WizardForm.TasksList.Parent := WizardForm.SelectDirPage;
  WizardForm.TasksList.Left := 0;
  WizardForm.TasksList.Top := WizardForm.DirEdit.Top +
    WizardForm.DirEdit.Height + ScaleY(16);
  WizardForm.TasksList.Width := WizardForm.SelectDirPage.ClientWidth;
  WizardForm.TasksList.Height := ScaleY(48);
  WizardForm.TasksList.Anchors := [akLeft, akTop, akRight];
  WizardForm.TasksList.TabOrder := 2;
  WizardForm.DirEdit.TabOrder := 0;
  WizardForm.DirBrowseButton.TabOrder := 1;

  PreferencesInfoLabel := TNewStaticText.Create(WizardForm);
  PreferencesInfoLabel.Parent := WizardForm.SelectDirPage;
  PreferencesInfoLabel.Left := 0;
  PreferencesInfoLabel.Top := WizardForm.TasksList.Top +
    WizardForm.TasksList.Height + ScaleY(8);
  PreferencesInfoLabel.Width := WizardForm.SelectDirPage.ClientWidth;
  PreferencesInfoLabel.Height := WizardForm.SelectDirPage.ClientHeight -
    PreferencesInfoLabel.Top;
  PreferencesInfoLabel.Anchors := [akLeft, akTop, akRight, akBottom];
  PreferencesInfoLabel.AutoSize := False;
  PreferencesInfoLabel.WordWrap := True;

  InstallPhaseLabel := TNewStaticText.Create(WizardForm);
  InstallPhaseLabel.Parent := WizardForm.InstallingPage;
  InstallPhaseLabel.Left := WizardForm.StatusLabel.Left;
  InstallPhaseLabel.Top := WizardForm.StatusLabel.Top;
  InstallPhaseLabel.Width := WizardForm.InstallingPage.ClientWidth -
    InstallPhaseLabel.Left;
  InstallPhaseLabel.Height := ScaleY(16);
  InstallPhaseLabel.Anchors := [akLeft, akTop, akRight];
  WizardForm.StatusLabel.Top := WizardForm.StatusLabel.Top + ScaleY(20);
  WizardForm.FilenameLabel.Top := WizardForm.FilenameLabel.Top + ScaleY(20);
  WizardForm.ProgressGauge.Top := WizardForm.ProgressGauge.Top + ScaleY(20);
end;

procedure UpdateWelcomePage();
var
  Body: String;
begin
  WizardForm.WelcomeLabel1.Caption := CustomMessage('CWelcomeTitle');
  if CurrentInstallMode = InstallModeReinstall then
    Body := FmtMessage(CustomMessage('CWelcomeReinstallBody'), ['{#MyAppVersion}'])
  else if CurrentInstallMode = InstallModeUpgrade then
    Body := FmtMessage(CustomMessage('CWelcomeUpgradeBody'), [InstalledVersionText, '{#MyAppVersion}'])
  else
    Body := FmtMessage(CustomMessage('CWelcomeInstallBody'), ['{#MyAppVersion}']);

  WizardForm.WelcomeLabel2.Caption := Body + #13#10#13#10 +
    CustomMessage('CWelcomeLicenseInfo');
  WizardForm.WelcomeLabel2.AdjustHeight;
end;

procedure UpdatePreferencesPage();
begin
  WizardForm.PageNameLabel.Caption := CustomMessage('CPreferencesTitle');
  WizardForm.PageDescriptionLabel.Caption := CustomMessage('CPreferencesBody');
  WizardForm.SelectDirLabel.Caption := CustomMessage('CInstallLocation');
  PreferencesInfoLabel.Caption := CustomMessage('COpenWithInfo') + #13#10#13#10 +
    CustomMessage('CPrivacyInfo') + #13#10#13#10 +
    CustomMessage('CAddonInfo');
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := PageID = wpSelectTasks;
end;

function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo,
  MemoTypeInfo, MemoComponentsInfo, MemoGroupInfo,
  MemoTasksInfo: String): String;
begin
  Result := FmtMessage(CustomMessage('CSummaryLocation'), [WizardDirValue]) +
    NewLine + NewLine;
  if WizardIsTaskSelected('desktopicon') then
    Result := Result + CustomMessage('CSummaryDesktopYes') + NewLine
  else
    Result := Result + CustomMessage('CSummaryDesktopNo') + NewLine;
  Result := Result + CustomMessage('CSummaryOpenWith') + NewLine + NewLine +
    CustomMessage('CSummaryUpdate') + NewLine +
    CustomMessage('CSummaryAddon') + NewLine + NewLine +
    CustomMessage('CSummaryUserData') + NewLine + NewLine +
    CustomMessage('CSummaryAction');
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  case CurPageID of
    wpWelcome:
      begin
        UpdateWelcomePage;
        WizardForm.ActiveControl := WizardForm.NextButton;
      end;
    wpSelectDir:
      begin
        UpdatePreferencesPage;
        WizardForm.ActiveControl := WizardForm.DirEdit;
      end;
    wpReady:
      begin
        WizardForm.PageNameLabel.Caption := CustomMessage('CSummaryTitle');
        WizardForm.PageDescriptionLabel.Caption := CustomMessage('CSummaryBody');
        WizardForm.ActiveControl := WizardForm.NextButton;
      end;
    wpInstalling:
      begin
        WizardForm.PageNameLabel.Caption := CustomMessage('CProgressTitle');
        WizardForm.PageDescriptionLabel.Caption := CustomMessage('CProgressBody');
        CurrentInstallPhase := '';
        SetInstallPhase('preparing');
        WizardForm.ActiveControl := WizardForm.CancelButton;
      end;
    wpFinished:
      begin
        WizardForm.FinishedHeadingLabel.Caption := CustomMessage('CFinishTitle');
        WizardForm.FinishedLabel.Caption := CustomMessage('CFinishBody') + #13#10#13#10 +
          CustomMessage('CFinishDescription');
        WizardForm.FinishedLabel.AdjustHeight;
        WizardForm.RunList.Top := WizardForm.FinishedLabel.Top +
          WizardForm.FinishedLabel.Height + ScaleY(12);
        WizardForm.RunList.Height := WizardForm.FinishedPage.ClientHeight -
          WizardForm.RunList.Top;
        WizardForm.RunList.Anchors := [akLeft, akTop, akRight, akBottom];
        WizardForm.ActiveControl := WizardForm.NextButton;
      end;
  end;
end;

// Inno Setup 7 BUG ATLATMASI — SİLME!
// [Code] bölümü OLMAYAN kurulumlarda kaldırıcı "PathRedir: Not initialized"
// iç hatası veriyor. Bu zararsız fonksiyon bölümün var olmasını garanti eder.
function InitializeUninstall(): Boolean;
begin
  // CloseApplications yalnız Setup/upgrade Restart Manager yoludur. Uninstall
  // açık ürünün image kilitlerini temizlemeyi garanti etmez. Ürünün sabit
  // yaşam döngüsü mutex'i süreç gerçekten bitene kadar açık kaldığından burada
  // fail-closed dururuz; kayıt/kısayolları silip binary bırakmayız.
  Result := not CheckForMutexes('{#PlayerLifecycleMutex}');
  if not Result then
    MsgBox(ExpandConstant('{cm:ClosePlayerBeforeUninstall}'),
      mbCriticalError, MB_OK);
end;
