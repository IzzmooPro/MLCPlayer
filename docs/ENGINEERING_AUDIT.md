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
- **Baslik:** Tam paket **taban** (baseline), milestone ve güncel checkpoint sonucu
- **Onem:** Orta — ölçüm hijyeni
- **Durum:** KANITLANDI → TAMAMLANDI (güncel checkpoint)
- **Kanit:**

  | koşum | sonuç | süre |
  |---|---|---|
  | **Taban** (REL-001…004 ÖNCESİ) | 3716 passed / 17 skipped | ~68 sn |
  | **Milestone** (17 Ağustos 2026, REL-001…005 SONRASI) | **3931 passed / 17 skipped / 1 failed** | **100,01 sn** |
  | **Güncel checkpoint** (18 Ağustos 2026, NATIVE-001 commit'i SONRASI) | **3992 passed / 17 skipped / 0 failed; exit 0; stderr BOŞ** | **82,44 sn** |

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
- **Test kaniti:** 18 Ağustos 2026'da temiz `a7ced18` HEAD'i üzerinde tek tam koşum: **3992 passed / 17 skipped / 0 failed**, pytest **exit 0**, yakalanan stderr **0 bayt**. Stdout/stderr ayrı dosyalara yazıldı; koşum tekrarlanmadı.
- **Canli kabul:** Güncel tam paket checkpoint'i tamamlandı. Milestone'daki bayat TEST-002 assertion'ı artık kapalı; NATIVE-001'in child-process stderr kapısı tam paket içinde de yeşil kaldı.
- **Kalan risk:** Tek yeşil tam koşum zaman içindeki bütün aralıklı native davranışları dışlamaz. `0xe24c4a02` artık exit 0 arkasında sessizce geçemez ve bu koşumda görülmedi; ancak native kaynak modül ve ürün etkisi ayrı NATIVE-001 riski olarak açıktır.
- **Commit durumu:** COMMIT EDILDI (bu güncel checkpoint kaydı)

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
- **Durum:** KANITLANDI → UYGULANDI → **Aşama 1:** HEDEF TESTLERLE DOGRULANDI → COMMIT EDILDI (`a7ced18`); **Aşama 2:** HEDEF TESTLERLE DOGRULANDI → COMMIT EDILDI (`4ed5c79`, `5c83c05`) → **CANLI KABUL BASARISIZ** (18 Ağustos 2026); **debugger kanıt ayrıştırması:** HEDEF TESTLERLE DOGRULANDI → COMMIT EDILDI (`ddcfc40`); **exact PDB teşhis kapısı:** KANITLANDI → **ONAY B ENGELLENDI**
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
- **Asama 2 (18 Ağustos 2026) — ÜRÜN KAPANIŞ YOLUNUN KABUL KAPISI:** durum **HEDEF TESTLERLE DOGRULANDI → COMMIT EDILDI (`4ed5c79`, `5c83c05`) → CANLI KABUL BASARISIZ**.

  **Ölçülen ürün yolu:** `player.close() -> closeEvent() -> stop() -> terminate()`. Yeni child YAZILMADI; mevcut `tests/native_player_shutdown_child.py` kullanıldı. Child kapanışı kendisi başlatmaz, yalnız `player.close()` çağırır; `stop`/`terminate` sınıf düzeyinde saydam kaydediciyle sarılır (ürünün MPV nesnesine fazladan referans EKLENMEZ) ve çıkış ürünle aynı `os._exit(exit_code)` politikasını korur.

  **Görünürlük:** `faulthandler.enable(file=sys.stderr, all_threads=True)` artık PyQt, mpv ve `app.player` importundan **ÖNCE** açılıyor; `MARK_FAULTHANDLER_ENABLED` marker'ı bunu ebeveyne bildiriyor. Hedefin açıkça `sys.stderr` olduğu ve `all_threads=True` verildiği kaynak testiyle kilitli. `app.exec()` döndükten sonra yaşayan MPV thread'leri sayılıp `MARK_THREADS_AFTER count=<n>` yazılıyor; kabul için değer 0 olmalı.

  **İlk kırmızı (deterministik, simüle edilmiş):** `returncode=0` + bütün başarı marker'ları + `RESULTS: failures=none stop=1 terminate=1` + stderr'de `Windows fatal exception: code 0xe24c4a02` → **FAIL**. Aralıklı native olguyu kırmızı üretmek için canlı test TEKRARLANMADI.

  **Kapı sözleşmesi** (`tests/native_shutdown_acceptance.py`, saf `evaluate_shutdown_result`): çıktı BAYT yakalanır (`text=True` yok), timeout kontrollü FAIL'dir, stderr **tamamen boş** olmalıdır (ilk turda hiçbir "zararsız uyarı" muaf değildir), fatal desenler stdout'ta da aranır, on bir zorunlu marker tam bir kez ve kesin sözdiziminde olmalıdır (prefix benzeri satır gerçek marker yerine geçmez), `stop < terminate` sırası, `code=0`, `count=0`, `MARK_MAIN_RETURNED 0` ve RESULTS satırının TAM eşliği zorunludur. Çözümleme ve fatal desen listesi cover-art kapısıyla TEK kaynaktan gelir; `Traceback` ve `PYTHON_EXCEPTION` yalnız bu kapıda anlamlı olduğu için ek liste olarak ve gerekçesiyle ayrı durur.

  **Medya güvenliği:** dosya yalnız salt-okunur açılır; koşum öncesi/sonrası `size` + `mtime_ns` karşılaştırılır (büyük dosyanın hash'i hesaplanmaz), fark FAIL'dir.

  **BES FAIL-OPEN (18 Ağustos 2026, bağımsız denetim) — kapı canlı koşuma HAZIR DEĞİLDİ.** `evaluate_shutdown_result` şu satırların **her birini** `[]` ile kabul ediyordu: `MARK_PLAYER_CREATED t=0.51` (medya adı yok), `MARK_MEDIA_OPEN_REQUESTED t=0.52`, `MARK_MEDIA_READY t=1.24` (duration/position yok), `MARK_CLOSE_ACCEPTED ... visible=True` (pencere kapanmamış) ve `MARK_CLOSE_REQUESTED t=nan`. Ayrıca `MLC_NATIVE_TEST_VIDEO=tests/native_shutdown_acceptance.py` geçerli medya sayılıyordu. Kapatılması:

  1. **`FREE` dilbilgisi KALDIRILDI.** İki medya marker'ı tam bir basename taşır, boş olamaz, birbiriyle ve (canlı çağrıda) beklenen dosyayla aynı olmalıdır. `MARK_MEDIA_READY` tam olarak `duration=<sayı> position=<sayı>` ister ve en az biri > 0 olmalıdır (`TIMEOUT` FAIL). `MARK_CLOSE_ACCEPTED` tam olarak `visible=False` ister.
  2. **Zaman damgaları** artık `math.isfinite` ve `>= 0` ile ölçülür; `nan`, `inf`, `-inf` ve negatif değerler FAIL. (`float()` dönüşümü bunları geçiriyordu.)
  3. **Medya türü fail-closed:** yalnız gerçek `.mkv`/`.mp4` dosyaları (uzantı büyük/küçük harf duyarsız); `.py`, `.txt`, `.wav`, uzantısız dosya, dizin ve olmayan yol reddedilir. Yanlış doğrudan yol verildiğinde sessizce klasöre düşülmez. Geçersiz medyada **child hiç başlatılmaz**.
  4. **Açık native opt-in:** canlı test yalnız `MLC_NATIVE_SHUTDOWN_ACCEPTANCE=1` **ve** geçerli medya birlikte varsa çalışır; medya tek başına yetmez. `MLC_NATIVE_SMOKE` bilerek kullanılmadı (başka native testleri de açardı). Varsayılan tam pytest koşumunda test **skip**tir.
  5. **`os.stat()` korumalı:** medya koşumdan önce/sonra silinir, taşınır veya okunamazsa traceback yerine kontrollü FAIL döner; child **ikinci kez çalıştırılmaz**.

  **IKI TEKNIK KUSUR DAHA (18 Ağustos 2026, aynı denetim) — kapatıldı:**

  6. **Boşluklu/Unicode medya adları REDDEDİLİYORDU.** `MARK_PLAYER_CREATED t=... kayıt 01.mkv` iki alan sayılıp FAIL üretiyordu; ad, boşlukla ayrışan bir alanda taşınıyordu. Ad artık kayıpsız ve boşluksuz bir alanda taşınır: `media_b64=<URL-safe Base64 UTF-8>`. Değerlendirici tam bir `media_b64=` alanı ister; geçersiz Base64 (`validate=True` — varsayılan çözücü alfabe dışı karakterleri sessizce atıp bozuk token'ı boş dizeye çeviriyordu), geçersiz UTF-8, boş ad, beklenenden farklı ad ve fazla alan **FAIL**'dir; iki medya marker'ının aynı dosyayı bildirdiği ayrıca doğrulanır. Ölçülen adlar: `kayıt 01.mkv`, `4K HEVC Film 01.mkv`, Türkçe harfler, emoji, parantez/köşeli parantez ve kenar boşlukları.
  7. **Child'ın KENDİ medya doğrulaması açıktı:** `resolve_video()` doğrudan verilen her dosyayı kabul ediyordu. Child doğrudan çalıştırılsa bile artık yalnız gerçek `.mkv`/`.mp4` kabul eder. Uzantı listesi ve ad kodlaması TEK kaynaktadır: yeni `tests/native_media_contract.py` (mpv/PyQt yüklemez); hem ebeveyn kapısı hem child oradan import eder ve ikisi de kendi `base64`/uzantı kodunu taşımaz — bu testle kilitli.

  **Test kaniti:** `tests/test_native_shutdown_acceptance_regressions.py` → **268 passed, 1 deselected** (deselect edilen tek düğüm canlı kabuldür; opt-in sınır testleri dahil). Önceki turda boş olmadıkları dört mutasyonla kanıtlanmıştı: dilbilgisi nötrleştirilince **41 failed**, zaman damgası yalnız `float()` yapılınca **45 failed**, medya türü denetimi kaldırılınca **9 failed**, opt-in kaldırılınca **8 failed**. Mevcut sözleşmeler bozulmadı: `test_child_shutdown_contract_regressions.py` + `test_player_shutdown_regressions.py` + cover-art deterministikleri → **151 passed, 2 skipped**.

  **TALIMAT IHLALI (gizlenmiyor):** yukarıdaki mutasyon turunda "medya türü denetimi yok" varyantı çalışırken `run_native_shutdown` gerçek child'ı **bir kez, yaklaşık 26,8 sn** başlattı — geçersiz bir `.py` girdisiyle. Bu, "native testi çalıştırma" talimatının ihlalidir. **Bu koşum canlı kabul veya ürün etkisi kanıtı DEĞİLDİR:** girdi geçerli medya değildi ve sonucu hiçbir yerde ölçüt olarak kullanılmadı. Süreç kendiliğinden kapandı; sonrasında artık child Python süreci kalmadığı `Win32_Process` listesiyle ölçüldü. Önlem: native sınırını ölçen testler artık `subprocess.run`'ı bir nöbetçiyle değiştirir ve **beklenmeyen her süreç başlatma testi anında kırmızı yapar**; mutasyon aracı canlı test düğümünü hiçbir koşulda toplamaz. "Native test hiç çalıştırılmadı" gibi mutlak bir ifade bu kayıtta KULLANILMAZ.

  8. **Opt-in yalnizca pytest dugumunde denetleniyordu.** `run_native_shutdown()` doğrudan çağrıldığında geçerli bir `.mkv` ile **açık izin olmadan** süreç başlatabiliyordu — 26,8 sn'lik kazanın aynı sınıfı bu alt seviyede hâlâ mümkündü. Kapı artık gerçek `subprocess` sınırındadır: izin yoksa `subprocess.run` **çağrılmaz**, kontrollü problem döner (`returncode=None`, stdout/stderr boş, medya stat'ı raporlanır, traceback yok). Fonksiyon `env=` kabul eder; child ortamı enjekte edilen ortamdan türer, global `os.environ` kirletilmez ve test davranışını değiştirmez. Kaynak sırası da testle kilitli: izin denetimi `subprocess.run` çağrısından ÖNCE.

  **Canli kabul (18 Agustos 2026): BASARISIZ.** Açık PowerShell opt-in'iyle **TEK** geçerli koşum yapıldı. (Bir önceki turun kaydı, koşumun ortam yokluğu yüzünden yapılamadığını söylüyordu; o ifade artık geçersizdir.)

  - **Medya:** `Resident.Alien.S01E01.Pilot.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb.mkv`. Dosya adı **1080p / H.264** belirtir; bu bir **4K/HEVC kabulü DEĞİLDİR**. Boyut önce = sonra = **2.651.661.814 bayt**, `mtime` değişmedi, medya hash'i hesaplanmadı, dosya salt-okunur açıldı.
  - **Sonuc:** pytest exit **1**, child exit **0** → **kabul FAIL**.
  - **Kirmizi kanit:** child stderr'inde **tam 9 adet** `Windows fatal exception: code 0xe24c4a02`. İzlerde `MPVEventHandlerThread` ve `mpv.py::_event_generator` / `_loop` görünüyor. **Bu, kaynak native modülün mpv/libmpv olduğunun KESİN kanıtı değildir**; debugger ve sembol olmadan kök modül bilinmiyor.
  - **Ayni kosumdaki BASARILI davranis kanitlari:** gerçek medya açıldı (`duration=2782.27`), `closeEvent` ürün yolu çalıştı, `stop=1` ve `terminate=1` (stop < terminate), pencere kapandı (`visible=False`), `app.exec()` dönüş kodu 0, kalan MPV thread sayısı **0**, `RESULTS failures=none`, koşumdan sonra ilgili Python child süreci kalmadı.

  **Dogru yorum (sinirlariyla):**
  - **"Ürün yolu etkilenmiyor" iddiası ARTIK GEÇERSİZDİR.** Olay, faulthandler açıkken **gerçek ürün kapanış yolunda** görüldü.
  - Buna karşılık bu tek koşum, **kullanıcıya görünen bir çökme veya donma kanıtı DEĞİLDİR**: child normal biçimde exit 0 verdi ve kapanış tamamlandı.
  - Olay **zararsız ya da güvenli KABUL EDİLEMEZ**. Kök neden ve ürün etkisi **AÇIK**tır.

  **Ham kanit:** yerel geçici çıktının SHA-256'sı `0E946B021E66DBF8CAB8AF628F6D4C54E01821C3495627D7E030F16E80FCF256`. Çıktı geçicidir; kalıcı bir artifact değildir ve mutlak kullanıcı yolu bu belgeye yazılmaz.

  **Debugger teşhisi ve düzeltilen rapor (18 Ağustos 2026; yeni native koşum yapılmadı):** CDB metni bağımsız olarak yeniden ayrıştırıldı. Komut yankısındaki marker metinleri kanıt sayılınca oluşan eski “second-chance” sonucu yanlıştı. Kesin satır dilbilgisiyle ölçüm **14 first-chance**, **13 tekrar**, **0 second-chance** oldu. İlk fault thread: `lua/stats` (TID `302c`); dağılım `lua/stats` = 2, `lua/ytdl_hook` = 1, `lua/select` = 11. `MPVEventHandlerThread` logda bulunur fakat kaynak fault thread değildir.

  **Kodun sınıflandırması (birincil kaynak):** LuaJIT Windows hata taşıması `LJ_EXCODE = 0xe24c4a00` tabanına Lua hata kodunu ekler; `LUA_ERRRUN = 2` olduğundan `0xe24c4a02`, LuaJIT'in Lua çalışma-zamanı hatasını SEH üzerinden taşıdığı koddur. Stack ve modül aralığı bu taşımanın depo `bin/mpv-2.dll` içindeki gömülü LuaJIT'ten geçtiğini gösterir; bu bulgu tek başına “mpv-2.dll çöktü” veya second-chance kanıtı değildir. Kaynaklar: [LuaJIT `lj_err.c`](https://github.com/LuaJIT/LuaJIT/blob/v2.1/src/lj_err.c), [Lua `lua.h`](https://github.com/LuaJIT/LuaJIT/blob/v2.1/src/lua.h), [mpv Lua belgeleri](https://github.com/mpv-player/mpv/blob/master/DOCS/man/lua.rst).

  Kabul kapısı gevşetilmedi: tam `Windows fatal exception: code 0xe24c4a02` izi artık genel “fatal” etiketi yerine **LuaJIT / LUA_ERRRUN SEH izi** olarak sınıflandırılır; stderr boş olmadığı için sonuç yine FAIL'dir. Diğer Windows fatal kodları genel fail-closed korumada kalır.

  **ONAY A — exact PDB uygunluk denetimi (18 Ağustos 2026; native koşum yok):** GitHub Actions workflow run `31755832255` içindeki `mpv-x86_64-debug` artifact'i (`9203486934`) indirildi. Artifact arşivi `mpv-debug-x86_64-20260814-git-7b8915bc1d.7z`, 57.309.570 bayt ve SHA-256 `873EF06F0996F993120F7633099A18CD1011CF4CDBE139CBE21A8F0575866787`; arşiv **yalnız `mpv.pdb`** içeriyor.

  Repo `bin/mpv-2.dll` dosyasının SHA-256'sı manifest ile aynı: `F709C7CA8B183BEC76B8158BF0C45C53018C63366750729352612F228FF7BDEA`. DLL'in CodeView kimliği `C2123266-4DC7-8196-4C4C-44205044422E`, age 1 ve beklediği ad `libmpv-2.pdb`. İndirilen `mpv.pdb` kimliği ise `83981475-63BC-A938-4C4C-44205044422E`, age 1. Yeniden adlandırılmış kopya da `symchk` tarafından `mpv-2.dll` için **mismatched** olarak reddedildi (exit 1).

  PDB'nin kaynağı ayrıca bağımsız ölçüldü: aynı workflow'un normal artifact'indeki `mpv.exe` ile `symchk /pf` denetiminden geçti (exit 0; private semboller, satır ve tip bilgisi mevcut). `lj_err_run`, `lj_err_throw`, `lua_State`, `TValue` ve `GCstr` bulunuyor; fakat bunlar `mpv.exe` PDB'sindedir ve repo DLL'inin adres/simge kanıtı olarak kullanılamaz. Sonuç: **exact `libmpv-2.pdb` elde edilemedi**; yayımlanan debug artifact DLL PDB'sini taşımıyor.

  Geçici harness yalnız ön hazırlık olarak fail-closed bırakıldı: exact GUID/age ve `symchk /pf` geçmeden runner kontrollü olarak durur; statik preflight geçti. **ONAY B ENGELLENDI.** ONAY A sırasında CDB hedefi, Python child, MLC Player, mpv, PyQt ve video **çalıştırılmadı**; run sentinel, debugger logu ve child çıktısı oluşmadı. Geçici klasör kalıcı artifact değildir ve mutlak kullanıcı yolu kayda alınmaz.

  **Süreç ihlali kaydı:** geçici harness, ilk kodlama ön testinden sonra **bağımsız denetime sunulmadan** değiştirildi ve çalıştırıldı. İkinci CDB koşumu yapılmamış ve repo değişmemiş olsa da bu bir **onay zinciri ihlali**dir; raporun thread ve second-chance yorumları bu yüzden ayrıca bağımsız ayrıştırmayla doğrulanmıştır.

  **Commit durumu (asamalara gore):**
  - **Aşama 1** (cover-art child yalıtımı + stderr görünürlük kapısı): **COMMIT EDILDI** — `a7ced18`.
  - **Aşama 2** (ürün kapanış yolu kabul kapısı + başarısız canlı kabulün kaydı): **COMMIT EDILDI** — `4ed5c79` ve `5c83c05`. Kapsam **YEDİ dosyaydı** ve **İKİ mantıksal commit'e** ayrıldı:

    **1) `test: add product shutdown native acceptance gate`** — kapı uygulaması, **DÖRT** dosya:
    `tests/native_player_shutdown_child.py`, `tests/native_media_contract.py`, `tests/native_shutdown_acceptance.py`, `tests/test_native_shutdown_acceptance_regressions.py`.

    **2) `docs: record failed native shutdown acceptance`** — kayıt ve belge koruması, **ÜÇ** dosya:
    `docs/ENGINEERING_AUDIT.md`, `docs/ROADMAP.md`, `tests/test_release_documentation_regressions.py`.

    Belge koruması kendi regresyon testini de değiştirdiği için kapsam altı değil **yedi** dosyaydı; bu tarihsel kapsam `tests/test_release_documentation_regressions.py` içinde mekanik olarak korunur.
  - **Canlı kabul:** **BASARISIZ** (18 Ağustos 2026; yukarıdaki tek koşum).

  **Canli kosum komutu (Windows PowerShell — bu kayit turunda TEKRAR CALISTIRILMADI):**

  ```powershell
  $env:MLC_NATIVE_SHUTDOWN_ACCEPTANCE = "1"
  $env:MLC_NATIVE_TEST_VIDEO = "C:\tam\yol\gerçek video.mkv"
  python -m pytest -q tests/test_native_shutdown_acceptance_regressions.py::test_the_product_shutdown_path_survives_a_real_run
  ```

  Bash biçimindeki `VAR=1 python ...` örneği KALDIRILDI; Windows PowerShell'de çalışmaz.

  **Hala OLCULMEYENLER:** `0xe24c4a02` ile taşınan asıl Lua hata mesajı ve onu doğuran Lua çağrısı, kullanıcıya görünen etki ve olgunun sıklığı. Ölçülen şey yalnızca **bir** ürün koşumu ve onun tek debugger kaydıdır.

  **SIRADAKI TEKNIK ADIM — AYRI KULLANICI ONAYI GEREKIR (bu turda YAPILMADI):**
  - Exact `libmpv-2.pdb` üreticiden sağlanmadan özel sembol harness'iyle native koşum **YAPILMAZ**.
  - PDB beklenmeden ilerlemek için alternatif, ürün kodunu değiştirmeyen diagnostic child'da mpv trace logunu açıp Lua hata metni/script kaynağını yakalayan ayrı bir kapıdır; önce deterministik ve statik testleri yazılır.
  - Yeni debugger/native koşumu gerçek pencere ve gerçek medya kullanacağı için **ayrıca ONAY B ister**; ürün kodu değiştirilmemelidir.
  - **4K / H.265 kabulü ancak kök neden düzeltmesinden SONRA yapılacaktır.**

- **Kalan risk:** **Canlı kabul BAŞARISIZDIR ve asıl Lua hatası AÇIKTIR.** Debugger, olayın LuaJIT `LUA_ERRRUN` taşıması olduğunu ve fault thread dağılımını belirledi; fakat Lua hata metnini, onu doğuran çağrıyı veya kullanıcıya görünen etkiyi belirlemedi. Kapanış sözleşmesi (stop/terminate sırası, thread 0, exec 0) sağlanmış olsa da bu olayın güvenli olduğu anlamına gelmez. İstisna artık child'da oluşursa üst test FAIL verir — gizlenmez, fakat **önlenmiş değildir**.
- **Commit durumu:** Aşama 1 **COMMIT EDILDI** (`a7ced18`); Aşama 2 **COMMIT EDILDI** (`4ed5c79`, `5c83c05`); debugger kanıt ayrıştırması ve kayıt düzeltmesi **COMMIT EDILDI** (`ddcfc40`); bu ONAY A PDB kaydı **COMMIT BEKLIYOR**.

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
