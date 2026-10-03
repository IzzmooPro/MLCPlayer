# MLC Player Paketleme ve Kurulum Planı

> **GÜNCEL INSTALLER UX SÖZLEŞMESİ VE TARİHSEL PAKETLEME KAYITLARI:** Kalıcı
> paketleme/installer kararları ve güncel UX sözleşmesi bu belgede tutulur;
> canlı durum veya sıradaki iş buradan çıkarılmaz. Güncel devir
> için `docs/CONTINUITY.md`, kesin yayın sırası için yalnız
> `docs/release/RELEASE_PROCESS.md`, doğrulanmış sonuçlar için
> `docs/VERIFICATION_LEDGER.json` kullanılır. Aşağıdaki eski sürüm, ölçüm ve
> checklist snapshot'ları tarihsel kayıttır; canlı kaynakla yeniden
> doğrulanmadan güncel engel sayılmaz. Tarihsel paketleme kayıtları, eski
> uyumluluk kontrol listesi ve ilk ikon notları 3 Ekim 2026'da
> `docs/history/PACKAGING_HISTORY.md` dosyasına taşındı.

Bu dosya Windows kurulumunun güncel UX sözleşmesini, kalıcı paketleme
kararlarını ve tarihsel tasarım kayıtlarını açıklar. Paketleme aşamasında
gerekçeler buradan okunabilir; yürütme sırası
`docs/release/RELEASE_PROCESS.md` üzerinden alınır ve o günkü kaynak, araç sürümleri
ile Windows kabul sonuçları yeniden doğrulanır.

## Güncel installer UX sözleşmesi

Bu bölüm kurulum deneyiminin onaylanmış ürün sınırıdır. Henüz installer
uygulaması, build veya fiziksel kurulum kanıtı değildir.

### Sabit kararlar

- Kurulum dili Windows dilinden otomatik seçilir; ayrı dil ekranı gösterilmez.
- İlk ekran MLC markalı, sade ve ürünün ne kuracağını açıkça anlatır.
- GPLv3 ve açık kaynak bilgisi sunulur; lisans kabulü zorunlu tutulmaz.
- VLC benzeri kalabalık bileşen ağacı, ActiveX, Mozilla veya tarayıcı eklentisi
  gösterilmez.
- Hedef klasör görünür ve değiştirilebilir; güncellemede önceki hedef korunur.
- Dosya ilişkilendirmeleri sessizce ele geçirilmez. MLC desteklenen türler için
  Windows'un "Birlikte aç" listesine eklenir; varsayılan uygulama seçimi
  Windows Ayarları üzerinden kullanıcıya bırakılır.
- Telemetri, reklam ve analiz yoktur. Mevcut başlangıç güncelleme davranışı
  kullanıcıya görünür biçimde açıklanır. Bu davranışı değiştiren tercih,
  installer'a ait değildir; ayrıca onaylı Player Settings işiyle kalıcı
  kullanıcı ayarı olarak uygulanmadan seçim kutusu gösterilmez. İnternet Video
  özelliği ayrı ve isteğe bağlıdır; ana kurulumla otomatik yüklenmez.
- Kurulumdan önce özet ekranı gösterilir. Kurulum sırasında "Dosyalar
  hazırlanıyor", "MLC Player kuruluyor" ve "Windows ile bütünleştiriliyor"
  gibi anlaşılır aşamalar kullanılır; teknik ayrıntılar varsayılan kapalıdır.
- Son ekranda "MLC Player'ı aç" bulunur. GitHub sayfasını açma varsayılan
  kapalıdır. İstenirse Windows Varsayılan Uygulamalar ekranı açılabilir.
- Kullanıcı ayarı, önbelleği veya geçmişi silen bir seçenek kurulum akışına
  eklenmez.

### Görsel yön adayları

- **A — Sinematik Gece:** Koyu yüzeyler, güçlü turuncu odak ve büyük MLC marka
  alanı. En belirgin ürün kimliğidir; kontrast ve klavye odağı özellikle
  doğrulanmalıdır.
- **B — Windows ile Uyumlu:** Açık nötr yüzey, Windows 11'e yakın düzen ve MLC
  turuncusunu yalnız önemli eylemlerde kullanır. En tanıdık ve erişilebilir
  yöndür; marka etkisi A'ya göre daha sakindir.
- **C — Dengeli Hibrit:** Koyu marka şeridi ile açık içerik yüzeyini
  birleştirir. Mevcut Inno Setup yapısına en düşük riskle uyarlanabilecek,
  marka ve kullanım kolaylığı dengeli yöndür.

Konsept bitmap'leri yalnız metin, yerleşim ve marka yönü seçimi içindir;
Inno Setup'ın gerçek piksel çıktısını, DPI davranışını, erişilebilirliği,
registry veya kurulum davranışını kanıtlamaz. Private görsel yolları Git'e
eklenmez.

### Seçilen görsel yön — C Dengeli Hibrit

Kullanıcı 26 Ağustos 2026'da önerilen **C — Dengeli Hibrit** yönünü açıkça
seçti. Installer uygulamasının görsel hedefi koyu MLC marka şeridi, açık içerik
yüzeyi, ölçülü turuncu birincil eylem vurgusu ve Windows'a tanıdık kontrol
düzenidir. A ve B yalnız karşılaştırma referansı olarak korunur; uygulama hedefi
değildir.

Bu seçim yalnız görsel kompozisyon yönünü kesinleştirir. Nihai ekran metinleri,
klavye odak sırası, gerçek Inno piksel çıktısı, yüksek DPI, erişilebilirlik,
build ve fiziksel kurulum ayrıca tasarlanıp doğrulanmadan kabul edilmiş sayılmaz.
Seçim installer veya ürün kodunu değiştirme yetkisi değildir.

#### İptal edilen uygulanabilir C v2 referansı

Kullanıcı iki uygulanabilir C v2 seçeneğinden ikincisini önce seçti; güvenli adı
`C-uygulanabilir-v2.png`, exact digest ve provenance kaydı `EV-20260826-033`
içindedir. Kullanıcı compiled v2 ekran açılmadan önce bu yönü iptal edip önceki
başarıyla derlenen C ekranına dönülmesini istedi (`EV-20260826-039`). V2 ve
`EV-20260826-022` preview'ları yalnız tarihsel karar kanıtıdır; güncel uygulama
hedefi değildir.

Güncel görsel hedef, `EV-20260826-031` artifact'ını üreten önceki C kaynak
davranışıdır: yerel Inno `modern` stili, `wizard-large*` sol marka görselleri,
başlık yüzeyiyle aynı `wizard-small*` görselleri ve native kontrol yerleşimi.
Bu hedef exact eski artifact byte'larının korunduğu anlamına gelmez; yeni build
ayrı artifact kimliği ve ayrı görsel kabul ister.

### C ekran sözleşmesi

Bu sözleşme C yönünün Türkçe ana metnini, etkin durumunu ve klavye akışını
tanımlar. Görsel yön provenance kaydı `EV-20260826-007`'dir. Buradaki
`C.*` message key değerleri uygulama aşamasında `[CustomMessages]` içinde
İngilizce fallback ve desteklenen sekiz dilin tamamıyla karşılanmalıdır;
çeviriler bu belgeye çoğaltılmaz. Bu sözleşme gerçek Inno uygulamasını,
build'i veya fiziksel kurulumu kanıtlamaz.

V2 seçimi ve build kayıtları tarihsel olarak korunur; aktif baseline önceki C
ekranıdır (`EV-20260826-039`). Yeni build ekranda doğrulanmadan önceki görsel
davranışın geri geldiğine ilişkin piksel/yerleşim PASS verilmez.

#### Ortak görsel ve etkileşim kuralları

- Koyu MLC marka şeridi dekoratiftir; açık içerik yüzeyindeki metin ve
  kontroller Windows'un metin ölçeklendirmesiyle kırpılmadan büyümelidir.
- Turuncu yalnız birincil eylem ve görünür klavye odağı için kullanılır;
  renk tek durum göstergesi değildir. Etiket, erişilebilir ad, rol ve durum
  her etkileşimli kontrolde programatik olarak bulunur.
- Native kontrol rolü ve erişilebilirlik, konseptteki exact renkten önce gelir.
  Bu nedenle gerçek ilerleme Inno'nun görünür native progress kontrolüdür;
  turuncu vurgu marka çizgisinde ve etkin aşama etiketinde kalır.
- `Tab` ileri, `Shift+Tab` geri dolaşır; `Space` odaktaki kutuyu değiştirir.
  `Enter` yalnız o ekrandaki geçerli birincil eylemi çalıştırır. `Esc`
  doğrudan çıkmaz, yerel iptal onayını açar. Geri dönüldüğünde yol ve seçimler
  korunur.
- Marka bitmap'i ekran okuyucu sırasına girmez. İlerleme duyuruları yalnız
  gerçek aşama değiştiğinde yapılır; yüzde veya sürekli metin tekrarıyla
  ekran okuyucu spam'i üretilmez.
- Hedef klasör için ikinci bir state oluşturulmaz. Tercihler ekranındaki alan
  Inno'nun `WizardDirValue` değeriyle çift yönlüdür; yükseltmede önceki klasör,
  `UsePreviousTasks=yes` ile önceki görev seçimi korunur.

#### Ekran metni ve kontrol matrisi

`C-WELCOME`

- **Amaç ve message key:** `C.WelcomeTitle` = “MLC Player'a hoş geldiniz”;
  `C.WelcomeInstallBody` = “Bu sihirbaz MLC Player {version} sürümünü
  bilgisayarınıza kurar.”; `C.WelcomeReinstallBody` = “Bu sihirbaz MLC Player
  {version} sürümünü yeniden kurar.”; `C.WelcomeUpgradeBody` = “Bu sihirbaz
  MLC Player'ı {old_version} sürümünden {version} sürümüne günceller.”;
  `C.WelcomeLicenseInfo` = “MLC Player, GPLv3 kapsamında dağıtılan
  açık kaynaklı bir medya oynatıcıdır. Kurmak veya çalıştırmak için lisans
  kabulü gerekmez. Internet Video eklentisi bu pakete dahil değildir.”
- **Kontroller ve Varsayılan:** seçim kutusu yok; sürüm install, reinstall
  veya upgrade kipinden ve exact kurulu/paket sürümünden üretilir. Paket sürümü
  kurulu sürümden eskiyse normal akış açılmaz; aşağıdaki downgrade engeli
  gösterilir.
- **İlk odak:** `İleri`.
- **Tab sırası:** `İleri` → `İptal`.
- **Geçiş:** `İleri` → `C-PREFERENCES`; `Esc`/`İptal` → açık iptal onayı.

`C-PREFERENCES`

- **Amaç ve message key:** `C.PreferencesTitle` = “Kurulum tercihleri”;
  `C.PreferencesBody` = “Kurulum konumunu ve kısayol seçimini gözden geçirin.”
- **Kontroller ve Varsayılan:** `C.InstallLocation` = “Kurulum konumu”; ilk
  kurulumda `{autopf}\MLC Player`, yükseltmede önceki effective hedef;
  `C.Browse` = “Gözat…”; `C.DesktopShortcut` = “Masaüstü kısayolu oluştur”
  ilk kurulumda işaretli, yükseltmede önceki seçim. Konum alanının tek state'i
  Inno `WizardDirValue` değeridir.
- **Sabit bilgi:** `C.OpenWithInfo` = “MLC Player desteklenen dosya türleri
  için ‘Birlikte aç’ listesine eklenir. Varsayılan uygulamanız değişmez.”;
  `C.PrivacyInfo` = “MLC Player açılışta GitHub'daki herkese açık sürüm
  bilgisini sessizce denetler. Telemetri, reklam veya analiz yoktur.”;
  `C.AddonInfo` = “Internet Video eklentisi bu pakete dahil değildir ve ayrı
  kurulur.” Internet Video için kur/indir seçim kutusu gösterilmez.
- **İlk odak:** kurulum konumu alanı.
- **Tab sırası:** konum → `Gözat…` → masaüstü kısayolu → başlangıç güncelleme
  bilgisi odak almaz → `Geri` → `İleri` → `İptal`.
- **Geçiş:** geçerli hedefte `İleri` → `C-SUMMARY`; geçersiz hedefte bu
  ekranda kalınır ve odak konum alanına döner; `Geri` → `C-WELCOME`.
- **Hedef güvenliği:** reinstall/upgrade sırasında effective hedef kayıtlı
  kurulum konumuyla birebir eşleşmelidir; farklı hedef kurulum başlamadan
  durdurulur. İlk kurulumda seçilen klasörde kayıtlı olmayan aynı adlı Player
  EXE'si veya başka kalan içerik varsa üzerine yazılmaz. Effective hedef ve EXE
  sürümü gerçek kopyalama başlamadan hemen önce yeniden ve sayısal olarak
  doğrulanır; başlangıçtan sonra sürüm değişmişse kurulum fail-closed durur.
- **Fail-closed bağımlılık:** başlangıç güncelleme tercihi Player Settings'in
  sahipliğindedir. Kalıcı kullanıcı ayarı ürün kodunda ayrıca onaylanıp açılış
  denetimine bağlanmadan installer seçim kutusu gösterilemez; bugünkü yalnız
  environment-variable davranışıyla dekoratif veya etkisiz tercih kabul edilmez.

`C-SUMMARY`

- **Amaç ve message key:** `C.SummaryTitle` = “Kuruluma hazır”;
  `C.SummaryBody` = “Seçimlerinizi kontrol edin.”
- **Kontroller ve Varsayılan:** salt okunur effective özet şu satırları
  gerçek Inno state'inden üretir: “Konum: {app}”; “Masaüstü kısayolu:
  Oluşturulacak/Oluşturulmayacak”; “Birlikte Aç listesi: Eklenecek
  (varsayılan uygulama değişmez)”; “Başlangıç güncelleme denetimi: GitHub
  release bilgisi, sessiz”; “Internet Video eklentisi: Dahil değil”; “Kullanıcı ayarları,
  geçmiş ve önbellek: Korunacak”. Özet alanının üzerindeki yerleşik
  `ReadyLabel`, “Kuruluma başlamak için `Kur`'u seçin. Ayarları gözden geçirmek
  veya değiştirmek için `Önceki`'yi seçin.” eylemini bir kez gösterir.
  Yerleşik salt-okunur özet alanı sistem pencere rengini kullanır; metin
  mantıksal boşluklarla gruplanır, satır sonunda kaydırılır ve yatay kaydırma
  göstermez. Uzun yerelleştirme veya hedef yolu yalnız dikey taşabilir.
- **İlk odak:** `Kur`.
- **Tab sırası:** `Geri` → `Kur` → `İptal`; ilk girişte `Kur` odaktadır.
- **Geçiş:** `Kur` → `C-PROGRESS`; `Geri` → `C-PREFERENCES` ve değişiklikten
  sonra özet yeniden üretilir.

`C-PROGRESS`

- **Amaç ve message key:** `C.ProgressTitle` = “MLC Player kuruluyor”;
  `C.ProgressBody` = “Lütfen bekleyin.”
- **Kontroller ve Varsayılan:** yerleşik progress bar; `Geri` ve `İleri`
  kapalıdır. Aşama metinleri yalnız karşılık gelen gerçek Inno olayıyla
  “Dosyalar hazırlanıyor” → “MLC Player kuruluyor” → “Windows ile
  bütünleştiriliyor” olarak değişir; sahte yüzde gösterilmez ve teknik
  ayrıntılar varsayılan kapalıdır. Welcome/Finish marka diline bağlanan ince
  turuncu alt çizgi yalnız `wpInstalling` yüzeyinde dekoratiftir; mevcut gerçek
  aşama metni aynı renkte ve kalın gösterilir. High Contrast etkinse bu iki
  dekorasyon uygulanmaz; progress, durum, dosya yolu ve iptal kontrolü değişmez.
- **İlk odak:** `İptal`; odak görünürdür ancak doğrudan iptal etmez.
- **Tab sırası:** `İptal` tek etkileşimli kontroldür; aşama bilgisi Tab durağı
  değil, erişilebilir durum duyurusu olarak okunur.
- **Geçiş:** tam ve başarılı dosya/registry/kısayol işlemi → `C-FINISH`;
  `Esc`/`İptal` → açık iptal onayı; hata → başarı sayfasına geçmeden güvenli
  sonuç mesajı.

`C-FINISH`

- **Amaç ve message key:** `C.FinishTitle` = “Kurulum tamamlandı”;
  `C.FinishBody` = “MLC Player kullanıma hazır.”; açıklama = “MLC Player
  bilgisayarınıza kuruldu. Varsayılan uygulama seçimini Windows Ayarları'ndan
  değiştirebilirsiniz.”
- **Kontroller ve Varsayılan:** “MLC Player'ı aç” işaretli; “Windows
  Varsayılan Uygulamalar ayarını aç” işaretsiz; “MLC Player GitHub sayfasını
  aç” işaretsiz. Internet Video otomatik indirilmez veya başlatılmaz. Sessiz
  kurulumda hiçbir post-install eylemi çalışmaz.
- **Gerçek eylem bağı:** “MLC Player'ı aç” yalnız başarılı kurulumdan sonra
  exact `{app}\{#MyAppExeName}` installed executable dosyasını çalıştırır. “Windows
  Varsayılan Uygulamalar ayarını aç” yalnız `ms-settings:defaultapps`
  sayfasını açar; MLC'nin varsayılan yapıldığı veya varsayılan yapıldı denmez.
  “MLC Player GitHub sayfasını aç” exact `{#MyAppUrl}` kaynağını kullanıcı
  açıkça seçtiğinde açar. Zorunlu kurulum başarıyla bittikten sonra seçili
  opsiyonlar sırayla denenir: Player → Windows Ayarları → GitHub. Her sonuç
  ayrı kaydedilir/gösterilir. Eylem çalıştırılamazsa hata sessizce yutulmaz;
  optional eylem hatası kurulumu başarısız saymaz ve sonraki seçili eylemi
  düşürmez.
- **İlk odak:** `Bitir`.
- **Tab sırası:** yerleşik `RunList` tek Tab durağıdır; listede `Yukarı/Aşağı`
  ile seçenekler arasında gezinilir ve `Space` ile seçim değiştirilir. Sonraki
  Tab durağı `Bitir`dir; ilk girişte `Bitir` odaktadır.
- **Geçiş:** `Bitir` zorunlu kurulum başarıyla tamamlandıysa yalnız kullanıcının
  işaretlediği optional eylemleri yukarıdaki sırayla dener ve ardından kurulumu
  kapatır.

#### Negatif durum ve kullanıcı metni

| Durum | Canonical kullanıcı sonucu |
|---|---|
| Yönetici yetkisi reddedildi | Bu sonuç Windows UAC tarafından yönetilir; MLC sihirbazı kendi canonical mesajını garanti etmez. UAC iptalinde MLC kurulum değişikliği yapılmaz. |
| Restart Manager kapanışı tamamlamadı | “MLC Player kapatılamadı. Çalışan uygulamayı kapatıp yeniden deneyin.” |
| Welcome, preferences veya summary iptali | “Kurulumdan vazgeçildi. Bilgisayarınızda değişiklik yapılmadı.” |
| Progress iptali veya orta-kopya hata | “Kurulum geri alındı. Önceki çalışan sürüm korunmuştur.” yalnız rollback readback'i bunu doğrularsa gösterilir; aksi hâlde onarım yolu verilir. |
| Hedef doğrulama/yazma hatası | “Hedef klasöre yazılamadı. Başka bir klasör seçin veya izinleri kontrol edin.” |
| Upgrade state'i geri okundu | “Önceki hedef ve tercihler korundu.” yalnız effective state gerçekten eşitse gösterilir. |
| Open With kaydı | “Varsayılan uygulama değiştirilmedi. İsterseniz seçimi Windows Ayarları'ndan yapabilirsiniz.” |
| Başarı sonrası OS gereksinimi | “Yeniden başlatma gerekiyor. Değişiklikleri tamamlamak için Windows'u yeniden başlatın.” yalnız gerçek restart requirement varsa gösterilir. |
| Daha yeni sürüm kurulu | `C.DowngradeBlocked` = “Bu bilgisayarda daha yeni bir MLC Player sürümü yüklü. Daha eski sürüm otomatik kurulamaz.” İlk ve tek odak `Kapat`; geçiş kurulum değişikliği yapmadan çıkıştır. |

Bu metinler teknik mekanizmanın yerine geçmez. İptal, rollback, sahip olunan
dosyalar, çalışan süreç ve kullanıcı verisi invariantları aynı belgedeki
“Kapanış, güncelleme ve kaldırma sözleşmesi”, “Kurulum kabul matrisi” ve
“Inno Setup için uygulanacaklar” bölümlerinden uygulanır. Success completion
yalnız bütün zorunlu adımlar başarılıysa gösterilir; downgrade sessizce
ilerlemez ve ayrı açık karar olmadan desteklenmiş sayılmaz.

#### Uygulama ve kabul kapıları

- Built-in `wpWelcome`, `wpSelectDir`, `wpReady`, `wpInstalling` ve
  `wpFinished` sayfaları yeniden kullanılır. `wpSelectDir` tek hedef state'ini
  koruyarak preferences görünümüne genişletilir; baştan paralel bir custom
  wizard/state modeli kurulmaz.
- Ürün ayarına bağlanmayan güncelleme kutusu, task/condition'a bağlanmayan
  association kutusu ve ana installer içinde Internet Video kurulum kutusu
  uygulanamaz.
- Tasarım kabulü; exact Inno 7.1.0 compile, sekiz dil, 100–250% DPI, 200% text
  scaling, 1366×768/4K, farklı DPI monitör geçişi, Narrator/NVDA ve yalnız
  klavye kabulünün yerine geçmez.
- İlk kurulum, reinstall, upgrade, downgrade reddi, özel hedefin korunması,
  her aşamada iptal, enjekte hata/rollback, Open With/Default Apps readback,
  main/add-on kaldırma sırası ve kalan dosya/registry/süreç ayrıca exact
  artifact üzerinde fiziksel kabul ister.
- Her görünür checkbox veya düğme için gerçek handler, seçili/seçili-değil
  yolları, hata sonucu ve action/readback fiziksel kabulde ölçülür. Handler'a
  bağlanmayan kontrol gösterilmez; etiket, Windows'un izin verdiğinden daha
  geniş bir sonuç vaat etmez.
- Finish action/readback ölçütleri: Player için resolved path exact
  `{app}\{#MyAppExeName}` ve process-start sonucu; Default Apps için yalnız
  `ms-settings:defaultapps` shell-launch sonucu ve görünür Settings sayfası,
  varsayılan değişikliği değil; GitHub için resolved exact `{#MyAppUrl}`
  shell-launch sonucu. Seçili olmayan her yolun hiç çalışmadığı da ölçülür.
- Önceki unsigned setup güncel v2 baseline'ı devralmaz. Kaynak uyarlamasından
  sonra ayrı onaylı yeniden build gerekir; compiled beş ekran, High Contrast
  fallback ve DPI/text davranışı kullanıcı görsel kabulü olmadan PASS yazılmaz.

### Görsel seçimden sonra uygulama sırası

1. Seçilen yönün ekran metinleri ve odak sırası kesinleştirilir.
2. Ayrı `codex/installer-experience` dalında regresyon önce kırmızı kanıtlanır.
3. Yalnız installer/test kodu değiştirilir; ürün oynatma koduna dokunulmaz.
4. Dil, klavye, yüksek DPI, gizlilik metni, kayıt defteri, güncelleme ve
   kaldırma sözleşmeleri dar testlerle doğrulanır.
5. Build için ayrıca açık onay alınır.
6. Gerçek Windows kurulum/güncelleme/kaldırma deneyi için ayrıca açık onay
   alınır.

## Kesin karar

MLC Player, PyInstaller **onedir** biçiminde paketlenecek. Python, PyQt6 ve
diğer çalışma zamanı bileşenleri uygulamanın yanındaki `_internal` klasöründe
kalacak. `onefile` kullanılmayacak.

Hedef kurulum yapısı:

```text
C:\Program Files\MLC Player\
|-- MLC Player.exe
|-- _internal\
|   |-- python314.dll
|   |-- python3.dll
|   |-- PyQt6\
|   |-- *.pyd
|   |-- base_library.zip
|   `-- bin\
|       `-- mpv-2.dll
|-- unins000.exe
`-- unins000.dat
```

`_internal` klasörü, Python DLL'leri ve `.pyd` dosyaları normal ve zorunlu
çalışma zamanı bileşenleridir. Bunlar silinmeyecek, yeniden adlandırılmayacak
ve gizli dosya niteliğiyle saklanmaya çalışılmayacaktır.

## Bu kararın nedeni

Mevcut `packaging/MLCPlayer.spec`, `COLLECT` aşaması içermediği için onefile paket
üretmektedir. Onefile biçimi Python, Qt ve yaklaşık 100 MB büyüklüğündeki
`mpv-2.dll` dosyasını her açılışta `%TEMP%\_MEI...` altına çıkartır. Daha
önce başka uygulamalarda geçici dizin temizliği, antivirüs veya kilitli DLL
nedeniyle `Failed to load Python DLL` ve silme/güncelleme sorunları yaşandı.

Onedir biçiminde çalışma zamanı dosyaları kalıcı olarak `_internal` altında
durur; her açılışta yeniden çıkartma yapılmaz. Başlangıç ve hata teşhisi daha
öngörülebilir olur.

## Doğrulanmış yerel referans

Aşağıdaki proje ve kurulu uygulama yalnız mimari referans olarak kullanıldı:

```text
Kaynak:
<yerel geliştirme dizini>\Offer Management System   (bu depoda YOK, özel proje)

Kurulu örnek:
C:\Program Files\Teklif Yönetim
```

İlgili referans dosyaları:

```text
packaging\TeklifYonetim.spec
packaging\TeklifYonetim.iss
packaging\Kurulum-Yap.bat
```

Teklif Yönetim'de çalışan temel düzen:

1. `EXE(..., exclude_binaries=True)` ile ana EXE oluşturulur.
2. `COLLECT(...)` ile EXE, Python, Qt, veri ve DLL bileşenleri toplanır.
3. PyInstaller destek dosyalarını `_internal` altında tutar.
4. Inno Setup, `dist\TeklifYonetim\*` içeriğini alt klasörlerle birlikte
   kurulum dizinine kopyalar.

Bu yapı MLC Player'a uyarlanacak; dosyalar körlemesine kopyalanmayacaktır.

## PyInstaller spec için uygulanacaklar

- `onedir` üretilecek.
- `EXE` aşamasında `exclude_binaries=True` kullanılacak.
- Sonuna `COLLECT` aşaması eklenecek.
- Ana çıktı klasörü `output\dist\MLC Player\` olacak (3 Ekim 2026'dan beri bütün üretim çıktıları `output\` altındadır).
- PyQt6 ve gerekli Python çalışma zamanı `_internal` altında kalacak.
- `mpv-2.dll`, `_internal\bin\mpv-2.dll` konumunda paketlenecek.
- Mevcut `app/main.py::get_bin_dir()` davranışı gerçek paket üzerinde
  doğrulanacak. Onedir çalışırken `sys._MEIPASS` üzerinden `_internal\bin`
  bulunmalıdır.
- `libmpv.dll.a` çalışma zamanı dosyası değildir. Kuruluma eklenmeyecek;
  yalnız `mpv-2.dll` ile temiz Windows kabulü yapılacak.
- `pytest`, test dosyaları, kaynak `.py` dosyaları, geliştirme klasörleri,
  loglar ve yerel ayarlar kuruluma alınmayacak.
- Uygulama ikonu ve Windows sürüm bilgileri spec'e açıkça bağlanacak.
- UPX kararı gerçek antivirüs ve başlatma kabulünden sonra verilecek; sırf
  dosya küçültmek için otomatik olarak etkinleştirilmeyecek.

Örnek mimari yalnız yön gösterir:

```python
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MLC Player",
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="MLC Player",
)
```

Gerçek spec yazılırken mevcut PyInstaller sürümünün sözleşmesi ve üretilen
dosya ağacı yeniden kontrol edilmelidir.

## Inno Setup için uygulanacaklar

Inno Setup, PyInstaller onedir çıktısının tamamını alt klasörleriyle birlikte
kurmalıdır:

```ini
[Files]
Source: "..\dist\MLC Player\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs
```

Planlanan temel ayarlar:

```ini
[Setup]
DefaultDirName={autopf}\MLC Player
CloseApplications=yes
CloseApplicationsFilter="MLC Player.exe,*.dll"
RestartApplications=no
```

Ana EXE yanında kurulumun güncellediği kilitli DLL kaynakları da Restart
Manager kapsamındadır; bu filtre yalnız ilgili dosya kaynaklarını hedefler ve
ad-temelli zorla süreç sonlandırma yetkisi vermez.

Ayrıca:

- MLC Player'a özel, sabit bir `AppId` üretilecek ve sonraki sürümlerde
  değiştirilmeyecek.
- Aynı anda iki kurulum çalışmasını engelleyen sabit bir `SetupMutex`
  kullanılacak.
- `AppVersion`, EXE sürüm bilgisi, setup dosya adı ve ilerideki Git etiketi
  tek sürüm kaynağıyla eşleştirilecek.
- Masaüstü kısayolu kullanıcı tarafından kapatılabilir görev olacak.
- Başlat menüsü ve kaldırma girdileri doğrulanacak.
- Kurulum sonunda uygulamayı başlatma seçeneği kullanıcı tercihine bağlı
  olacak ve sessiz kurulumda çalışmayacak.
- Programın kullanıcı logları ve ayarları Program Files içinde tutulmayacak.

## Körlemesine alınmayacak parçalar

Teklif Yönetim'in Inno betiğindeki aşağıdaki zorla kapatma yaklaşımı MLC
Player'a doğrudan taşınmayacak:

```pascal
taskkill /F /IM TeklifYonetim.exe
```

Önce Inno Setup/Windows Restart Manager ile nazik kapanış kullanılmalıdır.
MLC Player'ın libmpv, Qt yüzeyleri ve çalışan thread'leri kendi ürün kapanış
yoluyla tamamen sonlandırılmalıdır. Zorla kapatma ancak ayrı risk analizi ve
testten sonra, gerçekten gerekirse son çare olarak değerlendirilebilir.

Ayrıca başka bir Inno sürümündeki geçici hatayı atlatmak için yazılmış
`InitializeUninstall()` gibi kodlar gerekçesi doğrulanmadan taşınmayacaktır.
Kurulum derlenirken kararlı Inno Setup sürümü seçilecek; preview/RC derleyici
kullanılmayacaktır.

## Kapanış, güncelleme ve kaldırma sözleşmesi

- Kurulum/güncelleme başlamadan çalışan MLC Player tespit edilmelidir.
- Önce uygulamaya normal kapanış fırsatı verilmelidir.
- `MLC Player.exe`, libmpv thread'leri ve yardımcı süreçler tamamen
  sonlanmadan `_internal` dosyaları değiştirilmemelidir.
- Güncelleme sırasında eski `_internal` ile yeni `_internal` karışmamalıdır.
- Başarısız güncellemede yarım kurulmuş klasör bırakılmamalıdır.
- Kanıtlanmış yabancı 47 runtime dosyası ile current dist'te bulunmayan ölçülmüş
  iki eski OpenSSL `*-3-x64.dll` kalıntısının maintenance başlangıcında toplam
  49 exact direct-root adla silinmesi tek yönlü güvenlik
  sanitasyonudur. Sonraki kopyalama durursa bu dosyaların geri getirileceği
  veya eski kurulumun hâlâ çalışan sürüm olduğu iddia edilmez; gerçek rollback
  sonucu enjekte abort senaryosunda dosya ağacı ve açılışla geri okunur. Bu,
  OpenSSL ad ailesini genel olarak zararlı saymaz; current dist'in meşru
  `libcrypto-3.dll` ve `libssl-3.dll` dosyaları silme kapsamı dışındadır.
- Kaldırma sırasında uygulama çalışıyorsa kullanıcıya anlaşılır bildirim
  verilmeli veya kontrollü kapanış uygulanmalıdır.
- Kaldırıcı yalnız kurulumun sahip olduğu dosyaları silmelidir.
- Kullanıcı kararı (8 Eylül 2026): ana kaldırıcı eklenti kuruluysa onu da
  kaldırma seçeneğini varsayılan işaretli gösterir. Ayarlar/geçmiş/kayıtlı
  altyazı kimlikleri ile günlük/küçük resim önbelleği/geçici güncelleme
  dosyaları iki ayrı ve varsayılan boş seçimdir; sessiz kaldırmada da
  kullanıcı verisi korunur.
- Kurulum makineye özgü rastgele bir kimliği HKLM'de saklar. Kurulu Player ilk
  normal açılışta görünmez, tetikleyicisiz ve yalnız isteğe bağlı çalışan düşük
  yetkili görevi kendi SID'sine bağlar ve aynı kimliği kendi HKCU alanına
  kaydeder. Kaldırıcı HKU içinde bu kimlikle tam bir SID eşleşmesi ister; sıfır
  veya birden fazla eşleşmede kullanıcı verisini silmiş saymaz. IPC yalnız bu
  kullanıcının `%LOCALAPPDATA%\Programs\MLC Player\UninstallCleanup\v1\ipc` dizinindedir;
  helper, görev, IPC ve kayıt normal/sessiz her kaldırmada temizlenir.
- Temizlik yalnız kayıtlı Windows hesabının exact ürün alanlarıyla sınırlıdır:
  `HKCU\Software\MLCPlayer`, ürünün tüm ad-alanı eşleşen
  OpenSubtitles Credential Manager hedefleri, `%APPDATA%\MLCPlayer` altındaki
  exact ayar/log girdileri, `%LOCALAPPDATA%\MLCPlayer\cache\thumbnails`
  altındaki 64-hex `.jpg` dosyaları ve `%LOCALAPPDATA%\MLCPlayerUpdate_*`
  altındaki markalı kurucu/imza dosyaları. `%LOCALAPPDATA%\python` gibi
  paylaşılan eski yollar, kullanıcı medya/altyazı/screenshot dosyaları ve
  beklenmeyen girdiler silinmez; seçilmiş tam temizlikte böyle bir girdi
  kalırsa sonuç kullanıcıya açık başarısızlık olarak bildirilir.
- Eklenti kaldırma yolu exact HKLM kaydı, `{app}` sınırı ve `unins*.exe`
  kimliğiyle doğrulanır; eklenti kaldırma başarısızsa ana ürün dosyaları
  silinmeden işlem durur. Kullanıcı verisi yalnız ana kaldırma
  `usPostUninstall` aşamasına ulaştıktan sonra değişir; iptal, çalışan ürün
  mutex'i veya erken kaldırma hatası kullanıcı verisine dokunmaz.

## Paketleme öncesi zorunlu doğrulama

1. Tam pytest paketi yeşil olmalı.
2. `compileall` ve `git diff --check` temiz olmalı.
3. Temiz `build`, `dist` ve installer çıktı dizinleriyle yeniden derlenmeli.
4. `output\dist\MLC Player\MLC Player.exe` oluşmalı.
5. `_internal\python314.dll`, PyQt6 ve gerekli `.pyd` dosyaları bulunmalı.
6. `_internal\bin\mpv-2.dll` bulunmalı ve beklenen SHA-256 ile eşleşmeli.
7. Kaynak `.py`, test, cache, yerel log veya kullanıcı ayarı bulunmamalı.
8. Paketli EXE kurulum yapılmadan `dist` içinden çalıştırılmalı.
9. Gerçek video, ses, SRT ve ASS altyazı kabulü yapılmalı.
10. Uygulama kapatıldığında libmpv/Qt/QThread süreç sızıntısı olmamalı.

## Kurulum kabul matrisi

Temiz veya izole bir Windows ortamında en az şu senaryolar ölçülmelidir:

- İlk kurulum
- Kurulu sürümün üstüne aynı sürüm kurulumu
- Eski sürümden yeni sürüme güncelleme
- Uygulama açıkken güncelleme
- Normal kapatıp güncelleme
- Kurulumdan hemen sonra çalıştırma
- Windows yeniden başlatıldıktan sonra çalıştırma
- Program Files yolunda Türkçe karakter/boşluk etkileri
- Masaüstü ve Başlat menüsü kısayolları
- Normal kaldırma
- Uygulama açıkken kaldırma
- Kaldırma sonrasında Program Files artık taraması
- Kullanıcı log/ayar saklama politikasının doğrulanması
- Exact 49 residual sanitasyonundan sonra enjekte abort: yarım payload, kalan
  sakıncalı DLL, açılabilir sürüm ve kullanıcıya gösterilen onarım yolu readback'i

Her senaryoda süreçler, çıkış kodları, kurulum logu, kalan dosyalar ve gerçek
uygulama davranışı kaydedilmelidir. Yalnız EXE'nin açılması yeterli kabul
değildir.

## Paketleme tamamlandığında raporlanacaklar

- Kullanılan Python, PyInstaller ve Inno Setup sürümleri
- Nihai kurulum dosyasının adı, byte boyutu ve SHA-256 değeri
- Kurulan dosya ağacı ve beklenmeyen dosya taraması
- EXE ve `mpv-2.dll` SHA-256 değerleri
- Test ve gerçek Windows kabul sonuçları
- Güncelleme/kaldırma sırasında çalışan süreç davranışı
- Bilinen sınırlamalar

Commit, push, tag, release veya yayınlama işlemleri için ayrıca açık
kullanıcı onayı gerekir. Onay verildiğinde izlenecek sıra aşağıdadır ve
**değişmezdir**.

## Yayın yetkilendirmesi ve süreç

Bu plan **paketlemeyi** anlatır: neyin nasıl derlendiği, hangi ikililerin
girdiği, lisans ve boyut ölçümleri.

**Yayın süreci bu belgenin konusu DEĞİLDİR.** Kesin sıra, her adımın
giriş/çıkış şartı, dinamik varlık sözleşmesi ve hata hâlinde nerede
durulacağı tek resmî kaynaktadır:

> **`docs/release/RELEASE_PROCESS.md`**

Buradan çıkmayan iki kural, paketleme turlarında da geçerlidir:

- **Tag ve push build'den ÖNCE yapılmaz.**
- **Build, commit, push, tag ve release AYRI AYRI kullanıcı onayı
  ister.** Biri için verilen onay diğerine geçmez. `--target master`
  KULLANILMAZ; `--verify-tag --draft` zorunludur.

## Otomatik güncelleme — karar paketleme aşamasına bırakıldı

Otomatik güncelleme bu aşamada uygulanmayacak. EXE/setup ve yayınlama
aşamasına gelindiğinde aşağıdaki seçenekler yeniden değerlendirilip kullanıcı
kararıyla biri seçilecek.

### Seçenek A — Program Files kurulumu

```text
C:\Program Files\MLC Player
```

- Standart sistem-geneli kurulumdur.
- Güncelleme Program Files'a yazacağı için Windows UAC/yönetici onayı gerekir.
- Uygulama güncellemeyi denetleyebilir, indirebilir ve doğrulayabilir; ancak
  Windows'un UAC onayını güvenli biçimde atlayamaz.
- Önerilen varsayılan seçenek budur.

### Seçenek B — kullanıcı-başına kurulum

```text
%LOCALAPPDATA%\Programs\MLC Player
```

- Yalnız mevcut kullanıcıya kurulur.
- Normal koşullarda UAC istemeden güncellenebilir.
- Sistem-geneli Program Files düzeninden vazgeçilmiş olur.

### Güncelleyicinin değişmez güvenlik sözleşmesi

Hangi seçenek seçilirse seçilsin güncelleyici:

1. Yalnız kararlı ve mevcut sürümden gerçekten yeni sürümü kabul etmeli.
2. Setup dosyasını Program Files yerine kullanıcıya ait geçici/staging
   dizinine indirmeli.
3. Dosya adı, byte boyutu ve SHA-256 değerini doğrulamalı.
4. SHA-256'ya ek olarak dijital imza veya uygulamaya gömülü güvenilir açık
   anahtarla imzalanmış manifest doğrulaması yapmalı.
5. Doğrulama başarısızsa indirilen dosyayı silmeli ve mevcut kuruluma hiç
   dokunmamalı.
6. Çalışan MLC Player'ı önce Windows Restart Manager/Inno Setup
   `CloseApplications` ile nazikçe kapatmalı.
7. EXE, libmpv ve yardımcı thread/süreçlerin gerçekten sonlandığını
   doğrulamadan `_internal` dosyalarını değiştirmemeli.
8. Normal kapanış başarısızsa güncellemeyi güvenle durdurmalı. `taskkill /F`
   yalnız açık kullanıcı onaylı son çare olarak değerlendirilmeli.
9. Aynı anda iki kurulumu sabit `SetupMutex` ile engellemeli.
10. Kurulumun çıkış kodunu kontrol etmeli; yalnız `0` başarı sayılmalı.
11. Başarıdan sonra MLC Player'ı yükseltilmiş yönetici olarak değil, normal
    kullanıcı yetkisiyle yeniden açmalı.
12. Ağ, yetki, imza, disk veya kapanış sorunu varsa mevcut çalışan sürümü
    bozmadan durmalı.

Güvenilirlik hedefi "her koşulda mutlaka günceller" değildir. Sözleşme:

> Güncelleme güvenle tamamlanabiliyorsa doğrulanmış biçimde tamamlanır;
> tamamlanamıyorsa mevcut sürüme zarar verilmeden durulur.

### Otomatik güncelleme için ayrıca gerekli gerçek kanıtlar

- İki ayrı, sürüm numarası ve imzası doğrulanmış test kurulumu hazırlanmalı.
- Eski sürüm açık ve gerçek video oynatırken yeni sürüme güncellenmeli.
- SRT ve ASS altyazı açıkken kapanış/güncelleme denenmeli.
- UAC kabul ve UAC ret yolları ayrı ölçülmeli.
- Ağ kesintisi, bozuk indirme, yanlış hash ve geçersiz imza reddedilmeli.
- Eski sürüme düşürme girişimi reddedilmeli.
- Uygulama kapanmadığında kurulum dizisinin byte düzeyinde değişmediği
  kanıtlanmalı.
- Disk alanı yetersizliği ve yarıda kesilen kurulum için kurtarma davranışı
  ölçülmeli.
- Kullanıcı ayarları, loglar ve son kullanılanlar korunmalı.
- Güncelleme sonrası eski/yeni `_internal` dosyalarının karışmadığı
  doğrulanmalı.
- Aynı anda iki güncelleme girişimi engellenmeli.
- En az 20 ardışık eski → yeni güncelleme döngüsü çalıştırılmalı.
- Her döngüde kurulum çıkış kodu, süreç sızıntısı, dosya ağacı ve gerçek
  uygulama açılışı doğrulanmalı.

Bu kabul matrisi geçmeden "otomatik güncelleme güvenilir" veya "sorunsuz"
olarak raporlanmayacaktır.

### Araştırma için resmî başvuru kaynakları

- Microsoft Restart Manager:
  https://learn.microsoft.com/en-us/windows/win32/rstmgr/about-restart-manager
- Microsoft WinVerifyTrust:
  https://learn.microsoft.com/en-us/windows/win32/api/wintrust/
- Microsoft UAC mimarisi:
  https://learn.microsoft.com/en-us/windows/security/application-security/application-control/user-account-control/architecture
- Inno Setup `CloseApplications`:
  https://jrsoftware.org/ishelp/topic_setup_closeapplications.htm
- Inno Setup `SetupMutex`:
  https://jrsoftware.org/ishelp/topic_setup_setupmutex.htm
- Inno Setup `AppId` ve aynı uygulama sözleşmesi:
  https://jrsoftware.org/ishelp/topic_sameappnotes.htm
- Inno Setup çıkış kodları:
  https://jrsoftware.org/ishelp/topic_setupexitcodes.htm
- GitHub Releases API ve varlık SHA-256 bilgisi:
  https://docs.github.com/en/rest/releases/releases

## Internet videosu calisma zamani (sabit surumler)

MLC Player, site cikarimi icin resmi ikilileri KENDI kurulumunda tasir.
Kullanicinin bilgisayari Python/yt-dlp/Deno/Node icin TARANMAZ, sistem
PATH'indeki bir kopya fallback olarak KULLANILMAZ ve calisma sirasinda
bilesen INDIRILMEZ.

| Bilesen | Surum | Kaynak |
|---|---|---|
| `yt-dlp.exe` | `2026.08.19` | resmi GitHub release (degismez tag) |
| `deno.exe` | `v2.9.5` | resmi GitHub release ZIP (degismez tag) |

Kesin URL, byte boyutu ve SHA-256 degerleri `bin/RUNTIME_MANIFEST.txt`
icindedir. `latest` adresi KALICI build girdisi DEGILDIR.

### Guncelleme politikasi

- Runtime ikilileri OTOMATIK guncellenmez.
- Guncelleme YALNIZ yeni bir MLC Player setup/guncellemesiyle gelir.
- Uygulama icinde `yt-dlp -U`, `deno upgrade` veya baska self-update
  CALISTIRILMAZ.
- Yeni surume gecerken manifest (surum + URL + boyut + SHA-256) ayni turda
  guncellenir ve hash resmi release checksum dosyasindan yeniden dogrulanir.

### Paketleme hedefi

    _internal\bin\mpv-2.dll
    _internal\bin\yt-dlp.exe
    _internal\bin\deno.exe
    _internal\licenses\yt-dlp-LICENSE.txt
    _internal\licenses\yt-dlp-THIRD_PARTY_LICENSES.txt
    _internal\licenses\deno-LICENSE.txt

`deno.exe` bilerek `yt-dlp.exe` ile AYNI dizindedir; alt surecler yalnizca
uygulama surecinin PATH'ini miras alir. Sistem Deno'suna fallback YOKTUR ve
`--remote-components` ACILMAZ (resmi standalone `yt-dlp.exe` EJS betiklerini
zaten icerir).

### Lisans / provenance

- `yt-dlp` projesinin KENDI kaynak lisansi **Unlicense**; resmi metin
  `licenses/yt-dlp-LICENSE.txt` icindedir.
- ANCAK resmi PyInstaller `yt-dlp.exe` ucuncu taraf **GPLv3+** kod icerir ve
  yt-dlp'nin resmi README'sine gore BIRLESIK executable **GPLv3+** kapsamina
  girer. Bu ayrim kritiktir: kaynak lisansi ile dagitilan ikilinin lisansi
  ayni sey DEGILDIR.
- Ucuncu taraf lisans metinlerinin RESMI derlemesi pakete DAHILDIR:
  `licenses/yt-dlp-THIRD_PARTY_LICENSES.txt` (sabitlenmis commit'ten, 243550
  bayt, degistirilmeden). Iki dosya FARKLI seyi belgeler; ikisi de paketlenir.
- `deno` **MIT** lisanslidir; resmi metin `licenses/deno-LICENSE.txt`.
- Lisans metinleri OZETLENMEZ; resmi halleriyle tasinir.
- ACIK MADDE (release oncesi): GPLv3+ kapsamindaki birlesik executable icin
  karsilik gelen KAYNAK ERISIMI yukumlulugu release/setup turunda ayrica
  hazirlanmalidir.
- Bu bolum hukuki danismanlik DEGILDIR; MLC Player'in butununun lisans durumu
  hakkinda bu turda kesin hukum verilmemistir.

## Açık uyumluluk maddeleri

Aşağıdakiler 3 Ekim 2026'da kaynakla yeniden denetlendi. Kapanmış maddeler
(nonfree olmayan `mpv-2.dll`, karşılık gelen kaynak manifesti `ready`,
kurulumdaki `LICENSE`/`licenses/`, SPDX dosya başlıkları) ve eski kontrol
listesinin kendisi `docs/history/PACKAGING_HISTORY.md` içindedir.

- [ ] İndirilen altyazıların yeniden dağıtımı ve saklanmasıyla ilgili
      OpenSubtitles şartları doğrulanmalı. Çevrimiçi altyazı arayüzü
      (`SUBTITLE_SEARCH_UI_ENABLED=False`) bu doğrulama ve yazılı sağlayıcı
      onayı olmadan açılmaz.
- [ ] Kod imzalama: kurulum dosyası Authenticode imzası taşımaz. SignPath
      Foundation başvurusu onaylanmadı; durum `docs/release/SIGNPATH.md`,
      politika `docs/policies/CODE_SIGNING_POLICY.md` içindedir. İmza lisans
      ve telif yükümlülüklerinin yerine geçmez.
- [ ] Avukata yöneltilecek açık sorular: GPLv3+ `yt-dlp.exe` için karşılık
      gelen kaynak yükümlülüğünün kaynak arşiv URL'siyle karşılanıp
      karşılanmadığı; H.264/H.265 decode içeren ücretsiz dağıtımda patent
      havuzu yükümlülüğü; açık kaynak masaüstü istemcide uygulama başına tek
      API anahtarının dağıtımı. Soruların tam metni tarihsel kayıttadır.

## Uygulama ikonu

Onaylı görsel kimlik yuvarlak turuncu MLC ikonudur; standart ve şeffaf
PNG/ICO kaynakları `assets/` altındadır, ölçü ve SHA-256 değerleri
`assets/ICON_MANIFEST.txt` içindedir. Inno kurulumu
`SetupIconFile=..\assets\mlc-player-icon.ico` ve
`UninstallDisplayIcon={app}\{#MyAppExeName}` kullanır
(`packaging/MLCPlayer.iss`); kısayollar ana EXE ikonunu taşır. Gerçek görünüm
Inno kabulünde ayrıca doğrulanır.
