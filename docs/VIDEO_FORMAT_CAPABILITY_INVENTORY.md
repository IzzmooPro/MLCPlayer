# MLC Player video format yetenek envanteri

Bu kayıt, `419d6c7cede0b6fad37425b28c375fc89e61b141` üzerinde 24 Ağustos
2026'da alınan salt-okunur makine ve exact runtime ölçümüdür. Medya açılmadı,
Windows HDR ayarı değiştirilmedi ve ürün yapılandırması değiştirilmedi.

## Makine ve ekran yolu

- Aktif GPU: NVIDIA GeForce RTX 4070 Ti; sürücü `610.88`
  (`32.0.16.1088`), WDDM 3.2, Direct3D feature level 12_2.
- Pasif/ekran sürmeyen ikinci bağdaştırıcı: AMD Radeon Graphics,
  `32.0.21045.1000`.
- Aktif ekran: MSI G274QPF E2 (`MSI8CC2`), 2560x1440, 180 Hz.
- Aktif EDID: 384 bayt, SHA-256
  `f325d9f7e693b0ee79049ba342bf01066419110658a56452d0e0a20e44f4456f`.
  CTA HDR Static Metadata bloğu ham olarak `060701625F00`, BT.2020
  colorimetry bloğu `05C000` ölçüldü. Bu, giriş kablosu/ekranın ilan ettiği
  yetenektir; o anda HDR10 sinyali gönderildiğini kanıtlamaz.
- DxDiag `HDR Support: Supported` ve `AdvancedColorEnabled` bildirdi. Aktif
  renk uzayı ise
  `DXGI_COLOR_SPACE_RGB_FULL_G22_NONE_P709` idi. Microsoft, bu değerin SDR
  yolu temsil ettiğini ve SDR Advanced Color ekranlarda da aynı değerin
  görülebileceğini açıklar. HDR10 için aranan değer
  `DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020` hâlâ ölçülmedi.
- DxDiag parlaklık telemetrisi: 417.711792 nit tepe ve 391.463287 nit tam
  çerçeve. MSI resmî teknik sayfası DisplayHDR 400 ve 8-bit+FRC bildirir.

Kaynaklar: [Microsoft Advanced Color](https://learn.microsoft.com/windows/win32/direct3darticles/high-dynamic-range),
[MSI G274QPF E2](https://www.msi.com/Monitor/G274QPF-E2/Specification).

### 25 Ağustos 2026 canlı HDR çıkış güncellemesi

Ayrı sistem ayarı onayıyla aynı tek aktif MSI ekranın Windows HDR anahtarı
kapalıdan açığa alındı. Ayarlar arayüzü `HDR Açık` durumunu gösterdi ve hemen
sonraki DxDiag ölçümü etkin renk uzayını exact
`DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020` olarak verdi
(`EV-20260825-005`). Bu, aktif HDR10 Windows çıkış ön koşulunu kanıtlar;
MLC Player medya yolu, tone mapping, görsel doğruluk veya herhangi bir
video-format satırı için PASS değildir. Bu güncellemede medya açılmadı ve
hedef süreç sızıntısı yoktu.

## Exact mpv ve FFmpeg runtime

- `bin/mpv-2.dll`: 112772608 bayt, SHA-256
  `de80329f5c019ba2ee48184b5dc1e1d0c2ee9eeba3f1fb7959f20b4b0f684f4e`.
- mpv: `v0.41.0-930-g49418246f`; FFmpeg:
  `N-126239-g88ae625e6`; python-mpv: `1.0.8`; Python: `3.14.3`.
- VO derleme seçenekleri `gpu-next`, `gpu`, `direct3d` ve `libmpv` içeriyor.
  Windows GPU API/context seçenekleri D3D11, Vulkan, `winvk`, ANGLE,
  `dxinterop` ve `displayvk` yollarını içeriyor.
- `target-colorspace-hint` seçenekleri `auto/no/yes`; modları `target`,
  `source`, `source-dynamic`. Hedef transfer seçeneklerinde PQ, HLG ve scRGB;
  tone mapping seçeneklerinde BT.2390, BT.2446a, ST 2094-40 ve ST 2094-10
  bulunuyor. Çıkış seviye seçenekleri `auto/limited/full`.
- Derlenmiş codec listesi HEVC, VP9 ve AV1 yazılım sürücülerini; NVIDIA
  CUVID, AMD AMF ve Intel QSV sürücülerini içeriyor. `hwdec-codecs`
  varsayılan listesi H.264, HEVC, VP8, VP9, AV1, ProRes, FFV1, DPX ve APV'yi
  kapsıyor.

NVIDIA'nın resmî Video Codec SDK sayfası NVDEC'in Windows'ta H.264, HEVC,
VP9 ve AV1 dahil donanım çözmeyi desteklediğini açıklar. Buna rağmen derlenmiş
CUVID sürücüsü ve GPU modelinin varlığı tek başına bu exact MLC yolunda
donanım çözme PASS'i değildir; bunun için fingerprint edilmiş medya üzerinde
`hwdec-current` read-back gerekir. Kaynak:
[NVIDIA Video Codec SDK](https://developer.nvidia.com/video-codec-sdk).

## Ürünün bugünkü politikası

`app/config.py` hâlâ `vo=gpu` ve `hwdec=auto-safe` kullanıyor. Ürün
`gpu-next`, D3D11, `target-colorspace-hint`, hedef primaries/TRC veya özel tone
mapping politikasını varsayılan olarak zorlamıyor. Test-only HDR adayı bu
değerleri yalnız child kopyasında uygular; ürün sözlüğünü mutate etmez.

## Kanıt sınırı ve karar

Bu envanter şunları kanıtlar: exact DLL kimliği, derlenmiş seçeneklerin
okunabildiği, medya açmayan libmpv child'ının `MARK_DONE` ile çıkıp süreç
sızdırmadığı, ekranın HDR-capable olduğu ve aktif Windows yolunun ölçüm anında
P709 kaldığı.

Şunları kanıtlamaz: gerçek HEVC/AV1/VP9 donanım decode, 10-bit swapchain,
HDR10/HLG/HDR10+/Dolby Vision çıkışı, tone mapping kalitesi, overlay
parlaklığı, 4K60 performansı veya rakip oynatıcı davranışı. Bu nedenle
`VIDEO_FORMAT_ACCEPTANCE_MATRIX.json` içindeki 16 senaryonun tamamı
`BLOCKED` kalır.
