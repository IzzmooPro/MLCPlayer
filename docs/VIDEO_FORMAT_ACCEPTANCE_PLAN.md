# MLC Player video format ve renk yolu kabul planı

Bu belge SDR, HDR10, HLG, HDR10+, Dolby Vision ve modern 10-bit codec
davranışının kalıcı yürütme planıdır. İnsan özeti buradadır; satırların
makinece tek kaynağı `VIDEO_FORMAT_ACCEPTANCE_MATRIX.json` dosyasıdır.
Gerçek Windows üst satırı `WINDOWS_ACCEPTANCE_MATRIX.md`, karar kanıtları
`VERIFICATION_LEDGER.json`, güncel sıra `CONTINUITY.md` içindedir.

Bu plan **ürün desteği veya PASS ilanı değildir**. Başlangıçta bütün format
satırları `BLOCKED` ya da `NOT_RUN` kalır. Codec listesinin varlığı, dosyanın
açılması, ekran görüntüsü, monitörün HDR logosu veya başka oynatıcının sonucu
MLC Player renk yolu PASS'i değildir.

## Amaç ve kullanıcıya verilecek gerçek

Tek kelimelik “HDR” etiketi yeterli değildir. Ürün, kanıt oluşursa dört ayrı
gerçeği gösterebilmelidir:

```text
Girdi: HDR10+ / HEVC Main10 / PQ / BT.2020 / 1000 nit
Isleme: gpu-next + D3D11 / dinamik metadata kullanılıyor
Cikis: HDR10 / G2084-P2020 / 10-bit
Donanim decode: d3d11va
```

Dolby Vision fallback örneği:

```text
Girdi: Dolby Vision Profil 8.1
Isleme: HDR10 uyumlu taban ve renderer tone mapping
Cikis: HDR10 fallback
Donanim decode: ölçülen gerçek değer
```

Ekran/renderer Dolby Vision sinyalini ayrıca kanıtlamadıysa burada “Dolby
Vision çıkışı” yazılmaz. Aynı şekilde SDR içerik Windows HDR açıkken PQ hedefe
eşlenebilir fakat kaynak “HDR video” olarak yeniden etiketlenmez.

## Rakip oynatıcıların somut uygulamaları

### MPC Video Renderer

- Direct3D 11, HDR10, HLG ve kısmi Dolby Vision yollarını; HDR passthrough,
  HDR→SDR dönüşümü, metadata doğrulama ve SDR ekran nit değerini ayrı ele alır.
- Windows HDR varsayılanını beklenmedik ekran titreşimini önlemek amacıyla
  “değiştirme” durumuna taşımıştır.
- HDR altyazı/OSD parlaklığı, 10-bit görüntü biçimleri, ekran değişimi ve
  ayrıntılı istatistikler için ayrı düzeltmeler kaydeder.
- Kaynaklar: [özellikler](https://github.com/Aleksoid1978/VideoRenderer),
  [sürüm geçmişi](https://github.com/Aleksoid1978/VideoRenderer/blob/master/history.txt).
- **Alınacak ders:** metadata doğrulama, Windows durumunu koruyan varsayılan,
  ekran değişiminde yeniden ölçüm, altyazı/OSD luminance politikası ve görünür
  input/output istatistiği.
- **Sınır:** PotPlayer veya MPC-BE bu renderer'ı kullanıyorsa sonuç renderer'a
  aittir; player kabuğuna otomatik taşınmaz.

### Kodi

- Kullanıcıya uygulamanın ekran HDR modunu yönetmesi veya mevcut modu koruyup
  gerektiğinde tone mapping yapması arasında açık seçim sunar.
- DXVA ve yüksek hassasiyetli işleme ayrı ayardır; görüntü senkronu gibi
  seçeneklerin ses passthrough ile etkileşimini belgeler.
- Kaynak: [Kodi video ayarları](https://kodi.wiki/view/Settings/Player/Videos).
- **Alınacak ders:** onlarca düşük seviye anahtar yerine az sayıda anlaşılır
  renk politikası; gerçek sonuç ayrıca tanı panelinde görünür.

### VLC

- Kararlı VLC 3 hattı Windows Direct3D 11 HDR10 desteğini, HDR→SDR tone mapping
  ve SDR içeriğin HDR ekranda doğru gösterimi için düzeltmeleri kaydeder.
- Gelişim D3D11 kodu `auto`, `never`, `always` ve SDR'den üretilen HDR
  modlarını ayırır.
- Kaynaklar: [VLC 3 NEWS](https://github.com/videolan/vlc-3.0/blob/master/NEWS),
  [D3D11 renderer](https://github.com/videolan/vlc/blob/master/modules/video_output/win32/direct3d11.cpp).
- **Alınacak ders:** SDR-on-HDR ve HDR-on-SDR iki ayrı zorunlu regresyondur;
  SDR→HDR üretimi içerik niyetini değiştirdiği için varsayılan olamaz.
- **Sınır:** gelişim dalındaki özellik, her kurulu kararlı VLC sürümünde varmış
  gibi raporlanmaz.

### exact mpv `49418246f`

- `gpu-next` ile `target-colorspace-hint` hedef, kaynak ve `source-dynamic`
  politikaları sunar; `video-target-params` gerçek VO hedefini açıklar.
- Exact belgede `source-dynamic`, HDR10+ veya Dolby Vision verisini kullanarak
  sahne bazlı HDR10 üretebilir; tam HDR10+/Dolby Vision metadata passthrough
  garantisi değildir.
- Kaynaklar: [options](https://raw.githubusercontent.com/mpv-player/mpv/49418246f/DOCS/man/options.rst),
  [properties](https://raw.githubusercontent.com/mpv-player/mpv/49418246f/DOCS/man/input.rst).
- **Alınacak ders:** MLC'nin doğal aday yolu `gpu-next`/D3D11'dir; fakat mevcut
  `vo=gpu` ile aynı exact medya/ekran üzerinde A/B native kanıtı olmadan ürün
  varsayılanı değişmez.

## Bizim daha iyi yapacağımız kararlar

1. Varsayılan politika Windows HDR durumunu değiştirmez. Gelecekte otomatik
   anahtarlama istenirse önceki ekran durumu kaydedilir, ekran değişiminde
   yeniden değerlendirilir ve kapanışta geri yüklenmesi fail-closed ölçülür.
2. Kullanıcı ayarı ilk sürümde en fazla `Otomatik`, `Windows durumunu koru` ve
   `SDR hedefe tone-map et` gibi anlaşılır politikalardır. `HDR zorla` ve RTX
   Video HDR gibi SDR→HDR üretimleri çekirdek kabul tamamlanmadan eklenmez.
3. Medya Bilgisi dosya adına bakmaz. `video-params`, track Dolby Vision
   profil/level ve ölçülen hedef üzerinden Girdi/Isleme/Cikis ayrımı kurar.
4. Bilinmeyen veya çelişkili metadata “HDR” diye tahmin edilmez. `VF-META-01`
   PASS olmadan genel HDR rozeti açılmaz.
5. Altyazı/OSD luminance, tam ekran/pencere ve SDR/HDR geçişi bağımsız kabul
   satırıdır. Video doğruyken göz alan altyazı kabul edilmez.
6. Ekran görüntüsü (`ekran goruntusu`) yalnız UI/istatistik yerleşimini
   kanıtlar; HDR parlaklık,
   gamut veya tone-map doğruluğunu kanıtlamaz. Renk değerlendirmesi kontrollü
   ramp/test klibi ve mümkünse kolorimetre ile ayrıca yapılır.

## Zorunlu format kapsamı

Makine matrisindeki 16 satır şu riskleri kapsar:

- SDR BT.709 → SDR ekran;
- SDR BT.709 → Windows HDR ekran;
- HDR10 HEVC Main10 → HDR10 hedef;
- HDR10 → SDR tone mapping;
- HDR altyazı ve OSD luminance;
- AV1 Main10 HDR10 ve VP9 Profile 2 HDR;
- BT.2100 HLG;
- HDR10+ → HDR10 fallback veya dinamik HDR10;
- Dolby Vision Profil 8.1 HDR10 fallback;
- Dolby Vision Profil 8.4 HLG fallback;
- yalnız gerçek yetenek varsa native Dolby Vision çıkışı;
- 4K60 10-bit frame cadence;
- limited/full range siyah-beyaz seviyeleri;
- monitör taşıma ve Windows HDR durum geri yükleme;
- eksik/çelişkili renk metadata'sı.

HDR10+ ve Dolby Vision için “dosya açıldı” yeterli değildir. `scene-max-*`,
DV profil/level, taban katman transferi, hedef transfer/gamut ve ekran yeteneği
ayrı kaydedilir. Dinamik format girişi HDR10 hedefe dönüştüyse sonuç dürüstçe
fallback/dinamik HDR10 diye adlandırılır.

## Test medyası sözleşmesi

Her medya şu kayıt olmadan native koşuma giremez:

- resmî kaynak URL'si veya kullanıcıya ait kaynak açıklaması;
- lisans ya da test kullanım dayanağı;
- dosya adı yayımlanmadan boyut ve SHA-256;
- `ffprobe` JSON: container, codec, profil, piksel biçimi, bit derinliği,
  primaries, transfer, matrix, range, mastering metadata ve dynamic metadata;
- koşum öncesi/sonrası tam kimlik eşliği.

Büyük video dosyaları Git'e eklenmez. Sentetik ramp/metadata fixture'ı
üretilirse üretim komutu, FFmpeg kimliği ve çıktı hash'i kaydedilir. Sentetik
metadata görüntü kalitesi veya mastering kanıtı değildir; yapısal renk yolu
testidir.

## Native yürütme ve rakip yan-yana ölçüm

Her child için üst sınır **60 saniye**dir. Tek kullanıcı onayı tek senaryoya
aittir; 480/600 saniyelik birleşik paket yapılmaz. Başarısızlık, eksik marker,
timeout veya süreç sızıntısından sonra otomatik tekrar yoktur; önce neden
incelenir ve başarısız sonuç ledger'a yazılır.

Aynı exact medya ve değişmeyen Windows/ekran durumunda MLC, VLC, Kodi ve MPC
Video Renderer ancak makinede mevcut ve ayrı koşum onayı verilmişse yan yana
ölçülür. Her biri için:

- player sürümü ve gerçek renderer;
- giriş codec/renk metadata'sı;
- hardware decoder;
- Windows DXGI renk uzayı önce/sırasında/sonrasında;
- passthrough, tone mapping veya fallback sınıfı;
- VO/decoder frame drop;
- fullscreen/pencere ve altyazı/OSD davranışı;
- kapanış ve değiştirilmiş ekran durumunun geri yüklenmesi

kaydedilir. Rakibin PASS'i MLC PASS'i değildir; yalnız ürün kararı için somut
karşılaştırma verisidir.

## Ürün değişikliği karar kapısı

Önce mevcut `vo=gpu` ve test-only `gpu-next`/D3D11 adayı aynı girdilerle
ölçülür. Aday ancak şu koşullarda ürün değişikliği teklifi olur:

- `VF-CORE-01` SDR tabanı gerilemez;
- `VF-CORE-02/03/04` hedef sınıfları doğru ve fail-closed olur;
- kapanış, timeline, fullscreen ve süreç sızıntısı kapıları korunur;
- frame-drop veya başlangıç süresi kabul edilemez biçimde kötüleşmez;
- bilinmeyen metadata yanlış HDR PASS'i üretmez.

Bu kanıt ürün kodunu otomatik değiştirmez. `app/config.py` değişikliği,
regression testleri, commit, push, PR, merge, build ve kurulu kabul ayrı açık
onaylardır.

## Dosya güncelliği kapanış kapısı

Her araştırma, fixture, native sonuç veya ürün kararı aynı görev kapanmadan:

1. `VIDEO_FORMAT_ACCEPTANCE_MATRIX.json` satırını günceller;
2. `WINDOWS_ACCEPTANCE_MATRIX.md` özetini günceller;
3. yeni ve append-only `VERIFICATION_LEDGER.json` kaydı ekler;
4. `CONTINUITY.md` son kanıt ve sıradaki tek adımı günceller;
5. format-planı ve continuity regresyonlarını çalıştırır;
6. commit/push/PR/merge için ayrı onay ister.

Eksik medya, yanlış ekran modu, eksik marker, `BLOCKED`, `FAILED` veya
`SKIPPED` hiçbir zaman PASSED yapılmaz.
