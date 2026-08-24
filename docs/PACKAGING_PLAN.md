# MLC Player Paketleme ve Kurulum Planı

> **TARİHSEL KARAR KAYDI:** Bu belge paketleme tasarımının gerekçelerini ve
> eski ölçüm/checklist snapshot'larını korur; güncel durum veya sıradaki iş
> kaynağı değildir. Güncel devir için `docs/CONTINUITY.md`, kesin yayın sırası
> için yalnız `docs/RELEASE_PROCESS.md` kullanılır. Aşağıdaki eski sürüm,
> boyut ve işaretsiz kutular canlı kaynakla yeniden doğrulanmadan güncel engel
> sayılmaz.

Bu dosya, Windows kurulum paketinin tarihsel tasarım kararlarını açıklar.
Paketleme aşamasında gerekçeler buradan okunabilir; yürütme sırası
`docs/RELEASE_PROCESS.md` üzerinden alınır ve o günkü kaynak, araç sürümleri
ile Windows kabul sonuçları yeniden doğrulanır.

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

Mevcut `MLCPlayer.spec`, `COLLECT` aşaması içermediği için onefile paket
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
- Ana çıktı klasörü `dist\MLC Player\` olacak.
- PyQt6 ve gerekli Python çalışma zamanı `_internal` altında kalacak.
- `mpv-2.dll`, `_internal\bin\mpv-2.dll` konumunda paketlenecek.
- Mevcut `main.py::get_bin_dir()` davranışı gerçek paket üzerinde
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
CloseApplicationsFilter=MLC Player.exe
RestartApplications=no
```

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
- Kaldırma sırasında uygulama çalışıyorsa kullanıcıya anlaşılır bildirim
  verilmeli veya kontrollü kapanış uygulanmalıdır.
- Kaldırıcı yalnız kurulumun sahip olduğu dosyaları silmelidir.
- Kullanıcı ayarları ve loglarının korunması/silinmesi için ayrıca açık ürün
  kararı alınmalıdır; kurulum klasörünü geniş jokerlerle temizlemek bu kararın
  yerine geçmez.

## Paketleme öncesi zorunlu doğrulama

1. Tam pytest paketi yeşil olmalı.
2. `compileall` ve `git diff --check` temiz olmalı.
3. Temiz `build`, `dist` ve installer çıktı dizinleriyle yeniden derlenmeli.
4. `dist\MLC Player\MLC Player.exe` oluşmalı.
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

> **`docs/RELEASE_PROCESS.md`**

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

## YAYIN ENGELI: mpv-2.dll DAGITILAMAZ -> COZULDU (16 Agustos 2026)

**DURUM: kapatildi.** Asagidaki teshis kayit olarak korunuyor; en altta
degisim ve dogrulama sonuclari var.

**Tahmin degil, ikilinin KENDI icinden okundu.**

`bin/mpv-2.dll` (99.390.990 bayt, 25 Kasim 2024) icine gomulu FFmpeg
`configure` dizesi:

    --prefix=/__w/mpv-winbuild-cmake/mpv-winbuild-cmake/build64/install/mingw
    ... --enable-gpl --enable-version3 --enable-nonfree ...
    --enable-libx264 --enable-libx265 --enable-libxvid
    --enable-cuda --enable-cuvid --enable-nvdec --enable-nvenc ...

FFmpeg'in kendi `configure` yardim metni `--enable-nonfree` icin sunu der:
*"allow use of nonfree code, the resulting libs and binaries will be
unredistributable"*. Yani bu DLL kisisel kullanim icin derlenebilir ama
**hicbir bicimde ucuncu kisilere dagitilamaz** — ne setup icinde, ne yaninda.

- `--enable-lgpl` YOK; `--enable-gpl` + `--enable-version3` VAR. Yani LGPL
  degil, GPLv3 tarafindadir. MLC Player da GPLv3 oldugu icin bu KISIM sorun
  degildir; sorun yalniz `nonfree`dir.
- nonfree'yi tetikleyen bilesen `fdk-aac` DEGIL: ikilide `libfdk` izi yok,
  buna karsilik `nvenc`, `cuda`, `cuvid` var. Kaynak CUDA/NVENC tarafidir.
- `bin/SHA256SUMS.txt` bu dosya icin kaynagi bilerek bos birakiyor
  ("source/version is intentionally unspecified"). 99 MB'lik bir ikili
  kaynagi kayitli olmadan dagitilamaz; `yt-dlp`/`deno` icin uygulanan
  provenance disiplini buna da uygulanmalidir.

**Cozum basit ve dogrulandi:** ayni yukari-akis projenin (`mpv-winbuild-cmake`)
GUNCEL yapilandirmasi `--enable-nonfree` KULLANMIYOR; yalniz `--enable-gpl`
ve `--enable-version3` geciyor. Elimizdeki DLL eski/varyant bir yapidir.

Yapilacaklar (release turunda, sirasiyla):

1. `mpv-2.dll` guncel ve `nonfree` ICERMEYEN bir yapiyla degistir.
2. Degistirdikten SONRA ayni olcumu tekrarla: gomulu `configure` dizesinde
   `--enable-nonfree` OLMADIGINI dogrula. Bu, kabul kriteridir.
3. Surum, kaynak URL, boyut ve SHA-256'yi `bin/RUNTIME_MANIFEST.txt` icine
   yaz; `SHA256SUMS.txt`teki "intentionally unspecified" notunu kaldir.
4. mpv/FFmpeg icin GPLv3 lisans metnini ve karsilik gelen kaynak erisimini
   pakete ekle.
5. Codec/patent tarafi ayrica degerlendirilmeli: `libx264`, `libx265`,
   `libxvid` GPL'dir (lisans tarafi GPLv3 ile uyumludur) ancak H.264/H.265
   PATENT yukumlulukleri lisanstan AYRI bir konudur ve ticari dagitimda
   avukata sorulmalidir.

### YAPILDI: degisim ve dogrulama (16 Agustos 2026)

Yeni ikili: `mpv v0.41.0-923-g7b8915bc1`, FFmpeg `N-126125-g1d7b14f61`,
libass `0x1705000`. Kaynak arsiv, boyut ve SHA-256 artik
`bin/RUNTIME_MANIFEST.txt` icinde; `SHA256SUMS.txt`teki "intentionally
unspecified" notu KALDIRILDI. Eski nonfree DLL silinmedi, `bin/_old/` altina
alindi ve `.gitignore` ile hem depodan hem pakete girmekten uzak tutuldu
(`MLCPlayer.spec` acik dosya listesi kullanir, `bin/` glob'u YOKTUR).

**Lisans dogrulamasi (kabul kriteri yeniden tanimlandi).** Ilk kriter
"ikilide `--enable-nonfree` dizesi aranir" idi; yeni yapida FFmpeg'in
`configure`/lisans SABITLERI hic bulunmuyor (linker kullanilmayanlari
atmis), bu yuzden o kriter bu yapi icin GECERSIZDIR — "bulamadim" ile "yok"
ayni sey degildir. Bunun yerine uc bagimsiz kanit kullanildi:

1. Nonfree'yi ZORUNLU kilan bilesenlerin hicbiri ikilide yok:
   `libfdk` / `fdk_aac` / `libnpp` / `nppi_` / `cuda-nvcc` / `decklink`.
2. Etiketin (`20260814`) RESMI build tarifi yalniz `--enable-gpl` ve
   `--enable-version3` geciyor; `--enable-nonfree`, `--enable-libnpp` ve
   `--enable-cuda-nvcc` YOK. CUDA serbest `--enable-cuda-llvm` yolundan.
3. Eski ikilide FFmpeg'in kendi lisans sabiti literal olarak
   `nonfree and unredistributable` yaziyordu; yeni ikilide boyle bir sabit
   YOK ve nonfree bilesen izi de yok.

Sonuc: yeni yapi GPL(v3) tarafindadir ve MLC Player'in GPLv3 lisansiyla
uyumludur; dagitilabilir.

**API uyumlulugu olculdu.** Urunun bagli oldugu 31 secenek/ozelligin TAMAMI
yeni surumde mevcut (eksik yok). Altyazi stil sozlesmesinin kritik DEGERLERI
de yazilip geri okundu: `sub-ass-override=force`, `sub-border-style=
background-box` ve `outline-and-shadow`, `#AARRGGBB` renkler
(`#FFF26A3D`, `#C80020A0`), `sub-shadow-offset`, `sub-use-margins`,
`sub-ass-force-margins`, `sub-margin-y`, `sub-pos`, `sub-scale`,
`sub-border-size` — 14/14 dogru geri okundu.

**Not (davranis DEGISTIRILMEDI):** `sub-margin-y-offset` v0.36'da YOKTU ve
mevcut `sub-margin-y` tasariminin gerekcesi buydu. v0.41'de bu ozellik ARTIK
VAR. Gerekce eskidi ama bu turda hicbir altyazi yolu degistirilmedi; olasi
sadelestirme ayri bir turun konusudur.

**Test:** `pytest -q tests` -> **3158 passed, 17 skipped** (degisimden onceki
sonucun birebir aynisi).

**ACIK KALAN — fiziksel dogrulama.** Offscreen paketin gecmesi, altyazi
guvenli bandinin PIKSEL duzeyinde korundugunu KANITLAMAZ. mpv 0.36 -> 0.41
ve FFmpeg 6 -> 8 atlamasindan sonra `o_band` / `p_ass_band` gercek video
kabulu yeniden kosulmalidir (gercek pencere + gercek MKV, kullanici onayiyla).
Bu kosum yapilana kadar guvenli bant "dogrulanmis" SAYILMAZ.

## Yayin oncesi uyumluluk kontrol listesi

Asagidakiler somut ve dogrulanabilir maddelerdir. Hicbiri hukuki gorus
degildir.

### Kapatilmasi zorunlu

- [ ] `mpv-2.dll` nonfree olmayan yapiyla degistirildi ve olcumle dogrulandi
      (yukaridaki bolum).
- [ ] GPLv3+ birlesik `yt-dlp.exe` ve GPLv3 mpv icin **karsilik gelen kaynak
      erisimi**: kullaniciya, kullandigi ikiliyle ayni surumun kaynagini
      sunma yukumlulugu. Pratik yol, her ikili icin surum + kaynak arsiv
      URL'sini ve bir yedek kopyayi saklamaktir.
- [ ] Kokteki `LICENSE` (GPLv3, 35.149 bayt) setup icine de girmeli;
      `licenses/` klasoru pakete kopyalanmali.
- [ ] GPLv3'un onerdigi dosya basi telif/lisans bildirimleri kaynak
      dosyalara eklenmeli.

### OpenSubtitles API (olculdu)

Resmi sartlar: her istekte `Api-Key` basligi, uygulama adi + surum tasiyan
benzersiz `User-Agent`, **saniyede 1 istek** sinirlamasi, indirme kotalari
kullanici rutbesine bagli.

- [x] `app/opensubtitles.py` `Api-Key` gonderiyor ve
      `USER_AGENT = "MLC Player Subtitle Center v1"` kullaniyor — sartlara
      uygun bicimde ad + surum tasiyor.
- [x] Mevcut kod API anahtarini kullanicidan alir; uygulamaya gomulu anahtar
      YOKTUR. **Bu teknik durum bir uyumluluk karari degildir.** Servis
      yoneticisinin uygulama basina tek anahtar yonlendirmesi nedeniyle
      cevrimici arama arayuzu kapali tutulur; acik sart veya yazili saglayici
      onayi olmadan ne gomulu anahtar ne de kullanici-basina-anahtar akisi
      yayinlanir.
- [x] **KAPANDI (16 Agustos 2026):** onleyici hiz sinirlamasi eklendi.
      `MIN_REQUEST_INTERVAL_S = 1.0` ve `_respect_rate_limit()`, butun
      isteklerin gectigi TEK bogaz noktasi olan `_call()` icinde. Bekleme
      QThread worker'indadir, GUI donmaz; kilit es zamanli worker'larin ayni
      pencerede iki istek gondermesini engeller; saat GERI giderse bekleme
      aralikla SINIRLANIR. `429/406` tepkisel yolu AYNEN korunur — onleyici
      sinir onu degil, servise gereksiz yuku engeller.
      Sozlesme: 4 test (arka arkaya istekler araliklanir, yavas istek
      araligi tuketir ve bosa beklenmez, saat geri giderse ust sinir,
      anahtar yoksa aga cikilmadan once beklenmez).
- [ ] Indirilen altyazilarin yeniden dagitimi ve saklanmasi konusundaki
      sartlar dogrulanmali (uygulama altyaziyi yalniz kullanicinin diskine
      yaziyor; baska yere kopyalamiyor).

### Kod imzalama ve SmartScreen

- [ ] Kod imzalama sertifikasi arastirilmali. **Imza, lisans ve telif
      yukumluluklerinin yerine GECMEZ**; yalnizca dagitim guvenini artirir.
      Imzasiz setup Windows SmartScreen uyarisi uretir.

### Avukata yoneltilecek acik sorular

1. GPLv3 bir uygulamayla ayni pakette dagitilan GPLv3+ `yt-dlp.exe` icin
   "karsilik gelen kaynak" yukumlulugunu, kaynak arsiv URL'si sunmak
   karsiliyor mu, yoksa kopyayi bizim mi barindirmamiz gerekir?
2. H.264/H.265 decode iceren bir masaustu oynaticinin Turkiye'den ucretsiz
   dagitiminda patent havuzu (MPEG-LA / Access Advance) yukumlulugu dogar mi?
3. Acik kaynak bir Windows masaustu istemcisinde "uygulama basina tek API
   anahtari" nasil dagitilmalidir? Anahtarin kaynakta/ikili icinde gorulebilir
   olmasi kabul ediliyor mu; kullanicinin kendi anahtarini girmesi yasak mi?
   OpenSubtitles'tan yazili cevap alinmadan arayuz yeniden acilmayacak.

### Boyut etkisi (olculdu)

`mpv-2.dll` ~99 MB + `deno.exe` ~97 MB + `yt-dlp.exe` ~18 MB; yalnizca bu uc
dosya ~214 MB'dir. Kurulum boyutu ve setup sikistirma karari bu gercege gore
verilmelidir.

## Uygulama ikonu (tek gorsel kimlik)

Kaynak asset `assets/mlc-player-icon.png` (1254x1254 RGBA, kullanici
tarafindan saglandi, degistirilmeden alindi). Windows ICO ondan LANCZOS ile
uretildi: `assets/mlc-player-icon.ico` (16, 20, 24, 32, 40, 48, 64, 128, 256
px; alfa korundu). Olcu ve SHA-256 degerleri `assets/ICON_MANIFEST.txt`
icindedir.

Paketleme:

    _internal\assets\mlc-player-icon.ico

`MLCPlayer.spec` icinde `EXE(..., icon='assets/mlc-player-icon.ico')`.

### Setup icin KESIN alanlar (ileride uygulanacak)

Inno `.iss` bu turda URETILMEDI. Uygulanacak alanlar:

- `SetupIconFile=assets\mlc-player-icon.ico`
- `UninstallDisplayIcon={app}\MLC Player.exe`
- Masaustu ve Baslat menusu kisayollari ana EXE ikonunu kullanir.
- Setup ve kaldiricinin gercek gorunumu Inno kabulunde AYRICA dogrulanir.

