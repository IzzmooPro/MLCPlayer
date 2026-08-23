# MLC Player (Türkçe)

Windows için sinematik arayüzlü, libmpv tabanlı medya oynatıcı.

*[English README](README.md) — GitHub ana sayfasında görünen sürüm.*

Tek bir arayüz vardır: çerçevesiz pencere, video üzerinde otomatik gizlenen
kontrol katmanı, geniş zaman çizgisi ve ana pencerenin yanında duran sahipli
bağımsız pencere biçiminde oynatma listesi. Liste oynatıcıyı takip eder,
videoyla kesişmez ve diğer uygulamaların üzerinde yüzmez. Klasik menü/panel
görünümü kaldırılmıştır.

## Öne çıkanlar

- **Oynatma:** libmpv ile geniş kapsayıcı ve codec desteği. Video için
  MP4/MKV/AVI/MOV/WMV/FLV/MPEG/M4V/WEBM/TS/M2TS/VOB/OGV/3GP/ASF/MXF, ses için
  MP3/WAV/FLAC/OGG/M4A/AAC/OPUS/WMA/APE/ALAC/AIFF/AC3/DTS/MKA. Uzantı yalnız
  aday belirler; gerçek desteği libmpv verir.
- **Oynatma listesi:** ana pencerenin yanında duran, genişliği sürüklenebilir
  sahipli bağımsız pencere; küçük resim üretimi, doğal `1-2-10` sıralaması,
  klasör açma ve sürükle-bırak. Videoyla kesişmez ve her zaman üstte kalmaz.
- **Albüm kapağı:** ses dosyalarında gömülü kapak (yoksa klasördeki resim)
  video alanında gösterilir; siyah kare kalmaz.
- **Tek kopya:** ikinci başlatma yeni pencere açmaz; açık pencere öne gelir ve
  dosya oraya yüklenir. Böylece iki kopya birbirinin ayarlarını ezmez.
- **Güncelleme denetimi:** açılışta sessiz kontrol ve `Yardım → Güncellemeleri
  Denetle`. İndirilen kurulumun yayımlanan boyutu, SHA-256 özeti ve yayıncı
  Ed25519 imzası doğrulanır; doğrulanamayan dosya çalıştırılmaz ve silinir.
  Kapanış üründen geçer, süreç zorla öldürülmez.
- **Altyazılar:** Eşleşen yerel altyazılar otomatik bulunur ve siz seçene kadar
  gizli kalır. OpenSubtitles kullanan Altyazı Merkezi, API dağıtım şartları
  incelenirken geçici olarak gizlidir; ağ işlevi arayüzden erişilemez.
- **Altyazı görünümü:** yazı/kenarlık/arka plan rengi, boyut, kenarlık
  kalınlığı, dikey konum ve senkron. Canlı temsili önizleme içerir.
- **Güvenli alt bant:** altyazı hiçbir durumda kontrol katmanıyla çakışmaz;
  kullanıcının kayıtlı konum tercihi değiştirilmeden korunur.
- **Yerel altyazı:** medyanın yanındaki eşleşen `.srt` bulunur, kullanıcı
  açana kadar gizli başlar; her parça kendi altyazısını etkinleştirir.
- **Medya Bilgisi:** dosya, video, ses ve altyazı parçaları için tek ve
  okunabilir görünüm. Ham MPV anahtarı veya teknik iç metin gösterilmez.
- **Güvenli hata sistemi:** kullanıcıya giden metinlerde gerçek dosya yolu,
  adres ve iz kaydı maskelenir; ayrıntılar ayrı pencerede ve kopyalanabilir
  güvenli gövde olarak sunulur.
- **Gizlilik:** uzak adresler pencere başlığında ve `Son Açılanlar` içinde
  tam hâliyle saklanmaz; yalnız güvenli `host[:port]` gösterilir.

## Hızlı başlangıç

- Tek dosya için `Ctrl+O` kullanın, `Ortam → Klasör Aç` ile bir klasör seçin
  veya medyayı oynatıcıya sürükleyin. Yan oynatma listesini `Ctrl+P` ile açın.
- URL için `Ctrl+U` kullanın. Doğrudan HTTP/HLS akışları ana oynatıcıyla
  çalışabilir; site çıkarımı aşağıda anlatılan İnternet Videosu ek paketini
  gerektirir.
- Eşleşen yerel altyazılar otomatik bulunur fakat siz seçene kadar gizli
  kalır. Çevrimiçi altyazı arama geçici olarak gizlidir; yerel altyazı yükleme
  ve görünüm ayarları kullanılabilir.
- Arayüz dili `Araçlar → Dil` üzerinden seçilir ve yeniden başlatınca uygulanır.
  Bütün desteklenen kısayollar `Araçlar → Klavye Kısayolları` içindedir.

## Kurulum (hazır sürüm)

Aynı [Releases](https://github.com/IzzmooPro/MLCPlayer/releases/latest)
kaydındaki dosyaları kullanın:

1. Önce ana oynatıcıyı `MLCPlayer_Setup_v*.exe` ile kurun.
2. Site çıkarımı gerektiren internet videolarını oynatacaksanız aynı sürümün
   `MLCPlayer_InternetVideo_v*.exe` ek paketini de kurun. Bu isteğe bağlı paket
   yt-dlp ve Deno bileşenlerini sağlar; yerel medya veya doğrudan HTTP/HLS
   akışları için gerekli değildir.

Hazır kurulum Windows 10 veya 11, 64-bit ve yönetici onayı gerektirir. Ana
paket oynatıcı ile libmpv'yi içerir; büyük internet-video araçları yalnız ek
paketle gelir. Bu nedenle kurulu boyut ek paketin bulunmasına göre değişir.

Her kurulumun yanında bir `.sig` dosyası bulunur. Bu dosya, kurulumun SHA-256
özetine ait yayıncı Ed25519 imzasıdır. Otomatik güncelleme çalıştırılmadan önce
yayımlanan boyut, SHA-256 ve imza birlikte doğrulanır; uyuşmayan indirme
silinir. `.sig` dosyasını kendiniz çalıştırmazsınız.

Kurulum henüz kod imzalı değildir; Windows SmartScreen ilk çalıştırmada
“bilinmeyen yayıncı” uyarısı gösterebilir.

Projenin [Kod imzalama politikası](CODE_SIGNING_POLICY.md),
[Gizlilik politikası](PRIVACY.md), [SignPath hazırlık kaydı](docs/SIGNPATH_READINESS.md)
ve [başvuru taslağı](docs/SIGNPATH_FOUNDATION_APPLICATION.md) herkese açıktır.
Taslak henüz gönderilmemiş, kabul edilmemiş ve mevcut kuruluma uygulanmamıştır.

Kurulu sürüm `Yardım → Güncellemeleri Denetle` ile güvenli biçimde
yükseltilebilir. Yerleşik güncelleyici yalnız ana oynatıcıyı günceller;
İnternet Videosu ek paketini kullanıyorsanız aynı yeni sürümü Releases
sayfasından ayrıca indirip çalıştırın.

### Kaldırma ve kullanıcı verileri

Paketlerden birini kaldırmak ayarlarınızı ve günlüklerinizi korur; böylece
yükseltme veya yeniden kurulum tercihlerinizi silmez. Günlükler
`%APPDATA%\MLCPlayer\logs` altında tutulur ve `Araçlar → Günlük Yönetimi`
üzerinden güvenle incelenebilir veya silinebilir. Ek paketin ayrı kaldırıcısı
vardır; onu kaldırmak ana oynatıcıyı silmeden site çıkarımını kapatır.

## Çalıştırma (kaynaktan)

En kolay yol `Start.bat` dosyasına çift tıklamaktır: Python 3.12-3.14 yoksa
kurar, eksik paketleri `requirements.txt` üzerinden yükler ve programı açar.
Başlatmadan önce üç çalışma zamanı ikilisini de doğrular. Her şey hazırsa
hiçbir kurulum yapmadan doğrudan başlatır. Yalnızca kontrol için
`Start.bat -CheckOnly` kullanın; program açılmaz.

Elle yerel medya oynatmak için Windows, Python 3.12-3.14 ve `bin/mpv-2.dll`
gerekir. İnternet videosu site çıkarımı ayrıca `bin/yt-dlp.exe` ve
`bin/deno.exe` gerektirir; doğrudan HTTP/HLS oynatma mpv özelliğidir.
Mevcut `Start.bat` üç ikiliyi de zorunlu tutar.

```bash
pip install -r requirements.txt
```

```bash
python main.py
```

Bu çalışma zamanı ikilileri boyutları nedeniyle depoda tutulmaz; sağlamaları
`bin/RUNTIME_MANIFEST.txt` ve `bin/SHA256SUMS.txt` içinde izlenir.

## Testler

```bash
python -m pytest -q tests
```

Varsayılan paket tamamen offscreen çalışır ve gerçek kullanıcı ayarlarına
dokunmaz. Gerçek pencere ve gerçek video gerektiren native/fiziksel kabul
koşumları ayrıca opt-in ortam değişkenleriyle açılır; bunlar varsayılan
pakete dahil değildir.

## Paketleme

Release zinciri `packaging/` altındadır: `build_release.bat`,
`MLCPlayer.iss` ve ölçümlü doğrulama adımlarıyla `verify_build.py`.
Kararların gerekçesi `docs/PACKAGING_PLAN.md` içindedir.

## Lisans

Copyright (C) 2026 MLC Player katkıcıları.

MLC Player **GNU General Public License v3.0** ile lisanslanmıştır; tam metin
[`LICENSE`](LICENSE) dosyasındadır (gnu.org kanonik metni, 35 149 bayt,
değiştirilmeden).

Bu program özgür yazılımdır: GNU GPL sürüm 3 şartları altında
yeniden dağıtabilir ve/veya değiştirebilirsiniz. Hiçbir GARANTİ verilmez;
satılabilirlik veya belirli bir amaca uygunluk zımni garantisi dahi yoktur.
Ayrıntılar için GNU GPL'e bakınız.

Dağıtılan pakette üçüncü taraf bileşenler bulunur ve kendi lisanslarıyla
gelirler:

| Bileşen | Lisans | Geldiği paket | Metin |
|---|---|---|---|
| Python / PyQt6 / Qt ve Python çalışma zamanı bağımlılıkları | PSF / GPLv3 / LGPLv3 / bileşen lisansları | Ana paket | `licenses/THIRD_PARTY_NOTICES.txt` |
| mpv / libmpv | **GPLv3** (FFmpeg `--enable-gpl --enable-version3`) | Ana paket | `licenses/mpv-NOTICE.txt` |
| yt-dlp (kaynak) | Unlicense | İnternet Videosu ek paketi | `licenses/yt-dlp-LICENSE.txt` |
| yt-dlp (resmî ikili) | GPLv3+ | İnternet Videosu ek paketi | `licenses/yt-dlp-THIRD_PARTY_LICENSES.txt` |
| deno | MIT | İnternet Videosu ek paketi | `licenses/deno-LICENSE.txt` |

Resmî `yt-dlp.exe` üçüncü taraf GPLv3+ kod içerir; bu nedenle **birleşik
executable GPLv3+ kapsamındadır**. Kaynak lisansı ile dağıtılan ikilinin
lisansı aynı şey değildir.

### Değişiklik katkısı

Bakımcı dal/PR sırası, zorunlu CI kontrolü ve kanıt commit'lerini koruyan
birleştirme yöntemi [`docs/CHANGE_WORKFLOW.md`](docs/CHANGE_WORKFLOW.md)
dosyasındadır.

### Yayın öncesi açık maddeler

**Açık kalan iki madde.** İkisi de kod değişikliğiyle kapanmaz; karar
kullanıcıya, gerekirse hukukçuya aittir:

- **FFmpeg codec'lerinin patent tarafı (H.264/H.265).** Lisans sorunu
  DEĞİLDİR — `libx264`/`libx265` GPL'dir ve GPLv3 ile uyumludur. Patent
  havuzu yükümlülüğü lisanstan ayrı bir konudur ve VLC de bunu deposunda
  çözmez. MLC Player yalnız ÇÖZER (kodlama yapmaz), ücretsizdir ve küçük
  ölçeklidir; bu en düşük maruziyet konumudur.

  Açık kaynak olmak ve ücret almamak tek başına patent muafiyeti
  DEĞİLDİR; patent telif hakkından bağımsız işler. Konumu rahat kılan
  ölçektir: AVC/H.264 tarifesinde yılda ilk 100.000 birim telifsizdir.
  Yeniden değerlendirme eşiği bu yüzden tanımlıdır — yıllık dağıtım
  100.000'e yaklaşırsa ya da ürün ücretli hâle gelirse AVC lisansı ve
  HEVC havuzları gözden geçirilir. HEVC tarafında AVC'ye denk bir
  ücretsiz katman DOĞRULANMAMIŞTIR.
- **OpenSubtitles API kullanım şartlarının gözden geçirilmesi.** Mevcut
  kod her kullanıcının kendi API anahtarını girmesini bekler; ancak servis
  yöneticisinin güncel yönlendirmesi uygulama başına tek anahtar kullanılması
  yönündedir. Anahtarın açık kaynak masaüstü uygulamasında nasıl dağıtılacağı
  açık şart veya yazılı sağlayıcı cevabıyla doğrulanana kadar çevrimiçi arama
  arayüzü kapalıdır. Bu bir hukuki görüş değildir.
- **Karşılık gelen kaynak paketleri.** Eski yayın akışı mpv geliştirme
  paketini ve çalıştırılabilir add-on dosyalarını kaynak olarak sayıyordu;
  bunlar gerçek, yeniden derlenebilir kaynak değildir. Yeni 20260821 libmpv
  bütün kaynak girdileri binary ile birlikte yakalanarak derlendi. Doğrulanan
  paket sabit v0.38 release adı, boyutu ve SHA-256 değeriyle hazırlandı; yayın
  akışı aynı dosyayı kayıtlı kalıcı adrese yükleyecek. Cryptography wheel'inin
  OpenSSL 4.0.1 ve 32 Rust crate kaynağı da gömülü SBOM'a göre kilitlendi.
  Resmî yt-dlp 2026.08.19 ikilisinin Python, PyInstaller, paket ve native curl
  kaynak zinciri de hash ile sabitlendi. Kurulu lisans/notice paketi, tam Qt
  LGPLv3 metni ve dinamik Qt DLL değiştirme talimatı kaynakta tamamlandı.
  v0.38 kaynak build'i ve ayrı onaylı kurulu-artifact kabulü ana paketteki 12
  lisans/notice dosyasını ve Qt değiştirme yolunu kanıtladı; karşılık gelen
  kaynak sözleşmesi artık hazırdır. Bu sonuç native oynatma veya kaldırma
  kabulü yerine geçmez.

**Kapanan maddeler:**

- `mpv-2.dll` derlemesinin lisansı **doğrulandı** (16 Ağustos 2026). Yapı
  `--enable-gpl --enable-version3` taşıyor, `--enable-nonfree` TAŞIMIYOR
  ve nonfree gerektiren hiçbir bileşen (fdk-aac, libnpp, cuda-nvcc)
  içermiyor. Önceki derleme `nonfree` taşıdığı için dağıtılamazdı.
- **Binary köken kaydı** (17 Ağustos 2026). `licenses/mpv-NOTICE.txt` ve
  `bin/RUNTIME_MANIFEST.txt` kurulan paketin İÇİNDE; bunlar kullanılan
  binary'nin sürümünü, adresini ve SHA-256'sını kaydeder. Karşılık gelen
  kaynağın sunulduğu anlamına gelmez.
- **Dosya başı telif/lisans bildirimleri** (17 Ağustos 2026). 228 Python
  dosyası ve 5 betik SPDX kısa biçimini taşıyor: `GPL-3.0-only`. Kimliğin
  resmî SPDX listesinde bulunduğu ve `LICENSE` dosyasının kanonik gnu.org
  metniyle birebir aynı olduğu ölçülerek doğrulandı.
- **Hakkında penceresinde lisans bildirimi** (17 Ağustos 2026). Pencere
  artık lisans adını, garanti reddini ve kaynak kodu adresini gösteriyor.

Bu bölüm hukuki danışmanlık değildir; bir kontrol listesidir.
