# MLC Player yol haritası

**Snapshot: 18 Ağustos 2026** — NATIVE-001 commit'i ve güncel tam paket
checkpoint'inin ardından güncellendi. Bu belge her kabul edilen turun sonunda
yenilenir; buradaki durumlar o tarihteki ölçümleri yansıtır, kalıcı
gerçek değildir.

Durum sözlüğü `docs/ENGINEERING_AUDIT.md` içindedir; aynı kelimeler
burada da kullanılır. Yayın sırası burada tekrarlanmaz:
`docs/RELEASE_PROCESS.md`.

Her maddede dört alan vardır: **Durum**, **Bagimlilik**, **Olcut**
(tamamlanma ölçütü) ve **kullanıcı onayı** gerekip gerekmediği.

## Su anki asama

Yayın altyapısı sertleştirme turunda beş kusur (REL-001…REL-005) hedef
testlerle kapatıldı; NATIVE-001 ile native stderr görünürlük kapısı eklendi
ve bunlar mantıksal olarak ayrılmış yerel commit'lere bölündü;
`master` şu an (18 Ağustos 2026 snapshot'ı) `origin/master`'ın **on üç
commit** ilerisindedir ve **push yapılmadı**. Güncel tam paket
**3992 passed / 17 skipped / 0 failed**, exit 0 ve stderr boştur. **Push
yapılmadı**; canlı bir build/yayın koşumu da yapılmadı. Sıradaki teknik
risk, NATIVE-001'in bilinmeyen native kök nedeni ve ürün etkisidir.

---

## Tamamlanan ve hedef testle dogrulanan isler

### Runtime bütünlüğü (REL-001)
- **Durum:** HEDEF TESTLERLE DOGRULANDI, COMMIT EDILDI (`96a8f52`)
- **Bagimlilik:** yok
- **Olcut:** `--pre` üç runtime'ı boyut + SHA-256 ile doğruluyor → sağlandı (52 passed, canlı exit 0)
- **Kullanici onayi:** commit verildi ve uygulandı; push ayrı onay ister

### Tag ↔ kaynak bütünlüğü (REL-002)
- **Durum:** HEDEF TESTLERLE DOGRULANDI, COMMIT EDILDI
- **Bagimlilik:** yok
- **Olcut:** tag adı, dört sürüm alanı ve HEAD doğrulanıyor → sağlandı (45 passed)
- **Kullanici onayi:** commit verildi ve uygulandı; push ayrı onay ister

### Kesin artifact seçimi (REL-003)
- **Durum:** HEDEF TESTLERLE DOGRULANDI, COMMIT EDILDI (`85dda6d`), CANLI KABUL BEKLIYOR
- **Bagimlilik:** gerçek Windows build
- **Olcut:** zincir uçtan uca koşup doğru sürümü imzalamalı
- **Kullanici onayi:** commit uygulandı; canlı build ayrıca onay ister

### Yerel yayın kapısı (REL-004)
- **Durum:** HEDEF TESTLERLE DOGRULANDI, COMMIT EDILDI, CANLI KABUL BEKLIYOR
- **Bagimlilik:** REL-002, REL-003
- **Olcut:** gerçek bir yayın adayında exit 0 vermeli
- **Kullanici onayi:** commit uygulandı; push/release ayrı onay ister

### build/dist temizliği doğrulaması (REL-005)
- **Durum:** HEDEF TESTLERLE DOGRULANDI, COMMIT EDILDI (`85dda6d`), CANLI KABUL BEKLIYOR
- **Bagimlilik:** REL-003 (aynı betik), gerçek Windows build
- **Olcut:** `rmdir` başarısız olduğunda zincir gerçekten durmalı — kilitli klasörle canlı koşumda görülmeli
- **Kullanici onayi:** commit uygulandı; canlı build ayrıca onay ister

### Süreç belgesi tekilleştirmesi (DOC-001)
- **Durum:** HEDEF TESTLERLE DOGRULANDI, COMMIT EDILDI, TAMAMLANDI
- **Bagimlilik:** yok
- **Olcut:** a–j yalnız `RELEASE_PROCESS.md` içinde → sağlandı
- **Kullanici onayi:** commit verildi ve uygulandı

---

## Tam paket milestone kosumu (17 Agustos 2026)

- **Durum:** HEDEF TESTLERLE DOGRULANDI (hedef kapanış)
- **Bagimlilik:** REL-001…REL-005
- **Olcut:** tek failure kapatılmış olmalı → sağlandı
- **Kullanici onayi:** gerekmez (ölçüm)

Gerçek sonuç: **3931 passed / 17 skipped / 1 failed**, **100,01 sn**.
Taban 3716/17 idi; artış eklenen regresyon dosyalarındandır.

Tek failure ürün kusuru değildi: bayat `ADDON_TO_SIGN` test assertion'ı
(TEST-002). **Hedef testle kapatıldı** — bu bir *hedef kapanıştır*,
ürün davranışı değişmedi.

**Tam paket bu test-only düzeltmeden sonra BİLEREK yeniden
çalıştırılmadı.** 3931 yeşil testi tek bir test dosyası değişikliği için
yeniden koşturmak ölçüm değil, tekrardır. Bir sonraki tam koşum commit
öncesinde yapılacak.

## Commit checkpoint sonucu

- **Durum:** TAMAMLANDI (hedef kapanış kanıtıyla)
- **Bagimlilik:** yukarıdaki milestone
- **Olcut:** tam `pytest -q tests` yeşil (0 failed); milestone 3931/17/1 ile karşılaştırılıp fark açıklanmış; `compileall` ve `git diff --check` temiz
- **Kullanici onayi:** verildi; checkpoint yerel commit'lere bölündü (18 Ağustos 2026 snapshot'ında toplam beş yerel commit), push yapılmadı

18 Ağustos 2026 güncel HEAD checkpoint'i: **3992 passed / 17 skipped /
0 failed**, pytest **exit 0**, stderr **0 bayt**, **82,44 sn**. Koşum bir kez
yapıldı. TEST-002'nin bayat assertion'ı ve NATIVE-001 sonrası eklenen
regresyonlar artık aynı tam paket sonucunda birlikte yeşildir.

---

## Uzak release dogrulama otomasyonu

- **Durum:** ERTELENDI
- **Bagimlilik:** REL-004
- **Olcut:** `refs/tags/vX.Y^{}` peeled commit'i ve uzak varlık ad/boyut/SHA-256 eşliği mekanik denetlenmeli (şu an elle: adım g ve i)
- **Kullanici onayi:** gerekmez (salt-okunur), ama ağ kullanır — `prepublish` kapısına eklenmez, ayrı araç olur

---

## Genel mimari / guvenilirlik denetimi

- **Durum:** ERTELENDI
- **Bagimlilik:** yok
- **Olcut:** kapanış yaşam döngüsü, thread sahipliği ve hata sınırları tek tek ölçülmüş; bilinen aralıklı child takılmasının kök nedeni bulunmuş
- **Kullanici onayi:** gerekmez (inceleme)

---

## Performans ve gecikme denetimi

- **Durum:** ERTELENDI
- **Bagimlilik:** yok
- **Olcut:** açılış süresi, ilk kare gecikmesi ve seek gecikmesi gerçek 4K medyayla ölçülmüş; resize donması turundaki gibi öncesi/sonrası tablosu çıkarılmış
- **Kullanici onayi:** GUI/native koşum için **gerekir**

---

## Test / CI / bagimlilik denetimi

- **Durum:** ERTELENDI
- **Bagimlilik:** "Commit öncesi yapılacaklar"
- **Olcut:** tam paket süresi ve kararlılığı kayıtlı; bağımlılık sürümleri sabitlenmiş
- **Kullanici onayi:** gerekmez

## SIRADAKI TEKNIK RISK: `0xe24c4a02` (NATIVE-001)

- **Durum:** GORUNURLUK KUSURU KAPATILDI (HEDEF TESTLERLE DOGRULANDI, COMMIT EDILDI); **CANLI KABUL BASARISIZ (18 Ağustos 2026)**; **kök neden ve ürün etkisi AÇIK**
- **Bagimlilik:** yok — commit'i beklemez
- **Olcut:** (a) native istisna artık sessizce geçemez → **sağlandı ve commit edildi**; (b) ürün kapanış yolunda tek yalıtılmış canlı kabul → **koşum YAPILDI ve BAŞARISIZ**; (c) LuaJIT taşıması sınıflandırıldı, fakat asıl Lua hatası bulunmuş ya da bilinçli kabul edilmiş değil → **sağlanmadı**
- **Kullanici onayi:** gerçek-mpv/native koşum için **gerekir**

Ayrıntılı kayıt: `docs/ENGINEERING_AUDIT.md` → **NATIVE-001**.

Kapatılan: native senaryolar ayrı sürece taşındı ve üst test `exit 0` olsa
bile stderr'deki native istisnayı **FAIL** sayıyor.

**İlk düzeltme bağımsız denetimde REDDEDİLDİ**; o turdaki *23 passed*
sonucu nihai kabul DEĞİLDİR. Üç kusur giderildi: (1) sıraya bağımlı
`assert "mpv" not in sys.modules` iddiası — `app.player` zaten `mpv`
import ettiği için başka bir test önce koşunca düşüyordu; yerine bu
modülün import ETKİSİ ölçülüyor, (2) iki MPV instance'ına karşılık tek
kapanış marker çifti — artık senaryo başına ayrı marker ve ayrı
`stop < terminate` denetimi var, (3) aklanan `MARK_*_ERROR` — artık kesin
FAIL.

Dördüncü kusur (18 Ağustos 2026): `evaluate_child` marker BİÇİMİNİ
denetlemiyordu; `MARK_COVER_TRACKS abc`, değersiz `MARK_THREADS_AFTER` ve
`MARK_DONE junk` içeren çıktı TAMAM sayılıyordu. Artık `MARKER_GRAMMAR`
her zorunlu marker'ın token sayısını ve değerini zorluyor.

Güncel gerçek sonuç: **deterministik 61 passed**. Native kabul, child
üretim kodu değişmediği için tekrarlanmadı; geçerli canlı sonuç önceki
turun **39 passed / exit 0 / stderr BOŞ** koşumudur. Raporlanan iki-test
sıra regresyonu **iki yönde de yeşil**.

18 Ağustos 2026 tam paket checkpoint'i de **3992 passed / 17 skipped /
0 failed**, exit 0 ve stderr boş tamamlandı. Bu, görünürlük kapısının
tam paket içinde çalıştığını gösterir; native kök nedeni veya ürün
muafiyeti kanıtı değildir.

**Aşama 2 (18 Ağustos 2026): ürün kapanış yolu kabul kapısı HEDEF
TESTLERLE HAZIR ve COMMIT EDILDI (`4ed5c79`, `5c83c05`); CANLI KABUL
BAŞARISIZ.** Mevcut
`tests/native_player_shutdown_child.py` üzerinden
`player.close() -> closeEvent() -> stop() -> terminate()` yolunu ölçen saf
bir kapı eklendi; faulthandler artık PyQt/mpv importundan ÖNCE ve
`all_threads=True` ile açılıyor, `app.exec()` dönüşünden sonra yaşayan MPV
thread'leri sayılıyor.

**Kapının ilk hâli bağımsız denetimde REDDEDİLDİ** (beş fail-open):
eksik medya adı, alansız `MARK_MEDIA_READY`, `visible=True`, `t=nan` ve
`.py` dosyasının geçerli medya sayılması. Kapatıldı: `FREE` dilbilgisi
kaldırıldı, zaman damgaları `isfinite`+`>=0`, medya türü fail-closed
(`.mkv`/`.mp4`), açık opt-in `MLC_NATIVE_SHUTDOWN_ACCEPTANCE=1` ve
korumalı `os.stat()`.

**İki teknik kusur daha kapatıldı:** (6) boşluklu/Unicode adlar
(`kayıt 01.mkv`) protokolü bozuyordu — ad artık kayıpsız
`media_b64=<URL-safe Base64>` alanında taşınır; (7) child'ın kendi
`resolve_video()` doğrulaması açıktı — artık ebeveynle AYNI
`is_supported_media()` kullanılır. Uzantı listesi ve codec tek kaynakta:
`tests/native_media_contract.py`.

Mevcut sözleşmeler **151 passed, 2 skipped** ile bozulmadı; güncel
deterministik sonuç aşağıdadır.

**CANLI KABUL SONUCU (18 Ağustos 2026): BAŞARISIZ — tek geçerli koşum.**
Medya `Resident.Alien.S01E01.Pilot.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb.mkv`
(dosya adı 1080p/H.264 belirtir; **4K/HEVC kabulü değildir**), boyut önce =
sonra = 2.651.661.814 bayt, `mtime` değişmedi, hash hesaplanmadı. pytest
exit **1**, child exit **0**. Child stderr'inde **tam 9 adet**
`Windows fatal exception: code 0xe24c4a02`; izlerde
`MPVEventHandlerThread` ve `mpv.py::_event_generator`/`_loop` var — bu,
kaynak native modülün mpv/libmpv olduğunun **kesin kanıtı değildir**.

Aynı koşumda kapanış sözleşmesinin tamamı sağlandı: medya açıldı
(`duration=2782.27`), `closeEvent` ürün yolu çalıştı, `stop=1`/`terminate=1`
ve stop < terminate, `visible=False`, `app.exec()` = 0, kalan MPV thread
**0**, `RESULTS failures=none`, artık child süreci kalmadı.

**Yorum sınırları:** "ürün yolu etkilenmiyor" iddiası ARTIK GEÇERSİZDİR —
olay faulthandler açıkken gerçek ürün yolunda görüldü. Ancak bu tek koşum
kullanıcıya görünen bir çökme/donma kanıtı DEĞİLDİR; child normal biçimde
exit 0 verdi. Olay **zararsız veya güvenli sayılamaz**.

**Debugger kanıt düzeltmesi (yeni native koşum yok):** komut yankısındaki
marker metinleri olay sayılmadan yapılan kesin ayrıştırma **14 first-chance**,
**13 tekrar**, **0 second-chance** verdi. İlk fault thread: `lua/stats`;
dağılım `lua/stats` = 2, `lua/ytdl_hook` = 1, `lua/select` = 11.
`MPVEventHandlerThread` logda vardır fakat kaynak fault thread değildir.
Birincil LuaJIT kaynaklarına göre kod, `LJ_EXCODE = 0xe24c4a00` tabanı ile
`LUA_ERRRUN = 2` birleşimidir: `0xe24c4a02` gömülü LuaJIT'in çalışma-zamanı
hatasını Windows SEH üzerinden taşıdığını gösterir; tek başına “mpv-2.dll
çöktü” veya second-chance kanıtı değildir. Asıl Lua hata metni ve çağrı
kaynağı hâlâ açıktır. Kabul kapısı gevşetilmedi; bu özel iz doğru adla FAIL,
diğer fatal kodlar genel fail-closed korumayla FAIL olur.

Exact kaynak zinciri 18 Ağustos 2026'da ağ üzerinden salt-okunur eşlendi:
mpv `7b8915bc1d04c7e1b61184e00c7fbfaab1911e75`, build tanımı
`cd1edc11dc6887a50f705717619d879f5a93a488`, yayın anındaki
`openresty/luajit2` dal başı `52f52587b37867ab19236eb6917001c2d6b662e7`.
Build `v2.1-agentzh` hareketli dalını kullandığından LuaJIT commit'i artifact
içinde sabitlenmemiştir; dal/zaman eşlemesi exact binary provenansı yerine
geçmez. Kaynak, olayın LuaJIT hata taşıması olduğunu gösterir; **asıl Lua
çağrısını**, suçlu scripti, güvenli veya zararsız olduğunu kanıtlamaz.

Exact LuaJIT `lj_trace.c`, `lj_trace_err` yolunun JIT trace derlemesini
`LUA_ERRRUN` ile abort edip `lj_vm_cpcall` içinde `LJ_TRACE_ERR` olarak
yakaladığını da gösterir. Dolayısıyla kod tek başına **script runtime hatası
ile JIT trace abort** yolunu **ayırt etmez**; “mutlaka loglanacak asıl Lua hata
mesajı vardır” varsayımı kaldırıldı.

Sonraki deterministik kapı hazırlandı fakat **ÇALIŞTIRILMADI**:
`MLC_NATIVE_MPV_SCRIPT_ABLATION=1`, mevcut shutdown ve trace opt-in'leriyle
birlikte gerekir. `load-scripts=no` tek başına yetmez; yalnız kullanıcı script
dizinini kapatır. Kapı **dokuz built-in** script seçeneğini ve dış script
auto-load'unu birlikte kapatır, marker/trace ile fail-closed doğrular. Bu bir
**ürün düzeltmesi değildir**; ürün `MPV_CONFIG` **değişmedi**. Tek gerçek
ablation koşumu **AYRI ONAY B** ister ve otomatik tekrarlanmaz.

**Ablation aşaması son doğrulaması (yalnız deterministik):** hedef paketler
**608 passed, 4 skipped**; dört skip açık opt-in isteyen gerçek native
düğümlerdir. Bu doğrulama sırasında **CANLI KOSUM YAPILMADI**, video/mpv
child/CDB başlatılmadı. Kapı **COMMIT EDILDI (`583bb3d`)**. Kesin yedi dosya:
`docs/ENGINEERING_AUDIT.md`, `docs/PROJECT_STATUS.md`, `docs/ROADMAP.md`,
`tests/native_mpv_trace_contract.py`, `tests/native_player_shutdown_child.py`,
`tests/test_native_mpv_trace_regressions.py`,
`tests/test_release_documentation_regressions.py`.

**Built-in script ablation ONAY B — TEK KOSUM (18 Ağustos 2026):** pytest
exit 0, **1 passed**; otomatik tekrar yapılmadı, CDB kullanılmadı ve ürün
kodu değişmedi. Child stderr **0 bayt**, `0xe24c4a02` sayısı **0**, built-in
Lua modülü **0**, overflow/fatal/error sayısı 0; kapanış marker'ları tamam,
kalan MPV thread 0 ve artık süreç yoktu. Medya boyutu **2.651.661.814** bayt,
`mtime` ticks **638811093472871806** olarak önce/sonra değişmedi.

Trace **2.367.767 bayt / 32.416 satır**, SHA-256
`8F3E1EB01A9EB506D9977880E0DB9EE0F5A07381426CA920593A57A6FF42C1D1`;
child stdout SHA-256
`CC316FB8DE055F8F578F89A50CA220E4E75ABE925B22C2A7B36AF189F772D72F`;
boş child stderr SHA-256
`E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855`.
Geçici çıktılar kalıcı depo artifact'i değildir.

Bu tek negatif örnek **ürün düzeltmesi değildir**; kök neden **AÇIK** kalır.
Built-in scriptlerin gerekli koşul olduğunu, belirli bir scriptin suçlu
olduğunu veya JIT trace abort yolunu **kanıtlamaz**. Ablation sonuç kaydı
**COMMIT EDILDI (`29e017a`)**. Kayıt sonrası ilgili deterministik paketler
**611 passed, 4 skipped**; dört skip gerçek opt-in düğümleridir.

**Script-bisection kapısı deterministik olarak hazırlandı.**
`MLC_NATIVE_MPV_SCRIPT_BISECTION` `stats_ytdl`, `select`, `stats`, `ytdl_hook`
ve `observed_trio` profillerini kabul eder. Önce bütün scriptler kapanır,
yalnız seçilen profil açılır; marker profil adını doğrular. Seçilmeyen Lua
modülü görülürse veya seçilen Lua modülü görülmedi ise sonuç fail-closed'dur.
Bilinmeyen herhangi bir `lua/*` client'i de seçilmeyen sayılır; sessizce
geçmez. Geçersiz profil subprocess sınırına ulaşmaz ve ürün `MPV_CONFIG`
değişmedi. Hedef trace paketi **126 passed, 1 skipped**.

**İlk aşama bütçesi 2** koşumdur: `stats_ytdl` ve `select`. Bu iki koşum
otomatik yetkilendirilmiş değildir. Aralıklı olayda **tek negatif** sonuç
**eleme kanıtı değildir**; her gerçek koşum **AYRI KULLANICI ONAYI** ister.
İlgili deterministik paketler birlikte **645 passed, 4 skipped**; dört skip
gerçek opt-in düğümleridir. Kapı ve kayıt değişiklikleri **COMMIT EDILDI
(`06bd5f5`)**.
**4K/H.265 kabulü ancak kök neden düzeltmesinden sonra.**

**`stats_ytdl` bisection ONAY B — TEK KOSUM (18 Ağustos 2026):** pytest
exit 0 / **1 passed**; otomatik tekrar yapılmadı, CDB kullanılmadı ve
`select` koşumu yapılmadı. Trace profili doğruladı: stats 6, ytdl_hook 7,
select 0, diğer bilinen built-in modüller 0. Child stderr **0 bayt**,
`0xe24c4a02` sayısı **0**, overflow/fatal/error 0; kapanış tamamlandı,
kalan MPV thread ve artık süreç yoktu. Medya boyutu **2.651.661.814** bayt,
`mtime` ticks **638811093472871806** olarak önce/sonra değişmedi.

Trace **2.316.712 bayt / 31.672 satır**, SHA-256
`8B2E8B35453ECCC7EC5E81D11E70CA2A6AD09053110EBE65C3CBA370A6FDB9BB`;
child stdout SHA-256
`0F9C71848625D6936FD9E844D871564DE338139668FDA3A70B8CB1532A3280BF`;
boş child stderr SHA-256
`E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855`.

İlk regex sayımı geçersizdi: köşeli parantezler arasında boşluk varsayıp
etkin modülleri 0 gösterdi ve **kanıt olarak kullanılmadı**. Gerçek satırlar
ve ortak değerlendirici 6/7/0 sonucunu doğruladı. Bu tek negatif sonuç grubu
**elemez**. İlk bütçenin `select` profili **AYRI ONAY B** ister; select koşumu
bu kayıt anında yapılmamıştı. Kayıt sonrası ilgili deterministik paketler
**648 passed, 4 skipped**; dört skip gerçek opt-in düğümleridir. `stats_ytdl`
sonuç kaydı **COMMIT EDILDI (`dc31bf9`)**.

**`select` bisection ONAY B — TEK KOSUM (18 Ağustos 2026):** pytest exit 0 /
**1 passed**; otomatik tekrar yapılmadı ve CDB kullanılmadı. Trace profili
doğruladı: select 6, stats 0, ytdl hook 0, diğer bilinen built-in modüller 0.
Child stderr **0 bayt**, `0xe24c4a02` sayısı **0**, overflow/fatal/error 0;
kapanış tamamlandı, kalan MPV thread ve artık süreç yoktu. Medya boyutu
**2.651.661.814** bayt, `mtime` ticks **638811093472871806** olarak
önce/sonra değişmedi.

Trace **2.309.579 bayt / 31.548 satır**, SHA-256
`D83214B45DBF615D8009D0537C58E322F1504569BBE5E7B07DA3C97E8CC659A2`;
child stdout SHA-256
`B4942757310F5040616FF229C0D3A184D84F04D159492AE55D97269CE103C711`;
boş child stderr SHA-256
`E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855`.

**İlk iki profillik bütçe tamamlandı.** İki sonuç da tek-negatiftir; aralıklı
kusur nedeniyle **hiçbir grup elenmedi** ve kök neden **AÇIK**. Yeni native
koşum yetkilendirilmedi. Kayıt sonrası ilgili deterministik paketler
**651 passed, 4 skipped**; dört skip gerçek opt-in düğümleridir. `select`
sonuç kaydı **COMMIT EDILDI (`6f00ee3`)**.

**Salt-okunur kanıt sentezi (18 Ağustos 2026; yeni native koşum yapılmadı):**
tam raw kanıt taşıyan iki normal-script koşumunda `0xe24c4a02` sayıları **11**
ve **13**; her ikisinde stats, ytdl_hook, select ile birlikte **console,
auto_profiles, positioning ve commands** etkin görünüyordu. All-off,
`stats_ytdl` ve `select` tek koşumlarında sayı 0 kaldı. İlk trace kısmi pytest
stderr gösterimidir ve **tam raw kanıt değildir**. Exact mpv kaynağı her script
client'inin **ayrı Lua state** ve ayrı mpv client kullandığını söyler; bu bilgi
tek başına kaynağı belirlemez.

Sıradaki deterministik profil `observed_trio` = **stats + ytdl_hook + select**:
diğer bütün built-in'ler kapalı kalır. **Tek pozitif koşum kesin kök neden
kanıtlamaz**; **tek negatif koşum üçlüyü elemez**. Gerçek koşum ancak yeni,
açık tek koşumluk bütçe ve **ayrı ONAY B** ile yapılabilir. İlgili
deterministik paketler **719 passed, 4 skipped**; profil ve kayıt değişiklikleri
**COMMIT BEKLIYOR**.

**`observed_trio` bisection ONAY B — TEK KOSUM (18 Ağustos 2026):** pytest
exit 0 / **1 passed**, ancak **shutdown kabulü BASARISIZ**. Otomatik tekrar
yapılmadı ve CDB kullanılmadı. Trace yalnız stats 6, ytdl_hook 7 ve select 6;
diğer bilinen built-in modüller 0. Trace fatal/error/warn seviyeleri ve stdout
overflow problemi 0; bisection değerlendiricisi `[]`. Child stderr ise
**19.755 bayt** ve **15** adet `0xe24c4a02` taşıdı. Saf shutdown kapısı LuaJIT
SEH izi ile boş olmayan stderr'i reddetti; **pytest PASS ürün kabulü değildir**.

Trace **2.332.921 bayt / 31.715 satır**, SHA-256
`147ED1F9D889D69F030DB996757C47E7F6973E979213F4D2559FB9118FFFBD53`;
child stdout **999 bayt**, SHA-256
`43D92579AD85D88B34EFC0ECBFDEA113D62FB6FA1BB5502FF5E66DEC24070B1D`;
child stderr SHA-256
`DF1E20C0BF19D210C6CCA86029D26AA8A267E19D97EE8E68E3AD6836356032DC`.
Medya boyutu **2.651.661.814**, `mtime` ticks **638811093472871806** olarak
önce/sonra değişmedi; kapanış tamamlandı ve artık süreç kalmadı.

Üçlü bu tek örnekte olayı üretmeye **yeterli** oldu; bu, tek bir client'i veya
etkileşimi **kesin kök neden olarak kanıtlamaz** ve kullanıcıya görünen
çökme/donma kanıtı değildir. Kök neden ve release-ready madde 8 **AÇIK**;
kayıt sonrası ilgili deterministik paketler **721 passed, 4 skipped**; sonuç
kaydı **COMMIT BEKLIYOR**.

**ONAY A — exact PDB sonucu (18 Ağustos 2026; native koşum yok):** workflow
run `31755832255` içindeki `mpv-x86_64-debug` artifact'i (`9203486934`,
arşiv SHA-256 `873EF06F0996F993120F7633099A18CD1011CF4CDBE139CBE21A8F0575866787`)
**yalnız `mpv.pdb`** taşıyor. Repo `mpv-2.dll` CodeView kimliği
`C2123266-4DC7-8196-4C4C-44205044422E` / age 1; indirilen PDB kimliği
`83981475-63BC-A938-4C4C-44205044422E` / age 1. PDB, aynı workflow'un
`mpv.exe` dosyasıyla `symchk /pf` denetiminden geçti; `mpv-2.dll` için
**mismatched** sonucu verdi. Böylece **exact `libmpv-2.pdb` elde edilemedi**
ve özel sembol koşumu için **ONAY B ENGELLENDI**. Fail-closed geçici harness
statik preflight'tan geçti; CDB hedefi, Python child, MLC Player, mpv, PyQt
ve video çalıştırılmadı. Ayrıntılı kanıt `ENGINEERING_AUDIT.md` içindedir.

Exact DLL PDB'si üreticiden sağlanmadan özel sembol harness'i çalıştırılmaz.
PDB'siz alternatif kapı ürün koduna dokunmadan diagnostic child'da hazırlandı:
`tests/native_mpv_trace_contract.py` ve
`tests/test_native_mpv_trace_regressions.py`. Normal `MPV_CONFIG` değişmedi;
child kopyası `log_file`, `msg_level`, `msg_time`, `msg_module` seçeneklerini
yalnız iki açık izinle alır. `MLC_NATIVE_SHUTDOWN_ACCEPTANCE=1`,
`MLC_NATIVE_MPV_TRACE=1` ve yeni mutlak `MLC_NATIVE_MPV_TRACE_LOG` hedefi
birlikte zorunludur.

Trace paketinin sonucu **54 passed, 1 skipped**; shutdown/child/player/
cover-art ile dar regresyon **476 passed, 4 skipped**. Skip edilen düğümler
gerçek native koşumlardır. Tanı başarısı ürün kabulü değildir; Lua mesajı
yakalansa bile stderr veya kapanış sorununu aklamaz. PDB'siz trace kapısı
**COMMIT EDILDI (`4f5bc87`)**.

**ONAY B — TEK KOSUM (18 Ağustos 2026): pytest exit 1, TANI SONUCSUZ.**
Bilinen Resident Alien videosuyla bir koşum yapıldı; **otomatik tekrar
yapılmadı**, CDB kullanılmadı ve ürün kodu değiştirilmedi. Medya boyutu
önce/sonra **2.651.661.814 bayt**, `mtime` ticks önce/sonra
`638811093472871806`; boyut ve mtime değişmedi. Koşumdan sonra artık
child/pytest süreci yoktu.

Trace **2.341.534 bayt / 31.858 satır**, SHA-256
`125D0F347EF3DC1D3E5BFFB718E5BBB506FF46062C57A5FBD498896E6A007FB8`.
Loglama ve ilgili scriptler etkindi, fakat **Lua hata/traceback kaydı yok**;
bu yüzden tanı **TANI SONUCSUZ**, kök neden **AÇIK**. Ayrı shutdown sonucu
child stderr'inde **14.799 karakter** ve `0xe24c4a02` izi bildirdi; ürün
kabulü FAIL kaldı. Raw child stdout/stderr kalıcı ayrı artifact olarak
yazılmadığından bu koşum için eksiksiz marker iddiası kurulmaz. Yeni native
koşumdan önce bu kanıt boşluğu deterministik olarak kapatılmalı veya exact
DLL PDB'si sağlanmalı; her yeni koşum ayrıca kullanıcı onayı ister.

**Raw stream boşluğu gelecek koşumlar için kapatıldı; CANLI KOSUM
TEKRARLANMADI.** Shutdown runner tam `raw_stdout` / `raw_stderr` baytlarını
koruyor; trace runner bunları `.child_stdout.bin` ve `.child_stderr.bin`
olarak, eski kanıtı ezmeden yazıyor. Eksik stream, mevcut hedef ve yazma
hatası fail-closed. Deterministik sonuç **331 passed, 2 skipped**; skip'ler
gerçek native düğümlerdir. Bu değişiklik önceki tek koşumu geriye dönük
başarıya çevirmez: ONAY B **TANI SONUCSUZ**, **ONAY B sonuc kaydı COMMIT
BEKLIYOR**.

**IKINCI PDB'SIZ TRACE ONAY B (18 Ağustos 2026): TEK KOSUM, pytest exit 1,
TANI SONUCSUZ.** Raw artifact zinciri commit'i `c251abd` üzerinde aynı
Resident Alien videosuyla çalıştırıldı; otomatik tekrar yapılmadı, CDB ve
ürün kodu değişikliği yok. Medya boyutu/mtime değişmedi, timeout ve artık
süreç yok.

Raw stdout kapanışı doğruladı: `duration=2782.27`, `position=0.04`,
`stop=1` → `terminate=1`, `visible=False`, `app.exec=0`, **MPV thread=0**,
`RESULTS failures=none`, **main returned 0**. Raw stderr yine de **11 ayrı**
`0xe24c4a02` olayı taşıdı; ürün kabulü FAIL kaldı.

Artifact özetleri: trace
`C5532F519D26496873AD52A77CDC6B391DCA7361035DFDF4C3954A660012B720`,
raw stdout
`C2D866AB63CDD91BFD3EE61A6F291D263BDBC3EB57FEE9C1B3D64FA869A4B0F5`,
raw stderr
`CF5BC570743E015FEFEC28250D49C83CDB0100230133A798D8297038679D0011`.
Trace Lua hata/traceback kaydı üretmedi. Raw stdout ayrıca `log message
buffer overflow` ve **155 mesaj** atlandığını bildirdi; bu nedenle trace
**tüm mpv log mesajlarının korunduğunu kanıtlamaz**. Overflow giderilmeden
yeni native koşum yapılmaz; her yeni koşum ayrıca kullanıcı onayı ister.
**ONAY B sonuc kaydı COMMIT BEKLIYOR.**

**Overflow önleme deterministik olarak hazır; CANLI KOSUM TEKRARLANMADI.**
Trace dosyası için `msg_level=all=trace` korunurken python-mpv client event
kuyruğu ayrı `loglevel=warn` eşiğine alındı. Ürün `MPV_CONFIG`'i değişmedi.
Gelecekte `log message buffer overflow` yeniden görülürse tanı, geçerli Lua
kaydı olsa bile **FAIL-CLOSED** kalır. Kaynak bağı `mpv_request_log_messages`
API'si ve mpv seçenek kılavuzuyla testlidir. Deterministik sonuç **337
passed, 2 skipped**; bu sayı canlı overflow'un bittiğinin kanıtı değildir.

**UCUNCU PDB'SIZ TRACE ONAY B (18 Ağustos 2026): TEK KOSUM, pytest exit 1,
TANI SONUCSUZ.** Temiz `0ac71f8` üzerinde aynı video kullanıldı; otomatik
tekrar, CDB ve ürün kodu değişikliği yok. Raw stdout ölçümü **`overflow=0`**,
**`messages skipped=0`**: log-event taşması bu koşumda giderildi. Kapanış
marker'ları eksiksizdi (`stop=1` → `terminate=1`, `visible=False`,
`app.exec=0`, MPV thread=0, `RESULTS failures=none`, main returned 0).

Raw stderr yine de **13 ayrı** `0xe24c4a02` olayı taşıdı; trace Lua
hata/traceback kaydı üretmedi. Ölçülen sınır: **overflow olaylar için gerekli
bir koşul değildi**. Kök neden ve kullanıcıya görünen etki **AÇIK**.
Artifact SHA-256 değerleri: trace
`27E6407134BCC6609FBAC41F29F8B6A1E35692A5BB34906B2C904F4A39F18C30`,
raw stdout
`5BBFA4F383DB321919FCFB0EF6A5141C44194BD0FC26469970DADA79241ACEE4`,
raw stderr
`3CDAAC57BD4B7027DF99B77B1F34D6B5B6B18C29965D1E43ADF75AC6B9889A10`.
**Üçüncü ONAY B sonuç kaydı bu kayıt commit'iyle COMMIT EDILDI.**

**Talimat ihlali (gizlenmiyor):** bir önceki turun mutasyon koşumunda
"medya türü denetimi yok" varyantı gerçek child'ı bir kez, yaklaşık
26,8 sn boyunca geçersiz bir `.py` girdisiyle başlattı. **Bu koşum canlı
kabul veya ürün etkisi kanıtı değildir**; süreç kendi kapandı ve artık
child Python süreci kalmadığı ölçüldü. Önlem: native sınırındaki testler
`subprocess.run`'ı nöbetçiyle değiştirir ve beklenmeyen her süreç
başlatma testi anında kırmızı yapar.

**Opt-in artık gerçek subprocess sınırında.** Önceden yalnız pytest
düğümü denetliyordu; `run_native_shutdown()` doğrudan çağrılırsa geçerli
bir `.mkv` ile açık izin olmadan süreç başlatabiliyordu. Deterministik
sonuç: **268 passed, 1 deselected**.

**Commit durumu:** Aşama 1 COMMIT EDILDI (`a7ced18`); Aşama 2'nin YEDİ
dosyası iki commit ile tamamlandı: `4ed5c79` ve `5c83c05`. Debugger kanıt
ayrıştırması COMMIT EDILDI (`ddcfc40`); ONAY A PDB kaydı COMMIT EDILDI
(`a4f10ee`); PDB'siz trace kapısı COMMIT EDILDI (`4f5bc87`), raw artifact
zinciri COMMIT EDILDI (`c251abd`), ikinci ONAY B sonuç kaydı ve overflow
önleme düzeltmesi COMMIT EDILDI (`0ac71f8`), üçüncü ONAY B sonuç kaydı
bu kayıt commit'iyle COMMIT EDILDI. Ayrıntılı liste:
`docs/ENGINEERING_AUDIT.md` → NATIVE-001.

**Kapatılmayan:** LuaJIT'in taşıdığı asıl Lua hatası belirlenmedi ve ürüne
görünen etki ölçülmedi. Canlı kabul **başarısızdır**; olgu artık gerçek
ürün kapanış yolunda kanıtlanmıştır. **Tek koşum, ne olgunun bittiğini ne
de zararsız olduğunu ispatlar.** Yayına hazırlık ölçütlerinden biri olmaya
devam ediyor (bkz. madde 8).

---

## Gercek Windows build ve kabul matrisi

- **Durum:** CANLI KABUL BEKLIYOR
- **Bagimlilik:** REL-001, REL-003
- **Olcut:** `build_release.bat` uçtan uca exit 0; dört artifact üretilmiş ve imzalanmış; fiziksel kabul matrisi koşulmuş
- **Kullanici onayi:** **gerekir** — build ayrı bir onaydır

---

## Release rehearsal

- **Durum:** ERTELENDI
- **Bagimlilik:** yukarıdakilerin tamamı
- **Olcut:** a–j sırası **draft'a kadar** prova edilmiş; adım (j) yayımlama yapılmadan durdurulmuş; kapı exit 0 vermiş
- **Kullanici onayi:** **gerekir** — tag, push ve release ayrı ayrı onay ister

---

## Nihai release-ready kriterleri

Bir sürüm ancak şunların **hepsi** sağlandığında yayına hazır sayılır:

1. Tam paket yeşil ve taban farkı açıklanmış
2. REL-001…REL-005 commit edilmiş
3. `build_release.bat` gerçek koşumda exit 0
4. `prepublish.py --tag vX.Y` exit 0
5. Uzak peeled tag commit'i == yerel HEAD
6. Sekiz varlığın ad/boyut/SHA-256 eşliği doğrulanmış
7. Fiziksel kabul matrisi koşulmuş
8. `0xe24c4a02` riski ya kapatılmış ya bilinçli olarak kabul edilmiş
   — **güncel durum (18 Ağustos 2026): AÇIK.** Görünürlük kapısı hem
   cover-art hem ürün kapanış yolu için hazır ve ürün yolunda TEK geçerli
   canlı koşum yapıldı: **BAŞARISIZ** (child stderr'inde dokuz kez
   `0xe24c4a02`). Kök neden ve kullanıcıya görünen etki hâlâ bilinmiyor;
   madde AÇIK kalır.

- **Durum:** ERTELENDI
- **Bagimlilik:** 1–8
- **Olcut:** sekiz maddenin tamamı işaretli
- **Kullanici onayi:** her dış adım için ayrı ayrı gerekir
