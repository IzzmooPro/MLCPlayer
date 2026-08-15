# MLC Player

Windows için sinematik arayüzlü, libmpv tabanlı medya oynatıcı.

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

## Çalıştırma (kaynaktan)

Gereksinimler: Windows, Python 3.14 ve `bin/mpv-2.dll`.

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
| mpv / libmpv | kendi dağıtım lisansı | ilgili mpv derlemesiyle gelir |
| yt-dlp (kaynak) | Unlicense | `licenses/yt-dlp-LICENSE.txt` |
| yt-dlp (resmî ikili) | GPLv3+ | `licenses/yt-dlp-THIRD_PARTY_LICENSES.txt` |
| deno | MIT | `licenses/deno-LICENSE.txt` |

Resmî `yt-dlp.exe` üçüncü taraf GPLv3+ kod içerir; bu nedenle **birleşik
executable GPLv3+ kapsamındadır**. Kaynak lisansı ile dağıtılan ikilinin
lisansı aynı şey değildir.

### Yayın öncesi açık maddeler

Bunlar bilerek açık bırakılmıştır ve dağıtımdan önce kapatılmalıdır:

- GPLv3+ kapsamındaki birleşik executable için **karşılık gelen kaynak
  erişimi** yükümlülüğünün nasıl sağlanacağı.
- Pakete giren `mpv-2.dll` derlemesinin GPL mi LGPL mi olduğunun ve
  FFmpeg/codec dağıtım şartlarının doğrulanması.
- OpenSubtitles API kullanım şartlarının gözden geçirilmesi.
- GPLv3'ün önerdiği **dosya başı telif/lisans bildirimlerinin** kaynak
  dosyalara eklenmesi (şu an yalnız kök `LICENSE` ve bu bölüm vardır).

Bu bölüm hukuki danışmanlık değildir; yayın öncesi kontrol listesidir.
