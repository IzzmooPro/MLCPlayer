# MLC Player güncel durum

Güncelleme: 15 Ağustos 2026

## Durum

- HEAD: `0d7c1e8 Add modern frameless player title bar`
- Çalışma ağacı bilinçli olarak kirli; hiçbir şey commit edilmedi.
- Son tam doğrulama: `pytest -q` → **2662 passed, 15 skipped**; son
  ClickableSlider stale-widget hedef testi ayrıca **10/10 passed**. Tam paket
  bu küçük harness turundan sonra kullanıcı kararıyla yeniden koşulmadı.
  Daha sonraki yerel-SRT otomatik etkinleştirme hedef testi **38/38 passed**;
  bu dar turdan sonra tam paket özellikle yeniden çalıştırılmadı.
- Son tur (15 Ağustos 2026): frameless resize kenar/köşe düzeltmesi
  (`app/title_bar.py::_window_position`) **6/6**, dar regresyon **120/120**;
  native resize harness'i fail-closed yapıldı **6/6**. Ardından `Klasör Aç` +
  parça değişimi + yerel SRT birleşimi tek testle kilitlendi **1/1**; o adımda
  ürün kodu değişmedi. Tam paket ve fiziksel matris bu dar turlardan sonra
  bilerek çalıştırılmadı.
- URL turu (dar): `open_url()` artık adresi doğruluyor (yalnız `http`/`https`
  + boş olmayan hostname), `Bağlantı açılıyor…` durumu gösteriyor ve URL
  yaşam döngüsü yerel `_load_started_at` akışından AYRILDI
  (`_url_loading_active` / `_url_loading_started_at`, `time.monotonic`).
  Süre TEK BAŞINA hata sayılmıyor; hata yalnız MPV gerçekten `core-idle`
  dönerse veriliyor. Ham URL artık loga yazılmıyor (`sanitize_media_url`).
  Hedef test `tests/test_url_loading_regressions.py` **31/31 passed**.
  Paketleme (yt-dlp/EJS/spec) ve gerçek ağ testi bu turda YAPILMADI.
- URL gizliliği (dar): uzak adres artık pencere başlığında TAM gösterilmiyor
  (yalnız güvenli `host[:port]`), `QSettings["recent_files"]` içine ASLA
  yazılmıyor ve menü etiketi/tooltip/statusTip yalnız host taşıyor; gerçek
  hedef oturum boyunca yalnız bellekte ve `QAction.data()` içinde. Eski
  kayıtlardaki http/https girdileri açılışta geri yüklenmiyor ve ayar bir kez
  normalize ediliyor. Yerel geçmiş ve 10 kayıt sınırı korundu. Programın
  yeniden açılışında URL geçmişinin gelmemesi BİLİNÇLİ karardır.
  `tests/test_url_privacy_regressions.py` **20/20**,
  `tests/test_url_loading_regressions.py` **31/31**,
  `tests/test_media_folder_recent_regressions.py` **113/113**.
- Paketleme hazirligi (dar): resmi `yt-dlp 2026.07.04` ve `deno v2.9.5`
  ikilileri release checksum dosyalariyla dogrulanip `bin/` altina alindi
  (Git'e girmez; `bin/RUNTIME_MANIFEST.txt` izlenir). Yeni saf
  `app/runtime_binaries.py` TEK runtime kaynagidir: sistem taramasi/fallback
  ve runtime indirme YOK, PATH yalniz SUREC icinde ve idempotent degisir,
  mpv'ye `ytdl_hook-ytdl_path` ile paketteki tam yol verilir. `MLCPlayer.spec`
  onedir + `COLLECT`e cevrildi (`libmpv.dll.a` cikarildi, UPX kapali),
  `requirements.txt` artik Python `yt-dlp` istemiyor.
  `tests/test_runtime_binaries_regressions.py` **24/24**.
  dist build, setup, ag testi ve YouTube kabulu bu turda YAPILMADI.
- Paketleme sertlestirme (dar): site cikarimi artik YALNIZ paketli yt-dlp VE
  deno birlikte varsa aciliyor (`build_ytdl_config`); herhangi biri eksikse
  `ytdl=False` yazilip mpv'nin sistem PATH aramasi kapatiliyor, dogrudan
  HTTP/HLS oynatma etkilenmiyor. Guvenli onarim mesaji gercek
  `open_url -> update_url_loading -> show_user_error` zincirine baglandi.
  Resmi `yt-dlp-THIRD_PARTY_LICENSES.txt` (231397 B) exact hash ile alinip
  paketlendi; birlesik executable'in GPLv3+ kapsami belgede duzeltildi.
  Spec'e `contents_directory='_internal'` sabitlendi ve PACKAGING_PLAN
  icindeki kontrol karakterleri temizlendi.
  `tests/test_runtime_binaries_regressions.py` **41/41** (son fail-closed
  senaryosu dahil: exact yol uretilemezse `ytdl` acilmaz).
- Uygulama ikonu (dar): kullanicinin sectigi logo `assets/mlc-player-icon.png`
  (1254x1254 RGBA, degistirilmeden) ve ondan LANCZOS ile uretilen
  `assets/mlc-player-icon.ico` (16-256 px, 9 boyut) projeye alindi; olcu ve
  SHA-256 `assets/ICON_MANIFEST.txt` icinde. Yeni `app/app_icon.py` TEK
  kaynaktir: onbellekli QIcon, frozen/gelistirme yolu, eksik assette
  fallback YOK. `main.py` QApplication'dan hemen sonra pencere olusmadan
  ONCE ortak ikonu ve sabit `MLCPlayer.MLCPlayer` AppUserModelID'sini
  kuruyor; butun ust seviye pencereler bunu miras aliyor. `player.py`
  icindeki `SP_DriveDVDIcon` KALDIRILDI, `title_bar.py` yazinin soluna
  20 px logo ekledi (fare olaylarini gecirir). Spec `icon=` + `_internal
  assets` tasiyor; setup ikon alanlari plana yazildi.
  `tests/test_app_icon_regressions.py` **32/32**.
  PyInstaller build, dist ve setup bu turda YAPILMADI.
- **Tam paket yeşil (bu tur):** `pytest -q tests` → **3140 passed, 15 skipped,
  0 failed**. Öncesinde üç bağımsız koşum 78 / 54 / 78 FAIL veriyordu; ayrıntı
  aşağıdaki "Tam paket kırmızısı" bölümünde.
- Commit/push/EXE/setup yapılmadı.

## Aralıklı child takılması — KISMİ (15 Ağustos 2026)

**Kök neden BULUNAMADI. Bu bölüm ne bulunduğunu ve neyin elenmiş
olduğunu kaydeder; sorun AÇIK.**

Belirti: `pytest -q tests` turlarında aralıklarla bir ölçüm child'ı
`subprocess.TimeoutExpired` ile düşüyor (180 sn). Dört kez görüldü;
iki farklı dosyada (`test_default_cinematic_ui_regressions`,
`test_classic_ui_removal_regressions`) ve iki farklı child'da
(`default_ui_child.py`, `main_entry_child.py`).

**Elenen hipotezler (ölçümle):**

- Child'ın kendisi yavaş/bozuk DEĞİL: doğrudan çalıştırıldığında
  **36/36** koşumda 0,3-0,5 sn, exit=0.
- Boru (`capture_output=True`) yolu değil: aynı çağrı biçimiyle **6/6** temiz.
- libmpv ses aygıtı çekişmesi değil: **4 paralel × 5 tur = 20 child**,
  takılma 0.
- Kapanış (finalizasyon) fazı değil: yeni teşhis `olcum uretilmis mi:
  HAYIR` dedi — child HİÇ çıktı üretmeden asılı kalıyor, yani takılma
  AÇILIŞ fazında.

**Bu turda yapılanlar (hepsi harness):**

- `test_default_cinematic_ui_regressions.py`: child timeout'u **180 → 60 sn**
  (ölçülen gerçek süre 0,3-1,4 sn). Timeout artık çıplak `TimeoutExpired`
  değil; ölçümün üretilip üretilmediğini, SON FAZI, bütün fazları ve env'i
  taşıyan bir `AssertionError` veriyor.
- `default_ui_child.py`: açılış fazı işaretleri (`PHASE qapplication` →
  `mpvplayer_init` → `mpvplayer_ready` → `shown`), STDERR'e. Ölçüm
  sözleşmesi (stdout'taki tek JSON satırı) DEĞİŞMEDİ. Bir sonraki
  takılmada faz doğrudan görünecek.
- **Ayrı ve gerçek bir risk kapatıldı:** libmpv yükleyen 6 varsayılan child
  (`default_ui`, `layout`, `main_entry`, `smoke`, `timeline`, `title_bar`)
  normal Python finalizasyonuna giriyordu. `main.py:130` bu tehlikeyi
  ürünün kendi sözleriyle belgeliyor ("mpv DLL'leri interpreter kapanışında
  TAKILIYOR") ve `os._exit(ret)` kullanıyor. Child'lar artık flush + `os._exit`
  ile aynı politikayı izliyor. `startup_audio_device_scan_child.py` BİLİNÇLİ
  istisnadır: o fazdaki çökmeyi ölçmek için finalizasyona girer.
  Sözleşme: `tests/test_child_shutdown_contract_regressions.py`.
  **Bu değişiklik gözlenen takılmayı ÇÖZMEZ**; ayrı bir riski kapatır.

**Sonraki adım:** takılma bir daha görüldüğünde raporlanan SON FAZ okunacak.
Faz `mpvplayer_init` ise şüphe libmpv/ses aygıtı açılışında, `qapplication`
ise Qt platform kurulumundadır. Yeni hipotez olmadan tekrar koşulmayacak.

## Tam paket kırmızısı — Qt platform sızıntısı (15 Ağustos 2026)

**Kırmızı kanıt:** `pytest -q tests` 78 / 54 / 78 FAIL (koşuma göre değişken).
Başarısızlıkların tamamı overlay görünürlük, opaklık ve geometri ölçümleriydi
(`overlay_button_hit` 11, `overlay_autohide` 10, `overlay_right_controls` 9,
`overlay_hit_alpha` 9, `overlay_fade` 8, `overlay_responsive` 7, `overlay` 6,
`overlay_subtitle_state` 5, `overlay_visual` 4, `subtitle_timing` 3,
`playlist_panel` 2, `overlay_foreground_ownership` 2, `title_bar_hardening` 1,
`overlay_timeline_hit` 1). **Her dosya tek başına yeşildi.**

Geçici teşhis eklentisiyle başarısızlık anındaki gerçek durum ölçüldü:

    overlay_visible: True   overlay_opacity: 0.0   fade_state: Running
    suppressed: False       window_geom: QRect(640, 336, 1280, 720)
    platform: windows

**Kök neden (ürün DEĞİL, harness):** `tests/native_resize_diag_child.py` ayrı
süreçte gerçek pencereyle koşmak için modül düzeyinde
`os.environ.pop("QT_QPA_PLATFORM", None)` yapar — bu DOĞRUDUR ve değişmedi.
Ancak `test_native_resize_input_safety_regressions.py::child_module` fixture'ı
aynı modülü `exec_module()` ile SÜREÇ İÇİNDE çalıştırıyor; pop pytest sürecinin
ortamını kalıcı bozuyordu. QApplication sonradan gerçek `windows` platformunda
kuruluyor, pencereler ekranda konumlanıyor, fade gerçek zamanla ilerliyor ve
`_foreground_measurement_supported()` açılıyordu. Fixture `MLC_NATIVE_SMOKE`'u
zaten kaydedip geri yüklüyordu, `QT_QPA_PLATFORM` unutulmuştu. Alfabetik sırada
bu dosya bütün `test_overlay_*` dosyalarından önce geldiği için sızıntı onlara
vuruyordu; FAIL sayısının değişmesi gerçek pencere zamanlamasındandı.

Düzeltme: fixture anahtarı `finally` içinde geri yükler. Sözleşme
`tests/test_qt_platform_env_leak_regressions.py` (3 test) ile kilitlendi;
biri gerçek `pytest` alt sürecinde sızdıran + kurban dosyayı birlikte koşup
exit 0 arar. Ürün kodu değişmedi. Tam paket süresi 238 sn → 54 sn.

**Kalan 4 kırmızı ayrı ve gerçek sorunlardı (tek başına da düşüyorlardı):**

- `test_subtitle_timing` × 2: taklit `placeholder_label` yalnız `hide`/`show`
  taşıyordu; ürün URL turunda `media_controls._set_placeholder_text()` ile
  `text()`/`setText()`/`setVisible()` çağırmaya başlamıştı. Gerçek `QLabel`
  bu API'yi taşıdığı için ürün kusuru değil; taklit gerçek yüzeye çevrildi.
- `test_subtitle_timing::test_mpv_auto_discovers_...`: eski beklenti
  `sub_auto == "fuzzy"`. Yerel-SRT turunda değer bilerek `exact` yapılmış ve
  `test_local_subtitle_autoload_regressions.py:109` ile kilitlenmişti; eski
  satır yeni sözleşmeyle çelişiyordu. Gevşetilmeden dönüştürüldü.
- `test_title_bar_hardening::test_right_edge_press_on_open_playlist_panel_...`:
  test yalnız `startSystemResize` yolunu kabul ediyordu. `playlist_panel` ayrı
  top-level `Qt.Tool` penceresidir, `_can_use_system_resize()` orada bilerek
  `False` döner ve ürün sınırlı manuel yedek yolu kullanır
  (`test_frameless_resize_fallback_regressions.py`). Kullanıcı sözleşmesi
  daraltılmadan gerçek yola çevrildi: doğru kenar, gerçek sürükleme başlangıcı
  ve fare yakalaması denetleniyor. Ürün kodu değişmedi.

**Kalan risk (engelleyici değil, bu turda çözülmedi):**
`tests/default_ui_child.py` / `main_entry_child.py` bazı koşumlarda 180 sn
timeout ile ERROR veriyor (`test_default_cinematic_ui_regressions`). Aynı dosya
başka koşumlarda 2,9 sn'de yeşil geçiyor. Aralıklı native child takılması;
düzeltmeden ÖNCE de vardı ve tam paket süresinin çoğunu bu tüketiyor.

## Tamamlanan ürün işleri

- Sinematik arayüz: özel başlık çubuğu, overlay, fade/auto-hide, geniş timeline, fullscreen/ESC.
- Gömülü ve genişliği sürüklenebilir playlist paneli, sıralama, thumbnail üretimi.
- Ses/altyazı parça etiketleri, gruplanmış sağ-tık menüsü, `Klasör Aç`, doğal `1-2-10` sıralaması, ortak `Son Açılanlar`.
- Medya allowlist'i genişletildi. Video: MP4/AVI/MKV/MOV/WMV/FLV/MPEG/MPG/M4V yanında WEBM/TS/M2TS/MTS/VOB/OGV/3GP/3G2/ASF/MXF; ses: MP3/WAV/FLAC/OGG/M4A yanında AAC/OPUS/WMA/APE/ALAC/AIFF/AIF/AC3/DTS/MKA. Dosya seçici, klasör taraması, playlist paneli ve ana yüzey sürükle-bırak aynı `MEDIA_EXTENSIONS` kaynağını kullanıyor; uzantı yalnız medya adayı yapar, gerçek codec desteğini libmpv belirler.
- Altyazı Merkezi: güvenli ayarlar, arama/indirme/apply yaşam döngüsü, dosyanın yanına atomik `.srt`.
- Kapanış yaşam döngüsü: idempotent `stop → terminate`, her teardown adımı kendi hata sınırında, overlay/OSD yüzeyleri ve thumbnail worker sahipli biçimde bırakılıyor.
- Overlay girdi düzeltmesi: `OVERLAY_HIT_ALPHA = 2` (`app/video_frame.py`). Layered overlay penceresinde alfa=0 pikseller Windows hit-test'inde mpv yüzeyine düşüyordu; kontroller artık gerçek tıklamayla çalışıyor. Görsel fark ölçüldü (`max_rgb_diff=2`).
- Thumbnail worker: `ao=null` + açık `vid` seçimi + kare hazır olunca screenshot + atomik taşıma; başarısızlıkta `thumbnail_failed` sinyali ve `ThumbnailService.status()` sözleşmesi (`ready|failed|loading|empty`).

## Fiziksel kabul durumu (gerçek MKV, gerçek MPV)

Ana video: `<medya>\Film\Avatar.Fire.and.Ash.2025.2160p.WEB.h265-ETHEL.mkv`
Playlist: `Obsession.2025…`, `Paddington.In.Peru.2024…`, `The.Killer.2024…` (aynı klasör, READ-ONLY).

PASS: `buttons` (21), `separator` (6), `window_resize` (12), `alttab` (7),
`toggle` (3), `thumbnails` (3), `fullscreen` (4), `subtitles` (11),
`zorder` (6). CRASH: **0**.
BLOCKED (otomasyon/girdi katmanı): `timeline` fiziksel `%90` tıklaması bazı
koşumlarda ürüne ulaşmadan başlangıç değerinde kalıyor. Gerçek `ClickableSlider`
+ gerçek `VideoFrame` ile tek offscreen QTest ölçümü **4/4 passed**: kullanıcı
tıklaması tam bir seek üretiyor, bayat MPV pozisyon güncellemesi ikinci seek
üretmiyor ve hedef kalıcı olarak ezilmiyor. Ürün yarışı kanıtlanmadı; daha fazla
otomatik tekrar yapılmayacak, final kullanıcı manuel kabulüne bırakıldı.
Eski `ClickableSlider has been deleted` çökmesi ürün kusuru
değil, kapanış sonrası eski widget referansı tutan harness kusuruydu; offscreen
gerçek `QSlider` + `sip.delete()` regresyonu **10/10 passed** ile kapandı.
Bu düzeltme sonrası native/fiziksel tekrar yapılmadı.
BLOCKED (otomasyon eksiği, PASS sayılmaz): `dragdrop/explorer_multi_drop` (Explorer OLE sürükle-bırak otomasyonu yok).

`subtitles` grubu **PASS** (11 PASS / 0 FAIL / 0 BLOCKED, child+runner exit=0,
MARK_DONE, stop → terminate → close, `ao=null`), gerçek altyazısız medya ile:
`Obsession.2025…mkv` (video track 1, gömülü altyazı 0, duration>0).
Ölçülenler: `tracks_loaded_off`, `cc_on`, `cc_off`,
`no_subtitle_media_contract`, `subtitle_state_leak` (eski `sid=1` yeni medyaya
taşınmıyor), `no_subtitle_osd` (fiziksel CC tıklaması → OSD görünür, CC beyaz,
`sub_visibility=False`, yeni sub track yok, mesaj kaybolur, modal yok, oynatma
sürüyor), `no_subtitle_osd_layout` + `osd_layout_playlist_open` +
`osd_layout_fullscreen` + `osd_layout_after_resize` (dördünde de
`overlay_overlap=False`, `gap=15px`, video alanı içinde, yatay merkezde),
`product_shutdown_path`.

**Genel MKV kullanım kabulü PASS DEĞİL** — `timeline` otomasyon BLOCKED ve
`dragdrop/explorer_multi_drop` BLOCKED açık.

## Çözülen ürün hatası: OSD–kontrol katmanı çakışması

Kanıt: `no_subtitle_osd_layout` FAIL, `osd=(736,876,128,20)` /
`overlay=(100,810,1400,110)` → çakışma; "Altyazı bulunamadı" yazısı
oynat/duraklat düğmesinin arkasında kalıyordu. Kök neden:
`VideoFrame._center_osd()` OSD'yi video alanının alt kenarından yalnız 24 px
yukarı koyuyordu, kontrol katmanı ise alttaki ~110 px'i kaplıyor.
Düzeltme: OSD'nin alt kenarı artık katmanın **gerçek**
`control_overlay.geometry()` yüksekliğinden türetilen ayrılmış bandın
`OSD_OVERLAY_GAP=14px` üstünde; katman auto-hide/opacity=0 olsa bile bant
korunuyor, kısa pencerede `OSD_EDGE_MARGIN=10px` ile video içine clamp
ediliyor, uzun metin video genişliğini aşmıyor. `resizeEvent()` artık önce
katman geometrisini güncelliyor, OSD'yi sonra yerleştiriyor. Kural
`show_osd()` kullanan bütün mesajlar için geçerli (ses/bölüm/altyazı
bildirimleri de düzeldi). Yeni timer, TOPMOST bayrağı veya sabit ekran
koordinatı eklenmedi; metin, süre, fade timer'ı, z-order sahipliği ve mouse
transparency değişmedi.

## Altyazı stil sözleşmesi (`app/subtitle_style.py`)

- MPV renk biçimi **`#AARRGGBB`**'dir. Eski kod `#RRGGBBAA` üretiyordu;
  seçilen turuncu bu yüzden MPV'de başka renge dönüşüyordu.
  Canonical çıktı büyük harf: `QColor(242,106,61,255)` → `#FFF26A3D`.
- `sub_back_color` tek başına yalnız GÖLGE rengidir. Arka plan alfası > 0
  ise `sub_border_style=background-box` + `sub_shadow_offset=0.0`;
  alfa 0 ise `outline-and-shadow`. Kenarlık rengi/kalınlığı kutu modunda
  da uygulanır.
- ASS altyazıda normal `sub_*` seçenekleri için tek geçerli değer
  `sub_ass_override="force"`; bool `True`/`"yes"` canonical sayılmaz.
- Migrasyon: `subtitle/style_schema_version = 2`. İşaret yoksa yalnız
  GERÇEKTEN var olan renk anahtarları bir kez legacy RGBA→ARGB çevrilir;
  eksik anahtar icat edilmez, ikinci açılışta tekrar çevrilmez, yazma
  hatasında ayarlar yarım kalmaz. Eski `sub_ass_override=True` → `force`,
  `False` → `no`.
- `atomic_apply()`: yedi property + şema anahtarı ya tamamen yazılır ya da
  MPV ve QSettings çağrı öncesi hâline döndürülür; `sync()` sonrası
  `status()` hatası başarı sayılmaz, dialog sahte başarıyla kapanmaz.
  Kullanıcıya tek güvenli mesaj gider (ham hata/traceback/yol yok).
  `sub_delay` politikası korunur: MPV'ye uygulanır, ayarlarda 0 saklanır.
- Bitmap/PGS parçalarda renk/stil uygulanamaz; `style_notice()` güvenli
  bilgi üretir, codec okunamıyorsa sessiz kalır (asılsız uyarı yok).
- Gerçek libmpv readback (opt-in, `vo=null`/`ao=null`,
  `tests/subtitle_style_property_smoke_child.py`): 10/10 property hatasız
  yazıldı ve geri okundu — `#FFF26A3D`, `background-box`, `force` dahil.
  Bu tur **piksel/görüntü kabulü içermez**; SRT+ASS görüntü kabulü 3. turda.

## Altyazı Ayarları penceresi (`app/subtitle_appearance_dialog.py`)

- Seçilen 2 numaralı tasarım uygulandı: varsayılan **852×476** → sol 320,
  sağ 484, oran **%60**; gerçek minimum **760×430** → sol 320, sağ 392.
  Marj bütçesi her iki görünümde de korunur: `16 | 320 | 16 | önizleme | 16`.
  %100/%125/%150 DPI'da 1366×768'e sığıyor, hiçbir kontrol kırpılmıyor.
- Önizleme minimumu 330 px'dir. Sabit 500 px minimum, 852 px pencerede sağ
  iç marjı sıfırlıyor ve pencerenin 868 px'in altına inmesini engelliyordu.
- Sol sütun: `Senkron | Boyut | Kenarlık` tek kompakt satır, `Dikey konum`
  slider + yüzde, üç renk swatch'ı yan yana (dama desenli alfa göstergesi,
  tooltip'te canonical `#AARRGGBB`). Eski tek sütunlu `QFormLayout` ve
  "Renk seç" düğmeleri kaldırıldı.
- Spin alanları ok düğmeli (`CompactSpinBox`): genişlik gerçek metin +
  stepper ölçümünden gelir (127/76/101 px). Senkron biriminin metne
  eklenmesi (`-120.0 sn`) sütunu taşırdığı için birim tooltip ve
  accessibleName'de taşınır. Spinbox'a yatay padding VERİLMEZ: padding
  verildiğinde Qt ok düğmelerini içerik kutusuna göre yerleştirip değerin
  üzerine bindiriyordu (`1,0x` → `1,0`).
- Sağ: yerel `QPainter` önizlemesi (harici asset yok), iki satır örnek
  altyazı, `Temsili video önizlemesi — gerçek video çıktısı değildir`
  etiketi. Arka plan kutusu yalnız alfa > 0 iken çizilir; uzun metin
  sarılır ve yüzeyden taşmaz. Bitmap/PGS parçada `style_notice()`
  bilgisi kendi satırında.
- **Temsili sahne (düz siyah yüzeyin yerine).** Kırmızı kanıt: eski
  yüzeyde `unique_colours=3`, piksellerin %98,6'sı en koyu bantta,
  yatayda değişen satır oranı 0,11 — kullanıcı beyaz yazının aydınlık
  gökyüzünde, koyu yazının siluette nasıl görüneceğini göremiyordu.
  `build_preview_scene()` alacakaranlık gökyüzü gradyanı, bulutlar,
  ufuk ışığı, silüet gökdelenler + pencere ışıkları, sokak lambası,
  su yansımaları, insan silueti ve köşe karartmasından oluşan 16:9
  sahneyi **tamamen `QPainter` ile, rastgelelik olmadan** çizer. Ağ,
  kullanıcı videosu veya harici/telifli asset KULLANILMAZ. Sahne
  `cover` mantığıyla ortadan kırpılır (en-boy oranı bozulmaz) ve
  yalnız boyut değiştiğinde üretilip cache'lenir (`scene_builds()`).
  `QPixmap` başlatılmamış bellekle geldiği için yüzey önce doldurulur;
  aksi halde ondalık ufuk çizgisindeki yarım piksellik dikişte çöp
  kalıyor ve aynı boyutta iki çizim farklı çıkıyordu.
  Sahne YALNIZ arka plandır: `sub_back_color` yine yalnız metnin
  arkasındaki kutuyu boyar, sahneye filtre uygulanmaz. Sözleşme
  `tests/test_subtitle_preview_scene_regressions.py` (17 test) ile
  kilitlendi.
- Dialog MPV veya QSettings referansı TUTMAZ; uygulama dışarıdan enjekte
  edilen `apply_callback` ile `app/subtitle_style.py::atomic_apply()`
  üzerinden gider. Reset/İptal/Escape/X hiçbir kalıcı değişiklik bırakmaz;
  başarısız uygulamada pencere açık kalır.
- `menu_actions.show_subtitle_settings()` 31 satırlık ince entegrasyon
  noktasına indi.
- Görsel kabul GERÇEK Windows platformunda yapıldı
  (`MLC_DIALOG_REAL_PLATFORM=1`); offscreen görüntülerde Türkçe glifler kare
  çizildiği için görsel kanıt sayılmaz.
- **Çözülen ürün hatası (3. tur kırmızı kanıtı):** boyut/senkron alanına
  değer yazıp **Enter**'a basmak `QColorDialog`'u açıyordu. Kök neden:
  `ColorSwatch` bir `QPushButton` ve `QDialog` içinde `autoDefault`
  varsayılan olarak açık; Enter ilk `autoDefault` düğmeye gidiyordu.
  Düzeltme `ColorSwatch.__init__` içinde `setAutoDefault(False)` +
  `setDefault(False)`. Arayüz DONMUYORDU (50 ms kalp atışı, en kötü
  aralık 0,069 sn); açılan pencere iç içe modal döngü kuruyordu.
  Regresyon: `test_enter_in_a_spin_box_does_not_open_the_colour_picker`.
- **Çözülen ürün hatası: saydam arka plandan renk seçilemiyordu.**
  `_choose()` mevcut `#00000000` rengini `QColorDialog.getColor()`
  başlangıcı olarak veriyordu; seçicide yalnız RGB değiştiren kullanıcı
  `#000020A0` (alfa 0) uyguluyor, `sub_border_style` `outline-and-shadow`
  kalıyor ve "arka plan uygulanmıyor" görüyordu. Düzeltme:
  `_picker_seed()` — YALNIZ `key == "sub_back_color"` ve alfa == 0 iken
  seçiciye verilen GEÇİCİ tohumun alfası 255 yapılır; RGB korunur, tohum
  dialog durumuna/QSettings'e yazılmaz, kullanıcı seçicide bilerek
  alfa 0 seçerse zorla değiştirilmez, İptal `#00000000`'ı korur, Yazı ve
  Kenarlık swatch'ları etkilenmez. Gerçek MPV smoke (`N` senaryosu):
  tohum alfa 255 → readback `#FF0020A0` + `background-box` → ekranda
  52.539 mavi piksel, kesintisiz dizi 748/748 px.
- Alt eylem düğmeleri gerçek Windows penceresinde %100/%125/%150 DPI ve
  hem varsayılan hem minimum boyutta ölçüldü: `Uygula` pencere içinde,
  alt boşluk 12 px, `childAt()` ile tıklanabilir, kırpılma yok. Ekran
  görüntüsündeki kırpılma izlenimi yeniden ÜRETİLEMEDİ; layout
  değiştirilmedi.

## Altyazı Ayarları penceresi — dikey/kompakt tur

Kırmızı kanıt (ölçüldü): pencere 852×476, minimum 760×430; üç
`QDoubleSpinBox` yan yana (±120 sn, 0,5–3,0×, 0–10 px) ve gerçek Windows
ölçümünde yazı alanı ile ok alanı kesişiyordu. 32 test kırmızıydı.

- **Yeni ölçüler:** `DEFAULT_SIZE=(640, 480)`, gerçek minimum
  `560×430` (gerçek Windows platformunda doğrulandı; ilk denemede 444
  çıktı, dikey bütçe kısılarak 430'a indirildi). Ayarlar ÜSTTE,
  temsili önizleme ALTTA ve tam genişlikte (640'ta 608×259, minimumda
  528×209).
- **Spinbox yok; üç hazır değer listesi** (`subtitleDelayCombo`,
  `subtitleScaleCombo`, `subtitleBorderCombo`). Gerçek sayı
  `Qt.ItemDataRole.UserRole` altında float'tır; etiket metni HİÇ parse
  edilmez. Senkron −5…+5 sn / 0,25 adım (41 değer), boyut yedi hazır
  değer (0,75–2,00×), kenarlık 0–5 px / 0,5 adım (11 değer).
- Kapalı kutuda KISA biçim (`0 sn`, `1,00×`, `3,0 px`), açılır listede
  TAM etiket (`0 sn — Senkron`, `1,15× — Biraz büyük`). Gerekçe ölçüldü:
  tam etiket 168 px, minimum pencerede kutu başına 144 px düşüyordu.
- **Ölçülen ve düzeltilen iki gerçek kusur:** (1) stylesheet uygulanan
  `QComboBox`'ta `setMaxVisibleItems()` yok sayılıyor; 41 öğelik senkron
  listesi **800 px** yüksekliğinde açılıyordu → `combobox-popup: 0` ile
  **146 px**. (2) Child raporundaki tipografik eksi (U+2212)
  yönlendirilmiş cp1254 stdout'ta `UnicodeEncodeError` verip child'ı
  exit=1 ile düşürüyordu → çıktı UTF-8'e sabitlendi.
- **Arka planda açık `Şeffaf` seçeneği:** renk hücresinde birinci ve
  görünür düğme (`subtitleTransparentButton`, erişilebilir ad "Arka planı
  şeffaf yap"); tek tıklama alfa 0 yapar, önizleme kutusu anında kaybolur
  ve `sub_border_style` `outline-and-shadow` olur. İkinci düğme mevcut
  `QColorDialog` akışıdır; alfa > 0 olunca `background-box` geri gelir,
  iptal önceki seçimi korur. Yazı/Kenarlık seçicileri değişmedi.
- **Merkezi sayısal doğrulama** `subtitle_style.normalise_subtitle_numeric()`:
  bozuk/NaN/±sonsuz/string → ürün varsayılanı; aralık dışı → en yakın
  sınır (`sub_scale 3.0→2.0`, `sub_border_size 10.0→5.0`,
  `sub_delay 120→5.0`, `sub_pos 250→100`); aralık içi ama listede yok →
  en yakın hazır değer, EŞİT uzaklıkta KÜÇÜK olan (`1.20→1.15`,
  `2.75→2.5`, `-0.125→-0.25`). Aynı fonksiyon pencere açılışında,
  `style_properties()`/`atomic_apply()` sınırında ve
  `MPVPlayer.restore_subtitle_settings()` içinde kullanılır; eski aşırı
  kayıtlar artık doğrudan MPV'ye ULAŞMAZ. `sub_pos` 0–100 ve `sub_delay`
  oturumlar arası 0 politikası DEĞİŞMEDİ.
- Pencereyi yalnız açmak QSettings'e yazmaz; `Uygula` yalnız
  normalleştirilmiş hazır değerleri kaydeder; başarısız uygulamada
  pencere açık kalır ve ham yol/hata sızmaz.
- **Gerçek Windows kabulü: 13/13 PASS** (%100 ve %150 DPI × varsayılan ve
  minimum, üç combo popup'ı, şeffaf, yarı saydam kutu, 2,00× yazı, 5 px
  kenarlık, bitmap uyarısı, uygulama hatası). Ölçülenler: `clipped=[]`,
  paneller kesişmiyor, ayarlar önizlemenin üstünde, üç alt düğme görünür
  ve `childAt()` ile tıklanabilir, popup ekran içinde ve combo'nun
  altında (`196×362` senkron, `196×212` boyut, `196×332` kenarlık),
  seçimden sonra kapanıyor. Görüntüler geçici klasörde
  (`%TEMP%\mlc-subtitle-shots`), Git'e eklenmedi.
- Uç stres senaryosu (2,00× + 28 kelimelik metin): metin dikdörtgeni
  `(21,12,565,228)`, yüzey `(0,0,608,240)` — içeride kalıyor, alt kenara
  değiyor. Bu davranış eski tasarımda da aynıydı; değiştirilmedi.
- Sözleşme: `tests/test_subtitle_appearance_compact_regressions.py`
  (83 test). Eskiyen testler gevşetilmeden dönüştürüldü ve gerekçeleri
  dosyalarına yazıldı: yatay sütun oranı ölçen 4 test
  (`test_settings_column_stays_compact`,
  `test_preview_column_is_large_enough_to_be_readable`,
  `test_preview_is_clearly_wider_than_the_settings_column`,
  `test_the_preview_stays_the_wider_half_at_any_dpi`) ve spinbox ok
  düğmesi şart koşan 4 test (`test_spinboxes_keep_their_stepper_arrows`,
  `test_the_widest_value_fits_beside_the_stepper_arrows`,
  `test_a_click_on_the_stepper_changes_the_value_by_one_step`,
  `test_the_three_spinboxes_fit_the_compact_column`).

## Altyazı için güvenli alt bant (kontrol paneliyle çakışma)

**Önce harness onarıldı.** Resmî `h_position` koşumu yeni arayüzden
sonra eskimişti: `AttributeError: 'SubtitleAppearanceDialog' object has
no attribute 'delay_spin'`. Dialog sürüşü yarıda kaldığı için `%70` ve
`%95` HİÇ uygulanmıyor, MPV ikisini de aynı okuyordu (`95.0 / 95.0`) ve
bbox merkezleri özdeşti (`y70=666 = y95=666, delta=0`). Bütün A–N
senaryolarındaki `delay_spin`/`scale_spin`/`border_spin` erişimleri
`delay_combo`/`scale_combo`/`border_combo` + ürün API'si
(`select_value()`/`value()`) ile değiştirildi; etiket metni PARSE
EDİLMEZ. Onarım sonrası aynı koşum: `70.0 / 95.0`, `y70=572 y95=666,
delta=94` (monoton aşağı).

**Ölçüm güvenilir hâle getirildi.** Eski maske altyazısız BAŞLANGIÇ
karesiyle stilli kareyi karşılaştırıyor, iki çekim arasında auto-hide
tetiklendiği için KATMAN piksellerini altyazı sanıyordu (bbox yüksekliği
334 px). Yeni yol: aynı duraklatılmış karede altyazı GÖRÜNÜR/GİZLİ
eşlenik çifti (`sub_visibility` toggle; fare ve katman durumu değişmez),
ürün paletinde bulunmayan AYIRT EDİCİ yeşil yazı rengiyle renk filtresi,
auto-hide zamanlayıcısı ölçüm boyunca dondurulur ve iki çekimdeki katman
durumu birebir aynı değilse ölçüm GEÇERSİZ sayılır. Yeni bbox yüksekliği
104 px.

**Kırmızı piksel kanıtı (ürün değişmeden, 1400×772 yüzey):**
`sub_pos=100` → bbox `(333, 635, 1065, 739)`, katman üst kenarı 662,
**boşluk −77 px** (timeline'la kesişiyor), `sub_margin_y=22`,
`sub_ass_force_margins=False`.

- **Çözüm sabit yüzde DEĞİL.** `sub_pos` kullanıcının tercihidir:
  0–100 aralığı, %100 varsayılanı ve kayıtlı `%90` tercihi korunur;
  100 üstüne çıkılmaz, panel geometrisi küçültülmez.
- **`sub-margin-y-offset` bu libmpv'de YOKTUR** (v0.36.0-131; ölçüldü).
  Var olan `sub-margin-y` kullanılır; `sub_use_margins=True` ve ASS'de de
  geçerli olması için `sub_ass_force_margins=True` yazılır.
- Marj GERÇEK ayrılmış banttan türetilir:
  `(_osd_reserved_bottom() + SUBTITLE_BAND_GAP=12) * 720 / ölçek_referansı`.
  Tek kaynak `_osd_reserved_bottom()`tur (OSD ile paylaşılır); ikinci
  kopya yoktur. Katman auto-hide ile gizlense de bant korunur (yükseklik
  kullanılır, görünürlük değil) → altyazı ZIPLAMAZ.
- **İkinci kırmızı kanıt ve kök neden:** playlist açılınca boşluk
  **−27 px**e düştü. `osd-dimensions` teşhisi gösterdi ki `sub-margin-y`
  PENCERE yüksekliğine değil RENDER EDİLEN VİDEO ALANI yüksekliğine göre
  ölçekleniyor (playlist açıkken `mt=mb=159`, alan 772 → 454). Ölçek
  referansı artık `osd-dimensions`tan alınır; okunamazsa widget
  yüksekliğine düşülür. Sonuç: **+23 px**.
- `sync_subtitle_safe_band()` her `update_overlay_geometry()` çağrısında
  (yeniden boyutlandırma, tam ekran, playlist, DPI) ve
  `restore_subtitle_settings()` içinde uygulanır; readback ile doğrulanır.

**Gerçek video kabul matrisi** (`Avatar.Fire.and.Ash…mkv`, gerçek libmpv,
gerçek iki satırlı SRT) — `o_band` **16/16 PASS**:

| Durum | Yüzey | Boşluk |
|---|---|---|
| `%100` normal | 1400×772 | **23 px** |
| `%90` (kullanıcı tercihi) | 1400×772 | 88 px (yukarıda) |
| katman gizli / görünür | 1400×772 | bbox birebir aynı `(333,536,1065,639)` |
| stres 2,00× + 5 px | 1400×772 | 33 px |
| playlist açık | 840×772 | 23 px |
| tam ekran | 2560×1440 | 31 px |
| tek satır | 1400×772 | 12 px |

`sub_margin_y` readback: 116 (normal), 193 (playlist), 61-63 (tam ekran).
Tam ekran ve kalın kenarlıkta boşluk 31–33 px'e çıkar: mürekkep ile ASS
satır kutusu farkı render ölçeğiyle büyür. Güvenlik açısından sorun
değildir (altyazı banda girmez); üst sınır bu iki durum için ayrı
verilir (`SAFE_GAP_MAX_LARGE=36`), normal durumlar 28 altındadır.

**Kalan sınır:** bitmap/PGS altyazıda konum ve stil garantisi VERİLEMEZ;
`l_bitmap` senaryosu `MLC_SUB_BITMAP_VIDEO` verilmediğinde **BLOCKED**
kalır ve sahte PASS yapılmaz. Tek satır / iki satır ölçüldü; alt kenar
her ikisinde de bandın üstündedir. %150 DPI ölçümü Altyazı Ayarları
penceresi için yapıldı, gerçek video bandı için tek DPI'da (dpr=1.0)
ölçüldü.

Eskiyen kabul beklentileri gevşetilmeden güncellendi ve gerekçeleri
dosyaya yazıldı: `g_text_size` 0,8/1,8 → 0,75/2,0; `i_delay` 8,0 → 5,0
(aralık ±5 sn); `k_lifecycle` 1,6 → 1,5; `m_enter_key` 1,6 → 1,5;
`h_subtitle_not_behind_controls` → `h_subtitle_clears_the_control_band`
(eski kural çakışmayı TALEP eder duruma düşmüştü).

**Ürün kusuru (yol boyunca bulundu):** `PresetCombo.select_value()`
listede olmayan değerde `findData()` `-1` dönünce indeks 0'a düşüyordu;
`select_value(1.8)` yazı boyutunu 0,75×'e çekiyordu. Artık merkezî
`normalise_subtitle_numeric()` ile en yakın hazır değere yuvarlanır.

Sözleşme: `tests/test_subtitle_safe_band_regressions.py` (23 test).

## Güvenli bant — otomatik parça değişimi (merkezi gözlemci)

Ölçülen açık: efektif ASS `sub_pos` hesabı doğruydu ama ürün yaşam
döngüsüne BAĞLI DEĞİLDİ. `media_controls.select_subtitle_language()`
yalnız `sid` yazıyor, `open_subtitle()`/bekleyen altyazı/Altyazı Merkezi
`sub_add` yolları da senkronlamıyordu; `sid`/`track-list` için merkezi
gözlemci yoktu. Birim testleri `track_list`i elle değiştirip senkronu
ELLE çağırdığı için gerçek kullanıcı yolunu kanıtlamıyordu.

- **Tek merkez: `SubtitleTrackWatcher`.** `sub_add` çağrılarının yanına
  dağınık yama YOK. MPV'nin `sid`, `track-list` ve `osd-dimensions`
  özellikleri gözlenir; hangi ürün yolu parçayı değiştirirse değiştirsin
  bant uygulanır. `init_mpv_player()` içinde, ayarlar geri yüklenmeden
  ÖNCE bağlanır.
- **Thread kuralı korunur:** MPV callback'i kendi olay thread'inden
  gelir; yalnız Qt sinyali yayınlar, iş ana thread'de çalışır. QWidget'a
  yabancı thread'den dokunulmaz.
- **`osd-dimensions` de gözlenir.** Tam ekran/playlist geçişinde mpv yeni
  render alanını Qt resize olayından SONRA yerleştiriyor; yalnız
  geometriye bağlı senkron eski alanla hesaplıyordu (ölçüldü: tam ekranda
  boşluk 182 px, %150 playlistte −91 px).
- **Codec gecikmesi:** `sid` olayında codec henüz yoksa HAM konum
  uygulanır, `track-list` güncellenince ASS efektif konumu kesinleşir.
  `sid` dize gelirse güvenli tam sayı eşlemesi yapılır.
- **Ölçülen model düzeltmesi:** ASS `sub-pos` yüzdesi VİDEO ALANINA değil
  MPV PENCERESİNE oranlanıyor (7,43 px/puan). Alan referansı kullanılınca
  düzeltme yetersiz (−83 px) ya da aşırı (+119 px) çıkıyordu;
  `subtitle_surface_reference()` artık `osd-dimensions.h` kullanır.
  Marj (SRT) yolu render ALANI referansında kalır.
- Önbellek `(mpv, (margin, altyazı_türü, efektif_pos))`; aynı bildirimin
  50 kez tekrarı **0 ek yazım** üretir. Geometri değişiminde yalnız
  gerçekten değişen özellik yazılır.

**Gerçek ürün geçişi ölçümleri** (native, elle senkron YOK; kullanıcı
tercihi %90):

    ASS -> SRT : mpv sub_pos = 90,0   (kullanıcının HAM değeri)
    SRT -> ASS : mpv sub_pos = 74,2   (efektif düzeltme)
    kayıtlı QSettings = 90,0          (DEĞİŞMEDİ)
    geçiş sonrası bbox alt kenarı 543 = geçiş öncesiyle AYNI

**ASS piksel tablosu** (1400×772, bant üstü 662):

| Durum | mpv `sub_pos` | bbox alt | boşluk |
|---|---|---|---|
| ham 100 (düzeltmesiz) | 100 | 735 | −73 |
| kullanıcı %100 | 84,2 | 617 | **+45** |
| playlist açık | 84,2 | 626 | **+36** |
| tam ekran | 91,53 | 1255 | **+75** |
| kullanıcı %90 | 74,2 | 543 | **+119** |
| ASS→SRT→ASS sonrası | 74,2 | 543 | +119 |

`p_ass_band` **20/20 PASS** (hem %100 hem %150 DPI). Tam matris:
**17 PASS, 1 BLOCKED** (yalnız `l_bitmap`).

Sözleşme: `tests/test_subtitle_track_watch_regressions.py` (13 test) +
`tests/test_subtitle_safe_band_regressions.py` (41 test).

## Güvenli bant — kabul öncesi üç açık

**1. Tekrarlanan libmpv yazımları.** `update_overlay_geometry()` overlay
üzerindeki FARE HAREKETLERİNDE de çağrılıyor ve geometri değişmese bile
her senkron üç özelliği yeniden yazıyordu. Ölçüldü: **100 senkron = 300
property yazımı**. `sync_subtitle_safe_band()` artık (mpv nesnesi, marj)
durumunu YALNIZ başarılı yazımdan sonra önbelleğe alır: **100 senkron =
3 yazım**. Marj değişirse yalnız `sub_margin_y`, mpv nesnesi değişirse
(yeni oturum) sözleşmenin tamamı yazılır; hata önbelleklenmez ve sonraki
çağrı yeniden dener.

**2. %150 DPI gerçek kabulü.** `o_band` artık ayrı child süreçlerinde
`QT_SCALE_FACTOR=1` ve `1.5` ile koşuyor (`O` / `O150`); ölçümler DPR'a
göre MANTIKSAL piksele normalize ediliyor. İlk %150 koşumu **7 FAIL**
verdi (gap −19): kök neden birim uyumsuzluğuydu — ayrılmış bant
MANTIKSAL, `osd-dimensions` CİHAZ pikselinde. Bant `devicePixelRatioF()`
ile referansın birimine çevrildi (dpr=1.0'da değer değişmez).

| Durum | %100 DPI | %150 DPI |
|---|---|---|
| `%100` normal | 23 px | 23 px |
| stres 2,00×+5 px | 33 px | 33 px |
| playlist açık | 23 px | 23 px |
| tam ekran | 31 px | 26 px |
| tek satır | 12 px | 12 px |

`sub_margin_y` readback: 116 / 193 (playlist) / 63 (%100 tam ekran) /
95 (%150 tam ekran). `O` ve `O150` **16/16 PASS**.

**3. ASS güvenli bant — ÇÖZÜLDÜ (önceki "motor sınırı" sonucu YANLIŞTI).**
Önceki tur yalnız `sub-margin-y`yi denemiş ve `sub-pos` alternatifini hiç
sınamamıştı. Bağımsız denetim `sub-pos`un ASS'i hareket ettirdiğini
gösterdi; ölçüm tekrarlandığında doğrulandı: ham `sub_pos` 100 → 80
altyazıyı gerçekten yukarı taşıyor. `sub-margin-y` ise ASS'te gerçekten
etkisiz (116 → 300 = 0 px) — bu artık bir sınır değil, TASARIM GEREKÇESİ.

Ürün çözümü: ASS metin altyazısında güvenli bant, MPV'ye YALNIZ çalışma
anında yazılan EFEKTİF bir `sub_pos` ile sağlanır
(`effective_subtitle_position()` = kullanıcı değeri − bant yüzdesi).
Kullanıcının KAYITLI tercihi (QSettings ve Altyazı Ayarları penceresi)
DEĞİŞMEZ; ölçüldü: `stored=100` iken MPV `83.86`, `stored=90` iken MPV
`73.86`. SRT `sub-margin-y` yolunda kalır ve İKİ KEZ yukarı taşınmaz.
ASS↔SRT geçişinde efektif değer/gerçek değer otomatik değişir.

`atomic_apply()` (Uygula) kullanıcının HAM değerini MPV'ye yazdığı için
`menu_actions._apply_subtitle_style()` başarılı yazımdan sonra bandı
geçersiz kılıp yeniden senkronlar (ölçüldü: bu olmadan boşluk +47 → −73
düşüyordu).

Ölçüm harness'i de düzeltildi: (a) eşlenik-kare farkına kontrol katmanı
pikselleri karışıyordu — `apply_style()` ve tam ekran geçişi katmanı
yeniden gösterdiği için katman HER ölçümden önce gizlenir ve bant üstü
görünürlükten bağımsız `reserved_band_top()` ile hesaplanır;
(b) üst ve alt sınırlar AYRI raporlanır; (c) duraklatılmış mpv'de kare
yeniden çizilsin diye ölçüm öncesi yeniden seek edilir.

Gerçek ASS ölçümleri (1400×772, bant üstü 662):

| Durum | MPV `sub_pos` | bbox alt | boşluk |
|---|---|---|---|
| kullanıcı %100 | 83,86 | 615 | **+47** |
| ham 100 (düzeltmesiz) | 100 | 739 | −77 |
| ham 80 (motor deneyi) | 80 | 586 | +76 |
| playlist açık | 83,86 | 623 | **+39** |
| tam ekran | 91,18 | 1250 | **+80** |
| kullanıcı %90 | 73,86 | 540 | **+122** |

ASS'te üst sınır ayrı verilir (`SAFE_GAP_MAX_ASS=90`): ASS betiğinin
kendi `MarginV` değeri ürünün ofsetine eklenir ve dosyaya göre değişir,
önceden bilinemez. Hiçbir durumda kesişme yok.

`p_ass_band` **15/15 PASS** (hem %100 hem %150 DPI). Bitmap/PGS ayrı
BLOCKED olarak kalır.

**Tam gerçek-video matrisi: 17 PASS, 1 BLOCKED** (yalnız `l_bitmap`). SRT tarafındaki mevcut güvenli boşluklar, `%90`
tercihi, auto-hide'da zıplamama ve Altyazı Ayarları yerleşimi
değişmedi.

Sözleşme: `tests/test_subtitle_safe_band_regressions.py` (41 test).

## Altyazı Ayarları — palet/renk satırı/dar pencere turu

Kırmızı kanıt (mevcut üründe ölçüldü): `sub_pos` combo değerleri
merkezî doğrulamadan geçerken doğrudan `int(values.get("sub_pos", ...))`
ile okunuyordu ve pencere AÇILIRKEN çöküyordu — `None` → `TypeError`,
`"bozuk"` → `ValueError`, `NaN` → `ValueError`, `±inf` → `OverflowError`.

- **Şeffaflık paletin İÇİNE taşındı.** Ana penceredeki ayrı
  `subtitleTransparentButton` KALDIRILDI. Arka plan kutusuna tıklanınca
  açılan pencerede `Renk yok (Şeffaf)` düğmesi bulunur
  (`subtitleNoColourButton`, erişilebilir ad "Arka planı şeffaf yap
  (renk yok)"). Seçim `alpha = 0` üretir, pencere kapanır, önizleme
  kutusu kaybolur ve `sub_border_style` `outline-and-shadow` olur.
  İptal önceki rengi bit düzeyinde korur (`#C80020A0`), normal ve yarı
  saydam seçim değişmedi, Yazı/Kenarlık paletine bu seçenek EKLENMEZ.
- Sistem renk penceresi kendi düğme kutusunu gizlediği için pencere
  bilinçli olarak `DontUseNativeDialog` ile açılır; alfa sürgüsü
  (`ShowAlphaChannel`) yine görünür. **Ölçülen yan etki ve düzeltmesi:**
  non-native pencere Qt'nin İngilizce metinleriyle geliyordu
  ("Basic colors / OK / Cancel"); `pick_colour()` artık `qtbase_tr.qm`
  çevirisini YALNIZ pencere yaşarken kurar ("Temel renkler / Tamam /
  İptal") ve çıkarken kaldırır. Çeviri nesnesi önbelleğe ALINMAZ —
  modül düzeyinde tutulan `QTranslator`'ın C++ tarafı yok edilip
  sonraki çağrı `RuntimeError` veriyordu.
- Renk seçme sızdırma noktası artık tek: modül düzeyindeki
  `pick_colour(parent, initial, title, allow_transparent)`.
- **Üç renk kutusu EŞİT ve YAN YANA.** `sub_back_color` hücresine
  verilen çift genişlik payı ve içindeki `addStretch(1)` kaldırıldı;
  "Kenarlık" artık sağ kenara yapışmıyor. Ölçüm: kutu genişliği 86 px,
  aralar 10/10 px, sağ boşluk ≥ 20 px. Etiket ("Arka plan", offscreen'de
  108 px) kutudan geniş olduğu için üçüne ORTAK genişlik verilir.
- **Pencere daraltıldı:** `DEFAULT_SIZE=(600, 480)`,
  `MINIMUM_SIZE=(540, 430)`. 540 px gerçek Windows platformunda
  %100 ve %150 DPI'da kırpılmasız doğrulandı (`clipped=[]`), 560'a
  dönülmedi.
- **`sub_pos` açılış çökmesi kapatıldı:** slider değeri de
  `normalise_subtitle_numeric("sub_pos", ...)` üzerinden geçer.
  Ölçüm sonrası: beş bozuk değerin tamamında pencere açılıyor ve
  varsayılana (%100) düşüyor; `-50` → 0, `150` → 100, `"42"` → 42.
- **Gerçek Windows kabulü: 12/12 PASS** (%100/%150 × varsayılan ve
  minimum, palet açık, "Renk yok" seçildikten sonra, açılır liste,
  yarı saydam kutu, 2,00× + uzun metin, bitmap uyarısı, uygulama
  hatası). Her senaryoda `clipped=[]`, alt düğmeler pencere içinde ve
  `childAt()` ile tıklanabilir, üç renk kutusu eşit/yan yana, önizleme
  eylem satırıyla kesişmiyor, palet ekran içinde ve "Renk yok (Şeffaf)"
  görünür. Görüntüler `%TEMP%\mlc-subtitle-shots` içinde (Git'e
  eklenmedi).
- Sözleşme: `tests/test_subtitle_appearance_palette_regressions.py`
  (35 test). Eskiyen testler gevşetilmeden taşındı:
  `test_the_transparent_option_is_visible_and_one_click` (ayrı düğme →
  palet seçeneği), `test_the_transparent_button_clears_the_background_in_a_real_process`,
  `test_colour_picker_is_opened_with_the_alpha_channel` (statik
  `getColor` seam → `pick_colour`), `StubColorPicker` ve
  `subtitle_visual_acceptance_child.py` tohum ölçümü.

## Altyazı görünümü gerçek MPV/piksel kabulü (3. tur)

Runner: `tests/run_subtitle_visual_acceptance.py` (14 senaryo, her biri
ayrı child; `MLC_NATIVE_SMOKE=1`, `MLC_NATIVE_TEST_VIDEO`,
`MLC_SUB_BITMAP_VIDEO`). Son tam sonuç: **14/14 PASS** (`N` senaryosu
eklendikten sonra), exit 0, süreç sızıntısı yok, fare/foreground geri
yüklendi. İki bağımsız kare (`t=60` ve `t=2400`) ile tekrarlandı.

13 Ağustos bağımsız tekrarında ilk tam matris 12 PASS + 1 INCOMPLETE verdi:
`b_background_off`, ölçüm başlamadan hemen sonra libmpv `_set_property`
yolunda `0xC0000005` ile düştü (`MARK_DONE` yoktu ve runner doğru biçimde
başarısız saydı). Aynı B senaryosu ardından 10/10 bağımsız koşumda, iz
kayıtlı ikinci tam matris de 13/13 geçti. Ürün/piksel ölçütü hatası yeniden
üretilemedi; bu aralıklı native başlangıç çöküşü engelleyici olmayan risk
olarak açık tutuluyor.

- Medya: `Obsession.2025…mkv` (video 1, gömülü altyazı 0). Altyazı
  benzersiz geçici dizinde UTF-8 SRT/ASS; kullanıcı klasörüne veya repoya
  yazılmaz, tur sonunda silinir. `vo=gpu`, `ao=null` (`current-ao=null`
  doğrulandı), video `absolute+exact` ile duraklatıldı.
- Ölçüm iki ayaklı: libmpv property readback **ve** aynı duraklatılmış
  kare üzerinde gerçek Windows ekran görüntüsünden piksel farkı
  (altyazı kapalı referans kare − stilli kare). Karar mantığı saf
  `tests/subtitle_pixel_rules.py` modülünde, kendi testleriyle.
- Doğrulananlar: `#FFF26A3D` (12.952 turuncu piksel, beyaz karede 0),
  `background-box` kutusu (en uzun kesintisiz mavi dizi 748/748 px,
  33 tam satır), saydam arka planda kutu yok (dizi oranı 0,05),
  kenarlık rengi yazıdan ayrı küme (beyaz 13.086 / turuncu 24.622,
  turuncu bbox beyazı kapsıyor), kenarlık 1,0→5,0 px alan oranı 11,29×,
  ölçek 0,8→1,8 bbox 711×158 → 1321×274, konum %70→%95 merkez Y
  574→668, senkron +8 sn'de cue kayboluyor (18.139 → 150 px, `sub-text`
  boş) ve 0'a dönünce geri geliyor, `sub_ass_override=force` ASS'nin
  kendi sarısını eziyor (turuncu 45.314 / sarı 0),
  Cancel/Escape/Reset/Apply atomikliği gerçek libmpv + geçici QSettings
  ile, gerçek `hdmv_pgs_subtitle` parçada bilgi metni görünüyor ve
  bitmap görüntüsünün değiştiği İDDİA EDİLMİYOR (piksel farkı 0).
- `BACKGROUND_BOX_SHADOW_OFFSET=0.0` gerçek görüntüde doğrulandı:
  kutu boşluğu sol 7 / üst 6 / sağ 8 / alt 12 px, glif yüksekliği
  105 px; metin kırpılmıyor, bant aşırı büyümüyor. **Değer
  değiştirilmedi.**
- Ölçülen ama ürün hatası sayılmayan bulgu: `sub_pos=95` iken kontrol
  katmanı görünürken altyazı bbox'ının %54,5'i katman bandıyla
  kesişiyor. Altyazı katmanın ARKASINA düşmüyor (kesişim bölgesinde
  8.041 görünür altyazı pikseli). Bunu düzeltmek altyazı konumunu
  overlay görünürlüğüne bağlamayı gerektirir. Teknik öneri mevcut davranışı
  kabul etmektir: `%95` kullanıcı tarafından özellikle en alt konum olarak
  seçilir, kontrol katmanı geçicidir ve altyazı kaybolmaz; katman her
  görünüp kaybolduğunda altyazıyı oynatmak daha rahatsız edici ve risklidir.
- Harness'te düzeltilen iki kendi hatam: (1) iki farklı genişlikteki
  satırın BİRLEŞİK bbox doluluk oranı kutu ölçütü olarak yanıltıcıydı,
  yerine kesintisiz yatay dizi ölçüsü kondu; (2) yönlendirilmiş stdout
  cp1254 olduğu için rapor metnindeki `→` `UnicodeEncodeError` fırlatıp
  PyQt6'yı `0xC0000409` ile düşürüyordu — çıktı UTF-8'e sabitlendi ve
  `|` alanları kaçışlanıyor.

## Güvenli hata sistemi — 1-3. aşama

Kırmızı kanıt: `show_user_error()` yakalanan istisnanın HAM traceback'ini
`QMessageBox.setDetailedText()` ile kullanıcıya gösteriyordu; traceback ve
istisna metni kullanıcı adı, tam medya yolu, API anahtarı, parola,
`Authorization` başlığı ve URL token'ı taşıyabiliyordu. 31 testin 23'ü
kırmızıydı.

- Her hata tek bir değiştirilemez `ErrorEvent` kaydıdır: kayıt numarası,
  zaman, kategori, başlık, güvenli kullanıcı mesajı, istisna sınıfı,
  güvenli teknik özet, maskelenmiş geliştirici ayrıntısı.
- Kayıt numarası biçimi `MLC-YYYYMMDD-XXXX` (örn. `MLC-20260813-D9BB`);
  kullanıcıya hatanın AÇIKLAMASI gibi sunulmaz, yalnız destek içindir.
- Merkezi `redact()`: JSON `"token"/"password"/"api_key"` değerleri,
  `Bearer/Basic/Token` jetonları, `anahtar=değer` ve URL query
  parametreleri, `C:\Users\<ad>\...` yolları maskelenir. Tanı için
  dosya adı korunur, kullanıcı adı ve ara klasörler `<gizli>` olur.
  Zararsız Türkçe açıklamalara DOKUNULMAZ.
- `setDetailedText()` artık HİÇ çağrılmıyor; `details` parametresi
  geriye dönük uyumluluk için kabul edilip yalnız maskelenmiş biçimde
  loga yazılıyor.
- `_handle_exception()` tek kayıt üretir: aynı traceback ikinci kez
  loglanmaz, konsola da maskelenmiş metin basılır.
- İmzalar korundu: `show_error`, `show_user_error`, `log`,
  `debug/info/error`, `install_exception_handler`, `_friendly_message`.
  `show_user_error()` artık `ErrorEvent` döndürüyor (mevcut çağrılar
  dönüşü kullanmadığı için kırılma yok).
- Log rotasyon politikası bu turda DEĞİŞMEDİ.
- **Bağımsız incelemede bulunan üç açık kapatıldı** (28 kırmızı test):
  1. `log()` artık NİHAİ yazma sınırında her seviyede maskeliyor;
     `debug/info/error`, doğrudan çağrılar ve `MPVPlayer.log_handler`
     üzerinden gelen libmpv tanıları korunuyor. Maskeleme idempotent.
  2. `redact()` genişletildi: sözlük/JSON tek ve çift tırnak, tırnaklı
     değerler, `client_secret`/`passphrase`/`sig`/`x-api-key` gibi önekli
     anahtarlar, URL-encoded `%3D` ayracı ve `Bearer` dışındaki
     `Authorization` şemaları (`Digest`, `Negotiate`, `NTLM`, `Basic`).
     `Authorization` satırında kimlik gövdesinin hiçbiri kalmıyor.
     Çıplak `key` BİLEREK listelenmedi (`keyboard=`/`monkey=` zararsız).
  3. Yol maskeleme genişletildi (`<yol>`): boşluklu kullanıcı adı ve
     klasörler, `Users` dışındaki sürücü yolları ve UNC paylaşımları.
     Dizin, kullanıcı adı, sunucu ve paylaşım adı düşer; tanı için
     yalnız güvenli son dosya adı kalır (uzantısı yoksa o da maskelenir).
- Sözleşme: `tests/test_error_redaction_hardening_regressions.py`
- **İkinci bağımsız doğrulamada bulunan üç ek açık kapatıldı**
  (22 kırmızı test):
  1. `MPVPlayer.log_handler` konsola HAM libmpv mesajı basıyordu; artık
     `print()` de merkezi `redact()` süzgecinden geçiyor. Dosya logu
     idempotent olduğu için çift maskeleme veya çift kayıt oluşmuyor;
     `warn/error/fatal` politikası değişmedi.
  2. Boşluk içeren son dosya adı KISMEN sızıyordu
     (`D:\Private Folder\Musteri Sozlesmesi.mp4` → `<yol> Sozlesmesi.mp4`).
     Kalıp artık uzantıyla biten boşluklu adın tamamını eşliyor ve
     boşluklu ad TAMAMEN maskeleniyor (`<yol>`); boşluksuz modül adları
     tanı için korunmaya devam ediyor (`<yol>\player.py`). Yolun ardından
     gelen normal cümle silinmiyor.
  3. Karşı tür/kaçışlı tırnak içeren değerler maskelenmiyordu
     (`password="abc'def"`). Tırnaklı değer gövdesi artık kapatan tırnağa
     kadar okunuyor; satır sonu dışarıda bırakıldığı için kalıp satırın
     kalanını veya sonraki log kaydını yutmuyor.
- **Yol sınırı açığı kapatıldı** (22 kırmızı test): `_PATH_FINAL`
  boşluklu dosya adını `{0,6}` kelimeyle sınırlıyor ve uzantıdan sonraki
  `, ; ) ]` işaretlerini güvenli sınır saymıyordu; kalıp yolun yalnız
  ilk kelimesini eşleyip adın kalanını açıkta bırakıyordu
  (`<yol> Sozlesmesi.mp4, tekrar deneyin`). Artık kelime sayısında üst
  sınır yok, uzantı grubu tekrarlanabiliyor (`arsiv.tar.gz`,
  `film.mp4. devam`) ve yolu izleyen noktalama ile cümle korunuyor.
  63 bin karakterlik girdide `redact()` 0,011 sn.
- **Yol maskelemesi regex istisnalarından SATIR TARAYICISINA taşındı**
  (25 kırmızı test). Uzantıya/noktalamaya dayanan her istisna yeni bir
  kaçak bırakıyordu (`D:\Private\gizli klasor` → `<yol> klasor`,
  `//server/share/...` hiç eşleşmiyordu). Serbest metinde TIRNAKSIZ,
  boşluklu ve uzantısız bir yolun nerede bittiği genel olarak
  belirlenemez; virgül, noktalı virgül, parantez ve boşluk Windows
  dosya adında geçerlidir. Yeni sözleşme:
  1. **Tırnaklı yol** — açılış tırnağından eşleşen kapanış tırnağına
     kadar maskelenir; tırnaklar ve sonraki cümle KORUNUR
     (`Hata: "D:\...\gizli klasor", tekrar deneyin` →
     `Hata: "<yol>", tekrar deneyin`). Kapanmamış tırnak fail-closed.
  2. **Tırnaksız yol** — güvenli sınır yoktur, gizlilik lehine SATIR
     SONUNA kadar maskelenir. Yolun ÖNÜNDEKİ metin korunur, sonraki
     satır ASLA yutulmaz.
  3. **Tanı istisnası** — yalnız TIRNAKLI kaynak kod yollarında
     boşluksuz `.py`/`.pyw` adı korunur
     (`File "<yol>\player.py", line 12`). `.mkv`, `.mp4`, `.srt`,
     uzantısız dosya ve klasör adları korunmaz.
  Kökler: `C:\`, `C:/`, `\\server\share`, `//server/share`, `\\?\C:\`,
  `\\?\UNC\`. `https://`, `file.py:12`, `12:30`, `a/b` yol sayılmaz.
  Uygulama: `_PATH_ROOTS` + `_mask_paths_in_line()` (satır başına
  deterministik tarama, yeni bağımlılık yok). 117 KB girdide 1,18 sn.
- Bu değişiklik ESKİ beklentileri geçersiz kıldı; testler sessizce
  gevşetilmedi, yeni adlar ve açıklayıcı yorumlarla güncellendi:
  `test_unquoted_path_with_punctuation_is_masked_to_end_of_line`,
  `test_closing_marks_do_not_stop_an_unquoted_path` (+ tırnaklı eşi),
  `test_unquoted_spaced_path_is_masked_to_end_of_line` (+ tırnaklı eşi),
  `test_direct_log_call_with_unc_path_is_masked` (medya adı artık
  korunmuyor), `test_paths_leak_no_directory_user_or_share`.
- **Tarayıcının son üç sınırı kapatıldı** (27 kırmızı test):
  1. **Kesme işareti.** `'` Windows dosya adında GEÇERLİDİR; ilk tek
     tırnak kapanış sanılıyor ve yolun kalanı sızıyordu
     (`'<yol>'Brien\Private Folder\film.mkv'`). Ara çözümde adaydan
     sonraki karaktere bakan bir sezgi denendi; `Rock 'n' Roll`,
     `O' Brien` ve `Drivers' Backup` gibi geçerli adlarda BU DA
     sızdırdığı için sezgi tamamen KALDIRILDI. **Tek tırnaklı yol artık
     her zaman satır sonuna kadar fail-closed maskelenir**; sonraki
     cümle korunmaya çalışılmaz, açılış tırnağı ve öncesi kalır,
     sonraki satır yutulmaz. Tek tırnaklı yolda `.py` tanı adı da
     korunmaz. `"` dosya adında geçersiz olduğu için çift tırnakta ilk
     eşleşme kuralı DEĞİŞMEDİ.
  2. **`file://` URI.** `file://server/share/...`, `file:///C:/...`,
     `file://localhost/C:/...`, `%20` kodlu ve büyük/küçük harf
     varyantları artık yol sayılıyor. Şema sınırı RFC'ye göre
     daraltıldı: `file://` öncesinde harf, rakam, `+`, `-` veya `.`
     varsa BAĞIMSIZ şema başlangıcı sayılmaz — `custom-file://`,
     `profile-file://`, `x.file://`, `abc+file://`, `myfile://`,
     `9file://` dokunulmadan kalır. `https://`, `http://`, `ftp://`,
     `profile://`, `file.py:12` ve normal metindeki `file:` kelimesi
     de etkilenmiyor.
  3. **Satır sonları.** `split()` ile bölme özgün ayracı
     bozuyordu; artık CRLF, tek CR ve karışık ayraçlar birebir
     korunuyor (`_LINE_SPLIT` yakalama grubuyla ayırma).
  133 KB girdide `redact()` 0,039 sn.
- Sözleşmesi güncellenen eski testler (silinmedi, gevşetilmedi):
  `test_single_quoted_path_with_an_apostrophe_fails_closed` (eski adı
  `test_apostrophe_inside_a_quoted_path_is_not_a_closing_quote`),
  `test_double_quoted_paths_are_masked_up_to_the_closing_quote` (eski
  adı `test_quoted_paths_are_masked_up_to_the_closing_quote`; tek
  tırnaklı örnekler ayrı `test_single_quoted_paths_are_masked_to_end_of_line`
  testine taşındı).
- **Konsol çıktısı merkezi sınıra bağlandı** (38 kırmızı test).
  AST envanteri: `main.py` + `app/**/*.py` içinde **74** doğrudan
  `print()` vardı ve **54**'ü ham yol, URL veya ham `str(exception)`
  taşıyabiliyordu; dosya logu maskeliyken konsol bu sınırı ATLIYORDU.
  Yeni `app/errors.py::safe_console()`:
  - stdout'a yazmadan önce merkezi `redact()` uygular,
  - dosya loguna kayıt YAZMAZ (konsol ve log ayrı çıkışlardır),
  - maskeleme hata verirse HAM mesaj yerine sabit bir metin yazar,
  - konsol kapalı/bozuksa uygulamayı çökertmez,
  - `None` ve string olmayan değerlerde güvenlidir.
  74 çağrının tamamı `safe_console()` üzerinden geçirildi; kalan tek
  doğrudan çıkış `safe_console()` içindeki `builtins.print()`.
  `MPVPlayer.log_handler` artık ÖNCEDEN maskelemez: ham metni hem
  `safe_console()` hem `log()` alır, her biri kendi son sınırında
  maskeler ve birer kez yazar (çağıranın maskelemesine güvenilmez).
- Yapısal kapı (`tests/test_safe_console_regressions.py`): AST ile
  üretim kodunda doğrudan `print()`, `sys.stdout/stderr.write` ve
  `traceback.print_*` yasak; `builtins.print` yalnız `safe_console()`
  gövdesinde ve yalnız BİR kez bulunabilir. Yorum/string içindeki
  "print" metni sahte ihlal üretmez.
- Envanter sonucu: doğrudan üretim `print()` = **0**, izinli merkezi
  `builtins.print()` = **1**, başka stdout/stderr çıkışı = **0**.
- **2. aşama: ayrı "Hata Ayrıntıları" penceresi** (19 kırmızı test).
  Ana hata kutusu SADE kalır — simge, Türkçe başlık, kullanıcı mesajı,
  `Tamam` ve İKİNCİL `Hata Ayrıntılarını Görüntüle` düğmesi. Kayıt
  numarası, istisna sınıfı, teknik özet ve traceback ana kutuya ULAŞMAZ;
  `setDetailedText()` kullanılmaz. `Tamam` hem varsayılan hem Escape
  düğmesidir, Enter yanlışlıkla ayrıntıları açmaz.
  Yeni `app/error_details_dialog.py::ErrorDetailsDialog`: kayıt
  numarası, tarih, kategori, başlık, kullanıcı mesajı, hata türü,
  teknik özet ve salt okunur/kaydırılabilir maskelenmiş teknik ayrıntı.
  Ayrıntı YALNIZ `ErrorEvent.developer_detail`ten gelir (ham istisnadan
  traceback yeniden üretilmez), boşsa "Ek teknik ayrıntı bulunmuyor."
  yazar. Gösterim ve kopyalama sınırlarında `redact()` savunma amaçlı
  TEKRAR uygulanır. Kayıt numarası yalnız bu pencerede görünür.
  Düğmeler: `Bilgileri Kopyala` ve `Kapat`. Pano yalnız tıklamayla ve
  bir kez yazılır, log dosyası okunmaz, hata olursa uygulama çökmez ve
  ham veri konsola gitmez (küçük "Kopyalandı"/"Kopyalanamadı" etiketi,
  yeni pencere açılmaz).
  Pencereyi açmak yeni `ErrorEvent` üretmez, ikinci log kaydı yazmaz,
  kayıt numarasını değiştirmez; açılamazsa yalnız güvenli tür bilgisi
  `safe_console()` ile yazılır.
- Gerçek Windows görsel kabulü (`tests/error_details_dialog_child.py`,
  opt-in): %100 ve %150 DPI × default / uzun başlık-özet / 124 satırlık
  traceback / boş ayrıntı / 560×380 küçük pencere = 7 ölçüm. Hepsinde
  `clipped=[]`, iki düğme görünür, teknik alan salt okunur, uzun
  traceback'te kaydırma çubuğu etkin, pencere ekran içinde, ham sızıntı
  yok. Ana kutu ile ayrıntı penceresi aynı anda açık kalmaz
  (`box.exec()` döndükten SONRA açılır).
- **3. aşama: sınırlı saklama politikası + "Günlük Yönetimi" penceresi**
  (34 kırmızı test). Doğrulanan kusur: rotasyon yalnız yazma
  ONCESINDEKI boyuta bakıyordu. 2 MiB'ın 10 bayt altındaki dosyaya tek
  bir 500 KB kayıt yazılınca aktif log 2.597.173 bayta çıkıyor ve yedek
  hiç oluşmuyordu.
  Yeni sabitler: `MAX_LOG_FILE_BYTES = 2 MiB`, `LOG_BACKUP_COUNT = 1`,
  `MAX_LOG_RECORD_BYTES = 256 KiB`. **Kesin üst sınır = 4 MiB**
  (2 MiB aktif + 2 MiB yedek).
  - Rotasyon artık "mevcut boyut + YAZILACAK satır" hesabıyla yazmadan
    ONCE yapılıyor; aynı senaryoda aktif log 262.145 bayt, yedek
    oluşuyor, sınır aşılmıyor.
  - Tek kayıt 256 KiB'ı aşarsa UTF-8 karakteri ORTADAN BOLMEDEN
    kısaltılıp `[kayıt boyut nedeniyle kısaltıldı]` işareti ekleniyor;
    kısaltma maskelemeden SONRA yapıldığı için ham veriye dönüş yok.
  - Yazma, rotasyon ve temizleme aynı process-wide `RLock` altında.
  - Yeni API: `get_log_directory()`, `get_log_files()`,
    `get_log_usage()`, `clear_logs()` → `LogClearResult`.
    `clear_logs()` yalnız `uygulama.log` ve `uygulama.log.1` dosyalarına
    dokunur (glob/recursive/serbest yol YOK), idempotenttir, symlink
    hedefini takip etmez, başarıdan sonra yeni kayıt yazmaz ve ham
    `OSError` metnini kullanıcıya taşımaz.
- **Denetimde bulunan üç sınır açığı kapatıldı** (11 kırmızı test);
  "kesin üst sınır" ifadesi ancak bundan sonra geçerlidir:
  1. **Rotasyon hatası.** `_rotate_if_needed()` yalnız `False` dönüyor,
     `log()` ise dönüşü yok sayıp AYNI DOLU dosyaya yazıyordu (sentetik
     100 baytlık sınırda aktif dosya 135 bayt). Akış artık üç durumu
     ayırıyor: gerek yok / başarılı / gerekli ama başarısız. Üçüncü
     durumda kayıt DÜŞÜRÜLÜR (fail-closed), dosya büyümez, istisna
     çağırana taşmaz, konsola ham hata yazılmaz ve yeniden loglama
     denenmez.
  2. **Eskiden kalan aşırı büyük dosya.** 6 MiB'lık eski aktif log
     olduğu gibi yedeğe taşınıyor ve toplam 6.291.497 bayta çıkıyordu.
     Her yazımdan önce aynı kilit altında `_normalise_oversized()`
     çalışır: `MAX_LOG_FILE_BYTES` üstündeki İZİNLİ aktif/yedek dosya
     silinir, yeni aktif dosyayla devam edilir. Normal boyuttaki yedek
     silinmez, normal rotasyonda tanı geçmişi korunur; ilgisiz dosya,
     alt klasör ve symlink hedefi etkilenmez.
  3. **Satır sonu.** `MAX_LOG_RECORD_BYTES` artık diske yazılan kaydın
     TAMAMINI (`'
'` dahil) ifade eder; kesme bütçesinden bir bayt
     ayrılır, kısaltma işareti tam korunur, UTF-8 bölünmez.
  Ölçülen sonuç: rotasyon hatasında aktif 395 → 395 bayt (büyüme yok);
  6 MiB eski log sonrası toplam 41 bayt ≤ 4.194.304; tek büyük kayıt
  ASCII 262.144 / Türkçe 262.143 bayt ≤ 262.144.
- **Son iki sınır açığı kapatıldı** (12 kırmızı test):
  1. **Normalleştirme hatası yutuluyordu.** `_normalise_oversized()`
     silemediği dosyada yalnız `continue` ediyor, `_prepare_log_file()`
     bunu bilmeden yazmaya devam ediyordu: büyük AKTİF dosya
     silinemediğinde olduğu gibi yedeğe taşınıyor (44 + 2.400 = 2.444
     bayt, izinli 800), büyük YEDEK silinemediğinde aktife yeni kayıt
     ekleniyordu (54 + 2.400 = 2.454 bayt). Fonksiyon artık açık
     başarı/başarısızlık döndürür; izinli girdilerden biri güvenle
     incelenemez veya gerekli normalleştirme tamamlanamazsa
     `_prepare_log_file()` `False` döner ve `log()` fail-closed davranır.
     Ölçüm sonrası: aktif 2.400 → 2.400, yedek yok; ikinci senaryoda
     aktif 10 → 10, yedek 2.400 → 2.400 (5 ardışık çağrıda da sabit).
     Hata çağırana taşmıyor, ham `OSError` metni konsola çıkmıyor,
     özyinelemeli log üretilmiyor; dosya sistemi düzelince sonraki
     çağrı normalleştirip yazıyor.
  2. **Bağlantı hedefine yazılıyordu.** `uygulama.log` klasör dışındaki
     bir dosyaya symlink olduğunda `_normalise_oversized()` onu `size=0`
     sayıyor, `_prepare_log_file()` `isfile()`/`getsize()` ile bağlantıyı
     TAKİP ediyor ve `open(path,"ab")` HEDEFE yazıyordu: 8 baytlık dış
     hedef `log("short")` sonrası 43 bayt. Yeni
     `_is_link_or_reparse_point()` — `os.path.islink()`, varsa
     `os.path.isjunction()` ve `os.lstat().st_file_attributes &
     FILE_ATTRIBUTE_REPARSE_POINT`, tamamı hedefi açmadan — izinli aktif
     veya yedek ad bağlantıysa YALNIZ bağlantı girdisini kaldırır;
     kaldırılamazsa yazma durur. Ölçüm sonrası: hedef 8 → 8 bayt, aktif
     yol gerçek dosyaya dönüşüyor, büyük hedefli bağlantı yedeğe
     taşınmıyor, yedek bağlantının küçük ve büyük hedefleri değişmiyor.
     `get_log_files()` bağlantıyı listelemiyor, `get_log_usage()` hedef
     boyutunu saymıyor (5.000 baytlık hedefte `total_bytes = 0`).
     Gerçek Windows junction (`mklink /J`) ile hedef klasör ve içeriği
     bit düzeyinde korunuyor. `clear_logs()` sözleşmesi değişmedi.
  - **"Her koşulda 4 MiB" iddiası düzeltildi.** Dosya sistemi zaten
    sınırı aşmışsa ve işletim sistemi silmeye izin vermiyorsa program
    mevcut aşımı fiziksel olarak yok edemez. Garanti artık programın
    yönetebildiği NORMAL dosyalar için verilir (aktif ≤ 2 MiB, yedek
    ≤ 2 MiB, toplam ≤ 4 MiB); aksi hâlde yeni veri yazılmaz, mevcut aşım
    büyütülmez, akış fail-closed kalır.
  - Sözleşme: `tests/test_log_retention_link_regressions.py` (18 test).
- **Fail-closed sınıflandırma kusuru kapatıldı** (16 kırmızı test).
  `_is_link_or_reparse_point()` İKİ ayrı durumu aynı `True`'ya
  indiriyordu: "gerçek bağlantı" ve "türü belirlenemedi".
  `_normalise_oversized()` her `True`'yu bağlantı sanıp siliyordu.
  Kanıt: normal `uygulama.log` içeriği `b'ORIGINAL-DIAGNOSTIC'` iken
  sentetik `lstat` hatasında dosya SİLİNDİ ve yerine
  `b'[...] [INFO] NEW\n'` yazıldı; UNKNOWN durumdaki 2.400 baytlık
  aktif dosya da silindi (2.400 → 0).
  Yeni `_classify_entry()` TEK `os.lstat()` incelemesiyle dört durum
  döndürür: `ENTRY_MISSING`, `ENTRY_REGULAR` (boyut AYNI `lstat`ten),
  `ENTRY_LINK_OR_REPARSE`, `ENTRY_UNKNOWN_OR_UNSAFE`. UNKNOWN asla
  bağlantı gibi ele alınmaz: silinmez, taşınmaz, üzerine yazılmaz ve
  `_prepare_log_file()` `False` döner. Ölçüm sonrası: tanı dosyası
  byte-for-byte korunuyor (`ORIGINAL-DIAGNOSTIC` → aynısı), yedek
  oluşmuyor, UNKNOWN büyük aktif taşınmıyor, UNKNOWN büyük yedek varken
  aktife kayıt eklenmiyor; inceleme düzelince yazım sürüyor.
  `get_log_files()`/`get_log_usage()` artık sınıflandırmayı ÖNCE yapıyor
  (`and` soldan sağa değerlendiği için `os.path.isfile()` bağlantının
  hedef metadata'sını hâlâ takip ediyordu); symlink yolunda
  `isfile/exists/getsize` çağrı sayısı **0**.
  `_remove_log_entry()` de sınıflandırmaya bağlandı: `os.path.islink()`
  Windows'ta junction'a `False` dediği için junction "dizin" sanılıp
  hata veriyordu; artık `os.rmdir()` ile YALNIZ reparse point kaldırılıyor,
  hedef klasör içeriğine dokunulmuyor. Gerçek `mklink /J` ölçümü:
  `link_or_reparse` → `regular`, hedefteki dosya `b'12345678'` değişmedi,
  yeni kayıt yalnız gerçek aktif logda. Kaldırma engellenirse yazım
  fail-closed duruyor. Ürün kodunda `cmd`/subprocess yok (yalnız test
  kurulumunda).
  - Sözleşme: `tests/test_log_entry_classification_regressions.py`
    (20 test). Eskiyen iki test gevşetilmeden yeniden yazıldı:
    `test_classification_recognises_links_without_following_the_target`,
    `test_classification_uses_lstat_reparse_attributes`.
- Yardım menüsünde tek `Günlük Yönetimi` aksiyonu (üç nokta menüsü
  menubar'ı yansıttığı için orada da görünür) →
  `app/log_management_dialog.py::LogManagementDialog`: kısa Türkçe
  açıklama, saklama politikası, kullanıcı dostu toplam boyut,
  `Günlük Klasörünü Aç` (yalnız `QDesktopServices`, shell/subprocess
  yok), `Günlükleri Temizle` (ayrı onay penceresi; `İptal` varsayılan ve
  Escape) ve `Kapat`. Log İÇERİĞİ ve mutlak kullanıcı yolu ekranda
  gösterilmez; açılışta dosya sistemi, pano ve ağ dokunulmaz.
- Gerçek Windows kabulü (`tests/log_management_dialog_child.py`): %100
  ve %150 DPI, 560×320 varsayılan ve 460×280 küçük pencere —
  `clipped=[]`, üç düğme görünür, pencere ekran içinde. `cancel`
  senaryosunda dosya sistemi değişmedi; `confirm` senaryosunda yalnız
  `uygulama.log` ve `uygulama.log.1` silindi, `unrelated.txt` ve
  `altklasor/` korundu, boyut 6.600 → 0 bayt, durum
  "Günlükler temizlendi."
- Sözleşme: `tests/test_log_retention_limits_regressions.py` (19 test) +
  `tests/test_log_retention_regressions.py` (24 test) +
  `tests/test_log_management_dialog_regressions.py` (16 test) +
  `tests/test_error_details_dialog_regressions.py` (25 test) +
  `tests/test_safe_console_regressions.py` (42 test) +
  `tests/test_error_path_single_quote_regressions.py` (57 test) + `tests/test_error_path_uri_quote_regressions.py` (47 test) +
  `tests/test_error_path_scanner_regressions.py` (55 test) +
  `tests/test_error_path_boundary_regressions.py` (45 test) +
  `tests/test_error_redaction_gaps_regressions.py` (38 test) +
  `tests/test_error_redaction_hardening_regressions.py`
  (53 test) + `tests/test_error_reporting_core_regressions.py` (31 test,
  gerçek `APPDATA` yerine geçici dizin kullanır).
- Bu tur YALNIZ 1. aşamadır: ayrıntı penceresi, log yönetimi/"Logları
  Temizle" arayüzü ve "Hatayı Bildir" akışı YAPILMADI.

## Altyazı indirme: tek ve kesin davranış

Kırmızı kanıt: hedefte kullanıcıya ait bir `.srt` varken
`download_and_apply()` **False** dönüyordu — onay kancası olmadan akış
tamamen bloke oluyor, kullanıcıya "Mevcut altyazı dosyası korunuyor"
yazılıyordu. 15 test kırmızıydı.

- Hedef `subtitle_target_path()`: videonun klasöründe `<video adı>.srt`.
  Uzak dosya adı, dil eki, `.1`/`(1)` türevi YOK (bu kısım zaten
  doğruydu, artık testle kilitli).
- **Üzerine yazma onayı kaldırıldı.** `confirm_overwrite` kancası,
  `OverwriteConfirmDialog` sınıfı ve `SubtitleCenterCoordinator`'ın
  ilgili parametresi silindi. Yazma yalnız indirme + SRT doğrulaması
  TAMAMLANDIKTAN sonra, geçici dosya + flush/fsync + `os.replace` ile
  yapılır; geçersiz/boş/HTML gövde mevcut dosyaya hiç ulaşmaz.
- **Tek eylem.** "Yalnızca İndir" düğmesi ve `download_only()` akışı
  kaldırıldı; `İndir ve Uygula` tek giriş noktasıdır.
- **`after_download` kaldırıldı.** Ayar hiçbir davranışa bağlı değildi.
  Sabitler (`AFTER_DOWNLOAD_*`), ayar penceresindeki kutu ve controller
  eşlemesi silindi. `load()` artık yalnız `username` + `language`
  döndürür; eski QSettings anahtarı okunmaz, yazılmaz ve SİLİNMEZ —
  varlığı hata üretmez (`apply`, `download_only`, boş ve bozuk değerlerle
  ölçüldü).
- Sözleşme: `tests/test_subtitle_download_flow_regressions.py` (27 test).
  Eskiyen testler gevşetilmeden güncellendi/kaldırıldı ve gerekçesi
  dosyalarına yazıldı: `test_download_only_never_touches_mpv`,
  `test_denied_overwrite_makes_zero_network_calls`,
  `test_missing_confirm_callback_is_fail_closed`,
  `test_default_confirmation_is_a_themed_dialog`,
  `test_explicit_buttons_ignore_the_after_download_preference`,
  `test_download_buttons_disabled_until_selection`,
  `test_action_row_button_order`.
- **Gerçek Windows kabulü** (`tests/native_subtitle_download_child.py`,
  `MLC_DIALOG_REAL_PLATFORM=1`): geçici klasörde `Ornek Film.mkv` +
  önceden var olan `Ornek Film.srt`, gerçek `QMainWindow` +
  `SubtitleCenterDialog`, gerçek düğme tıklaması. **11/11 PASS**,
  exit 0, `MARK_DONE`. Ölçülenler: ek pencere sayısı 0 (onay çıkmadı),
  içerik 44 bayta atomik değişti, klasörde yalnız `Ornek Film.mkv` +
  `Ornek Film.srt`, geçici artık yok, MPV'ye TAM hedef yol uygulandı,
  durum "Altyazı indirildi ve uygulandı.", kapanışta QThread hatası yok;
  geçersiz (HTML) indirmede dosya byte-for-byte korundu.
  KAPSAM SINIRI: istemci deterministik yerel sahtedir ve MPV yerine
  çağrı kaydeden nesne kullanılır — gerçek libmpv altyazı görüntüsü bu
  child'ın kapsamında DEĞİLDİR.

## SubtitleTrackWatcher zamanlama + kapanış turu (2026-08-14)

Bağımsız tekrar, önceki "ürün değil harness zamanlaması" sonucunu
reddetti: P/P150 ardışık üç koşumun ikisinde tam ekran altyazısı kontrol
bandına **105 px** giriyordu (`gap=-105`, `bottom=1435`, `band_top=1330`).

### Kırmızı kanıt

`test_subtitle_track_watch_regressions.py` +
`test_player_shutdown_regressions.py` ilk koşum: **6 failed, 84 passed**.

- `SubtitleTrackWatcher.detach()` yoktu; exact callback ile hiçbir
  `unobserve_property()` çağrısı yapılmıyordu.
- Detach sonrası doğrudan/gecikmiş callback no-op garantisi yoktu.
- 150 `osd-dimensions` bildirimi **150 ana-thread senkronu** üretiyordu.
- Kapanışta watcher, MPV `stop/terminate` öncesinde ayrılmıyordu.

### Ürün düzeltmesi

- Watcher bağlı MPV nesnesini ve kayıt sırasında kullanılan **tek callback
  nesnesini** saklıyor. `detach()` idempotent; `sid`, `track-list` ve
  `osd-dimensions` exact callback ile tam bir kez ayrılıyor.
- MPV olay thread'indeki fırtınada yalnız ilk bildirim queued Qt sinyali
  üretiyor; ana thread son MPV geometrisini okuyup tek kez senkronluyor.
  Detach sonrası doğrudan veya önceden kuyruğa alınmış bildirim no-op.
- Gerçek MPV aynı OSD değerini art arda iki kez yayıyor. Zaman izi P-r01'de
  tam ekran isteğinden 17 ms sonra son 2560x1440 değerinin ana thread'de
  okunduğunu ve `sub_pos` 84,20 -> 91,53 yazıldığını gösterdi. Sabit sleep
  artırılmadı, polling/sürekli timer eklenmedi; beşer tekrarda ek bounded
  retry gerektiren geç durum görülmedi.
- Watcher gerçek `MPVPlayer` QObject çocuğudur. Kapanış sırası artık
  `watcher.detach -> mpv.stop -> mpv.terminate`; detach hatası kapanışı
  engellemez ve ham teknik metin yazdırılmaz.

### Güçlendirilmiş gerçek kabul

Runner her çağrı için benzersiz oturum klasörü, her tekrar için `r01-r05`
logu üretir. P/P150 beşer kez ayrı child'da koşar; normal, playlist, tam
ekran ve normale dönüşün her biri piksel + MPV readback ile ölçülür.

Oturum: `20260814-120815-37992` — **10/10 child PASS**, her child 21/21,
FAIL/BLOCKED/timeout/eksik marker/process leak yok.

| Koşum | normal gap/pos | playlist gap/pos | fullscreen gap/pos | dönüş gap/pos |
|---|---:|---:|---:|---:|
| P-r01 | 45 / 84,20 | 36 / 84,20 | 75 / 91,53 | 45 / 84,20 |
| P-r02 | 45 / 84,20 | 36 / 84,20 | 75 / 91,53 | 45 / 84,20 |
| P-r03 | 45 / 84,20 | 36 / 84,20 | 75 / 91,53 | 45 / 84,20 |
| P-r04 | 45 / 84,20 | 36 / 84,20 | 75 / 91,53 | 45 / 84,20 |
| P-r05 | 45 / 84,20 | 36 / 84,20 | 75 / 91,53 | 45 / 84,20 |
| P150-r01 | 45 / 84,20 | 36 / 84,20 | 53 / 87,29 | 45 / 84,20 |
| P150-r02 | 45 / 84,20 | 36 / 84,20 | 53 / 87,29 | 45 / 84,20 |
| P150-r03 | 45 / 84,20 | 36 / 84,20 | 53 / 87,29 | 45 / 84,20 |
| P150-r04 | 45 / 84,20 | 36 / 84,20 | 53 / 87,29 | 45 / 84,20 |
| P150-r05 | 45 / 84,20 | 36 / 84,20 | 53 / 87,29 | 45 / 84,20 |

### Son doğrulama

- Yeni/güncellenen odak sözleşmeleri: **144 passed**.
- İlk tam paket bir test vekili uyumluluğunu yakaladı: başlatılmamış
  `MPVPlayer.__new__()` SIP nesnesi QObject parent sanılıyordu. Ürün etkisi
  yoktu; başlatılmışlık `thread()` ile güvenle yoklanarak düzeltildi,
  ilgili paket **93/93** geçti.
- Nihai tam paket: **2642 passed, 15 skipped** (2633 -> 2642, tam +9 test).
- `compileall` temiz; `git diff --check` whitespace hatası yok (yalnız
  önceden var olan CRLF uyarıları).
- Commit/push/tag/release/paketleme yapılmadı.

## Harness altyapısı (yeni oturumda bilinmesi gerekenler)

- `tests/run_physical_acceptance.py <grup[,grup]>` — `MLC_NATIVE_SMOKE=1`, `MLC_NATIVE_TEST_VIDEO`, `MLC_PLAYLIST_VIDEOS` ister. BLOCKED/CRASH/eksik marker asla PASS değildir (`classify_group` / `overall_exit_code`).
- Fiziksel sürükleme `threaded_drag()` ile **ayrı worker thread'den** gönderilir; Qt GUI thread'inden gönderim `startSystemResize` gibi native modal döngülerde yanlış ölçüm üretiyordu. Her sürüklemede input sözleşmesi (`input_contract_problems`) doğrulanır.
- Saf, test edilen yardımcılar: `tests/physical_tolerances.py`, `tests/physical_targets.py`, `tests/physical_audio.py`, `tests/physical_layout.py`.
- Ses güvenliği: fiziksel child MPV'yi `ao=null` ile açar ve gerçek `current-ao` doğrulanmadan yüksek ses testi yapılmaz (`BLOCKED: AUDIO_SAFETY`).
- Native child'lar ürünün çıkış politikasını izler (`app.exec()` sonrası `os._exit`), kapanış `PLAYER.close()` ile başlar, `stop=1 → terminate=1` sınıf düzeyinde sayılır.
- Tanı child'ları: `native_overlay_input_zorder_child.py`, `native_resize_diag_child.py --direction <yön>`, `native_thumbnail_diag_child.py`, `native_player_shutdown_child.py`.
- `MLC_NO_SUB_VIDEO` sözleşmesi: dosyanın var olması yetmez; grup içinde gerçek yükleme, `video track > 0` ve `sub track == 0` doğrulanır, aksi halde `BLOCKED: NO_REAL_SUBTITLE_FREE_VIDEO`. Tıklama önkoşulu sağlanmazsa `BLOCKED: CLICK_TARGET`.
- Medya keşfi opt-in (`MLC_MEDIA_PROBE=1`): `tests/find_subtitle_free_media.py` → aday başına ayrı, timeout'lu `tests/media_track_probe_child.py` (`vo=null`, `ao=null`, yalnız `track_list`). Recursive tarama, kopyalama, dönüştürme ve ağ erişimi yok; en fazla 20 aday. Karar mantığı saf modülde: `tests/media_probe_rules.py`.

## Sıradaki tek adım

**GITHUB DEPOSU (madde 4) — KULLANICI KİMLİK DOĞRULAMASI GEREKİR.**
1. (klasör taşıma), 2. (sürüm tek kaynak) ve 3. (ayar kirlenmesi kök nedeni)
TAMAMLANDI ve madde 3 GERÇEK KOŞUMLA DOĞRULANDI (aşağıya bakınız).

### Yayın planı — 16 Ağustos 2026 kullanıcı kararı

Sıra bağımlılığa göre kuruldu, keyfî değil:

1. ~~**Klasör taşıma + ad**~~ → **YAPILDI.** Proje artık
   `C:\Users\<kullanici>\Desktop\Programlar TEST\2026 YENİLER\MLC Player`
   altında. Her şeyden önce yapıldı ki GitHub remote, installer yolları ve
   belgeler nihai konumu referans alsın.
2. ~~**Sürüm tek kaynak → v0.1**~~ → **YAPILDI.** Üç ayrı sürüm vardı:
   `config.VERSION = "1.1"` (hiç kullanılmıyordu), Hakkında penceresinde
   düz metin "Sürüm 1.1", installer'da `v1.0` + `VersionInfoVersion=1.0.0.0`.
   Artık `app/config.py` → `APP_VERSION = "v0.1"` tek kaynak; `WINDOWS_VERSION`
   (`0.1.0.0`) ondan türetilir, Hakkında sabitten okur, `MLCPlayer.iss`
   aynı değeri taşır ve setup adı `MLCPlayer_Setup_v0.1.exe` tanımdan türer.
   `tests/test_version_consistency.py` (6 test) üç yüzeyi bağlar; Inno
   betiği Python'u içe aktaramadığı için bağ testle korunur, ayrışırsa kırılır.
3. **Ayar kirlenmesi kusuru** (aşağıda "AÇIK ARAŞTIRMA" bölümü).
   Yayından önce kapanmalı: paketlenmiş sürümde de aynı harness koşulabilir.
4. **GitHub deposu.** Üç şeyi birden çözer: güncelleme kontrolünün adresi,
   GPLv3'ün karşılık gelen kaynak yükümlülüğü, yedek. Hesap: `IzzmooPro`.
   KULLANICI KİMLİK DOĞRULAMASI GEREKİR; ayrıca ikili dağıtılacaksa depo
   PUBLIC olmalıdır (private, kaynak erişimi yükümlülüğünü karşılamaz).
5. **Güncelleme denetimi** (buton + açılışta kontrol). 4'e bağımlı.
   Referans: `2026 YENİLER\Offer Management System\ui\utils\updater.py`
   (693 satır) + `tests/test_updater_asset_verification.py`,
   `test_update_dialog_lifecycle.py`. Oradan TAŞINACAK özellikler:
   `UpdateChecker(QThread)` (arayüz donmaz), `STARTUP_CHECK_TIMEOUT = 3`,
   izinli host listesi + `is_release_download_url()`, indirilen setup'ın
   **SHA-256 doğrulaması**, yarım indirmenin silinmesi, indirme sürerken
   pencere kapanışının güvenli ele alınması.
   BİZE UYARLANACAK: hata metinleri güvenli hata sisteminden geçer (ham
   URL/yol loglanmaz), YENİ TIMER EKLENMEZ (ürün değişmezi), kapanış
   kooperatiftir (`terminate()` yok). Asset adı `MLCPlayer_Setup_v0.1.exe`.
6. **Gerçek build → kurma/kaldırma kabulü.** En sona: 1-5'in hepsini
   içermeli. Kurma VE kaldırma sorunsuz mu, artık dosya kalıyor mu.

### ÖLÇÜLDÜ — codec kapsamı (kullanıcı sorusu: "her şeyi oynatabiliyor mu?")

Ölçüt kullanıcı kararıyla **VLC** alındı. Kullanıcının gerçek kütüphanesi
(`<medya>\Film` + `<medya>\Dizi`, 43 dosya) tek tek açıldı ve GERÇEK çözüm doğrulandı:

| | |
|---|---|
| Toplam dosya | 43 |
| Açılan + çözülen | **37** |
| Bozuk (VLC de açamıyor) | 6 |
| **Codec kaynaklı başarısızlık** | **0** |

Çalışan kombinasyonlar: `mkv/hevc/eac3` (20), `mkv/h264/eac3` (10),
`mkv/h264/dts` (2), `mkv/hevc/ac3`, `mkv/hevc/dts`, `mkv/hevc/pcm_s24le`,
`mp4/hevc/eac3` (2).

Açılmayan 6 dosya BOZUK: VLC de aynı hatayı veriyor —
`0x00 at pos 0 invalid as first byte of an EBML number`, `EBML header
parsing failed`. Dosyalar sıfır baytla başlıyor. Kontrol olarak bizim
açtığımız S02E12'de VLC "broken seekhead" uyarısı veriyor ama oynatıyor;
biz de oynatıyoruz — yani o dosyada VLC kadar toleranslıyız.

Decoder listesi **520 kayıt**; H.264, HEVC, AV1, VP9, VP8, MPEG-2/4, VC-1,
WMV3, ProRes, DNxHD, Theora / AAC, AC3, E-AC3, DTS, TrueHD, MLP, MP3, FLAC,
Opus, Vorbis, ALAC, WMA, APE, PCM — hepsi mevcut.

**Sonuç: codec kapsamında VLC'ye göre pratik fark YOK.** Fark yalnız
DVD/Blu-ray menüsü ve egzotik ağ protokollerinde olur; ikisi de ürünün
kapsamında değildir (arayüzde disk açma yok, ağ tarafı HTTP/HLS + yt-dlp).

YÖNTEM NOTU: ilk iki tarama 18 ve 22 SAHTE başarısızlık üretti. Sebep tek
süreçte 43 mpv nesnesi oluşturup yok etmek ve ardından 43 kez seek
zorlamaktı; ikisi de belgede izlenen Python 3.14/ctypes/python-mpv
kararsızlığını tetikliyor. ÜRÜN bunu yapmaz (oturum başına tek oynatıcı).
Güvenilir ölçüm seek KULLANMADAN, oynatmanın ilerlemesiyle yapılandır.

---

ÇÖZÜLDÜ (16 Ağustos 2026) — **boyutlandırmada video donması.** Kullanıcı
raporu: oynatma sırasında pencere boyutlandırılınca video "donuk donuk"
geçiyor; kullanıcı bunun mpv değişiminden önce olmadığını düşünüyordu ve
HAKLIYDI. Aynı prob, aynı makine, arka arkaya:

| `sync_subtitle_safe_band()` | ortalama | medyan | p95 | max |
|---|---|---|---|---|
| mpv 0.36 (eski) | 0,37 ms | 0,35 | 0,42 | 1,24 |
| mpv 0.41 (düzeltmeden önce) | 3,84 ms | 0,41 | **41,70** | **84,55** |
| mpv 0.41 (düzeltmeden sonra) | 0,05 ms | 0,04 | **0,07** | **0,12** |

Medyan hep aynıydı; bozulan KUYRUKTU — bu yüzden "bazen var bazen yok"
hissediliyordu. 84 ms = 60 Hz'de beş kare.

Kök neden: bant hesabı her çağrıda `osd-dimensions`, `sid` ve `track-list`
özelliklerini libmpv'den GUI thread'inde SENKRON okuyordu. Okumaların kendisi
ucuz (boştayken üçü 0,2 ms); pahalı olan KİLİT BEKLEMESİ — yeni mpv
boyutlandırma sırasında swapchain'i kurarken core lock'u eskisinden çok daha
uzun tutuyor. Elenen iki hipotez: property okuma maliyeti (karenin %1,2'si)
ve `control_overlay.raise_()` Z-sırası (0,03 ms).

Düzeltme: `SubtitleTrackWatcher` bu üç özelliği ZATEN gözlüyordu ama gelen
değeri atıyordu (`_notify(self, _name, _value)`). Artık saklıyor;
`VideoFrame._observed_property()` önce gözlenen değeri kullanıyor, yoksa eski
senkron yola düşüyor. Yeni timer/thread YOK, bant hesabı DEĞİŞMEDİ (52 mevcut
bant testi yeşil). Sözleşme: 3 yeni test — gözlemci varken 100 senkronda
sıfır libmpv okuması, gözlemci yokken senkron okuma hâlâ meşru, gözlenen yeni
alan banda yansıyor. Kullanıcı gerçek pencerede onayladı.

---

ÇÖZÜLDÜ (16 Ağustos 2026) — **altyazı görünmez tıklama payını da
temizliyordu.** Kullanıcı raporu: "güzel konumlandırma ama biraz daha
aşağıya almamız gerek."

Gerçek pencerede ölçüldü (1376×790): katman 110 px ve `overlay_timeline`
katmanın EN ÜSTÜNDEN başlıyor (y=0..47). Ama o 47 px'in çoğu TIKLAMA
alanıdır (`OVERLAY_TIMELINE_HIT_HEIGHT = 48`); kullanıcının GÖRDÜĞÜ çubuk
yalnız 3 px ve dikeyde ortalanmış. Yani çizilen çubuğun üstünde
**~22 px görünmez pay** var ve ayrılan bant onu da temizliyordu:
altyazının altı 672, görünen çubuk 708 → 36 px boşluk.

Düzeltme: `overlay_timeline_top_padding()` = `(48 - 3) // 2` = 22.
`subtitle_reserved_bottom()` bu payı SAYMAZ. Pay elle uydurulmadı, mevcut
iki sabitten türüyor; stylesheet'teki groove yüksekliği değişirse bant
kendiliğinden uyar.

DOKUNULMAYANLAR: tıklama alanı KÜÇÜLMEDİ (bilerek geniştir), OSD bandı
`_osd_reserved_bottom()` = 110 olarak KALDI (OSD yerleşimi değişmedi),
katman gizliyken bant hâlâ 0 (kullanıcının onayladığı davranış).

Ölçüt de aynı yere taşındı: `painted_controls_top()` katmanın üst kenarına
payı ekler. GEVŞETME DEĞİLDİR — `SAFE_GAP_MIN` aynen korundu, yalnız sıfır
noktası görünmez paydan görünen çubuğa taşındı.

`o_band` **17/17 PASS ×2 DPI**; boşluklar (çizilen çubuğa göre):
`stress_2x_5px` 25, `playlist_open` 20, `fullscreen` 28, `single_line` 13.
17 eskiyen test gevşetilmeden dönüştürüldü: sabit `110` yerine türetilmiş
`SUBTITLE_RESERVED` kullanılıyor, böylece bir daha elle güncelleme
gerekmeyecek. Kullanıcı gerçek pencerede onayladı.

**KAPANDI (16 Ağustos 2026) — kök neden kanıtlandı ve düzeltildi.**
Qt 6'da `QSettings(organization, application)` yapıcısı
`QSettings.setDefaultFormat()` değerini YOK SAYAR; her zaman NativeFormat
ile açılır. Ölçüm:

    setDefaultFormat sonrası -> Format.IniFormat
    QSettings(org, app)      -> Format.NativeFormat, \HKEY_CURRENT_USER\...
    QSettings(IniFormat,...) -> <dizin>\MLCPlayer\MLCPlayer.ini

Yani ~20 child'ın izolasyon deyimi `player.settings` için hiç çalışmıyordu;
`%TEMP%\mlc_subtitle_settings` altındaki 439 klasörün hepsi BOŞTU ve her
koşum doğrudan HKCU'ya yazıyordu. Düzeltme: `app/settings_store.py` →
`user_settings()` tek giriş noktası, biçimi AÇIKÇA verir. `player.py` ve
`subtitle_settings.py` oradan geçer; child'lar DEĞİŞMEDİ (mevcut deyim
artık gerçekten işe yarıyor). `tests/test_settings_isolation_regressions.py`
kaçağı ve "ürün kodu QSettings'i doğrudan kurmaz" kuralını korur.

GERÇEK KOŞUMLA DOĞRULANDI (kullanıcı izniyle, tek child,
`a_text_color`, gerçek 4K video): izole dizinde artık `.ini` VAR —
`<izole>\a_text_color-<pid>\MLCPlayer\MLCPlayer.ini` (565 bayt,
`sub_color=#FFF26A3D`, `sub_pos=90`, yani senaryonun sonda değerleri),
gerçek `HKCU\...\subtitle` ise DEĞİŞMEDİ (`#FFFFFFFF`, `sub_pos=100`).
Düzeltmeden önce tam bu değerler kayıt defterine yazılıyordu.

NOT (dürüst kayıt): aynı koşum kapanışta `access violation` ile düştü ve
`MARK_DONE` yayılmadı; sözleşme gereği koşum INCOMPLETE'tir. Bütün
senaryo RESULT satırları PASS. Bu çökme, PROJECT_STATUS'ta zaten izlenen
aralıklı Python 3.14/ctypes/python-mpv kapanış riskiyle aynı sınıftadır
(bkz. `P-r01` kaydı) ve ayar izolasyonuyla ilgisi yoktur; izole `.ini`
çökmeden ÖNCE yazılmıştı.

Aşağıdaki tarihsel kayıt, kusurun nasıl bulunduğunu belgeler.

**ÇÖZÜLDÜ — harness gerçek kullanıcı ayarlarını kirletmiş.**
Kullanıcı ekran görüntüsünde altyazıların YEŞİL göründüğünü bildirdi.
Ürün varsayılanı `#FFFFFFFF` (beyaz); ölçülen gerçek kayıt:

    HKCU\Software\MLCPlayer\MLCPlayer\subtitle
      sub_color = #FF00FF00      <- tests/subtitle_visual_acceptance_child.py
                                    PROBE_GREEN = QColor(0, 255, 0, 255)

Bu, CLAUDE.md'nin açık yasağıdır: "Qt/QSettings testleri benzersiz geçici
dizin kullanmalı; gerçek kullanıcı ayarlarını kirletmemeli."

Bilinenler: görsel kabul child'ı `MPVPlayer()` oluşturmadan ÖNCE
`QSettings.setDefaultFormat(IniFormat)` + `setPath(...)` çağırıyor (satır
2661-2663, player 2677'de kuruluyor) — yani izolasyon DOĞRU sırada. Ama
`%TEMP%\mlc_subtitle_settings\*` dizinleri oluşmuş ve İÇLERİ BOŞ: hiç `.ini`
yazılmamış. Yazımlar `player.settings` (`QSettings("MLCPlayer","MLCPlayer")`,
`player.py:148`) üzerinden `atomic_apply()`e gidiyor. Kaçağın tam yolu
KANITLANMADI; hangi child ve hangi koşumda olduğu da kesin değil (bugünkü
koşumlar veya izolasyon eklenmeden önceki bir oturum olabilir).

Sonraki tur: child'ı izole ayar dizinine yazıp yazmadığını doğrulayan
deterministik bir test yaz (koşum sonrası dizinde `.ini` VAR olmalı ve
gerçek kayıt defteri anahtarı DEĞİŞMEMİŞ olmalı), sonra kök nedeni kapat.
Bu kapanana kadar hiçbir görsel kabul koşumu "kullanıcı ayarına dokunmaz"
sayılmaz.

Kullanıcı onayıyla düzeltildi (16 Ağustos 2026): `sub_color` beyaza,
`sub_pos` 90 → 100. Diğer değerlere DOKUNULMADI.

ÖLÇÜLDÜ — **seek gecikmesi ürün kusuru DEĞİL.** Kullanıcı atlamaların
"tak diye" olmadığını bildirdi. Gerçek 4K HEVC dosyada ölçüm:
anahtar kare aralığı 1,01 sn; `absolute+exact` (ürünün yolu) ortalama
294 ms, `absolute+keyframes` ortalama 296 ms — İKİSİ AYNI. Gecikme seek
türünden değil, 31 GB'lık 2160p HEVC'nin okuma+çözme maliyetinden geliyor.
Seek modunu değiştirmek kazanç sağlamaz.

PASS — **`dragdrop/explorer_multi_drop` (16 Ağustos 2026, kullanıcı onayı).**
Explorer'dan 3-4 video seçilip oynatıcıya bırakıldı: hepsi listeye girdi,
sıralama doğru, ilki kendiliğinden oynadı, hata penceresi ve takılma yok.
Manuel kabul listesinde AÇIK MADDE KALMADI.

**Setup/EXE turu — kullanıcı kararıyla BURADA DURULDU (16 Ağustos 2026).**
Teknik engel kalmadı: dağıtılamaz mpv değişti, güvenli bant iki motorda da
doğrulandı, OpenSubtitles hız sınırı kapandı. Paketleme başlamadan ÖNCE
`docs/PACKAGING_PLAN.md` içindeki uyumluluk kontrol listesi kapatılmalı
(karşılık gelen kaynak erişimi, `licenses/` klasörünün setup'a girmesi,
dosya başı GPLv3 bildirimleri, kod imzalama). Bunlar kullanıcı/avukat
kararıdır.

Kalan küçük işler: `dragdrop/explorer_multi_drop` (manuel, kullanıcı elinde)
ve backlog 8/9 (VLSub ve VLC kaynak incelemesi; yayını bloke etmez).

ÇÖZÜLDÜ (16 Ağustos 2026) — **OpenSubtitles önleyici hız sınırı.** Servisin
resmî sınırı saniyede 1 istek; ürün bugüne kadar YALNIZ tepkisel davranıyordu
(`429/406` → `RateLimitError`). Artık bütün isteklerin geçtiği tek boğaz
noktası `_call()` içinde `_respect_rate_limit()` var: bekleme QThread
worker'ındadır (GUI donmaz), kilit eş zamanlı worker'ları ayırır, saat geri
giderse bekleme aralıkla sınırlanır. Tepkisel yol aynen korundu.
Sözleşme: 4 test. Tam paket süresine etkisi +4 sn.

ÇÖZÜLDÜ (16 Ağustos 2026) — **SRT güvenli bandı yeni motora kalibre edildi.**
`o_band` **17/17 PASS**, iki DPI'da da:

| durum | önce | sonra | marj |
|---|---|---|---|
| `playlist_open` | 105 px | **20 px** | 193 → 114 |
| `stress_2x_5px` | 153 px | **24 px** | → 57 |
| `fullscreen` | 30 px | **25 px** | 63 → 61 |
| `single_line` | 15 px | **12 px** | 116 → 114 |

İKİ ayrı kusur vardı ve ikisi de ölçümle ayrıldı:

1. **`sub-scale` çarpanı (yeni).** mpv 0.41 `sub-margin-y`yi yazı ölçeğiyle
   ÇARPIYOR, 0.36 çarpmıyordu. Ekran görüntüsünden piksel taramasıyla
   ölçüldü: 0.36'da ölçek 1,0→2,0 eğimi 2,888→2,881 (oran 0,998);
   0.41'de 2,881→5,769 (oran 2,003). Taban eğim iki motorda AYNI.
2. **Ölçek referansı (eskiden beri yanlış).** Referans olarak RENDER ALANI
   (`h - mt - mb`) besleniyordu. Aynı pencerede letterbox değiştirilip
   ölçüldü: eğim SABİT kalıyor (`osd h=1360 → 2,881`, `h=639 → 2,881`;
   iki motorda da). Yani referans YÜZEY yüksekliğidir. Eski varsayım yalnız
   letterbox payı küçükken (`mt=mb=8`/`28`) doğru sonuç veriyordu; playlist
   açıkken pay 159 olunca marj 193'e şişiyordu.

Doğrulanan model: `alt_kenar = yüzey - marj × (yüzey/720) × sub_scale`.
`single_line`: 772 − 116×(772/720) = 647,6; ölçülen bbox alt kenarı 647.

Eskiyen testler gevşetilmeden dönüştürüldü ve gerekçeleri dosyalarına
yazıldı: `test_the_scale_reference_is_the_rendered_video_area` →
`..._is_the_surface_height_not_the_video_area`; letterbox değişiminin marjı
değiştirmesini şart koşan iki test artık "hiçbir şey yazılmaz" diyor
(ölçülen doğru davranış); DPI ve dpr testlerindeki sayılar 1142→1158 ve
116→114 olarak güncellendi.

---

Önceki kayıt: **SRT güvenli bandını yeni motora göre yeniden kalibre et.** Gerçek video
kabulü koşuldu (16 Ağustos 2026, mpv v0.41). ASS tarafı **9/10 PASS** ve
tablo iki DPI'da birebir kararlı. SRT (`o_band`) tarafında **deterministik
bir konum regresyonu** var — iki DPI'da da birebir aynı sayılar:

| durum | ölçülen | beklenen | eski (v0.36) |
|---|---|---|---|
| `stress_2x_5px` | **gap=153** | 10–36 | 33 |
| `playlist_open` | **gap=105** | 10–28 | 23 |
| `fullscreen` | gap=30 ✅ | 10–36 | 31 |
| `single_line` | gap=15 ✅ | 10–36 | 12 |

Altyazı bandın İÇİNE girmiyor (güvenlik ihlali YOK); **çok yukarıda**
duruyor. Bozulan iki durumun ortak yanı, render edilen video alanının
pencereden farklı olması (2,00× yazı ve dar playlist yüzeyi). Şüphe
`sync_subtitle_safe_band()` içindeki `osd-dimensions` ölçek referansında:
v0.36 için kalibre edilmiş türetme v0.41'de aşırı marj üretiyor. Not:
v0.41'de `sub-margin-y-offset` ARTIK VAR; mevcut tasarımın gerekçesi
(o özelliğin yokluğu) ortadan kalktı, çözüm bu yolu kullanabilir.
Sıra: tek kırmızı ölçüm → minimum ürün düzeltmesi → `o_band` tekrar.

ASS tarafı doğrulandı (kayıt): normal 42, playlist 33, tam ekran 69,
dönüş 42 px; `sub_pos` 84,2 / 91,53. %150 DPI'da 41/33/49/41. Hepsi
pozitif ve ASS üst sınırı 90'ın altında.

Ayrıca bir koşumda (`P-r01`) kapanışta `access violation` görüldü ve
INCOMPLETE sayıldı; bu, PROJECT_STATUS'ta zaten izlenen aralıklı
Python 3.14/ctypes/python-mpv riskiyle aynı sınıftadır.

ÇÖZÜLDÜ (bu turda, harness): kabul 10/10'dan 2/10'a düşmüştü ve motor
suçlu görünüyordu. Değilmiş — 15 Ağustos 23:44'te test videosunun yanına
bir `.srt` gelmiş; ürün onu doğru biçimde etkinleştirip harness'in ham
`sub-add` ile eklediği parçanın seçimini alıyordu. Harness artık ürünün
kendi `suppress_local_subtitle()` sözleşmesini kullanıyor. Ürün kodu
DEĞİŞMEDİ.

---

Önceki kayıt: **Altyazı güvenli bandının GERÇEK VİDEO ile yeniden kabulü.** Yayın engeli
olan nonfree mpv değiştirildi (bkz. `docs/PACKAGING_PLAN.md` → "YAYIN
ENGELİ … → ÇÖZÜLDÜ"): artık **mpv v0.41.0-923 / FFmpeg N-126125**
kullanılıyor. Offscreen paket **3158 passed** ile temiz, API ve stil
değerleri 14/14 doğrulandı — ama bu, bandın PİKSEL düzeyinde korunduğunu
kanıtlamaz. mpv 0.36 → 0.41 ve FFmpeg 6 → 8 atlamasından sonra `o_band` ve
`p_ass_band` gerçek video koşumları tekrarlanmalı. Bu yapılana kadar güvenli
bant "doğrulanmış" SAYILMAZ. Koşum kullanıcı onayı, gerçek pencere ve gerçek
MKV gerektirir.

İkinci sırada: OpenSubtitles istemcisinde **önleyici hız sınırlaması yok**
(servis saniyede 1 istek istiyor; bizde yalnız `429/406` tepkisel ele alınıyor).

Not: `sub-margin-y-offset` v0.36'da yoktu ve mevcut tasarımın gerekçesiydi;
v0.41'de artık var. Bu turda hiçbir altyazı yolu değiştirilmedi.

Sonra backlog **8 (VLSub)** ve **9 (VLC)** kaynak incelemesi.

Açık ama proaktif iş gerektirmeyen: aralıklı native child takılması
(`default_ui_child.py` / `main_entry_child.py`). Faz işaretleri yerinde; bir
sonraki takılmada adım kendini gösterecek. Yeni hipotez olmadan koşma.

DÜZELTME (15 Ağustos 2026): bu bölüm uzun süre "Medya Bilgisi ÖNCE
tasarlanacak, kod yazılmadı" diyordu; kaynak doğrulamasında madde 5, 6 ve 7
zaten TAMAMLANMIŞTI (aşağıda işaretlendi). Belge dört tur geride kalmıştı.

ÇÖZÜLDÜ (harness): kapanışta meşru olarak silinen `overlay_timeline`
referansını `group_timeline()` bütün fazlarda yeniden kullanıyordu.
`widget_alive()`/`live_overlay_widget()` ile her ölçüm öncesi canlı referans
alınıyor; widget yoksa ham RuntimeError/exit=90 yerine
`BLOCKED: WIDGET_GONE`. Ürün `app/video_frame.py` bu düzeltmede değişmedi.

ERTELENDİ (kullanıcı kararı, 14 Ağustos 2026): Güvenli hata sisteminin
**4. aşaması "Hatayı Bildir/Gönder"**. 1-3. aşamalar (güvenli hata
çekirdeği, Hata Ayrıntıları, Günlük Yönetimi) tamamlandı ve yeterli
kabul edildi. Yeni hata raporlama tasarımı, ağ erişimi, backend veya
gönderim akışı YAPILMAYACAK; mevcut `ErrorEvent` + `clipboard_text()`
zaten güvenli, maskelenmiş bir gövde üretiyor.

ÇÖZÜLDÜ (bu turda): `sub_pos` yüksek değerlerde kontrol bandıyla
kesişiyordu. Artık güvenli alt bant var — SRT `sub-margin-y`,
ASS efektif `sub-pos`; ikisi de gerçek ayrılmış banttan türetiliyor ve
merkezi `SubtitleTrackWatcher` ile her parça/geometri değişiminde
uygulanıyor. Kullanıcının kayıtlı `sub_pos` tercihi DEĞİŞMİYOR.

Final kullanıcı manuel kabulü — **PASS (16 Ağustos 2026, kullanıcı onayı).**
**Frameless pencere fiziksel resize'ı** gerçek Windows penceresinde elle
doğrulandı: sağ kenar, sol kenar, alt kenar, sağ-alt köşe, sol-alt köşe,
**playlist paneli açıkken sağ kenar** (ayrı top-level `Qt.Tool` yüzeyi,
sınırlı manuel yedek yolu) ve bırakma sonrası sürüklemenin bitmesi. Kullanıcı
raporu: hepsi düzgün; imleç kenara gelince şekil değişiyor, kayma/sıçrama
yok. Otomatik fiziksel koşum `BLOCKED: INPUT_CONTRACT` olarak KALIR ve
tekrarlanmaz; kabul bu manuel doğrulamayla kapanmıştır.

Bu maddeyle birlikte manuel kabul listesinde AÇIK kalan tek madde
`dragdrop/explorer_multi_drop`tur (aşağıda).

Ertelendi (kullanıcı kararı): `dragdrop/explorer_multi_drop`: Explorer'dan gerçek çoklu sürükle-bırakın güvenilir otomasyonu araştırılsın. Otomasyon güvenilir değilse madde BLOCKED kalmalı ve manuel kabul maddesi olarak yazılmalı; `add_external_files()` çağırmak fiziksel PASS sayılmaz.

Sıra: aşağıdaki küçük ürün/araştırma paketi → kalan
canlı ve kullanıcı manuel kabulleri → commit'lere ayırma → GPLv3
`LICENSE`/`README` → EXE/setup.

## Mevcut düzeltmelerden sonra doğrudan geçilecek ürün/araştırma paketi

Kullanıcı kararı (14 Ağustos 2026): açık timeline/harness düzeltmeleri
tamamlanınca aşağıdaki maddeler kaybedilmeden, küçük ve bağımsız turlar
halinde ele alınacak. Çözülmüş davranışlar sebepsiz tekrar test edilmeyecek;
yalnız değişikliğin etkilediği yol nokta atışı regresyonla doğrulanacak.

1. **TAMAMLANDI — Video yüzeyi üzerinde fare tekerleğiyle ses:** İmleç oynatılan sahne/
   video yüzeyi üzerindeyken tekerlek sesi artırıp azaltmalı. Ses çubuğunun
   mevcut davranışı korunmalı; tek teker hareketi iki kez uygulanmamalı,
   seek/playlist kaydırması tetiklenmemeli ve ses sınırları aşılmamalı.
   Ürün `VideoFrame.wheelEvent()` içinde yalnız çıplak video sahnesinde,
   standart 120 birim/5 ses adımıyla ortak `change_volume()` yolunu kullanıyor;
   yüksek çözünürlüklü artıklar birikiyor, yatay teker ve çocuk yüzeyler
   ele geçirilmiyor. Hedef offscreen dosya önce 7 failed/6 passed, sonra
   **13/13 passed**. Gerçek mpv `wid` üzerinde fiziksel teker final kullanıcı
   manuel kabulüne bırakıldı; bu tur için native/tam paket tekrarlanmadı.
2. **2A VE 2B TAMAMLANDI — SRT otomatik etkinleştirme:** Kullanıcı geçerli bir
   `.srt` dosyasını oynatıcıya bıraktığında dosya yüklenmeli, yeni altyazı
   parçası seçilmeli ve altyazı görünürlüğü otomatik açık olmalı. Geçersiz
   dosya mevcut altyazı/oynatma durumunu bozmamalı.
   2A sonucu: canlı ve pending bırakma mevcut `SubtitleSession.apply()`
   yaşam döngüsüne bağlandı; tam `external-filename` doğrulanıyor, seçiliyor ve
   görünür yapılıyor. `apply()` transactional hale getirildi: yeni track
   doğrulanmadan eski çalışan track kaldırılmıyor; başarıda yeni track korunup
   yalnız eski oturum track'i kaldırılıyor. Hedef test **14/14 passed**.
   2B sonucu: `sub_auto=exact`; aynı klasördeki doğrulanmış `.srt` sessizce
   seçilip görünür yapılıyor. Medya başına durum `pending/done`; geç gelen
   external track sonradan seçiliyor, klasör/QSettings yeniden taranmıyor,
   kullanıcı altyazıyı kapatınca otomasyon tekrar açmıyor. Başarılı açık
   sürükle-bırak seçimi otomatik seçimi susturuyor; başarısız bırakma
   susturmuyor. İlk ek dil kodu, sonraki ekler izinli etiket olmak zorunda.
   Hedef test **38/38 passed**; gerçek libmpv'de geç gelen etiketli SRT kabulü
   final kullanıcı/manual kabulüne bırakıldı.
   **Video açılışında yerel SRT'yi otomatik etkinleştirme:** Video ile aynı
   klasörde ve aynı temel adda bulunan altyazı (`Film.mkv` -> `Film.srt`)
   video açılır açılmaz otomatik yüklenmeli, seçili altyazı parçası yapılmalı
   ve görünürlük açık olmalı. Bu işlem tamamen sessiz olmalı; kullanıcıya
   "altyazı bulundu/eklendi" bildirimi, pencere veya OSD gösterilmemeli.
   Eşleştirme mpv'nin resmi `sub-auto=exact` yaklaşımıyla uyumlu ve anlaşılır
   olmalı: `Film.mkv` için `Film.srt`, `Film.tr.srt` ve `Film.tur.srt` adaydır;
   `Başka Film.srt` veya yalnız klasörde bulunduğu için ilgisiz bir SRT aday
   değildir. Bozuk SRT videonun açılmasını engellememeli ve mevcut altyazı
   durumunu bozmamalı.

   **Araştırma sonucu ve uygulanan kesin sözleşme (14 Ağustos 2026):**
   Önceki ürün `sub_auto="fuzzy"`, `sub_visibility="no"` kullanıyordu ve her
   yeni medyada görünürlüğü ayrıca kapatıyordu; dolayısıyla benzer adlı
   dosyaları gereğinden geniş yükleyebiliyor ama kullanıcıya göstermiyordu. mpv'nin
   güncel resmî kılavuzunda varsayılan `exact`, tam video temel adını ve dil
   soneklerini yükler. Güncel kaynak kodu eşleşmeyi büyük/küçük harf duyarsız
   yapıyor; ISO/IETF dil soneklerini (`tr`, `tur`, `en`, `eng`, `pt-BR` vb.)
   ve `forced`, `default`, `sdh`, `hi`, `cc` etiketlerini tanıyor. VLC'nin
   resmî masaüstü belgesi de altyazıların varsayılan açık olmasını normal
   davranış sayıyor; fakat ad eşleştirme ayrıntısını mpv kadar kesin
   tanımlamadığı için MLC sözleşmesinin teknik kaynağı mpv olacak.

   - Yalnız yerel video ile **aynı gerçek klasördeki** `.srt` otomatik açılır;
     URL'lerde ve mpv'nin başka yapılandırma altyazı klasörlerinde bu özel MLC
     davranışı çalışmaz.
   - Tam video gövdesi zorunludur. Örnek: `Film.2026.mkv` için
     `Film.2026.srt`, `Film.2026.tr.srt`, `Film.2026.tur.srt`,
     `Film.2026.tr.forced.srt` ve `Film.2026.tr.sdh.srt` geçerlidir;
     `Film.srt`, `Başka Film.srt` ve `Film.2026 Türkçe.srt` geçerli değildir.
   - Birden fazla adayda: düz `<video-adı>.srt` birinci; yoksa Altyazı
     Merkezi'ndeki kayıtlı dilin ISO soneki (`Türkçe` -> `tr`/`tur`) birinci;
     aynı öncelikte kalanlar mpv'nin dil/track önceliği ve doğal dosya sırası
     ile deterministik seçilir. Rastgele klasör sırası kullanılmaz.
   - Yükleme tamamlanıp `track-list` içinde `external=true`, uzantı `.srt`,
     `external-filename` aynı klasör ve ad sözleşmesine uygun olarak
     doğrulandıktan sonra o track'in `sid` değeri seçilir ve
     `sub_visibility=True` yapılır. Sadece dosya adına bakarak görünürlük
     açılmaz; böylece bozuk/okunamayan dosya sahte başarı oluşturmaz.
   - Otomatik etkinleştirme her medya yüklemesinde **yalnız bir kez** denenir.
     Kullanıcı sonradan altyazıyı kapatırsa `track-list`/geometri olayları onu
     tekrar açamaz. Playlist parça değişiminde yeni medya için yeniden
     değerlendirilir; aynı parçadaki tekrar olaylar idempotenttir.
   - Başarı tamamen sessizdir: QMessageBox, durum yazısı veya OSD yoktur.
     Otomatik yükleme hatası da videoyu kesmez; yalnız maskelenmiş geliştirici
     loguna düşebilir. Altyazı düğmesi/menüsü gerçek MPV durumunu yansıtır.
   - Uygulama yönü: `sub_auto` geniş `fuzzy` yerine `exact` yapılır; fakat
     yalnız ayar değişikliğine güvenilmez. Mevcut merkezi `track-list`
     gözleminden ayrılmış, tek-atımlık ve yaşam döngüsü temiz bir yerel-SRT
     etkinleştiricisi seçimi/görünürlüğü doğrular. Manuel `.ass/.ssa/.vtt/.sub`
     desteği korunur; bu otomatik-açık sözleşmesi yalnız `.srt` içindir.
   - Nokta atışı kabul örnekleri: tam ad; `tr`/`tur`; `tr.forced`/`tr.sdh`;
     farklı ad; benzer/kısaltılmış ad; birden fazla dil; bozuk SRT; kullanıcı
     kapattıktan sonra olay tekrarı; playlistte ikinci video; URL. Uzun genel
     fiziksel matris tekrar edilmeyecek.
3. **Alt kenar ve köşelerden pencere boyutlandırma — TAMAMLANDI
   (kaynak/offscreen doğrulaması):**
   - Kök neden: `FramelessResizeFilter._window_position()` child koordinatını
     `watched.mapTo(player, point)` ile çeviriyordu. Bu yalnız aynı pencere
     hiyerarşisi için doğrudur; `video_frame.control_overlay` ise ayrı bir üst
     seviye `Qt.WindowType.Tool` penceresidir ve videonun alt kenarına sıfır
     boşlukla, tüm genişlikte oturur. Orada `mapTo()` ana pencere değil GLOBAL
     ekran koordinatı üretiyordu. Sonuç iki yönlüydü: sol kenar ve sol-alt köşe
     overlay üzerindeyken hiç algılanmıyor, overlay'in iç bölgesi ise yanlışlıkla
     alt kenar sanılıp resize başlatıyordu.
   - Düzeltme: `app/title_bar.py::_window_position()` artık
     `player.mapFromGlobal(event.globalPosition().toPoint())` kullanıyor; bu tur hem
     gömülü child'lar hem de ayrı üst seviye overlay için doğrudur.
     `resize_edges_at()` ve `RESIZE_MARGIN` değişmedi.
   - Ürün düzeltmesi doğrulaması: hedef test
     `tests/test_frameless_resize_edge_delivery_regressions.py` **6/6 passed**;
     dar regresyon (`window_edge_margin` + dört `title_bar` paketi)
     **120/120 passed**.
   - Gerçek `native_resize_diag_child.py --direction bottom_left` koşumu
     **BLOCKED: INPUT_CONTRACT**. Neden ürün değil girdi teslimiydi:
     `SetCursorPos` imleci hedefe (303, 916) götüremedi, imleç (1336, 823)'te
     kaldı. Pencereye tek bir press ulaşmadı (`press_count=0`),
     `startSystemResize` hiç çağrılmadı (`start_calls=0`), geometri değişmedi
     (`deltas` hepsi 0). Bu bir ürün FAIL'i DEĞİLDİR; düzeltilen kod yolu o
     koşumda hiç çalıştırılmadı. Final marker `MARK_DONE`, exit=1, crash yok.
   - Harness güvenliği: aynı koşum masaüstünde hedef dışı ~1100 px'lik sol
     sürükleme üretti. `native_resize_diag_child.py::input_worker()` artık
     **fail-closed**: sol tuş zaten basılıysa, imleç toleransa oturmadıysa veya
     `WindowFromPoint` beklenen pencereyi vermiyorsa TEK bir mouse olayı bile
     gönderilmez; başarısız `SendInput` başarı sayılmaz; LEFTDOWN sonrası hatada
     `finally` içinde LEFTUP denenir. Önkoşullar yalnız worker thread'de ve Win32
     verisiyle denetlenir, Qt nesnesine dokunulmaz. Doğrulama:
     `tests/test_native_resize_input_safety_regressions.py` **6/6 passed**
     (Win32 sahtelenir; gerçek fare/pencere/video yok).
   - AÇIK KALAN: gerçek Windows penceresinde fiziksel kenar/köşe sürüklemesi
     **final kullanıcı manuel kabuline** taşındı. Otomatik fiziksel koşum bu
     turda kullanıcı kararıyla tekrarlanmadı.
4. **Klasör Aç / dizini oynatma listesi yapma (mevcut, korunacak):** Kaynak
   doğrulamasında özellik zaten mevcut: `Ortam > Klasör Aç` seçilen klasörün
   yalnız üst seviyesindeki desteklenen medya dosyalarını doğal ad sırasıyla
   (`Bölüm 1`, `Bölüm 2`, `Bölüm 10`) tek oynatma listesine koyuyor ve ilk
   dosyayı başlatıyor. Dolayısıyla klasörde 10 desteklenen video varsa 10'u da
   sırayla listeye ekleniyor; altyazı, metin, kısayol ve alt klasör girdileri
   listeye katılmıyor. İptal, okunamayan/boş klasör veya ilk dosyanın açılamaması
   mevcut oynatma durumunu atomik olarak koruyor/geri alıyor. Bu yeni özellik
   olarak tekrar yazılmadı. Alt klasörleri özyinelemeli tarama eklenmedi;
   kullanıcı seçtiği klasörün doğrudan içeriğini görmeye devam ediyor.

   **Yerel-SRT birleşimi: TAMAMLANDI — birleşim kilitlendi (15 Ağustos 2026).**
   - **Ürün kodu DEĞİŞMEDİ.** Kaynak incelemesinde kusur kanıtlanamadı; eksik
     olan kusur değil kapsamdı. Mevcut `test_a_new_playlist_item_is_evaluated_again`
     parça değişimini elle taklit ediyordu (`current_file`, `track_list`, `sid`,
     `sub_visibility` doğrudan set ediliyordu); gerçek kablolama hiç koşulmuyordu.
   - Kilitleyen tek test:
     `tests/test_local_subtitle_autoload_regressions.py::test_a_folder_playlist_activates_each_media_own_subtitle`
     **1/1 passed**. Zincir gerçek ürün kodudur: `folder_media_files()` →
     `play_from_playlist()` → `_hide_subtitles_for_new_media()` →
     `activate_local_subtitle()`. Doğrulananlar: doğal sıra Film1→Film2; her
     medyanın kendi SRT'si tam `external-filename` doğrulamasıyla seçiliyor;
     `current_file` mpv `play()` çağrısından ÖNCE yeni medyaya geçiyor; geçişte
     `sub_visibility=False`; `track-list` bayatken Film1'in `sid`'i Film2 adına
     seçilmiyor ve karar `pending` kalıyor; Film2 track'i gelince seçim
     tamamlanıyor; Film1'in `done`/`suppress` durumu Film2'yi engellemiyor.
   - Sızma yolu kaynaktan kapalı: durum anahtarı `current_file` yolunun kendisi
     ve `verified_track_id()` tam yol karşılaştırması yapıyor; bayat `track-list`
     penceresinde eşleşme oluşamıyor.
   - **KALAN RİSK — ÖLÇÜLDÜ VE KAPANDI (16 Ağustos 2026).** Soru şuydu: yeni
     medyada `sid` açıkça sıfırlanmıyor; eski seçim yeni dosyaya taşınıp
     yanlış altyazı sessizce görünür mü? Gerçek libmpv (v0.41) ve iki gerçek
     4K medya ile ölçüldü (`sub_auto=exact`, ürün ayarları):

     | adım | `sid` | `sub_visibility` | seçili parça |
     |---|---|---|---|
     | Film1 yüklendi | 5 | False | Film1'in kendi SRT'si |
     | kullanıcı `sid=3` seçti | 3 | True | gömülü |
     | Film2 `play()` hemen sonrası | **3** | **False** | farklı dosyanın 3'ü |
     | Film2 parça listesi yerleşti | 5 | False | Film2'nin kendi SRT'si |

     Eski `sid` SAYISI kısa bir pencerede taşınıyor ve o an başka bir parçaya
     denk geliyor — ama ürün geçişten ÖNCE `sub_visibility=False` yaptığı için
     o pencerede ekranda hiçbir şey görünmüyor. Liste yerleşince her medya
     kendi altyazısını alıyor. `activate_local_subtitle()` görünürlüğü ancak
     `verified_track_id()` ile TAM YOL doğrulamasından sonra açtığı için
     yanlış parça görünür hâle gelemiyor. Koruma tasarlandığı gibi çalışıyor;
     bu madde manuel kabul listesinden ÇIKARILDI.
5. **TAMAMLANDI — Medya Bilgisi:** `app/media_info.py` + `app/media_info_dialog.py`
   yazıldı ve `player.py` / `menu_actions.py` / `video_frame.py` /
   `media_controls.py` üzerinden bağlandı. `test_media_info_builder` +
   `test_media_info_dialog` + `test_media_info_integration` **162/162 passed**.
   Aşağıdaki özgün tasarım notu kayıt olarak korunuyor.

   Özgün tasarım notu: Mevcut uygulamada kullanıcıya
   açılan bir "Medya Bilgisi/Ayrıntıları" penceresi yok. `track_labels.py` ve
   MPV `track-list` verileri ses/altyazı menülerinde kısmen kullanılıyor, ancak
   bütün medya için tek ve anlaşılır bir görünüm sunulmuyor. Ana menüde ve
   video sağ-tık menüsünde **Medya Bilgisi** eylemi olacak; medya yokken pasif
   kalacak. Ham MPV anahtarlarını göstermeyen kompakt, temalı pencere:

   - Genel: dosya adı, klasör/konum, dosya boyutu, süre, kapsayıcı/format ve
     varsa medya başlığı;
   - Video: çözünürlük, görüntü oranı, codec, kare hızı, bitrate ve güvenle
     tespit edilebiliyorsa HDR bilgisi;
   - Ses: seçili ve diğer parçaların anlaşılır dil, codec, kanal düzeni,
     örnekleme hızı ve bitrate bilgisi;
   - Altyazı: seçili ve diğer parçaların dili, codec/türü, gömülü veya harici
     oluşu ve harici ise yalnız kullanıcı arayüzünde uygun dosya adı;
   - Eksik/bozuk metadata çökme veya `None`, `demux-*`, ham track ID gibi teknik
     metin üretmemeli; bilinmeyen alan `Bilinmiyor` olmalı veya gizlenmeli.

   Bilgi yerel MPV özellikleri ve mevcut güvenli format yardımcılarından
   okunacak; sırf bu pencere için ağ isteği, medya dönüşümü veya sürekli
   `ffprobe` child süreci başlatılmayacak. URL'de sorgu tokenları gösterilmeyecek.
   Tam yol/kopyalanabilir teknik özet ancak kullanıcının açık eylemiyle
   sunulmalı. Pencere açıkken parça değişirse güvenli biçimde yenilenmeli veya
   hangi medya anlık görüntüsünü gösterdiği açık olmalı. Kabul yalnız sahte ve
   bozuk metadata, yerel video, URL ve çok parçalı bir medya üzerinde hedefli
   testlerle yapılacak; tam fiziksel matris tekrarlanmayacak.
6. **TAMAMLANDI — Üç nokta menüsü kapandıktan sonra düğme görselini sıfırlama:**
   `title_bar.py::show_overflow_menu()` artık `try/finally` içinde
   `setDown(False)` + `_set_more_state(menu_open=False, dismissed=...)` yapıyor;
   `menuOpen` / `menuDismissed` stil durumları ve yalnız `more_button` Enter/Leave
   dinleyen `eventFilter` eklendi. `test_title_bar_overflow_button_regressions.py`
   **11 test**. Özgün kayıt: Özel
   başlık çubuğundaki `titleMore` düğmesi genel `QPushButton:hover` stilini
   kullanıyor; `show_overflow_menu()` içindeki bloklayan `menu.exec()` dönüşünde
   açık/basılı görsel durum ayrıca temizlenmiyor. Menü Escape ile, bir eylem
   seçilerek veya dışarı tıklanarak kapandığında düğme gri seçili görünümde
   kalmamalı.

   - Normal hover ile `menu açık` durumu görsel olarak ayrılacak. Menü açıkken
     belirgin vurgu olabilir; `exec()` her dönüş yolunda (`finally`) açık durum
     kaldırılıp düğme `down/focus/style` durumu güvenle yenilenecek.
   - İmleç gerçekten düğmenin üstündeyse yalnız normal ve hafif hover görünümü
     kalabilir; menü kapalıyken basılı/seçili görünüm ASLA kalmamalı.
   - Mevcut kalıcı tek `QMenu`, menü eylemlerinin canlı checked/enabled durumu,
     üç nokta menüsünde duplicate olmaması ve klavye/fare açma yolları
     korunacak. Yeni timer veya yeni menü nesnesi üretilmeyecek.
   - Escape, eylem seçimi ve dışarı tıklama kapanışları tek hedefli offscreen
     regresyonla kilitlenecek; görsel ton final kullanıcı kontrolünde bakılacak.
     Bu kayıt henüz ürün kodu değişikliği değildir.

7. **TAMAMLANDI — Kontrol katmanına göre dinamik altyazı konumu:**
   `video_frame.py::subtitle_reserved_bottom()` katman gerçekten auto-hide ile
   gizlendiğinde 0 döner; `_overlay_band_hidden` / `_overlay_auto_hide_pending` /
   `_overlay_band_applied` ayrımı sayesinde fade'in her karesinde değil yalnız
   kararlı geçişte MPV'ye yazılır ve bastırma/minimize araya girerse bant
   çökmez. `_osd_reserved_bottom()` OSD için tek kaynak olarak DEĞİŞMEDİ.
   `test_subtitle_safe_band_regressions.py` 41 → **52 test**.
   Özgün kayıt: Mevcut güvenli bant, timeline/kontrol katmanı auto-hide ile
   tamamen gizlense bile korunuyor; bu yüzden altyazı sabit kalıyor. Kullanıcı
   kararı (15 Ağustos 2026): kontrol katmanı görünürken altyazı çakışmayacak
   biçimde üst güvenli konumda; katman tamamen gizlenince ise videonun altına
   daha yakın doğal konuma inebilmeli. Katman yeniden görünmeye başlarken
   altyazı kontroller çizilmeden önce yukarı çıkmalı; aşağı iniş yalnız fade-out
   tamamen bittikten sonra olmalı.

   - Fade'in her karesinde MPV property yazılmayacak. Yalnız kararlı
     `visible/hidden` durum geçişlerinde, mevcut önbellek/coalesce yolu üzerinden
     tek efektif senkron yapılacak; sürekli timer veya polling eklenmeyecek.
   - Kullanıcının kayıtlı `sub_pos` tercihi değişmeyecek. SRT için efektif
     `sub-margin-y`, ASS için mevcut efektif `sub-pos` yolu kullanılacak;
     bitmap/PGS motor sınırı ayrıca açıkça korunacak.
   - Alt konum ekran kenarına yapışmayacak; küçük güvenli alt boşluk kalacak.
     Playlist açık/kapalı, pencere/tam ekran ve %100/%150 DPI referansları
     mevcut güvenli bant hesabından türetilecek.
   - Sık mouse giriş-çıkışında zıplama/thrash olmaması, aynı kararlı durumda
     sıfır ek MPV yazımı ve gösterme başlangıcında hiçbir timeline çakışması
     hedefli testlerle kilitlenecek. Görsel geçiş davranışı uygulama öncesinde
     ayrıca değerlendirilecek; bu kayıt henüz ürün kodu değişikliği değildir.

8. **VLSub/OpenSubtitles incelemesi:** Tam kaynak güncel olarak incelenecek:
   https://github.com/opensubtitles/vlsub-opensubtitles-com
   Arama, kimlik doğrulama, dil/sonuç eşleme, indirme ve hata akışlarından
   MLC Player'a gerçekten yarayacak fikirler çıkarılacak. Lisans ve kullanım
   şartları doğrulanmadan kod kopyalanmayacak veya bağımlılık alınmayacak.
9. **VLC kaynak incelemesi:** Tam kaynak güncel olarak incelenecek:
   https://github.com/videolan/vlc
   Özellikle altyazı parçası seçimi, sürükle-bırak, ses tekerleği, frameless/
   native resize ve medya yaşam döngüsünde bize uygun fikirler araştırılacak.
   VLC kodunu doğrudan alma ile yalnız davranış/arkitektür fikrinden
   yararlanma arasındaki lisans farkı açıkça raporlanacak.
10. **Yayın öncesi hukuki ve uyumluluk araştırması:** Güncel ve birincil
   kaynaklarla bağımlılık/lisans envanteri çıkarılacak. Python paketleri,
   mpv/libmpv, FFmpeg/codec dağıtımı, OpenSubtitles API şartları, VLC/VLSub
   kaynak kullanımı, ikon/font/görsel varlıklar, gizlilik-log/ağ davranışı,
   üçüncü taraf bildirimleri, kaynak kodu sunma yükümlülüğü ve installer
   metinleri ayrı ayrı değerlendirilecek. Kod imzalama sertifikası ve
   SmartScreen itibarı ayrıca araştırılacak; imzanın lisans/telif
   yükümlülüklerinin yerine geçmediği açıkça korunacak. Sonuç hukuki görüş
   iddiası değil, yayın öncesi somut kontrol listesi ve gerektiğinde uzman
   avukata yöneltilecek açık sorular olacak.

Uygulama sırası: **1–7 TAMAMLANDI** → 8/9 kaynak araştırması → 10
hukuki/uyumluluk kontrolü → kalan canlı/manual kabul → paketleme kararı.
Kökte GPLv3 `LICENSE` ve `README` hâlâ YOK; paketli `yt-dlp`/`deno`/`mpv`
nedeniyle bu artık teorik bir eksik değildir ve dağıtımdan önce kapatılmalıdır.

Belgede kayıtlı olmayan iki ek tur kaynakta doğrulandı:
`app/thumbnail_service.py` küçük resim önbelleği artık uygulama kimliğinden
bağımsız sabit yoldadır (`test_thumbnail_cache_location_regressions.py`,
10 test) ve `packaging/` altında `build_release.bat` + `verify_build.py`
(`--pre` / `--post` / `--final`) + `MLCPlayer.iss` release zinciri mevcuttur.

## Açık riskler (engelleyici değil)

- Altyazı piksel runner'ında bir bağımsız tam tekrar sırasında
  `b_background_off` medya hazırlığı başında libmpv `_set_property`
  çağrısında `0xC0000005` verdi. Olay Görüntüleyicisi hatalı modülü
  `python314.dll` olarak kaydetti (`mpv-2.dll` değil). Sonrasında 30/30
  tekil B, 10/10 ardışık A→B çifti ve stil harness'ini kullanmayan 50/50
  normal ürün aç–oynat–kapat child'ı temizdi. Ürün davranışına bağlanamadı;
  yayın engeli değil, Python 3.14/ctypes/python-mpv test ortamı riski olarak
  izleniyor. Eksik marker veya nonzero exit hâlâ PASS sayılmıyor.
- Python yorumlayıcı finalizasyonunda `0xC0000005`: Qt + libmpv + `audio-device-list` okumasıyla ürün kodu olmadan 3/3 yeniden üretildi. `main.py` `os._exit(ret)` kullandığı için kullanıcı bu faza girmez.
- Fiziksel ölçümler tek makinede yapıldı; çoklu monitör doğrulanmadı.
  Altyazı güvenli bandı %100 VE %150 DPI'da gerçek video ile ölçüldü
  (`O`/`O150`, `P`/`P150`); diğer görsel senaryolar hâlâ `dpr=1.0`.
- Altyazı piksel harness'inin eski zamanlama kırılganlığı ürün olayı olarak
  doğrulandı ve merkezi queued olay birleştirmeyle kapatıldı. P/P150 artık
  her kabulde beşer kez koşar; 2026-08-14 matrisi 10/10 child ve 210/210
  satır PASS verdi. Tek başarılı son koşum önceki FAIL'i gizleyemez.
- Altyazı piksel kabulü tek medya + iki kare ile yapıldı; HDR/DV kaynakta
  renk toleransı yeniden değerlendirilmeli.
- `sub_back_color` alfası < 255 iken kutu rengi video ile harmanlandığı
  için ham renk maskesiyle bulunamaz; alfa etkisi kareler arası fark ile
  ölçülüyor (56.233 piksel).
- Aynı adlı `Son Açılanlar` girdileri klasör adı olmadan ayırt edilemiyor.
- Shuffle + playlist sarma ve asenkron MPV yükleme hatası ayrıca ele alınabilir.
- OpenSubtitles canlı sözleşmesi gerçek API anahtarı olmadan doğrulanmadı.
