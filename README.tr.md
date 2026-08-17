# MLC Player (Türkçe)

Windows için sinematik arayüzlü, libmpv tabanlı medya oynatıcı.

*[English README](README.md) — GitHub ana sayfasında görünen sürüm.*

Tek bir arayüz vardır: çerçevesiz pencere, video üzerinde otomatik gizlenen
kontrol katmanı, geniş zaman çizgisi ve gömülü oynatma listesi paneli.
Klasik menü/panel görünümü kaldırılmıştır.

## Öne çıkanlar

- **Oynatma:** libmpv ile geniş kapsayıcı ve codec desteği. Video için
  MP4/MKV/AVI/MOV/WMV/FLV/MPEG/M4V/WEBM/TS/M2TS/VOB/OGV/3GP/ASF/MXF, ses için
  MP3/WAV/FLAC/OGG/M4A/AAC/OPUS/WMA/APE/ALAC/AIFF/AC3/DTS/MKA. Uzantı yalnız
  aday belirler; gerçek desteği libmpv verir.
- **Oynatma listesi:** ana pencereye gömülü, genişliği sürüklenebilir panel;
  küçük resim üretimi, doğal `1-2-10` sıralaması, klasör açma ve sürükle-bırak.
- **Albüm kapağı:** ses dosyalarında gömülü kapak (yoksa klasördeki resim)
  video alanında gösterilir; siyah kare kalmaz.
- **Tek kopya:** ikinci başlatma yeni pencere açmaz; açık pencere öne gelir ve
  dosya oraya yüklenir. Böylece iki kopya birbirinin ayarlarını ezmez.
- **Güncelleme denetimi:** açılışta sessiz kontrol ve `Yardım → Güncellemeleri
  Denetle`. İndirilen kurulum SHA-256 ile doğrulanır; doğrulanamayan dosya
  çalıştırılmaz ve silinir. Kapanış üründen geçer, süreç zorla öldürülmez.
- **Altyazı Merkezi:** OpenSubtitles üzerinden arama, indirme ve uygulama.
  İndirilen altyazı medyanın yanına atomik `.srt` olarak yazılır.
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

## Kurulum (hazır sürüm)

Son kurulum dosyası: [Releases](https://github.com/IzzmooPro/MLCPlayer/releases/latest)
(`MLCPlayer_Setup_v*.exe`, kurulu boyut ~295 MB). Kurulu bir sürüm varsa
`Yardım → Güncellemeleri Denetle` ile de yükseltilebilir; indirilen dosya
SHA-256 ile doğrulanmadan çalıştırılmaz.

## Çalıştırma (kaynaktan)

En kolay yol `Start.bat` dosyasına çift tıklamaktır: Python 3.12+ yoksa
kurar, eksik paketleri `requirements.txt` üzerinden yükler ve programı açar.
Her şey hazırsa hiçbir kurulum yapmadan doğrudan başlatır. Yalnızca kontrol
için `Start.bat -CheckOnly` (program açılmaz).

Elle kurulum gereksinimleri: Windows, Python 3.12+ ve `bin/mpv-2.dll`.

```bash
pip install -r requirements.txt
```

```bash
python main.py
```

`bin/` dizinindeki çalışma zamanı ikilileri (`mpv-2.dll`, `yt-dlp.exe`,
`deno.exe`) boyutları nedeniyle depoda tutulmaz; sağlamaları
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

| Bileşen | Lisans | Metin |
|---|---|---|
| mpv / libmpv | **GPLv3** (FFmpeg `--enable-gpl --enable-version3`) | `bin/RUNTIME_MANIFEST.txt` |
| yt-dlp (kaynak) | Unlicense | `licenses/yt-dlp-LICENSE.txt` |
| yt-dlp (resmî ikili) | GPLv3+ | `licenses/yt-dlp-THIRD_PARTY_LICENSES.txt` |
| deno | MIT | `licenses/deno-LICENSE.txt` |

Resmî `yt-dlp.exe` üçüncü taraf GPLv3+ kod içerir; bu nedenle **birleşik
executable GPLv3+ kapsamındadır**. Kaynak lisansı ile dağıtılan ikilinin
lisansı aynı şey değildir.

### Yayın öncesi açık maddeler

**Açık kalan iki madde.** İkisi de kod değişikliğiyle kapanmaz; karar
kullanıcıya, gerekirse hukukçuya aittir:

- **FFmpeg codec'lerinin patent tarafı (H.264/H.265).** Lisans sorunu
  DEĞİLDİR — `libx264`/`libx265` GPL'dir ve GPLv3 ile uyumludur. Patent
  havuzu yükümlülüğü lisanstan ayrı bir konudur ve VLC de bunu deposunda
  çözmez. MLC Player yalnız ÇÖZER (kodlama yapmaz), ücretsizdir ve küçük
  ölçeklidir; bu en düşük maruziyet konumudur.
- **OpenSubtitles API kullanım şartlarının gözden geçirilmesi.** Mevcut
  tasarımda her kullanıcı KENDİ API anahtarını girer, yani şartları kendi
  adına kabul eder. Tek bir anahtarın programa gömülmesi bu sorumluluğu
  bize taşırdı.

**Kapanan maddeler:**

- `mpv-2.dll` derlemesinin lisansı **doğrulandı** (16 Ağustos 2026). Yapı
  `--enable-gpl --enable-version3` taşıyor, `--enable-nonfree` TAŞIMIYOR
  ve nonfree gerektiren hiçbir bileşen (fdk-aac, libnpp, cuda-nvcc)
  içermiyor. Önceki derleme `nonfree` taşıdığı için dağıtılamazdı.
- **Karşılık gelen kaynak erişimi** (17 Ağustos 2026). `licenses/mpv-NOTICE.txt`
  ve `bin/RUNTIME_MANIFEST.txt` artık kurulan paketin İÇİNDE; her bileşenin
  sürümü, kaynak adresi ve SHA-256'sı orada. Kaynakta değişiklik yapmıyoruz.
- **Dosya başı telif/lisans bildirimleri** (17 Ağustos 2026). 228 Python
  dosyası ve 5 betik SPDX kısa biçimini taşıyor: `GPL-3.0-only`. Kimliğin
  resmî SPDX listesinde bulunduğu ve `LICENSE` dosyasının kanonik gnu.org
  metniyle birebir aynı olduğu ölçülerek doğrulandı.
- **Hakkında penceresinde lisans bildirimi** (17 Ağustos 2026). Pencere
  artık lisans adını, garanti reddini ve kaynak kodu adresini gösteriyor.

Bu bölüm hukuki danışmanlık değildir; bir kontrol listesidir.
