# MLC Player mimari envanteri

**Durum:** SORUMLULUK ANALİZİ TAMAMLANDI, ÜRÜN KODU DEĞİŞTİRİLMEDİ

**Ürün kaynak tabanı:** `78518dd67e882e35da69ea7bb6bfc74e3cafc1c7`

**Görev belge tabanı:** `adbf8ca5ec31b2804fab12467125980dd3f3d298`

**Ölçüm tarihi:** 23 Ağustos 2026

Bu dosya refactor kararı değil, ölçüm ve sahiplik kaydıdır. Satır sayısı tek
başına kusur veya bölme gerekçesi değildir. Kullanıcı davranışı, state
sahipliği, yaşam döngüsü, bağımlılık ve test sınırı birlikte incelenmeden ürün
kodunda davranış değişikliği yapılmaz.

Altı kaynak dosyanın normalize SHA-256 ve yapı sayıları
`docs/ARCHITECTURE_INVENTORY.json` içindedir. Regresyon testi bu değerleri canlı
kaynakla karşılaştırır; bu dosyalardan biri değişip envanter güncellenmezse CI
fail-closed durur.

## Yapısal ölçüm

| Modül | Satır | Yapı | Benzersiz `self` state | Timer/thread/native izi | Doğrudan owner alanı | İlgili test dosyası |
| --- | ---: | --- | ---: | --- | ---: | ---: |
| `app/video_frame.py` | 2623 | 3 sınıf, 3 üst işlev, 110 girintili işlev/yöntem | 64 | 12 / 1 / 12 | 48 | 52 |
| `app/media_controls.py` | 1288 | 61 üst işlev, 2 iç işlev | 0 | 0 / 0 / 2 | 38 | 23 |
| `app/player.py` | 1209 | 1 sınıf, 1 üst işlev, 78 girintili işlev/yöntem | 53 | 6 / 2 / 5 | 22 | 72 |
| `app/playlist_panel.py` | 1102 | 5 sınıf, 72 girintili işlev/yöntem | 41 | 0 / 0 / 0* | 6 | 7 |
| `app/menu_actions.py` | 1082 | 35 üst işlev, 5 iç işlev | 0 | 0 / 0 / 3 | 58 | 19 |
| `app/updater.py` | 1028 | 4 sınıf, 19 üst işlev, 27 girintili işlev/yöntem | 19 | 0 / 4 / 7 | 1 | 4 |

`self` state değeri dosyadaki bütün sınıfların benzersiz doğrudan atamalarını;
owner alanı `player`, `main_window` veya `video_frame` üzerinden erişilen
benzersiz alanları sayar. Timer/thread/native izi metinsel aday sayımıdır,
çalışma zamanı kapsaması değildir. Test dosyası sütunu doğrudan modül veya
ana sembol referansı taşıyan dosyaları gösterir; test sayısı veya coverage
yüzdesi değildir. `playlist_panel.py` doğrudan thread oluşturmaz, fakat sahipli
`ThumbnailService` yaşam döngüsünü açıp kapatır.

## Modül sorumlulukları ve sınırlar

### `video_frame.py`

- Görünür davranış: sinematik kontrol katmanı, fade/auto-hide/hit alanları,
  OSD, boş ekran, playlist penceresi sahipliği, PiP/tam ekran, fare/klavye,
  sağ-tık menüsü ve altyazı güvenli bandı.
- State/yaşam döngüsü: 64 state alanıyla en yoğun dosyadır. Ayrı top-level
  overlay/OSD yüzeylerini ve timer'ları oluşturur, event filter kurar ve
  kapanışta `release_overlay_surfaces()` ile bırakır.
- Thread/native sınır: `SubtitleTrackWatcher` libmpv callback'lerini kilit ve
  queued Qt sinyaliyle ana thread'e taşır; attach/detach exact callback
  kimliğine bağlıdır. Win32 foreground ölçümü ve layered pencere davranışı da
  bu dosyadadır.
- Bağımlılık: `player.py` yalnız buradaki `VideoFrame` ve
  `SubtitleTrackWatcher`ı içe alır; dosya ise 48 doğrudan ana-pencere alanına,
  `PlaylistPanel`a ve menü yardımcılarına erişir.
- Test/gerçek risk: overlay, subtitle safe band, foreground, z-order,
  fullscreen, resize ve shutdown testleri geniştir; gerçek çoklu
  monitör/DPI/HDR kabulü henüz Windows matrisinde PASS değildir.
- Karar: en yüksek yapısal risklerden biridir, fakat ilk toplu refactor hedefi
  değildir. Overlay, subtitle band veya fullscreen state'i başlangıç P0 kanıtı
  olmadan taşınmaz. `SubtitleTrackWatcher` ayrı bir aday dikiştir, ancak native
  callback yaşam döngüsü nedeniyle ilk deneme için seçilmez.

### `player.py`

- Görünür davranış: ana pencere kompozisyonu, libmpv kurulumu/callback'leri,
  periyodik UI senkronu, sürükle-bırak, son açılanlar, PiP/pencere modları ve
  diğer modüllere facade yöntemleri.
- State/yaşam döngüsü: 53 state alanı; MPV, ana timer, subtitle watcher,
  subtitle session, media-info penceresi, resize filter, playlist paneli ve
  overlay kapanış sırasının sahibi.
- Kritik sıra: subtitle işleri drenajı → timer/info/URL temizliği → watcher
  detach → overlay/playlist/resize temizliği → fullscreen çıkışı → MPV
  `stop()` → `terminate()`.
- Bağımlılık/test: uygulama katmanının kompozisyon köküdür; 72 test dosyası
  doğrudan sembol veya modül referansı taşır. Orkestratör rolü korunmalı,
  ayrıntı state sahipliği başka modüle gerçekten geçtiğinde küçülmelidir.
- Karar: yüksek riskli ikinci alan. Yalnız satır azaltmak için wrapper veya
  kapanış sırası taşınmaz.

### `playlist_panel.py`

- Görünür davranış: satır çizimi/küçük resim, filtre, dahili ve harici
  sürükle-bırak, sona taşıma önizlemesi, bağımsız pencere taşıma/yapışma,
  genişlik ve açılış/kapanış animasyonu.
- State/yaşam döngüsü: state beş sınıfa bölünmüştür. `WindowPlacement` geometri
  hesabını ayırır; `PlaylistPanel` animation ve `ThumbnailService` sahibidir,
  `closeEvent()` thumbnail servisini kapatır.
- Bağımlılık: yalnız altı doğrudan player alanına erişir; altı dosya arasında
  en düşük owner bağımlılıklarından biridir.
- Test/karar: yerleşim ve snap saf işlevleri doğrudan testlidir. Sınıfı başka
  dosyaya taşımak tek başına mimari kazanım sağlamaz; panel şu anda görece
  uyumlu bir bileşendir ve ilk hedef değildir.

### `media_controls.py`

- Görünür davranış: dosya/klasör/recent/URL açma, URL yükleme state'i, altyazı,
  seek/oynatma/ses, playlist, ekran görüntüsü ve hız.
- State/yaşam döngüsü: kendi sınıf state'i yoktur; 61 üst işlev 38 farklı
  player alanını doğrudan okur/yazar. Yani risk iç state'ten değil alanların
  aynı modülde karışmasından gelir.
- Bağımlılık: `player.py` geniş facade için, `menu_actions.py` ise yalnız
  `is_remote_media_url` ve `safe_media_host` için bu modülü içe alır.
- Test: klasör sıralama işlevlerinin doğrudan testleri; URL/IPC normalizasyonu
  için `test_url_loading_regressions.py` içindeki geçersiz şema ve hedef
  davranış testleri vardır. Taşıma öncesinde yeni yaprak modülün doğrudan
  sözleşmesi ayrıca yazılmalıdır.
- Karar: ilk düşük-riskli ayrıştırma için en uygun modüldür; MPV/Qt yaşam
  döngüsüne dokunmadan state'siz hedef çözümleme sınırı çıkarılabilir.

### `menu_actions.py`

- Görünür davranış: ana menü kurulumu, subtitle/video ayarları, recent
  etiketleri, track/device/chapter menüleri, log ve media-info pencereleri,
  kısayol/dil/hakkında ve güncelleme eylemi.
- State/yaşam döngüsü: yerel sınıf state'i yoktur, ancak 58 player alanına
  erişir ve 59 sinyal bağlantısı kurar. Modeless media-info penceresinin kimlik
  korumalı kapanış state'ini player üzerinde yönetir.
- Bağımlılık: updater ve media-controls gibi yüksek katmanları aynı kurulum
  dosyasında birleştirir. Alan bazlı bölme ileride değerlidir, fakat ilk turda
  menü ağacını taşımak görünür davranış ve çeviri riskini gereksiz büyütür.
- Karar: media-target yaprağı çıktıktan sonra menu → media-controls kenarı
  kaldırılır; daha geniş menü bölme kararı sonraya bırakılır.

### `updater.py`

- Görünür davranış: startup/manual kontrol, modern güncelleme penceresi,
  indirme ilerlemesi, normal kapanış ve installer başlatma.
- Güvenlik/yaşam döngüsü: asset adı/host/URL/boyut/SHA-256/Ed25519 doğrulaması,
  iki QThread, kısmi dosya temizliği, launch öncesi ikinci doğrulama ve açık
  dosya kilidi aynı zincirdedir.
- Test: iki ana updater dosyasında 27 doğrudan test vardır; gerçek UAC,
  SmartScreen ve kurulu-artifact kabulü deterministik test değildir.
- Karar: çekirdek doğrulama ile dialog ileride ayrılabilir; fakat bu
  güvenlik-kritik sınır ilk refactor değildir ve installed-artifact güncelleme
  başlangıç kanıtı olmadan taşınmaz.

## Risk sıralaması

Her modül 0–3 arasında ayrı ayrı değerlendirilir:

- state sahibi sayısı;
- thread/timer/native yaşam döngüsü yoğunluğu;
- ters veya döngüsel bağımlılık;
- bir değişikliğin etkilediği görünür davranış sayısı;
- geçmiş gerçek kusur sayısı;
- native/kurulu davranış kapsamasındaki boşluk.

Ölçüm sütunları sırasıyla state (S), yaşam döngüsü/native (L), bağımlılık (D),
görünür davranış genişliği (B), geçmiş kusur yoğunluğu (K) ve gerçek-Windows
kanıt boşluğudur (E). Her biri 0–3'tür.

| Sıra | Modül | S | L | D | B | K | E | Toplam | Karar |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | `video_frame.py` | 3 | 3 | 3 | 3 | 3 | 2 | 17 | En yüksek risk; P0 olmadan bölme yok |
| 2 | `player.py` | 3 | 3 | 2 | 3 | 3 | 2 | 16 | Orkestratör; kapanış sırası korunur |
| 3 | `updater.py` | 2 | 3 | 1 | 2 | 3 | 2 | 13 | Güvenlik kritik; ilk hedef değil |
| 4 | `menu_actions.py` | 0 | 1 | 3 | 3 | 2 | 1 | 10 | Alan karışımı; görünür menü riski |
| 5 | `playlist_panel.py` | 2 | 2 | 1 | 2 | 2 | 1 | 10 | Görece uyumlu, servis kapanışı kritik |
| 6 | `media_controls.py` | 0 | 1 | 2 | 3 | 2 | 1 | 9 | State'siz ilk dikiş uygun |

Toplam puan otomatik refactor önceliği değildir. Yüksek puan daha fazla dikkat
gerektirir; ilk uygulama düşük riskli, davranışı koruyan ve ölçülebilir
bağımlılık kazanımı olan dikişten seçilir. Büyük patlama refactor yasaktır.

## İlk güvenli ayrıştırma adayı

**Öneri:** yeni yaprak modül `app/media_targets.py`.

İlk kapsam yalnız aşağıdaki state'siz veya player-state'inden bağımsız hedef/yol
işlevleridir:

- `media_suffixes`
- `natural_sort_key`
- `folder_media_files`
- `is_network_path`
- `is_remote_media_url`
- `safe_media_host`
- `normalize_media_url`
- `normalize_external_target`

Kazanım: dosya/URL güvenlik ve normalizasyon sözleşmesi MPV/Qt oynatma
işlemlerinden ayrılır; `menu_actions.py` yalnız iki güvenli sunum yardımcısı
için bütün `media_controls.py` modülüne bağımlı kalmaz. `media_controls.py`
geçişte uyumluluk importlarıyla eski çağrı yüzeyini korur; kullanıcı davranışı
ve çeviri metni değişmez.

Uygulama kapısı:

1. `docs/WINDOWS_ACCEPTANCE_MATRIX.md` P0 senaryolarını mevcut runner'larla
   eşleştir ve eksik başlangıç kanıtını belirle.
2. Yeni yaprak modül için geçerli/geçersiz URL, Windows/UNC yol, klasör
   sıralama ve güvenli host doğrudan regresyonlarını önce kırmızı çalıştır.
3. Yalnız bu sekiz işlevi taşı; open/playback/playlist state'ine dokunma.
4. Hedef deterministik testlerden sonra ilgili gerçek dosya/URL açma senaryosu
   ayrı onayla ölçülmeden daha büyük refactor'a geçme.

Bu analizde ürün kodu değiştirilmedi, native koşum/build/kurulum yapılmadı ve
hiçbir Windows matris satırı PASS'e yükseltilmedi.
