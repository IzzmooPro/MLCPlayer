# MLC Player gerçek Windows kabul matrisi

**Durum:** SÖZLEŞME HAZIR, SENARYOLAR NOT_RUN

**Plan tabanı:** `78518dd67e882e35da69ea7bb6bfc74e3cafc1c7`

**Hazırlanma tarihi:** 23 Ağustos 2026

Bu matris gerçek Windows davranışını kaydeder. Deterministik veya hosted CI
sonucu buradaki satırları PASS yapmaz. Bir sürümdeki PASS başka sürüme taşınmaz.
`BLOCKED, PASS değildir`; donanım veya exact artifact yoksa açıkça BLOCKED
yazılır.

## Sonuç sözlüğü

- `NOT_RUN`: henüz çalıştırılmadı.
- `PASSED`: beklenen davranış aynı exact commit/runtime/artifact üzerinde
  ölçüldü.
- `FAILED`: beklenen davranış sağlanmadı; otomatik tekrar yapılmaz.
- `BLOCKED`: gerekli donanım, medya, izin veya artifact yok.

## Her koşumda zorunlu kimlik

- exact commit;
- kaynak koşumunda runtime manifest ve DLL SHA-256;
- kurulu koşumda installer adı, boyutu ve artifact SHA-256;
- uygulama ve installer sürümü;
- Windows sürümü, ekran ölçeği, monitör/GPU ve ses çıkışı (mahrem veri yok);
- kullanılan medyanın türü/codec'i ve gerekiyorsa güvenli kimliği;
- komut veya manuel adımlar;
- child exit code, final marker, stderr özeti ve süreç sızıntısı sonucu;
- ölçüm zamanı ve sonucu kaydeden ledger kimliği.

## P0 — Her mimari değişiklik öncesi başlangıç çizgisi

| Kimlik | Senaryo | Beklenen kanıt | Durum |
| --- | --- | --- | --- |
| WIN-P0-01 | Uygulama açılışı ve normal kapanış | Exit 0, final marker, stderr sınıflaması, süreç sızıntısı yok | PASSED |
| WIN-P0-02 | Gerçek yerel video oynatma | Süre ilerler, kare/oynatma kanıtı vardır, medya değişmez | PASSED |
| WIN-P0-03 | Ses ve yerel altyazı parçası değiştirme | Seçim libmpv read-back ile doğrulanır | NOT_RUN |
| WIN-P0-04 | Seek, duraklatma ve devam | Zaman/state read-back beklenen aralıkta | NOT_RUN |
| WIN-P0-05 | Tam ekran, native resize ve geri dönüş | Boyut/state doğru, donma ve kontrol kaybı yok | NOT_RUN |
| WIN-P0-06 | Dosya/altyazı sürükle-bırak | Doğru medya veya altyazı uygulanır | NOT_RUN |
| WIN-P0-07 | Oynatma listesi ekleme, taşıma ve sınırlar | Sıra ve seçim korunur, son satır hedeflenebilir | NOT_RUN |
| WIN-P0-08 | İkinci uygulama örneği/IPC | Dosya veya URL ilk örneğe geçer, artık süreç yok | NOT_RUN |

Bu eşleme yalnız yürütme planıdır. **Eşleme PASS değildir**; aşağıdaki
runner'ların varlığı ve deterministik testlerin geçmesi satır durumunu
değiştirmez.

### WIN-P0-01 — Açılış ve normal kapanış

- **Deterministik sınır:** `tests/test_player_shutdown_regressions.py` ve
  `tests/test_native_shutdown_acceptance_regressions.py` marker, çağrı sırası,
  stderr ve süreç-sızıntısı sözleşmesini korur; gerçek pencereyi kanıtlamaz.
- **Native ölçüm:** `tests/native_shutdown_acceptance.py`; yalnız
  `MLC_NATIVE_SHUTDOWN_ACCEPTANCE=1` ile, gerçek videoda medya-ready sonrası
  ürünün normal kapatma yolunu fail-closed ölçer.
- **Exact girdiler:** commit, runtime manifesti ve DLL SHA-256; desteklenen
  `.mkv`/`.mp4` yolu; Windows/runtime kimliği.
- **Açık boşluk:** kaynak koşumu kurulu installer davranışı değildir.

### WIN-P0-02 — Gerçek yerel video oynatma

- **Deterministik sınır:** `tests/test_playback_lifecycle_regressions.py` ve
  `tests/test_native_matrix_runner.py` yaşam döngüsü ile fail-closed runner
  kararını korur; kare üretildiğini kanıtlamaz.
- **Native ölçüm:** `tests/run_native_overlay_matrix.py` içindeki
  `default_cinematic_video_nofocus` senaryosu duration, ilerleyen position,
  video durumu, final marker, exit ve süreç temizliğini ölçer.
- **Exact girdiler:** ortak kimliklere ek olarak güvenli fingerprint'i alınan
  gerçek, yeterli süreli video ve koşuma özel JSON çıktı yolu.
- **Açık boşluk:** bu otomasyon görüntü kalitesini insan gözüyle veya gerçek
  hoparlörden ses çıkışını doğrulamaz.

### WIN-P0-03 — Ses ve yerel altyazı parçası değiştirme

- **Deterministik sınır:** `tests/test_track_label_regressions.py`,
  `tests/test_subtitle_track_watch_regressions.py` ve yerel altyazı testleri
  seçim/state sözleşmesini korur.
- **Native ölçüm:** `tests/run_physical_acceptance.py buttons` ve `subtitles`
  grupları altyazı görünürlüğü ile CC durumunu ölçer; mevcut
  `tests/media_track_probe_child.py` track read-back sağlayabilir fakat tek
  başına fail-closed ebeveyn kabul runner'ı değildir.
- **Exact girdiler:** en az iki ses ve iki altyazı parçası içeren gerçek medya;
  ayrıca `MLC_NO_SUB_VIDEO` için altyazısız gerçek medya ve runtime kimliği.
- **Açık boşluk:** mevcut runner gerçek ses parçasını ve iki ayrı altyazı
  parçasını kullanıcı eylemiyle değiştirip ikisini de libmpv read-back ile
  kabul etmiyor. Bu satır yeni dar runner veya kayıtlı manuel adım olmadan
  PASSED yapılamaz; `buttons` grubu hoparlörü korumak için `ao=null` kullanır.

### WIN-P0-04 — Seek, duraklatma ve devam

- **Deterministik sınır:** `tests/test_overlay_timeline_seek_race_regressions.py`,
  `tests/test_resume_regressions.py` ve playback yaşam döngüsü testleri state
  geçişlerini korur.
- **Native ölçüm:** `tests/run_physical_acceptance.py buttons,timeline` gerçek
  SendInput ile pause/resume ve farklı timeline noktalarına seek uygulayıp
  libmpv state/position read-back alır.
- **Exact girdiler:** seek aralıklarını taşıyacak yeterli sürede gerçek video;
  `MLC_NATIVE_SMOKE=1`, `MLC_NATIVE_TEST_VIDEO` ve ortak runtime kimliği.
- **Açık boşluk:** fiziksel runner gerçek ses çıkışını ölçmez; bu satırın
  hedefi yalnız zaman ve oynatma state'idir.

### WIN-P0-05 — Tam ekran, native resize ve geri dönüş

- **Deterministik sınır:** `tests/test_window_modes_regressions.py`,
  `tests/test_frameless_resize_edge_delivery_regressions.py` ve
  `tests/test_native_resize_input_safety_regressions.py` geometri/girdi
  sözleşmesini korur.
- **Native ölçüm:** `tests/run_physical_acceptance.py window_resize,fullscreen`
  gerçek kenar SendInput, tam ekran düğmesi ve Esc dönüşünü ölçer.
- **Exact girdiler:** gerçek video, mevcut ekran/DPI/monitör bilgisi, runtime
  kimliği ve fiziksel runner izolasyon dizini.
- **Açık boşluk:** tek monitör/tek DPI sonucu P1 çoklu monitör ve farklı DPI
  satırlarına taşınmaz.

### WIN-P0-06 — Dosya ve altyazı sürükle-bırak

- **Deterministik sınır:** `tests/test_subtitle_drop_activation_regressions.py`
  ve playlist/drop sözleşmesi testleri doğru hedef ayrımını korur.
- **Native ölçüm:** `tests/run_physical_acceptance.py dragdrop` mevcut haliyle
  bilerek `BLOCKED` üretir; Explorer OLE sürükle-bırak otomasyonu yoktur ve
  doğrudan `add_external_files()` çağrısını fiziksel PASS saymaz.
- **Exact girdiler:** Explorer'dan sürüklenecek gerçek video ve ona ait yerel
  altyazı; başlangıç playlist/track durumu; ekran ve runtime kimliği.
- **Açık boşluk:** gerçek Explorer dosya bırakma ve ayrı altyazı bırakma için
  kayıtlı manuel kabul veya güvenilir yeni native otomasyon gerekir.

### WIN-P0-07 — Oynatma listesi ekleme, taşıma ve sınırlar

- **Deterministik sınır:** `tests/test_playlist_panel_regressions.py` ve
  `tests/test_playlist_wrap_regressions.py` sıra, bırakma hedefi ve sınır
  davranışını korur.
- **Native ölçüm:** `tests/run_physical_acceptance.py buttons,thumbnails`
  çoklu playlistte önceki/sonraki yükleme ve satır-medya eşliğini ölçer;
  `tests/native_acceptance_smoke_child.py` ekleme/aktif satır için yardımcı
  native kanıttır, fakat fiziksel yeniden sıralama kabulü değildir.
- **Exact girdiler:** birbirinden ayırt edilebilir en az üç gerçek video,
  `MLC_PLAYLIST_VIDEOS` sırası, runtime ve ekran kimliği.
- **Açık boşluk:** satırı fareyle taşıma, ilk satırı en sona bırakma ve son
  satırın altındaki hedef çizgisi mevcut native runner'da ölçülmüyor. Bu
  davranış ayrıca manuel veya dar native kabul gerektirir.

### WIN-P0-08 — İkinci örnek ve IPC

- **Deterministik sınır:** `tests/test_single_instance_regressions.py` mutex,
  dosya/URL iletimi ve güvenli mesaj sözleşmesini korur.
- **Native ölçüm:** exact commit için fail-closed ikinci-örnek/IPC runner'ı
  yoktur. Eski kullanıcı kabulü yeni başlangıç çizgisine aktarılmaz.
- **Exact girdiler:** temiz ilk kaynak örneği, gerçek yerel video, güvenli URL,
  iki süreç PID'i, IPC port/mutex durumu, final process inventory ve runtime
  kimliği.
- **Açık boşluk:** dosya ve URL iki ayrı gerçek koşumda ilk örneğe geçmeden,
  ikinci süreç çıkmadan ve artık süreç olmadığı kaydedilmeden PASSED yazılmaz.

## Önerilen yürütme sırası

1. Kısa otomatik çekirdek: `native_shutdown_acceptance.py` ve yalnız
   `default_cinematic_video_nofocus` overlay senaryosu.
2. Fiziksel etkileşim paketi: `buttons,timeline,window_resize,fullscreen`;
   aynı medya/playlist girdileriyle tek kez.
3. Eksik kabul paketi: parça değiştirme, Explorer video/altyazı bırakma,
   playlist son-hedef taşıma ve iki IPC senaryosu. Mevcut runner bunları tam
   ölçmediği için önce dar runner mı kayıtlı manuel adım mı kullanılacağı
   kararlaştırılır.

Her paket ayrı onayla başlar. Başarısız paket otomatik tekrarlanmaz; ilk gerçek
neden incelenir. İlk iki paket üçüncü paketin boşluklarını PASS yapmaz.

## P0 kaynak-native sonuçları — `69af424`

Ortak kimlik: Windows 11 Pro `10.0.26200` 64 bit, 2560x1440/180 Hz,
ölçülen DPI `96`, NVIDIA GeForce RTX 4070 Ti sürücü `32.0.16.1088` ve AMD
Radeon Graphics sürücü `32.0.21045.1000`. Kaynak runtime `mpv-2.dll`
`112772608` bayt, SHA-256
`de80329f5c019ba2ee48184b5dc1e1d0c2ee9eeba3f1fb7959f20b4b0f684f4e`.
Gerçek MP4 `345752445` bayt, SHA-256
`c3e53407690d6738a09b74655dd81296c8637015d835cf503ebc54787b6834a9`;
koşum öncesi/sonrası değer aynıdır.

- `WIN-P0-01` **PASSED** (`EV-20260823-019`): özel opt-in kapanış kapısı
  exit 0, `1 passed in 2.62s`, tam marker/stderr/süreç-sızıntısı sözleşmesiyle
  tamamlandı.
- `WIN-P0-02` **FAILED** (`EV-20260823-020`): duration `5071.726`, position
  `4.6`, gerçek video ve `MARK_DONE` oluştu; davranış hatası ve child süreç
  sızıntısı yoktu. Buna rağmen süreç kapanışta `0xC0000005` döndürdüğü için
  fail-closed runner exit 1 verdi. Otomatik tekrar yapılmadı.
- İlk neden kaynak incelemesi, eski `native_overlay_smoke_child.py` akışının
  ürünün `player.close()` temizliğinden önce `mpv.stop()/terminate()` çağırıp
  300 ms daha canlı UI timer'ı bıraktığını gösterdi. Üç
  `UI update error: 'NoneType' object has no attribute 'track_list'` satırı
  tam bu aralıkta oluştu. Bu, oynatma kanıtını silmez fakat runner exit kapısı
  düzeltilmeden satırı PASS yapmaya da yetmez.
- `EV-20260823-021` ile test-only kapanış sırası regresyon-first kanonik
  `player.close()` yoluna geçirildi; ilgili deterministik grup **102 passed /
  2 skipped / 0 failed** verdi. Native retry henüz yapılmadığı için
  `WIN-P0-02` **FAILED** kalır.
- Exact `98f4440` üzerindeki tek onaylı retry (`EV-20260823-022`) önceki geç
  UI hatalarını kaldırdı ve gerçek oynatma + bütün marker'ları üretti; ancak
  child `MARK_DONE` sonrasında normal Python/libmpv finalizasyonunda yine
  `0xC0000005` döndürdü. Kalan test-only boşluk flush + `os._exit`
  sözleşmesidir; ek retry yapılmadı ve satır **FAILED** kalır.
- Bu test-only boşluk `EV-20260823-023` ile regresyon-first kapatıldı: hedef
  test önce **1 failed**, sonra **1 passed**; ilgili deterministik grup **103
  passed / 2 skipped / 0 failed** verdi. Ürün kodu değişmedi ve native retry
  yapılmadı; bu nedenle satır hâlâ **FAILED** durumundadır.
- Exact `9ef4935` üzerindeki ayrı onaylı tek native retry
  (`EV-20260823-024`) aynı MP4 ve DLL parmak izleriyle duration `5071.726`,
  position `4.633`, tam `RESULTS`/`MARK_DONE`, exit `0` ve sıfır süreç
  sızıntısı verdi. Koşum sonrası medya/runtime hash'leri değişmedi;
  `WIN-P0-02` artık **PASSED** durumundadır.

Exact iki ebeveynli master `36f418e` üzerinde aynı MP4 ve DLL ile ayrı
onaylanan fiziksel `buttons,timeline,window_resize,fullscreen` paketi
`EV-20260824-002` olarak **FAILED** kaldı. `buttons` child'ı altı PASS yanında
`cc_on[closed]` için bir FAIL üretti; ardından oynatma-listesi sonu modalı
kapanmadan 600 saniyelik grup timeout'unu beklediği için kullanıcı koşumu
durdurdu. `MARK_DONE` ve özet yoktur; diğer üç grup başlamadı. Bu nedenle
`WIN-P0-04` ve `WIN-P0-05` tabloda `NOT_RUN` kalır. Otomatik tekrar yapılmaz;
önce CC önkoşulu ile modal/timeout harness sözleşmesi regresyon-first ayrılır.

`EV-20260824-004` bu ayrımı deterministic olarak kapattı: gerçek altyazı
track'i veya lineer playlist hedefi yoksa fiziksel tıklama yapılmadan açık
`BLOCKED` yazılır; ölçülebilir önceki/sonraki tıklamasında beklenmedik modal
900 ms sonra gerçek Esc ile bounded kapatılır. Seçili paket grup üst sınırları
`buttons=180`, `timeline=300`, `window_resize=180`, `fullscreen=120` saniyedir.
İlgili harness ailesi **131 passed / 0 failed** verdi. Bu native PASS değildir;
aynı tek MP4 eksik altyazı/playlist önkoşullarını kendiliğinden sağlamaz ve
iki P0 satırı `NOT_RUN` kalır.

Exact iki ebeveynli master `227550d` üzerinde ayrı onaylı yalnız `buttons`
grubu `EV-20260824-006` olarak ilk denemede **PASS** verdi: 44,4 saniye, exit
`0`, `MARK_DONE`, **21 PASS / 0 FAIL / 0 BLOCKED**, kanonik `stop -> terminate`
ve sıfır süreç sızıntısı. Kapalı ve açık playlist panelinde CC on/off,
oynat/duraklat, sessiz, ses kaydırıcısı, ayarlar, sonraki/önceki ve tam ekran
düğmeleri gerçek SendInput/read-back ile geçti. Girdi, aynı doğrulanmış MP4'ün
iki ayrı hardlink playlist yolu ve ürünün SRT otomatik-etkinleştirme yoluna
girmeyen aynı-gövdeli gerçek ASS track'idir. Bu dar başarı tek başına
`WIN-P0-03`, `WIN-P0-04`, `WIN-P0-05` veya `WIN-P0-07` satırını PASS yapmaz:
timeline ile seek, native resize/fullscreen grup ölçümü, gerçek çoklu parça
değişimi ve birbirinden ayırt edilebilir üç videolu yeniden sıralama hâlâ
ayrıdır.

Exact iki ebeveynli master `b68a3c7` üzerinde ayrı onaylı yalnız `timeline`
grubu `EV-20260824-008` olarak ilk denemede **PASS** verdi: 148,6 saniye, exit
`0`, `MARK_DONE`, **58 PASS / 0 FAIL / 0 BLOCKED**, kanonik
`stop -> terminate` ve sıfır süreç sızıntısı. Kapalı playlist, açık playlist
ve tam ekran fazlarında fiziksel 10/25/50/75/90 yüzde tıklamaları, üst/alt hit
bantları, hızlı/yavaş sürükleme ve dışarı sürükleme temizliği geçti. Değer
hatası sıfır; tıklama zaman hatası 0,40–0,46 saniye, sürükleme zaman hatası
1,43–1,49 saniye ve 5,07 saniyelik kabul sınırı içindedir. Bu sonuç fiziksel
seek'i kanıtlar; aynı exact committe pause/resume ölçümü olmadığı için
`WIN-P0-04` durumu **NOT_RUN** olarak korunur. `window_resize` ve dedicated
`fullscreen` grupları çalışmadığından `WIN-P0-05` de **NOT_RUN** kalır.

Exact iki ebeveynli master `346603b` üzerinde ayrı onaylı yalnız
`window_resize` grubu `EV-20260824-010` olarak ilk denemede **PASS** verdi:
40,4 saniye, exit `0`, `MARK_DONE`, **12 PASS / 0 FAIL / 0 BLOCKED**, kanonik
`stop -> terminate` ve sıfır süreç sızıntısı. Dört kenar, dört köşe ve
playlist açıkken sağ/alt/sağ-alt fiziksel resize hareketlerinde hedef eksenler
tam 70 piksel değişti, diğer eksenler sabit kaldı; örtüşme yok ve tüm sorun
listeleri boştu. Dedicated `fullscreen` grubu aynı exact committe çalışmadığı
için `WIN-P0-05` durumu **NOT_RUN** olarak korunur. Farklı DPI ve çoklu monitör
kapsamı da bu dar koşumun dışındadır.

Exact iki ebeveynli master `460f0c5` üzerinde ayrı onaylı yalnız `fullscreen`
grubu `EV-20260824-012` olarak ilk denemede **PASS** verdi: 7,3 saniye, exit
`0`, `MARK_DONE`, **4 PASS / 0 FAIL / 0 BLOCKED**, kanonik
`stop -> terminate` ve sıfır süreç sızıntısı. Gerçek düğme tıklaması pencereyi
tam 2560x1440 ekran geometrisine taşıdı; gerçek Esc 960x600 varsayılan boyuta
ve ekran merkezine döndürdü, playlist kapalı ve overlay görünür kaldı. Resize
PASS'i farklı exact commit `346603b` üzerindedir; bu nedenle iki ayrı native
sonuç birleştirilerek `WIN-P0-05` yükseltilmez ve durum **NOT_RUN** kalır. Satırı
kapatmak için tek exact committe birleşik `window_resize,fullscreen` koşumu
veya eşdeğer kayıtlı manuel kabul gerekir.

Bu sonuç kaynak-native kanıttır; kurulu v0.39 artifact kabulü değildir.

## P1 — Ortam ve dayanıklılık

| Kimlik | Senaryo | Beklenen kanıt | Durum |
| --- | --- | --- | --- |
| WIN-P1-01 | Çoklu monitör arasında taşıma | Pencere/overlay doğru ekranda ve erişilebilir | NOT_RUN |
| WIN-P1-02 | Farklı DPI/ölçek | Kontroller taşmaz, hit alanları görselle eşleşir | NOT_RUN |
| WIN-P1-03 | Ses cihazı değiştirme | Donma/çökme yok; sonuç açıkça kaydedilir | NOT_RUN |
| WIN-P1-04 | Ağ videosunda bağlantı kesilmesi | Sır temiz hata, gizli veri yok, UI geri döner | NOT_RUN |
| WIN-P1-05 | Uzun oynatma listesi | Etkileşim ve kapanış kabul edilebilir, sızıntı yok | NOT_RUN |
| WIN-P1-06 | Uyku/uyanma veya ekran kilidi | Oynatma ve pencere durumu açık sonuçla kaydedilir | NOT_RUN |

## P2 — Donanıma bağlı kapsam

| Kimlik | Senaryo | Beklenen kanıt | Durum |
| --- | --- | --- | --- |
| WIN-P2-01 | HDR ekran ve HDR medya | Gerçek HDR donanımı/Windows ayarıyla görüntü yolu | BLOCKED |
| WIN-P2-02 | Bluetooth ses gecikmesi/değişimi | Gerçek Bluetooth cihazıyla davranış ölçümü | BLOCKED |
| WIN-P2-03 | Birden fazla GPU/driver yolu | Kullanılan GPU/driver açık, oynatma sonucu ölçülü | BLOCKED |

P2 satırları uygun donanım doğrulanmadan çalıştırılmaz ve PASSED yazılmaz.

## Var olan araçların yeniden kullanımı

- `tests/run_physical_acceptance.py`
- `tests/run_native_overlay_matrix.py`
- `tests/run_subtitle_visual_acceptance.py`
- `tests/native_feature_acceptance.py`
- `tests/native_shutdown_acceptance.py`

Yeni runner ancak mevcut araç kesin olarak senaryoyu ölçemiyorsa ve önce bu
boşluk belgelenirse eklenir.

## İlk sıradaki çalışma

P0 satırlarını mevcut runner ve testlerle eşleştir. Eksik ölçümleri yaz; hiçbir
native koşumu veya kurulum açık kullanıcı onayı olmadan başlatma.
