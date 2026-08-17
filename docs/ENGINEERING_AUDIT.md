# Mühendislik denetim kaydı

Bulguların kalıcı kaydı. Her kayıt aynı alanları taşır; "iyileşti"
demek yerine **neyin ölçüldüğü** yazılır.

Yayın süreci burada tekrarlanmaz: `docs/RELEASE_PROCESS.md`.

## Durum sözlüğü

| durum | anlamı |
|---|---|
| **KANITLANDI** | kusur ölçümle gösterildi (kırmızı kanıt var) |
| **UYGULANDI** | ürün değişikliği yazıldı |
| **HEDEF TESTLERLE DOGRULANDI** | ilgili regresyon paketi yeşil |
| **CANLI KABUL BEKLIYOR** | gerçek build/pencere/yayın koşumu yapılmadı |
| **COMMIT BEKLIYOR** | değişiklik çalışma ağacında, commit edilmedi |
| **COMMIT EDILDI** | değişiklik yerel Git geçmişine kaydedildi; push anlamına gelmez |
| **TAMAMLANDI** | işin gerektirdiği tüm test ve **uygulanabilir** kabul ölçütleri sağlandı; canlı kabul gereken işlerde canlı kabul de tamamlandı |
| **ERTELENDI** | bilerek sonraya bırakıldı |

`TAMAMLANDI` ölçütü işin türüne göre uygulanır: canlı kabul gerektiren
işlerde (build, gerçek pencere, yayın) o kabul **şarttır**; yalnız belge
veya saf kaynak işlerinde canlı kabul **uygulanmaz** ve aranmaz.

**Commit bekleyen bir iş TAMAMLANDI sayılmaz.** Çalışma ağacında duran
değişiklik henüz kalıcı değildir.

## Kayıt kuralları

- Bağımsız olarak doğrulanmış her yeni bulgu **sabit bir kimlik** alır
  (`REL-`, `TEST-`, `DOC-`…). Kimlik yeniden kullanılmaz.
- **Claude raporu tek başına kanıt değildir.** Kanıt; komut çıktısı,
  ölçüm, test sonucu veya kaynak/satır referansıdır.
- Durum yalnız **bağımsız doğrulamadan** sonra ilerletilir.
- **Test sonucu, değişen dosyalar ve kalan risk zorunlu alanlardır**;
  boş bırakılmaz.
- Kapatılan risk **silinmez**; kaydı, sonucu ve kapanış kanıtı korunur.
- `docs/ROADMAP.md` her kabul edilen turun ardından güncellenir.
- `git status`, dal adı, commit sayısı gibi **dinamik** bilgiler
  tarih/snapshot belirtilmeden kalıcı gerçek olarak yazılmaz.

---

## REL-001

- **Kimlik:** REL-001
- **Baslik:** `mpv-2.dll` yayın ön-kontrolünde yalnız varlık bakımından denetleniyordu
- **Onem:** Yüksek — paketin %59'u o dosyadır; bozuk/yanlış sürüm bir DLL release zincirine girebilirdi
- **Durum:** KANITLANDI → UYGULANDI → HEDEF TESTLERLE DOGRULANDI → COMMIT EDILDI
- **Kanit:** `packaging/verify_build.py::check_pre()` içinde İKİ ayrı liste vardı. `SOURCE_FILES` üç runtime'ı da sayıyordu ama yalnız varlık denetimi yapıyordu; SHA-256 doğrulaması ayrı bir demettteydi (`yt-dlp.exe`, `deno.exe`) ve `mpv-2.dll` orada YOKTU.
- **Kok neden:** Tek kaynak yerine iki liste. Biri güncellenirken diğeri unutulabilir — nitekim unutulmuş.
- **Degisen dosyalar:** `packaging/verify_build.py`, `tests/test_verify_build_runtime_regressions.py`
- **Test kaniti:** 11 yeni test; dar regresyon (`+ test_runtime_binaries_regressions`) **52 passed**. Boyut kısayolunun hash yolunu maskelemediği, aynı boyutlu bozulma ve mutasyon denetimiyle ayrıca kanıtlandı.
- **Ek duzeltme (17 Agustos 2026, ayni kayit):** iki fail-closed açığı daha kapatıldı.
  1. `manifest_entries()` kaynaklı `OSError`/`UnicodeError`/`ValueError` yakalanmıyordu; eksik veya geçersiz UTF-8 taşıyan manifest **traceback** üretiyordu. Artık kontrollü hata + `--pre` exit 1.
  2. `fail()` koşulsuz `print` kullanıyordu; `log=` verilse bile hata mesajları stdout'a **kaçıyordu** ve çağıran toplayamıyordu. `fail(message, log=print)` oldu; `verify_runtime_binaries` içindeki bütün hata yolları verilen logger'a yazıyor. Varsayılan `print` olduğu için `check_pre`/`check_post`/`check_final` değişmeden çalışıyor.
  Eskiyen dört test gevşetilmeden dönüştürüldü: `capsys` yerine enjekte edilen logger'dan okuyorlar.
  **Yeni hedef test sonucu:** `tests/test_verify_build_runtime_regressions.py` → **17 passed**.
- **Canli kabul:** `python packaging/verify_build.py --pre` → **exit 0**, üç runtime da OK (`mpv-2.dll 119.757.824`, `yt-dlp.exe 18.226.085`, `deno.exe 97.408.288`).
- **Kalan risk:** Manifest'teki **beklenen değerlerin kendisi** doğrulanmıyor; yanlış hash'le güncellenen bir manifest ön-kontrolü yine yeşil geçer.
- **Commit durumu:** COMMIT EDILDI — `96a8f52`

---

## REL-002

- **Kimlik:** REL-002
- **Baslik:** `v0.35` ve `v0.36` tag'leri bir sürüm gerideki kaynak commit'ine işaret ediyor
- **Onem:** Yüksek — tag adı, tag içindeki kaynak sürümü ve kurulumu üreten commit ayrışmış
- **Durum:** KANITLANDI → UYGULANDI → HEDEF TESTLERLE DOGRULANDI → COMMIT EDILDI
- **Kanit:** Salt-okunur ölçüm: `v0.35 -> 2804c2f = 45de83c^` (snapshot'ında `APP_VERSION v0.34`), `v0.36 -> 5b987d1 = 8284771^` (snapshot'ında `APP_VERSION v0.35`). Release'ler `targetCommitish: master` ile oluşturulmuş.
- **Kok neden:** Çıkarım (kanıt değil): bump commit'i uzağa ulaşmadan release açılmış. **Release EXE'lerinin iç sürümü ÖLÇÜLMEDİ**; paket içeriği hakkında iddia yoktur.
- **Degisen dosyalar:** `packaging/verify_release_ref.py`, `tests/test_verify_release_ref_regressions.py`
- **Test kaniti:** **45 passed**. `APP_VERSION`, `MyAppVersion`, `VersionInfoVersion`, `VersionInfoProductVersion` ve HEAD doğrulanıyor; strict UTF-8 (`errors="replace"` fail-open'ı kaldırıldı), annotated tag `^{commit}` peel'i ve **bypass'sız** HEAD denetimi testle kilitli.
- **Canli kabul:** `--tag v0.36` → **exit 1**, beş ayrışma raporlandı. Beklenen sonuç; tarihsel kusurun canlı kanıtı.
- **Kalan risk:** Araç zincire bağlı değil, elle çalışır. Windows sürüm türetme kuralı `app/config.py::WINDOWS_VERSION` ile **elle** aynı tutuluyor; ürün kuralı değişirse sessizce ayrışır.
- **Commit durumu:** COMMIT EDILDI — bu kayıtla aynı pre-publish commit'i. **Geçmiş tag'ler değiştirilmedi.**

---

## REL-003

- **Kimlik:** REL-003
- **Baslik:** `build_release.bat` jokerle eski installer seçebiliyordu
- **Onem:** Yüksek — eski bir artifact imzalanıp yeni sürüm gibi raporlanabilirdi
- **Durum:** KANITLANDI → UYGULANDI → HEDEF TESTLERLE DOGRULANDI → COMMIT EDILDI → CANLI KABUL BEKLIYOR
- **Kanit:** `for %%F in ("installer_output\MLCPlayer_Setup_*.exe")` — `for` eşleşenleri gezer, SON eşleşme kazanır ve sıra dosya sistemine bağlıdır. Klasör birikimlidir. Asıl tehlike sıralama değil: Inno adımı yeni EXE'yi üretemezse joker sessizce eskisini seçer.
- **Kok neden:** Sonuç dosyası hesaplanmak yerine **aranıyordu**.
- **Degisen dosyalar:** `packaging/build_release.bat`, `tests/test_release_artifact_selection_regressions.py`
- **Test kaniti:** Eski 9 publishability testi **korundu** (`test_release_guard_regressions.py`, HEAD'e göre değişmemiş); 20 yeni artifact testi eklendi. Toplam **29 passed**. Sürüm/yol türetmesi ayrıca gerçek `cmd` ile doğrulandı (hiçbir şey silmeden).
- **Canli kabul:** Gerçek build **YAPILMADI**.
- **Kalan risk:** Betik uçtan uca çalıştırılmadı; PyInstaller/Inno/imza adımları bu turlarda koşmadı. Adlandırmanın ISS `OutputBaseFilename` ile bağı testle korunuyor ama iki yerde ayrı yazılı.
- **Commit durumu:** COMMIT EDILDI — `85dda6d`

---

## REL-004

- **Kimlik:** REL-004
- **Baslik:** Yerel yayın öncesi kapı yoktu
- **Onem:** Yüksek — yayın anında hiçbir mekanik denetim çalışmıyordu
- **Durum:** KANITLANDI → UYGULANDI → HEDEF TESTLERLE DOGRULANDI → COMMIT EDILDI → CANLI KABUL BEKLIYOR
- **Kanit:** `build_release.bat` tag'den habersiz (`git`/`gh` geçmez); `check_publishable.py` çalışırken tag henüz yok. Yayın anında tag bütünlüğü, ağaç temizliği ve varlık tamlığı denetlenmiyordu.
- **Kok neden:** Doğrulama build zincirine bağlanamaz (build sırasında tag yoktur), ama ayrı bir kapı da kurulmamıştı.
- **Degisen dosyalar:** `packaging/prepublish.py`, `tests/test_prepublish_regressions.py`
- **Test kaniti:** **32 passed.** Temiz Git ağacı (staged/tracked/untracked ayrı ayrı), tag bütünlüğü, dört installer/imza, **kriptografik Ed25519** doğrulama (başka EXE'ye ait geçerli imza da reddedilir) ve dört source mirror boyut/SHA-256 kontrolü. Hiçbir Git yazma komutu ve hiçbir ağ çağrısı yapılmadığı `subprocess.run` ve `socket.connect`/`urlopen` sarmalanarak ölçüldü.
- **Canli kabul:** Gerçek depoda `--tag v0.36` → exit 1 (tarihsel ayrışma + kirli ağaç). Gerçek bir yayın koşumu **YAPILMADI**.
- **Kalan risk:** Uzak GitHub doğrulaması (adım g ve i) **otomatik değil**; ağ gerektirir, kapı bilerek ağsızdır. Kapı yerel dosyaları denetler, GitHub'a gerçekten ne yüklendiğini görmez.
- **Commit durumu:** COMMIT EDILDI — bu kayıtla aynı pre-publish commit'i. Bozuk ASCII `.sig` ve bozuk manifest traceback'leri fail-closed kapatıldı (`UnicodeError`, `ValueError`/`TypeError`).

---

## REL-005

- **Kimlik:** REL-005
- **Baslik:** `build`/`dist` temizliği doğrulanmadan zincir devam ediyordu
- **Onem:** Yüksek — PyInstaller'ın ürettiği sanılan ağaç, önceki koşumun artığı olabilirdi
- **Durum:** KANITLANDI → UYGULANDI → HEDEF TESTLERLE DOGRULANDI → COMMIT EDILDI → CANLI KABUL BEKLIYOR
- **Kanit:** `packaging/build_release.bat` STEP 2'de `if exist "build" rmdir /s /q "build"` ve `dist` için aynısı vardı; **sonuç hiç denetlenmiyordu**. `rmdir /s /q` sessizce başarısız olabilir (kilitli dosya, açık Explorer penceresi, yetki sorunu) ve komut hata kodu döndürmeyebilir.
- **Kok neden:** Silme **denendi**, ama silinip silinmediği **ölçülmedi**. Aynı kusur sınıfı `installer_output` tarafında zaten kapatılmıştı (kesin dört hedef + `goto :fail`); `build`/`dist` o turda atlanmıştı.
- **Degisen dosyalar:** `packaging/build_release.bat`, `tests/test_release_artifact_selection_regressions.py`
- **Test kaniti:** Dört yeni kaynak-regresyon testi: `build` ve `dist` için ayrı ayrı `if exist … goto :fail` koruması, başarı mesajının **iki denetimden de sonra** geldiği, `rmdir`in yalnız bu iki hedefte ve jokersiz kullanıldığı, `installer_output` davranışının **değişmediği**. Dosya sonucu: **25 passed**.
- **Canli kabul:** Gerçek build **YAPILMADI**; betik bu turda çalıştırılmadı ve hiçbir klasör silinmedi. Koruma yalnız kaynak metninde ölçüldü.
- **Kalan risk:** Kilitli klasör senaryosu gerçek Windows'ta yeniden üretilmedi; `rmdir` başarısızlığının bu koşulda gerçekten `if exist` ile yakalandığı canlı koşumda görülmeli.
- **Commit durumu:** COMMIT EDILDI — `85dda6d`

---

## TEST-001

- **Kimlik:** TEST-001
- **Baslik:** Tam paket **taban** (baseline) sonucu ve açık bir çökme riski
- **Onem:** Orta — ölçüm hijyeni
- **Durum:** KANITLANDI (taban), CANLI KABUL BEKLIYOR (güncel koşum)
- **Kanit:**

  | koşum | sonuç | süre |
  |---|---|---|
  | **Taban** (REL-001…004 ÖNCESİ) | 3716 passed / 17 skipped | ~68 sn |
  | **Milestone** (17 Ağustos 2026, REL-001…005 SONRASI) | **3931 passed / 17 skipped / 1 failed** | **100,01 sn** |

  Taban ve milestone AYRI değerlerdir; taban güncel sonuç gibi
  sunulmamalıdır.

  **Tek failure ürün kusuru DEĞİLDİ:**
  `test_internet_video_addon_regressions.py::test_the_chain_builds_and_signs_the_addon`
  — eski test `ADDON_TO_SIGN` adlı geçici bir değişkeni arıyordu; ürün
  jokeri kaldırıp kesin `ADDON_SETUP` yolunu imzalamaya geçtiği için o
  değişken kalktı. **Bayat test assertion'ı**, davranış hatası değil.
  Ayrıntı: TEST-002.
- **Kok neden:** —
- **Degisen dosyalar:** —
- **Test kaniti:** Yukarıdaki taban koşumu.
- **Canli kabul:** Milestone koşumu yapıldı (yukarıdaki tablo). Bayat test düzeltildikten **sonra** tam paket bilerek yeniden çalıştırılmadı; 3931 yeşil testi tek bir test-only düzeltme için yeniden koşturmak gereksizdir.
- **Kalan risk:** **`0xe24c4a02` YENİDEN GÖRÜLDÜ** — aynı cover-art gerçek-mpv testinde, milestone koşumunda. Windows ölümcül istisnası, pytest `exit 0` verdiği hâlde ortaya çıkıyor. Risk **AÇIK**; pytest çıkış kodundan **bağımsız** izlenmelidir, çünkü yeşil sonuç onu gizliyor. Kök neden hâlâ araştırılmadı.
- **Commit durumu:** —

---

## TEST-002

- **Kimlik:** TEST-002
- **Baslik:** Add-on zincir testi uygulama ayrıntısına bağlanmıştı
- **Onem:** Orta — test bayatladı; ürün DÜZELDİĞİ için kırmızıya döndü
- **Durum:** KANITLANDI → UYGULANDI → HEDEF TESTLERLE DOGRULANDI → COMMIT EDILDI
- **Kanit:** Milestone koşumundaki tek failure:
  `test_the_chain_builds_and_signs_the_addon` → `assert "ADDON_TO_SIGN" in chain`.
  O değişken jokerle doldurulan bir arama sonucuydu
  (`for %%F in ("installer_output\MLCPlayer_InternetVideo_*.exe")`);
  REL-003 jokeri kaldırıp kesin `ADDON_SETUP` yoluna geçince değişken de
  kalktı.
- **Kok neden:** Test **davranışı** değil, bir **geçici değişken adını**
  ölçüyordu. Uygulama ayrıntısına bağlanan test, iyileştirme sırasında
  yanlış alarm verir.
- **Degisen dosyalar:** `tests/test_internet_video_addon_regressions.py`
  **Ürün/batch kodu DEĞİŞMEDİ.**
- **Test kaniti:** Sözleşme gevşetilmeden GÜÇLENDİRİLDİ: add-on build
  komutu, `if not exist "!ADDON_SETUP!"` koruması ve kesin
  `sign_release.py "!ADDON_SETUP!"` çağrısı ayrı ayrı aranıyor; üçünün
  **sırası** (build < koruma < imza) ve imzalama satırlarında **joker
  bulunmadığı** da doğrulanıyor. Sonuçlar:
  `test_internet_video_addon_regressions.py` **9 passed**,
  `test_release_artifact_selection_regressions.py` **25 passed**,
  `test_release_guard_regressions.py` **9 passed** (toplam **43 passed**).
- **Canli kabul:** Gerekmez (test-only düzeltme; ürün davranışı değişmedi).
- **Kalan risk:** Test hâlâ betiğin **kaynak metnini** ölçer, gerçek
  koşumunu değil. Sıra denetimi metin konumuna dayanır; bloklar yeniden
  düzenlenirse konum karşılaştırması yanıltabilir.
- **Commit durumu:** COMMIT EDILDI — `85dda6d`

---

## NATIVE-001

- **Kimlik:** NATIVE-001
- **Baslik:** Native `0xe24c4a02` istisnası yeşil pytest sonucunun arkasında gizleniyordu
- **Onem:** Yüksek — ölümcül görünümlü bir native olay, `exit 0` nedeniyle hiçbir kapıya takılmıyordu
- **Durum:** KANITLANDI → UYGULANDI → HEDEF TESTLERLE DOGRULANDI → COMMIT EDILDI
- **Kanit (olculen):**
  - `tests/test_cover_art_regressions.py` ANA pytest sürecinde doğrudan `mpv.MPV` kuruyordu; fixture yalnız `terminate()` çağırıyordu (ürün kapanışı `stop() -> terminate()` kullanır).
  - Bağımsız dosya koşumu: **3 passed / exit 0**, buna rağmen stderr'de
    `Windows fatal exception: code 0xe24c4a02`,
    `MPVEventHandlerThread -> mpv.py:689 _event_generator`.
  - Olay **hem** fixture geçişinde **hem de AKTİF testin** `wait_until_playing()` satırında görüldü.
  - Ortam: Python 3.14.3, python-mpv 1.0.8, libmpv API (2,5), mpv v0.41.0-923, FFmpeg N-126125.
- **Olculmeyen:** İstisnayı doğuran **native modül** belirlenemedi (sembol/debugger yok). **Ürün üzerindeki etki ölçülmedi**; ürün yolunun etkilenmediği İSPATLANMADI. Ürün `faulthandler` açmadığı için olay orada görünmez olurdu — bu görünmezlik, yokluk anlamına gelmez.
- **Kok neden:** Kesin kök neden **bulunamadı**. Kanıtlanan şey görünürlük kusurudur: `exit 0` native stderr'i akladığı için olay hiçbir kapıya takılmıyordu.
- **Degisen dosyalar:** `tests/cover_art_native_child.py` (yeni), `tests/test_cover_art_regressions.py`. **Ürün kodu, bağımlılık sürümleri ve `MPV_CONFIG` DEĞİŞMEDİ.**
- **Test kaniti:** Native senaryolar ayrı sürece taşındı; saf `evaluate_child()` deterministik olarak sınandı. **Deterministik: 61 passed** (18 Ağustos 2026 dilbilgisi turundan sonra). Native kabul, child üretim kodu değişmediği için TEKRARLANMADI; geçerli canlı sonuç bir önceki turun **39 passed / exit 0 / stderr BOŞ** koşumudur.

  **İLK DÜZELTME BAĞIMSIZ DENETİMDE REDDEDİLDİ.** O turdaki *23 passed* sonucu **nihai kabul DEĞİLDİR**; üç gerçek kusur taşıyordu:

  1. **Sıraya bağımlı test.** `assert "mpv" not in sys.modules` süreç genelini ölçüyordu; `app.player` zaten `mpv` import ettiği için başka bir test önce koşunca düşüyordu — kanıt:
     `pytest test_app_icon_regressions.py::test_the_real_main_window_uses_the_shared_icon test_cover_art_regressions.py::test_the_parent_process_never_imports_mpv` → **1 passed, 1 failed**.
     Yerine **bu modülün import ETKİSİ** ölçülüyor: taze kopya yüklenip `mpv` durumu ve MPV thread kümesi önce/sonra karşılaştırılıyor, ayrıca modül düzeyinde `import mpv` olmadığı statik olarak doğrulanıyor. Sıra regresyonu **iki yönde de yeşil**.
  2. **Eksik kapanış kapsaması.** Child iki instance kuruyordu ama tek `MARK_STOP`/`MARK_TERMINATE` çifti vardı; ikinci kapanış tamamen kaldırılsa bile değerlendirici yeşil kalabiliyordu. Artık senaryo başına ayrı marker (`MARK_COVER_*`, `MARK_NOCOVER_*`) ve **her senaryo için ayrı** `stop < terminate` denetimi var.
  3. **Aklanan hata.** `MARK_STOP_ERROR` yazılmasına rağmen kabul ediliyordu. Artık `MARK_*_ERROR` **kesin FAIL**; başarılı marker onu aklamıyor ve child exit 1 veriyor.

  **DORDUNCU KUSUR (18 Ağustos 2026, bağımsız denetim): marker biçimi fail-open'dı.**
  Değerler yalnız "beklenenden farklı mı" diye bakılıyor, BİÇİM hiç
  denetlenmiyordu. Kanıt: `MARK_COVER_TRACKS abc`, değersiz
  `MARK_THREADS_AFTER` ve `MARK_DONE junk` içeren çıktı `evaluate_child`
  tarafından `[]` — yani TAMAM — sayılıyordu. Artık `MARKER_GRAMMAR` her
  zorunlu marker için token sayısını ve değer dilbilgisini tanımlıyor:
  değersiz marker'lar TAM 1 token, sayısal marker'lar TAM 2 token
  (`MARK_COVER_TRACKS >= 1`; `MARK_COVER_SELECTED`,
  `MARK_NOCOVER_AUDIO_SELECTED` yalnız `1`; `MARK_NOCOVER_ALBUMART`,
  `MARK_THREADS_AFTER` yalnız `0`). Fazla/eksik token, metin, negatif ve
  boş değer FAIL. Eski gevşek semantik denetimler KALDIRILDI; zorunlu
  marker listesi de dilbilgisinden türüyor, ikinci bir liste yok.
  Boş olmadığı mutasyonla kanıtlandı: dilbilgisi çağrısı nötrleştirilince
  **13 failed**.

  Ek sertleştirmeler: marker ayrıştırması `startswith()` yerine **tam ilk-token** eşliği (`MARK_DONE_FAKE` artık `MARK_DONE` yerine geçmiyor), tekil marker tekrarı reddediliyor, `subprocess` çıktısı **bayt** yakalanıp açıkça çözülüyor (`text=True` yok; bozuk kodlamada ASCII desenin aranabilirliği testle ölçülü), geçici dosyalar `TemporaryDirectory` ile temizleniyor.
- **Canli kabul:** Yeni native child ile **TEK** gerçek kabul koşumu yapıldı: **39 passed, exit 0, stderr BOŞ**.

  **Bu sonuç NE ZAMAN alındı:** ilk ÜÇ düzeltmeden (sıra bağımlılığı, senaryo başına kapanış marker'ları, `MARK_*_ERROR` reddi) **SONRA**, dördüncü düzeltmeden (marker dilbilgisi sertleştirmesi) **ÖNCE**. Yani 39 passed rakamı dördüncü düzeltmenin *sonrasına* ait DEĞİLDİR.

  **Neden tekrarlanmadı:** dördüncü düzeltme yalnız **saf `evaluate_child` dilbilgisini** değiştirdi; child'in üretim/native senaryo kodu (MPV kurulumu, oynatma, kapanış, `mark()` çağrıları) **değişmedi**. Aynı native senaryoyu yeniden koşturmak yeni bilgi üretmeyeceği için koşum **bilinçli olarak tekrarlanmadı**.

  **Dilbilgisi sonrası bağımsız ölçüm:** deterministik **61 passed** (native koşum içermez).
- **Kalan risk:** **Tek native koşum, aralıklı kusurun tamamen bittiğini İSPATLAMAZ.** Ayrıca bu kaydın ilk hâli bağımsız denetimde REDDEDİLDİ; "hedef testler yeşil" tek başına yeterli kanıt olmadı — sıraya bağımlı bir iddia, eksik kapsama ve aklanan bir hata ancak dış denetimle görüldü. Olgu ölçümlerde ~%20-40 sıklıkla görülmüştü; bir yeşil koşum bunu dışlamaz. İstisna artık child'da oluşursa üst test FAIL verir — yani gizlenmez, ama **önlenmiş de değildir**. `module`-scoped fixture'a bilerek geçilmedi: instance sayısını azaltmak olguyu gizler, çözmez.
- **Commit durumu:** COMMIT EDILDI

---

## DOC-001

- **Kimlik:** DOC-001
- **Baslik:** Yayın süreci üç yerde birden yazılıydı
- **Onem:** Orta — kopyalar elle eşit tutuluyordu, sessiz ayrışma riski
- **Durum:** UYGULANDI → HEDEF TESTLERLE DOGRULANDI → COMMIT EDILDI → TAMAMLANDI
- **Kanit:** Kesin sıra `CLAUDE.md`, `docs/PACKAGING_PLAN.md` ve `packaging/prepublish.py` docstring'inde ayrı ayrı yazılıydı; hangisinin resmî olduğu belirsizdi.
- **Kok neden:** Tek kaynak yoktu.
- **Degisen dosyalar:** `docs/RELEASE_PROCESS.md` (yeni), `docs/ENGINEERING_AUDIT.md` (yeni), `docs/ROADMAP.md` (yeni), `CLAUDE.md`, `docs/PACKAGING_PLAN.md`, `packaging/prepublish.py`, `tests/test_release_documentation_regressions.py` (yeni)
- **Test kaniti:** `tests/test_release_documentation_regressions.py` — ayrıntılı a–j sırasının yalnız resmî belgede bulunduğunu, diğerlerinin ona bağlandığını ve kritik değişmezlerin korunduğunu ölçer.
- **Canli kabul:** Gerekmez (belge turu).
- **Kalan risk:** Belgeler ürün davranışını değil, metni ölçer. Sürecin gerçekten izlendiği ancak bir sonraki yayında görülür.
- **Commit durumu:** COMMIT EDILDI — bu kayıtla aynı pre-publish commit'i
